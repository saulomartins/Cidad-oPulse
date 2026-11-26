from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import BASE_DIR, env_settings
from app.database import SessionLocal, get_db, init_db
from app.models import AccessToken, AppSetting
from app.routers import awards, jobs, sentiment, settings, systems
from app.seed import seed_initial_data
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _get_auth_settings() -> dict[str, str]:
    """Read effective auth settings combining env vars and DB AppSetting overrides."""
    cfg = {
        "app_password": (os.getenv("APP_PASSWORD") or env_settings.app_password or "").strip(),
        "google_client_id": (os.getenv("GOOGLE_CLIENT_ID") or env_settings.google_client_id or "").strip(),
        "admin_google_emails": (os.getenv("ADMIN_GOOGLE_EMAILS") or env_settings.admin_google_emails or "").strip(),
        "allowed_google_emails": (os.getenv("ALLOWED_GOOGLE_EMAILS") or env_settings.allowed_google_emails or "").strip(),
    }
    db = SessionLocal()
    try:
        rows = (
            db.query(AppSetting)
            .filter(AppSetting.key.in_(list(cfg.keys())))
            .all()
        )
        for r in rows:
            # Env vars take priority if explicitly set; otherwise DB value applies
            if not cfg[r.key] and (r.value or "").strip():
                cfg[r.key] = r.value.strip()
    except Exception:
        pass
    finally:
        db.close()
    return cfg


def _get_signing_secret(auth_cfg: dict[str, str]) -> str:
    return auth_cfg["app_password"] or auth_cfg["google_client_id"] or "cidadao-pulse-local-secret"


def _expected_admin_token(password: str) -> str:
    """Derive a stable HMAC session token from APP_PASSWORD (survives container restarts)."""
    return hmac.new(
        password.encode("utf-8"),
        b"cidadao-pulse-auth-session-v1",
        hashlib.sha256,
    ).hexdigest()


