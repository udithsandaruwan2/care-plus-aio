"""Background TTS after reply text has already been returned (Step 84)."""

from __future__ import annotations

import logging
import threading

from apps.common.observability import request_id_var
from apps.matching.push import push_turn_stage

from .tts import pack_for_api, synthesize

logger = logging.getLogger(__name__)


def schedule_deferred_reply_audio(
    *,
    user_id: int,
    reply: str,
    reply_lang: str,
    request_id: str = "",
    session_id: int | None = None,
) -> None:
    """Synthesize off the request thread and push ``turn.reply_audio``."""

    def _work() -> None:
        token = request_id_var.set(request_id or "")
        try:
            tts = synthesize(reply, reply_lang)
            packed = pack_for_api(tts)
            push_turn_stage(
                int(user_id),
                "reply_audio",
                {
                    **packed,
                    "reply_lang": reply_lang,
                    "request_id": request_id or None,
                    "session_id": session_id,
                    "tts_cache_hit": "+cache" in (tts.source or ""),
                },
            )
        except Exception:
            logger.exception("deferred reply audio failed user=%s", user_id)
        finally:
            request_id_var.reset(token)

    threading.Thread(target=_work, name="tts-defer", daemon=True).start()
