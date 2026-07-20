# Dialogue AI policy (Step 15j)

Locked split so cost and PDPA stay sane:

| Path | Backend | Notes |
|------|---------|--------|
| **CHAT** / situational Serah lines | `DIALOGUE_CHAT_BACKEND=stub\|gemini` | Stub when no `GEMINI_API_KEY` or backend=`stub` |
| **CLARIFY** prompts | Local templates | No Gemini |
| **MATCH / REFINE** ranking | **VEHMF only** | Never Gemini-picked caregiver IDs |
| Intent slot fill | `VOICE_INTENT_BACKEND` | Separate from chat |

## Env

```bash
DIALOGUE_CHAT_BACKEND=          # blank → gemini if key else stub
DIALOGUE_GEMINI_RATE_LIMIT=30   # chat turns / user / window; 0 disables Gemini chat
DIALOGUE_GEMINI_RATE_WINDOW_SEC=3600
GEMINI_API_KEY=
```

## Runtime

- `GET /api/v1/voice/policy/` — `{ chat_backend, match_engine: "vehmf", gemini_ranks_caregivers: false, … }`
- Each `POST /voice/turn/` audits `route`, `situation`, `chat_source`, `chat_backend`, `match_engine`
- Turn payload includes `chat_source` (`stub` \| `gemini` \| `rate_limited` \| `vehmf` \| `none`)

## Acceptance

- No `GEMINI_API_KEY` → CHAT still replies via stub; MATCH still returns real seed caregivers via VEHMF.
- Over rate limit → stub reply with `chat_source=rate_limited` (no Gemini call).