def _sign_email_session(role: str, email: str, secret: str) -> str:
    payload = f"{role}|{email}".encode("utf-8")
    b64 = base64.urlsafe_b64encode(payload).decode("ascii")
    sig = hmac.new(secret.encode("utf-8"), f"g:{b64}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"g_{b64}.{sig}"


def _verify_email_session(token: str, secret: str) -> tuple[str, str] | None:
    if not token.startswith("g_") or "." not in token:
        return None
    body, sig = token[2:].split(".", 1)
    expected = hmac.new(secret.encode("utf-8"), f"g:{body}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        decoded = base64.urlsafe_b64decode(body.encode("ascii")).decode("utf-8")
        role, email = decoded.split("|", 1)
        if role in {"admin", "editor", "viewer"} and "@" in email:
            return role, email
    except Exception:
        return None
    return None


def _parse_email_list(raw: str) -> set[str]:
    return {e.strip().lower() for e in (raw or "").replace(";", ",").replace("\n", ",").split(",") if "@" in e}


def _hash_guest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _lookup_valid_guest_token(raw_token: str, record_use: bool = False) -> tuple[str, str] | None:
    """Validate an admin-issued guest token (`cp_...`). Returns (role, label) or None."""
    cleaned = (raw_token or "").strip()
    if not cleaned:
        return None
    db = SessionLocal()
    try:
        tok_hash = _hash_guest_token(cleaned)
        row = (
            db.query(AccessToken)
            .filter(AccessToken.token_hash == tok_hash, AccessToken.is_active == True)  # noqa: E712
            .first()
        )
        if not row:
            return None
        now = datetime.now(timezone.utc)
        if row.expires_at is not None:
            exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
            if exp <= now:
                return None
        if record_use:
            row.last_used_at = now
            row.use_count = int(row.use_count or 0) + 1
            db.commit()
        role = row.role if row.role in {"viewer", "editor"} else "viewer"
        return role, row.label
    finally:
        db.close()


def _is_auth_required(auth_cfg: dict[str, str]) -> bool:
    return bool(
        auth_cfg["app_password"]
        or auth_cfg["google_client_id"]
        or auth_cfg["admin_google_emails"]
    )


def _resolve_auth_context(request: Request) -> tuple[bool, str, str, dict[str, str]]:
    """
    Resolve authentication & role for the incoming request.
    Returns (is_authenticated, role, label, auth_cfg).
    """
    auth_cfg = _get_auth_settings()
    password = auth_cfg["app_password"]
    auth_required = _is_auth_required(auth_cfg)

    auth_header = request.headers.get("Authorization", "")
    bearer = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""

    if password and bearer and hmac.compare_digest(bearer, _expected_admin_token(password)):
        return True, "admin", "Administrador", auth_cfg

    cron_secret = request.headers.get("X-App-Password", "").strip()
    if password and cron_secret and hmac.compare_digest(cron_secret, password):
        return True, "admin", "Administrador", auth_cfg

    if bearer.startswith("g_"):
        email_sess = _verify_email_session(bearer, _get_signing_secret(auth_cfg))
        if email_sess:
            return True, email_sess[0], email_sess[1], auth_cfg

    if bearer:
        guest = _lookup_valid_guest_token(bearer, record_use=False)
        if guest:
            return True, guest[0], guest[1], auth_cfg

    if auth_required:
        return False, "anonymous", "", auth_cfg

    return True, "admin", "Admin Local", auth_cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="CidadãoPulse API",
    description="Monitoramento de Sentimento na Internet/Redes Sociais + Radar Semanal Mundial de Premiações para Software de Atendimento ao Cidadão",
    version="1.0.0",
    lifespan=lifespan,
)

cors_list = [o.strip() for o in (env_settings.cors_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_list or ["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_and_rbac_middleware(request: Request, call_next):
    path = request.url.path
    if (
        request.method != "OPTIONS"
        and path.startswith("/api/")
        and path not in {"/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/google"}
    ):
        authenticated, role, label, _ = _resolve_auth_context(request)
        if not authenticated:
            return JSONResponse(
                status_code=401,
                content={"detail": "Acesso protegido. Faça login com Gmail, senha do admin ou token de acesso."},
            )
        request.state.auth_role = role
        request.state.auth_label = label

        # Admin-only routes: API keys/settings, access config, and guest token management
        if role != "admin" and (
            path.startswith("/api/settings")
            or path.startswith("/api/auth/tokens")
            or path.startswith("/api/auth/access-config")
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Acesso restrito ao administrador."},
            )

        # Viewer tokens are strictly read-only
        if role == "viewer" and request.method not in {"GET", "HEAD", "OPTIONS"}:
            return JSONResponse(
                status_code=403,
                content={"detail": "Seu acesso possui permissão apenas de leitura."},
            )

    return await call_next(request)


class LoginRequest(BaseModel):
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str


class AccessConfigUpdate(BaseModel):
    app_password: str | None = None
    clear_app_password: bool = False
    google_client_id: str | None = None
    admin_google_emails: str | None = None
    allowed_google_emails: str | None = None


FRIENDLY_TOKEN_WORDS = [
    "minas", "educa", "inova", "pulso", "escola", "gestao", "cidadao",
    "digital", "futuro", "portal", "ensino", "rede", "acesso", "painel",
]


def _generate_friendly_token() -> str:
    word = secrets.choice(FRIENDLY_TOKEN_WORDS)
    digits = secrets.randbelow(9000) + 1000
    return f"{word}-{digits}"


def _mask_token_preview(raw_token: str) -> str:
    if len(raw_token) <= 6:
        return f"{raw_token[:2]}••••"
    return f"{raw_token[:3]}••••{raw_token[-2:]}"


class CreateAccessTokenRequest(BaseModel):
    label: str = Field(..., min_length=2, max_length=120)
    role: str = Field(default="viewer", pattern="^(viewer|editor)$")
    expires_in_days: int | None = Field(default=30, ge=1, le=3650)
    custom_token: str | None = Field(default=None, max_length=80)


def _serialize_token(row: AccessToken) -> dict:
    now = datetime.now(timezone.utc)
    is_expired = False
    if row.expires_at is not None:
        exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        is_expired = exp <= now
    return {
        "id": row.id,
        "label": row.label,
        "role": row.role,
        "token_prefix": row.token_prefix,
        "is_active": bool(row.is_active and not is_expired),
        "is_expired": is_expired,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "use_count": row.use_count or 0,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@app.get("/api/auth/status")
def auth_status(request: Request):
    authenticated, role, label, auth_cfg = _resolve_auth_context(request)
    return {
        "auth_required": _is_auth_required(auth_cfg),
        "authenticated": authenticated,
        "role": role,
        "label": label,
        "password_enabled": bool(auth_cfg["app_password"]),
        "google_enabled": bool(auth_cfg["google_client_id"]),
        "google_client_id": auth_cfg["google_client_id"],
    }


@app.post("/api/auth/login")
def auth_login(payload: LoginRequest):
    secret = (payload.password or "").strip()
    auth_cfg = _get_auth_settings()
    password = auth_cfg["app_password"]
    auth_req = _is_auth_required(auth_cfg)

    # 1. Admin password check
    if password and hmac.compare_digest(secret, password):
        return {
            "auth_required": auth_req,
            "authenticated": True,
            "role": "admin",
            "label": "Administrador",
            "token": _expected_admin_token(password),
        }

    # 2. Guest access token check (cp_...)
    guest = _lookup_valid_guest_token(secret, record_use=True)
    if guest:
        role, label = guest
        return {
            "auth_required": auth_req,
            "authenticated": True,
            "role": role,
            "label": label,
            "token": secret,
        }

    if not auth_req:
        return {
            "auth_required": False,
            "authenticated": True,
            "role": "admin",
            "label": "Admin Local",
            "token": "",
        }

    raise HTTPException(status_code=401, detail="Senha do admin ou token de acesso inválido/expirado.")


async def _verify_google_id_token(credential: str, expected_client_id: str) -> dict:
    """Verify a Google Identity Services ID token via Google's official tokeninfo endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": credential},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token do Google inválido ou expirado.")
    info = resp.json()
    if info.get("aud") != expected_client_id:
        raise HTTPException(status_code=401, detail="Token do Google não pertence a esta aplicação.")
    if str(info.get("email_verified", "")).lower() != "true":
        raise HTTPException(status_code=401, detail="E-mail da conta Google não verificado.")
    return info


@app.post("/api/auth/google")
async def auth_google(payload: GoogleLoginRequest):
    auth_cfg = _get_auth_settings()
    client_id = auth_cfg["google_client_id"]
    if not client_id:
        raise HTTPException(status_code=400, detail="Login via Google (Gmail) não está configurado.")

    info = await _verify_google_id_token((payload.credential or "").strip(), client_id)
    email = str(info.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Não foi possível identificar o e-mail Google.")

    admin_emails = _parse_email_list(auth_cfg["admin_google_emails"])
    allowed_emails = _parse_email_list(auth_cfg["allowed_google_emails"])

    if email in admin_emails:
        role = "admin"
    elif email in allowed_emails:
        role = "viewer"
    elif not admin_emails and not allowed_emails:
        # First login convenience if client_id set without allowlist -> read-only unless listed
        raise HTTPException(
            status_code=403,
            detail=f"O e-mail {email} não está autorizado. Peça ao administrador para adicioná-lo na lista de e-mails autorizados.",
        )
    else:
        raise HTTPException(
            status_code=403,
            detail=f"O e-mail {email} não está na lista de e-mails autorizados pelo administrador.",
        )

    token = _sign_email_session(role, email, _get_signing_secret(auth_cfg))
    return {
        "auth_required": True,
        "authenticated": True,
        "role": role,
        "label": email,
        "token": token,
    }


@app.get("/api/auth/access-config")
def get_access_config():
    auth_cfg = _get_auth_settings()
    return {
        "password_enabled": bool(auth_cfg["app_password"]),
        "password_from_env": bool((os.getenv("APP_PASSWORD") or env_settings.app_password or "").strip()),
        "google_client_id": auth_cfg["google_client_id"],
        "admin_google_emails": auth_cfg["admin_google_emails"],
        "allowed_google_emails": auth_cfg["allowed_google_emails"],
    }


@app.put("/api/auth/access-config")
def update_access_config(payload: AccessConfigUpdate, db: Session = Depends(get_db)):
    def upsert(key: str, value: str):
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))

    if payload.clear_app_password:
        upsert("app_password", "")
    elif payload.app_password is not None and payload.app_password.strip():
        upsert("app_password", payload.app_password.strip())

    if payload.google_client_id is not None:
        upsert("google_client_id", payload.google_client_id.strip())
    if payload.admin_google_emails is not None:
        upsert("admin_google_emails", payload.admin_google_emails.strip())
    if payload.allowed_google_emails is not None:
        upsert("allowed_google_emails", payload.allowed_google_emails.strip())

    db.commit()
    auth_cfg = _get_auth_settings()
    admin_token = _expected_admin_token(auth_cfg["app_password"]) if auth_cfg["app_password"] else ""
    return {
        "password_enabled": bool(auth_cfg["app_password"]),
        "google_client_id": auth_cfg["google_client_id"],
        "admin_google_emails": auth_cfg["admin_google_emails"],
        "allowed_google_emails": auth_cfg["allowed_google_emails"],
        "admin_token": admin_token,
    }


@app.get("/api/auth/tokens")
def list_access_tokens(db: Session = Depends(get_db)):
    rows = db.query(AccessToken).order_by(AccessToken.created_at.desc()).all()
    return [_serialize_token(r) for r in rows]


@app.post("/api/auth/tokens", status_code=201)
def create_access_token(payload: CreateAccessTokenRequest, db: Session = Depends(get_db)):
    custom = (payload.custom_token or "").strip()
    if custom:
        if len(custom) < 4:
            raise HTTPException(status_code=400, detail="A palavra/código de acesso precisa ter pelo menos 4 caracteres.")
        if " " in custom:
            raise HTTPException(status_code=400, detail="Use uma palavra ou código sem espaços (ex.: educacao2026 ou equipe-mg).")
        raw_token = custom
    else:
        raw_token = _generate_friendly_token()

    auth_cfg = _get_auth_settings()
    if auth_cfg["app_password"] and hmac.compare_digest(raw_token, auth_cfg["app_password"]):
        raise HTTPException(status_code=400, detail="Escolha uma palavra diferente da senha do administrador.")

    tok_hash = _hash_guest_token(raw_token)
    if db.query(AccessToken).filter(AccessToken.token_hash == tok_hash).first():
        raise HTTPException(status_code=409, detail="Já existe um token ativo com esta mesma palavra/código.")

    prefix = _mask_token_preview(raw_token)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=int(payload.expires_in_days))
        if payload.expires_in_days
        else None
    )
    row = AccessToken(
        label=payload.label.strip(),
        role=payload.role,
        token_hash=tok_hash,
        token_prefix=prefix,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    data = _serialize_token(row)
    data["token"] = raw_token  # Shown ONLY once on creation
    return data


@app.delete("/api/auth/tokens/{token_id}", status_code=204)
def revoke_access_token(token_id: int, db: Session = Depends(get_db)):
    row = db.query(AccessToken).filter(AccessToken.id == token_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Token não encontrado.")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


app.include_router(systems.router)
app.include_router(sentiment.router)
app.include_router(awards.router)
app.include_router(settings.router)
app.include_router(jobs.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "cidadao-pulse"}


# Serve built React SPA directly from FastAPI in single-service cloud deployments (Render / HF Spaces / Docker)
_frontend_dist = Path(os.getenv("FRONTEND_DIST_DIR") or (BASE_DIR.parent / "frontend" / "dist"))
if (_frontend_dist / "index.html").is_file():
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Endpoint não encontrado.")
        candidate = (_frontend_dist / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(_frontend_dist.resolve())):
            return FileResponse(str(candidate))
        return FileResponse(str(_frontend_dist / "index.html"))
