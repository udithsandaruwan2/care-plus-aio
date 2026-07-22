"""Render localized notification emails (Step 40)."""

from __future__ import annotations

from typing import Any

from apps.matching.i18n import lang_key

from .copy import EMAIL_COPY, supported_template_keys


class UnknownEmailTemplateError(ValueError):
    pass


def render_notification_email(
    template_key: str,
    *,
    language: str,
    context: dict[str, Any],
) -> tuple[str, str]:
    """Return (subject, plain_text_body) for a template key and language."""
    if template_key not in supported_template_keys():
        raise UnknownEmailTemplateError(template_key)
    lk = lang_key(language)
    spec = EMAIL_COPY[template_key]
    subject_tpl = spec["subject"].get(lk) or spec["subject"]["en"]
    body_tpl = spec["body"].get(lk) or spec["body"]["en"]
    try:
        subject = subject_tpl.format(**context)
        body = body_tpl.format(**context)
    except KeyError as exc:
        raise ValueError(f"Missing template context key: {exc.args[0]}") from exc
    return subject, body
