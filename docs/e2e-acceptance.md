# Care Plus — E2E acceptance matrix (demo / thesis bar)

Target: every happy path works without stuck states, false timeouts, or silent failures.  
Live Stripe/PayHere and real email OTP are a **production gate** (Phase 5), not required for Phases 1–4.

Demo logins (password `CarePlus!demo`): `demo.patient@careplus.local`, `demo.caregiver@careplus.local`.

| # | Flow | Voice | Tap | Caregiver side | Pass criteria |
|---|------|-------|-----|----------------|---------------|
| 1 | Social chat | Say/type “hi” / “how are you” on `/app` | Same via Type instead | — | Reply &lt; 2s; no “took too long” Retry banner; `chat_source` may be stub |
| 2 | Care seek → cards | “Find a caregiver for diabetes” (messy ASR OK) | — | — | VEHMF cards appear; matching HUD progresses to results |
| 3 | Profile | “Open number 2” / “Review &lt;name&gt;” | **View profile** on card | — | Drawer opens over cards; brief/detail spoken summary |
| 4 | Care request | “Send the request” / “Hire them” | **Request this caregiver** | Accept on `/requests` | Patient `bookingStage=awaiting_accept` + `careRequestId` set; caregiver sees pending |
| 5 | Accept → pay | After accept: pick package by voice → “Continue to payment” | Checkout from `/requests` when accepted | — | Lands on OrderPayPage; **tap Pay** (demo gateway) succeeds; voice never charges |
| 6 | Reject / cancel | After reject Serah offers next; “cancel” resets | — | Reject on `/requests` | Next caregiver offered; `cancel_flow` clears booking funnel |
| 7 | Booking parity | Voice request sets poll | Card request sets **same** `bookingStage` / `careRequestId` | — | Accept poll runs for both voice and tap; offline queue promotes to awaiting_accept on flush |

## Related loops

| Flow | Pass criteria |
|------|---------------|
| Checkout entries | `/orders/:id/pay` and `/requests/:id/checkout` share pay UX; OTP demo gate documented |
| Schedule after pay | After demo pay, schedule/relationship visible or clear “awaiting schedule” copy |
| Messages | After accept, Serah can deep-link to `/messages` care thread |
| Orders list | Patient can open `/orders` and resume unpaid / view paid |
| Role guards | Non-admin cannot use admin routes (redirect/deny) |

## Explicit non-goals (demo bar)

- Voice charging money  
- Perfect freeform Gemini forever (8s cap + stubs)  
- Mobile Serah booking before web E2E green  
- Live PayHere before Phase 5  
