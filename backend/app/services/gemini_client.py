from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_json_payload(raw_text: str | None) -> Any:
    """Safely extract JSON object or array from model output text."""
    if not raw_text:
        return None
    text = raw_text.strip()

    # Try fenced ```json ... ``` blocks first
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try locating first JSON array or object
    for open_ch, close_ch in [("[", "]"), ("{", "}")]:
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    return None


def extract_grounding_urls(interaction: Any) -> list[dict[str, str]]:
    """Extract grounded search URLs from Interactions API steps if present."""
    urls: list[dict[str, str]] = []
    steps = getattr(interaction, "steps", None) or []
    for step in steps:
        step_type = getattr(step, "type", "")
        if step_type == "google_search_result":
            results = getattr(step, "result", None) or getattr(step, "results", None) or []
            if isinstance(results, list):
                for item in results:
                    url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)
                    title = getattr(item, "title", None) or (item.get("title") if isinstance(item, dict) else "")
                    if url:
                        urls.append({"url": str(url), "title": str(title or "")})
    return urls


FALLBACK_MODELS: list[str] = [
    "gemini-4-hydrogen",
    "gemini-4-argon",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]


def _is_transient_overload(err_str: str) -> bool:
    low = err_str.lower()
    return any(
        tok in low
        for tok in ("503", "429", "service_unavailable", "high demand", "overloaded", "unavailable", "resource_exhausted")
    )


def call_gemini_interaction(
    api_key: str,
    prompt: str,
    model: str = "gemini-4-hydrogen",
    use_google_search: bool = False,
    system_instruction: str | None = None,
    timeout_seconds: float | None = None,
) -> tuple[str | None, list[dict[str, str]], str | None]:
    """
    Call the Gemini Interactions API via google-genai SDK (>= 3.5.0)
    with strict per-attempt timeout and automatic fallback across current models
    on transient 503/429/timeout overload.
    Returns (output_text, grounding_urls, error_message).
    """
    if not api_key:
        return None, [], "GEMINI_API_KEY não configurada."

    primary = model or "gemini-4-hydrogen"
    candidates = [primary] + [m for m in FALLBACK_MODELS if m != primary]
    req_timeout = float(timeout_seconds or (45.0 if use_google_search else 25.0))
    last_error = ""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(req_timeout * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        for candidate_model in candidates:
            kwargs: dict[str, Any] = {
                "model": candidate_model,
                "input": prompt,
                "store": False,
                "timeout": req_timeout,
            }
            if system_instruction:
                kwargs["system_instruction"] = system_instruction
            if use_google_search:
                kwargs["tools"] = [{"type": "google_search"}]

            try:
                interaction = client.interactions.create(**kwargs)
                output_text = getattr(interaction, "output_text", None)
                grounding_urls = extract_grounding_urls(interaction)
                if candidate_model != primary:
                    logger.info("Gemini call succeeded using fallback model %s (primary %s overloaded)", candidate_model, primary)
                return output_text, grounding_urls, None
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Gemini interaction call failed on %s: %s", candidate_model, last_error)
                if not (_is_transient_overload(last_error) or "timeout" in last_error.lower() or "timed out" in last_error.lower()):
                    return None, [], last_error
        return None, [], last_error
    except Exception as exc:
        logger.warning("Gemini client init failed: %s", exc)
        return None, [], str(exc)
