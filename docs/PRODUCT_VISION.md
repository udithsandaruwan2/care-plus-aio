# Care Plus — Product Vision (Old → New)

> Maps the **Old Care Plus / Lumora** HND platform (`Old Care Plus/care-plus-main`) onto the
> **new Care Plus** modular monolith (Aurora Neural + VEHMF).  
> Use this when deciding “what does done look like?” for any milestone.

**Reference tree:** `Old Care Plus/care-plus-main/` (local only — not shipped in production images).

---

## 1. What the old platform was

A Django 5 + PostgreSQL **server-rendered** web app for Sri Lanka:

- Roles: Admin / Caregiver / Patient  
- Auth: password + email OTP  
- Marketplace: browse/search caregivers, public profiles  
- Matching: scikit-learn RandomForest on synthetic CSV → Gemini (“Serah”) re-rank  
- Voice AI: browser Web Speech STT/TTS chat UI  
- Hire flow: checkout radios → Email “request” → accept/reject → mock payment → `PatientCaregiverLink`  
- Medical records, admin analytics, KnownCondition catalog  
- Marketing “Medcare” theme + Lumora dashboard UI kit  

**Gaps in old:** no mobile, no real payments, no geo distance, no realtime health stream, no calendar booking, hire/comms overloaded on Email, weak tests/RBAC.

---

## 2. Brand & UX decision

| Aspect | Decision |
|--------|----------|
| Product name | **Care Plus** |
| Design system | **Aurora Neural** (docs/FRONTEND.md) — not Medcare lorem / not Lumora dual-brand |
| Signature UX | Neural Core voice assistant (Goal Ring, chips, FSM) |
| Assistant name | **Serah** retained as the grounded chat/advice persona (optional display name) |
| Languages | Sinhala, Tamil, English (UI + speech + embeddings) |

---

## 3. Capability matrix

| Capability | Old | New target | Plan steps |
|------------|-----|------------|------------|
| Register patient/caregiver | ✅ | ✅ JWT + roles | 6, 10, 22b–c |
| Email OTP | ✅ (soft) | ✅ proper elevation | 22f |
| Consent / audit | ❌ | ✅ PDPA gate + immutable audit | 7–8, 68–69 |
| Voice → structured intent | partial chat | ✅ Neural Core pipeline | 13–15 |
| Medical vocabulary | KnownCondition | ✅ versioned vocab + synonyms | 15b–15c |
| Serah advice chat | ✅ Gemini | ✅ grounded + disclaimer | 15d–15e |
| ML matching | RF + Gemini IDs | ✅ VEHMF + XAI | 16–22 |
| Browse/search caregivers | ✅ | ✅ API + map UI | 20b–20e |
| Caregiver detail | ✅ | ✅ | 20d |
| Hire request/accept | ✅ via Email | ✅ `CareRequest` | 23–24 |
| Active care link | ✅ Link | ✅ `CareRelationship` | 25–26 |
| Care packages LKR | UI hardcode | ✅ catalog + order | 29–30 |
| Payment | mock UI | ✅ PaymentIntent + webhook | 31–33 |
| Medical records | ✅ | ✅ encrypted + RBAC | 34–37 |
| Messaging | prototype HTML | ✅ threads + WS | 38 |
| Reviews | weak | ✅ moderated → trust | 42–44 |
| Admin analytics | ✅ | ✅ | 54–58 |
| Marketing leads | Appointment/Subscription | ✅ | 27, 57 |
| Health vitals stream | ❌ static profile | ✅ Timescale + anomalies | 45–49 |
| Scheduling | ❌ bool available | ✅ calendar + Redlock | 50–53 |
| Mobile apps | ❌ | ✅ Expo | 62–67 |
| Compliance / ship | weak | ✅ | 68–75 |

---

## 4. Domain model evolution

| Old model | New model(s) |
|-----------|----------------|
| `Profile` (god object) | `User` + `PatientProfile` + `CaregiverProfile` (+ onboarding fields) |
| `KnownCondition` | `ConditionTerm` vocab (si/ta/en synonyms) |
| `Email` (messages + hire) | `Message` / `MessageThread` + `CareRequest` |
| `PatientCaregiverLink` | `CareRelationship` |
| `MedicalRecord` | `MedicalRecord` (encrypted) |
| `Appointment` / `Subscription` | `Lead` / `Subscriber` |
| `CareType` / `Food` / `Hospital` / `PaymentType` | `CarePackage` / `AddOn` / `Order` / `Payment` |
| `Review` | `Review` (real rating + moderation) |
| *(none)* | `VoiceIntent`, `MatchRun`, `MatchResult`, `HealthMetric`, `Shift`, `ConsentLog`, `AuditLog` |

---

## 5. User journeys (acceptance-level)

### Patient happy path
1. Register → consent AI → complete profile (vocab conditions)  
2. Tap Neural Core → speak need → chips fill → VEHMF results  
3. Open caregiver → Request care → choose package → pay  
4. Message caregiver → share/view records → rate after end  
5. (Later) vitals alerts / emergency re-match  

### Caregiver happy path
1. Register → onboarding + certs → set availability/calendar  
2. Inbox: accept/reject requests → get paid confirmation  
3. Current patient: messages + records  
4. End agreement → available again; collect reviews  

### Admin happy path
1. Manage users, vocab, packages  
2. Moderate reviews; process leads  
3. Analytics: matches, requests, latency  
4. Audit browser / erasure requests  

---

## 6. Explicit non-goals (v1 launch)

- Diagnosing disease or prescribing medication (Serah = informational only)  
- Replacing hospitals / emergency services (alert UX must say call 1990 / local emergency)  
- Copying old Medcare lorem marketing pages verbatim  
- Windows desktop tray launcher  

---

## 7. Evidence files in the old repo

- `backend/users/models.py` — Profile, KnownCondition, Review  
- `backend/dashboard/models.py` — MedicalRecord, Email, Link, catalogs  
- `backend/home/recommendation_engine.py` + `serah_gemini.py` — old matching  
- `backend/dashboard/ai.py` + `templates/dashboard/ai.html` — Serah voice UI  
- `backend/templates/dashboard/sidebar.html` — role navigation  
- `backend/home/templates/home/checkout.html` — hire/pay UX intent  
- `backend/caregiver_data.csv` — synthetic training reference only  

---

## 8. How agents / humans should use this doc

Before implementing a step, check:

1. Which **old capability** does this close?  
2. Which **new model/API/UI** replaces the old hack?  
3. What is the **✅ Acceptance** in DEVELOPMENT_PLAN.md?  
4. Update PROGRESS.md when done.
