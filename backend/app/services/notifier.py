from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import NotificationLog

logger = logging.getLogger(__name__)


def _send_smtp_sync(
    host: str,
    port: int,
    user: str,
    password: str,
    sender: str,
    recipients: list[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender or user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        if port == 587:
            server.starttls()
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.sendmail(sender or user, recipients, msg.as_string())


async def send_notification(
    db: Session,
    runtime_config: dict[str, Any],
    title: str,
    markdown_body: str,
    highlights: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Send notifications via configured Webhook (Slack/Teams/Generic) and/or SMTP Email."""
    results: list[dict[str, Any]] = []
    highlights = highlights or []

    # 1. Webhook (Slack / Microsoft Teams / Generic)
    webhook_url = str(runtime_config.get("webhook_url", "") or "").strip()
    provider = str(runtime_config.get("webhook_provider", "slack") or "slack").lower()

    if webhook_url:
        if provider == "teams":
            payload: dict[str, Any] = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "2563EB",
                "summary": title,
                "sections": [
                    {
                        "activityTitle": title,
                        "text": markdown_body,
                        "facts": [{"name": f"#{i+1}", "value": h} for i, h in enumerate(highlights[:6])],
                    }
                ],
            }
        elif provider == "slack":
            blocks: list[dict[str, Any]] = [
                {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
                {"type": "section", "text": {"type": "mrkdwn", "text": markdown_body[:2900]}},
            ]
            if highlights:
                bullet_text = "\n".join(f"• {h}" for h in highlights[:8])
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": bullet_text[:2900]}})
            payload = {"text": f"{title}\n{markdown_body}", "blocks": blocks}
        else:
            payload = {
                "title": title,
                "message": markdown_body,
                "highlights": highlights,
                "source": "CidadaoPulse",
            }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(webhook_url, json=payload)
            if 200 <= resp.status_code < 300:
                status, details = "sent", f"HTTP {resp.status_code}"
            else:
                status, details = "failed", f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            status, details = "failed", str(exc)

        log = NotificationLog(channel=provider, title=title[:290], status=status, details=details[:1000])
        db.add(log)
        results.append({"channel": provider, "status": status, "details": details})

    # 2. SMTP Email
    smtp_host = str(runtime_config.get("smtp_host", "") or "").strip()
    alert_to = str(runtime_config.get("alert_email_to", "") or "").strip()
    if smtp_host and alert_to:
        recipients = [e.strip() for e in alert_to.split(",") if e.strip()]
        smtp_port = int(runtime_config.get("smtp_port", 587) or 587)
        smtp_user = str(runtime_config.get("smtp_user", "") or "")
        smtp_password = str(runtime_config.get("smtp_password", "") or "")
        smtp_from = str(runtime_config.get("smtp_from", "") or smtp_user or "cidadaopulse@localhost")

        html_items = "".join(f"<li style='margin-bottom:6px'>{h}</li>" for h in highlights)
        html_body = f"""
        <div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:0 auto;color:#0f172a">
          <div style="background:#0f172a;color:#fff;padding:18px 24px;border-radius:10px 10px 0 0">
            <h2 style="margin:0;font-size:18px">CidadãoPulse — Alerta Automático</h2>
          </div>
          <div style="border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 10px 10px">
            <h3 style="margin-top:0;color:#1d4ed8">{title}</h3>
            <p style="white-space:pre-line;line-height:1.6">{markdown_body}</p>
            {"<ul>" + html_items + "</ul>" if html_items else ""}
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0"/>
            <p style="font-size:12px;color:#64748b">Enviado automaticamente pelo CidadãoPulse.</p>
          </div>
        </div>
        """
        text_body = f"{title}\n\n{markdown_body}\n" + "\n".join(f"- {h}" for h in highlights)

        try:
            await asyncio.to_thread(
                _send_smtp_sync,
                smtp_host,
                smtp_port,
                smtp_user,
                smtp_password,
                smtp_from,
                recipients,
                f"[CidadãoPulse] {title}",
                text_body,
                html_body,
            )
            status, details = "sent", f"Enviado para {', '.join(recipients)}"
        except Exception as exc:
            logger.warning("SMTP error: %s", exc)
            status, details = "failed", str(exc)

        log = NotificationLog(channel="email", title=title[:290], status=status, details=details[:1000])
        db.add(log)
        results.append({"channel": "email", "status": status, "details": details})

    if not results:
        log = NotificationLog(
            channel="none",
            title=title[:290],
            status="skipped",
            details="Nenhum canal de notificação (Webhook ou SMTP) configurado.",
        )
        db.add(log)
        results.append({"channel": "none", "status": "skipped", "details": log.details})

    db.commit()
    return results
