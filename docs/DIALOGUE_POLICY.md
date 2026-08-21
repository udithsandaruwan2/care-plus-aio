# Dialogue AI policy (Step 15j / Step 97)

Locked split so cost and PDPA stay sane:

| Path | Backend | Notes |
|------|---------|--------|
| **CHAT** / situational Serah lines | `DIALOGUE_CHAT_BACKEND=stub\|gemini\|local` | Stub when no key / no `LOCAL_LLM_URL`; `local` is OpenAI-compatible chat only |
| **CLARIFY** prompts | Local templates | No Gemini |
| **MATCH / REFINE** ranking | **VEHMF only** | Never Gemini- or local-LLM-picked caregiver IDs |
| Intent slot fill | `VOICE_INTENT_BACKEND=auto\|local\|gemini\|stub` | Separate from chat |

## Intent fallback chain (Step 97)

```
slot classifier (Step 96) → Gemini → stub
```

| `VOICE_INTENT_BACKEND` | Behaviour |
|------------------------|-----------|
| `auto` (or blank) | Classifier if active → else Gemini if keyed → else stub |
| `local` | Classifier → stub (**no Gemini** — offline profile) |
| `gemini` | Gemini → stub |
| `stub` | Heuristics only |

Turn payload fields: `intent_source`, `intent_backend`, `intent_fallback_reason` (also mirrored under `intent.*`).

## Env

```bash
VOICE_INTENT_BACKEND=auto       # blank → auto
DIALOGUE_CHAT_BACKEND=          # blank → gemini if key else local URL else stub
DIALOGUE_GEMINI_RATE_LIMIT=120  # chat turns / user / window; 0 disables Gemini chat
DIALOGUE_GEMINI_RATE_WINDOW_SEC=3600
GEMINI_API_KEY=
LOCAL_LLM_URL=                  # e.g. http://127.0.0.1:11434  (OpenAI-compatible)
LOCAL_LLM_MODEL=local
LOCAL_LLM_TIMEOUT_SEC=8
```

## Fully offline deployment profile

1. Train and promote a slot classifier: `python manage.py train_slots --force` (or gated promote after cold start).
2. Set:
   ```bash
   VOICE_INTENT_BACKEND=local
   DIALOGUE_CHAT_BACKEND=stub
   GEMINI_API_KEY=
   EMBEDDING_BACKEND=hash
   ASR_BACKEND=faster_whisper   # or client
   ```
3. Optional open-ended chat without cloud: `DIALOGUE_CHAT_BACKEND=local` + `LOCAL_LLM_URL=http://…/v1` (chat **only** — never MATCH).
4. Matching remains local VEHMF + FAISS/hash embedder; no internet required for a Sinhala care-seeking turn to return chips + ranked caregivers.

## Runtime

- `GET /api/v1/voice/policy/` — `{ chat_backend, intent_backend, intent_fallback_chain, offline_profile, match_engine: "vehmf", gemini_ranks_caregivers: false, … }`
- Each `POST /voice/turn/` audits `route`, `situation`, `chat_source`, `chat_backend`, `intent_source`, `intent_backend`, `match_engine`
- General talk → **CHAT** (Gemini / local LLM / stub + history). Explicit caregiver ask → **VEHMF**. Then CHAT resumes with match context.
- English **CHAT / ACTION / CLARIFY** may skip server TTS (browser `speechSynthesis`) so replies stay instant.
- **Sinhala and Tamil always use server TTS** (Edge neural → Gemini TTS → espeak-ng). Chrome/Firefox almost never ship those voices, so browser speech is silent.
- Gemini chat receives recent `DialogueSession` turns plus grounded VEHMF names/XAI after a match.
- Intent Gemini runs only on explicit caregiver-seeking / refine / emergency turns (when the active backend reaches Gemini).

## Acceptance

- No `GEMINI_API_KEY` → CHAT still replies via stub (or local LLM); MATCH still returns real seed caregivers via VEHMF.
- `VOICE_INTENT_BACKEND=local` + active classifier → Sinhala utterance yields chips with `intent_source=slot_classifier` and a real VEHMF match.
- Over rate limit → stub reply with `chat_source=rate_limited` (no Gemini call).
