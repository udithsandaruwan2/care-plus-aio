"""OpenAI-compatible local chat HTTP client (Step 97) — chat only, never MATCH."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def local_llm_configured() -> bool:
    return bool((getattr(settings, "LOCAL_LLM_URL", "") or "").strip())


def _chat_completions_url() -> str:
    raw = (getattr(settings, "LOCAL_LLM_URL", "") or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.endswith("/chat/completions"):
        return raw
    if raw.endswith("/v1"):
        return f"{raw}/chat/completions"
    return f"{raw}/v1/chat/completions"


def post_chat_completion(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 180,
) -> str | None:
    """POST to OpenAI-compatible ``/v1/chat/completions``. Returns assistant text or None."""
    endpoint = _chat_completions_url()
    if not endpoint:
        return None
    model_name = (model or getattr(settings, "LOCAL_LLM_MODEL", "") or "local").strip() or "local"
    timeout = float(getattr(settings, "LOCAL_LLM_TIMEOUT_SEC", 8) or 8)
    body = {
        "model": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        logger.exception("local_llm.chat_failed")
        return None
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    out = (content or "").strip()
    return out or None
