# Research Methodology

**Document purpose.** This chapter provides a thesis-ready methodology for **Care Plus**: a research system that transforms multilingual spoken care needs (Sinhala, Tamil, and English) into an explainable, ranked caregiver recommendation via the **VEHMF** (Vector Embedding Hybrid Matching Framework) engine, with optional dynamic re-weighting under health emergencies and concurrency-safe scheduling.

**How to use this file.** Paste or adapt sections into your thesis Methodology chapter. Equations, evaluation protocols, and ethical controls are written for academic citation; implementation details are aligned with the Care Plus modular monolith described in `docs/ARCHITECTURE.md`.

---

## 1. Research design overview

### 1.1 Nature of the inquiry

The work follows a **design-science / engineering research** paradigm (artefact construction + empirical evaluation), complemented by a **mixed-methods evaluation** plan:

| Strand | Purpose | Primary outputs |
|--------|---------|-----------------|
| **Artefact design** | Build a reproducible voice→intent→match pipeline under resource constraints | VEHMF engine, AHP weights, Neural Core UI, APIs |
| **Offline IR / RS evaluation** | Measure ranking quality against baselines | NDCG@k, MAP@k, hit-rate, ablation tables |
| **Systems evaluation** | Prove latency and lean-resource claims | p50/p95/p99 match latency; RAM/CPU budget |
| **Human-centred evaluation** (planned / optional) | Validate understandability of XAI and multilingual UX | Task success, SUS/UMUX, preference vs baseline |

The research does **not** treat a large language model as a caregiver ranker. Conversational generation (Serah) and ranking (VEHMF) are deliberately **decoupled**: generative AI may structure intent or chat, but **final caregiver ordering is always produced by the hybrid numerical fusion model**. This separation is a methodological control against opaque, non-reproducible LLM ranking.

### 1.2 Guiding research questions

The methodology is organised to answer:

1. **RQ1 (Hybrid ranking).** Does a four-factor fusion of content-based similarity, collaborative filtering, geospatial proximity, and trust outperform content-only (CBF) ranking for caregiver recommendation under Sri Lankan profile constraints?
2. **RQ2 (Weight elicitation).** Can Analytic Hierarchy Process (AHP) stakeholder pairwise comparisons yield a consistent weight vector (Consistency Ratio \(CR < 0.1\)) that is usable at inference time?
3. **RQ3 (Voice→structure).** Can multilingual speech (si/ta/en, including code-mixed utterances) be mapped to a structured care intent with sufficient completeness to drive matching without manual form filling?
4. **RQ4 (Latency & efficiency).** Can the end-to-end match path achieve a **p95 latency under 800 ms** on a lean stack (≤ 4 GB RAM / 2 vCPU class target, no GPU at runtime)?
5. **RQ5 (Emergency adaptation).** Does dynamic AHP re-weighting under health-critical events increase medical-fit dominance in the top-\(k\) without requiring a separate ranking model?
6. **RQ6 (Explainability).** Do factor-level score breakdowns and dominant-factor explanations improve user comprehension relative to score-only lists? *(evaluated via XAI instrumentation + planned user study)*

### 1.3 Design priorities (ordered)

Correctness → **latency** → **resource efficiency** → research completeness. Trade-offs that violate the first three (e.g., calling an LLM to re-rank caregivers on every request) are rejected by design.

### 1.4 Scope and non-goals

**In scope:** voice and text intent capture; VEHMF ranking with XAI; geospatial and trust signals; emergency weight overrides; scheduling concurrency controls; consent/audit for AI processing; Sinhala/Tamil/English UI and speech pathways.

**Out of scope for the core research claims:** claiming clinical diagnosis; using generative AI as the sole matcher; full hospital EHR integration; guaranteeing real-world travel times without traffic APIs (geo uses distance/decay proxies unless travel-time services are later added).

---

## 2. Problem formulation

### 2.1 Matching as ranked retrieval

Let \(\mathcal{C} = \{c_1,\ldots,c_N\}\) be the caregiver candidate set eligible for matching (e.g., available, consented, region-filtered). Given a patient query state \(q\) (structured intent + optional patient embedding + location + hard filters), the system returns a ranked list:

\[
\pi(q) = \mathrm{argsort}_{c \in \mathcal{C}} \; S(q,c)
\]

where \(S(q,c) \in \mathbb{R}\) is the fused compatibility score. Evaluation treats \(\pi(q)\) as an information-retrieval ranking over caregivers.

### 2.2 Structured intent representation

Spoken or typed input is mapped to a structured schema \(I\), for example:

\[
I = \{\textit{condition},\; \textit{language(s)},\; \textit{care\_level},\; \textit{urgency},\; \textit{specialty},\; \textit{geo constraints}\}
\]

Missing critical fields trigger a **clarify** dialogue state rather than a low-quality match. Medical terms are normalised through a versioned multilingual vocabulary (synonyms in Sinhala, Tamil, and English → canonical slugs), reducing ASR and slang variance before embedding and filtering.

### 2.3 Fusion score (VEHMF)

Each candidate \(c\) receives four normalised factor scores in \([0,1]\):

| Symbol | Factor | Intuition |
|--------|--------|-----------|
| \(s_{\mathrm{cbf}}\) | Content-based (vector similarity) | Skills, languages, conditions, care level vs query |
| \(s_{\mathrm{cf}}\) | Collaborative filtering | Latent preference from interaction history |
| \(s_{\mathrm{geo}}\) | Geospatial fitness | Closer / shorter travel proxy → higher |
| \(s_{\mathrm{trust}}\) | Trust / reliability | Reviews, completion, certifications, availability history |

With AHP weights \(\mathbf{w}=[\alpha,\beta,\gamma,\delta]^\top\), \(\alpha+\beta+\gamma+\delta=1\), \(\mathbf{w}\ge 0\):

\[
S(q,c) = \alpha\, s_{\mathrm{cbf}}(q,c) + \beta\, s_{\mathrm{cf}}(q,c) + \gamma\, s_{\mathrm{geo}}(q,c) + \delta\, s_{\mathrm{trust}}(c)
\]

In matrix form for \(N\) candidates:

\[
\mathbf{S} = \mathbf{M}\mathbf{w},\quad \mathbf{M}\in\mathbb{R}^{N\times 4},\quad \mathbf{S}\in\mathbb{R}^{N}.
\]

**Emergency override.** Under a health-critical event, \(\mathbf{w}\) is replaced by a pre-validated emergency vector (default research setting \(\mathbf{w}_{\mathrm{em}}=[0.80,0.05,0.05,0.10]\)), emphasising medical/content fit over logistics and CF.

---

## 3. System methodology (artefact architecture)

### 3.1 Layered pipeline

The methodology realises four logical layers (Perception → Cognition → Decision → Execution):

1. **Perception (edge).** Browser/mobile captures audio; optional live captions via Web Speech; MediaRecorder uploads audio for server ASR when needed.
2. **Cognition (NLP & dialogue).** ASR → language identification / locked UI language → intent structuring (Gemini or stub) → dialogue **router** classifying turns as CHAT | MATCH | REFINE | ACTION | EMERGENCY (etc.).
3. **Decision (VEHMF).** Candidate retrieval + four-factor scoring + AHP fusion + XAI text + persistence of `MatchRun` / `MatchResult`.
4. **Execution (state).** Care requests, relationships, scheduling with distributed locks, notifications, audit/consent gates.

### 3.2 Lean vs full deployment profiles

| Concern | Lean profile (research MVP) | Full profile (north-star) |
|---------|-----------------------------|---------------------------|
| Topology | Modular monolith | Split VEHMF service if CPU-bound |
| Vector index | FAISS `IndexFlatIP` (exact) | HNSW approximate |
| CF | Offline ALS / implicit MF | Same, larger interaction graphs |
| DB | One Postgres + PostGIS + Timescale | Optionally specialised TSDB |
| Broker | Redis (cache, locks, Celery, channels) | May add dedicated MQ |

The thesis experiments are designed primarily on the **lean** profile so claims remain reproducible on modest hardware.

### 3.3 Reproducibility controls

- Pinned dependency versions (container images + lockfiles).
- Versioned ML artefacts under `ml/artifacts/` (FAISS embeddings, CF checkpoints).
- Versioned AHP config (`config/ahp_weights.json`) including pairwise matrix, \(\lambda_{\max}\), \(CR\), and emergency vector.
- Deterministic seeds for offline CF training where applicable.
- Audit logs for consent-gated AI turns and match invocations.
- Feature flag `CF_ENABLED` to ablate collaborative filtering without code forks.

---

## 4. Method: multilingual voice → structured intent

### 4.1 Speech recognition strategy

A **pluggable ASR backend** is used:

- Local **faster-whisper** (CPU `int8`) for English/general; optional Sinhala-specialised Whisper checkpoint for si-heavy audio.
- Optional cloud ASR / Gemini paths when configured.
- UI language lock (සිංහල | தமிழ் | English) constrains captions, ASR language hints, and Serah TTS replies; auto/mixed modes record `languages[]` for code-mixing.

**Methodological rationale.** Relying solely on browser STT fails for Sinhala/Tamil quality and for reproducible server-side experiments; a server ASR path enables offline replay of audio fixtures in tests.

### 4.2 Intent extraction

Intent extraction uses a **schema-constrained** LLM (Gemini Flash) when available, else a deterministic stub for CI/offline. Outputs must validate against the JSON schema (condition, language, care level, urgency, raw text). Vocabulary grounding maps colloquial phrases (e.g., “sugar problem”, Sinhala dengue synonyms) to canonical condition slugs before matching.

### 4.3 Conversational control loop

Unlike a one-shot “speak → cards” form, the production methodology uses a **turn router**:

| Route | When | Ranking side-effect |
|-------|------|---------------------|
| CHAT | Greetings, thanks, FAQ, small-talk | None |
| MATCH | Explicit care-seeking with enough fields | Full VEHMF |
| REFINE | Post-match constraints (“only Tamil within 5 km”) | Re-run VEHMF with deltas; track rank deltas |
| EMERGENCY | Critical health / emergency phrases | VEHMF with emergency weights |
| ACTION | Book / request / navigate | Domain APIs, not re-rank |

**Critical rule:** MATCH/REFINE never accept caregiver IDs from the LLM. This is both an ethical and a validity control for RQ1–RQ2.

### 4.4 Session memory

Dialogue sessions store recent turns, chips, route history, and last `MatchRun` so refine and “about match” questions remain coherent without re-asking the entire need.

---

## 5. Method: content-based filtering (CBF)

### 5.1 Representation

Caregiver profiles (languages, specialties, care level, certifications, free-text bio, condition tags) are embedded into a dense vector \(\mathbf{v}_c \in \mathbb{R}^{d}\) (lean default: hash embedder; optional sentence embedding model such as E5 when enabled). Patient query \(q\) is embedded to \(\mathbf{v}_q\) from structured intent (+ optional transcript).

Vectors are **L2-normalised** so that inner product equals cosine similarity:

\[
\mathrm{sim}(q,c) = \mathbf{v}_q^\top \mathbf{v}_c.
\]

### 5.2 Retrieval

FAISS `IndexFlatIP` retrieves top-\(K\) (e.g., 50–100) neighbours. Exact search is preferred in the lean profile to avoid approximate-search confounding when reporting ranking metrics.

### 5.3 Normalisation into fusion

Raw similarities over the candidate pool are min–max normalised to \([0,1]\) per request so factor scales are comparable before AHP weighting.

---

## 6. Method: collaborative filtering (CF)

### 6.1 Interaction model

Implicit feedback events are logged: profile view, care request, accept, complete, rate. These form a sparse patient–caregiver interaction matrix.

### 6.2 Training protocol

- **Offline only** (Celery beat / management command); never train inside the HTTP request path (latency control for RQ4).
- Algorithm family: **implicit ALS** (or LightFM-class MF in the full profile).
- Artefacts versioned; engine loads latest compatible checkpoint via `get_cf_model()`.

### 6.3 Ablation

With `CF_ENABLED=false`, weight \(\beta\) is set to 0 and redistributed across remaining AHP factors so \(\mathbf{w}\) still sums to 1. This yields a clean CBF+Geo+Trust baseline for RQ1.

### 6.4 Cold start

New patients/caregivers have weak CF signals; fusion naturally falls back to CBF/geo/trust. Cold-start behaviour is reported separately in evaluation (segmented metrics).

---

## 7. Method: geospatial fitness

### 7.1 Storage and query

Patient and caregiver locations are stored as `geometry(Point, 4326)` in **PostGIS** with GiST indexes. Candidate sets may be prefiltered by radius (`near`, `radius_km`) before fusion.

### 7.2 Scoring

Distance (or travel-time proxy) \(d(q,c)\) is mapped to a decaying score, e.g. higher when closer, clipped and normalised across the pool to \(s_{\mathrm{geo}}\in[0,1]\). Hard max-distance constraints from REFINE turns remove candidates before scoring.

**Limitation to disclose in the thesis.** Straight-line or simple decay is not identical to real road travel time; any production travel API would be a drop-in replacement for the geo repository without changing the fusion equation.

---

## 8. Method: trust scoring

Trust \(s_{\mathrm{trust}}\) aggregates moderated reviews, completion rates, certifications, and prior trust with inertia (to avoid volatile swings from single events). Soft presence (`is_available`) can exclude caregivers from top-\(N\) entirely. Trust is recomputed asynchronously after review moderation, not synchronously in the match hot path beyond reading the stored score.

---

## 9. Method: AHP weight elicitation

### 9.1 Hierarchy

Goal: *best caregiver match for home care*. Criteria (fixed order for the engine): **CBF, CF, Geo, Trust**.

### 9.2 Pairwise comparison

Stakeholders (clinicians, caregivers, patients/families, platform designers—as available) compare criteria on Saaty’s 1–9 scale. Entry \(a_{ij}\) states how much more important criterion \(i\) is than \(j\), with \(a_{ji}=1/a_{ij}\) and \(a_{ii}=1\).

Default research matrix (clinical content preferred over CF; trust ≈ geo):

\[
A =
\begin{bmatrix}
1 & 5 & 3 & 2 \\
1/5 & 1 & 1/3 & 1/4 \\
1/3 & 3 & 1 & 1 \\
1/2 & 4 & 1 & 1
\end{bmatrix}
\]

### 9.3 Solution and consistency

Compute the principal eigenvalue \(\lambda_{\max}\) and principal eigenvector \(\mathbf{v}\); normalise to weights \(\mathbf{w}=\mathbf{v}/\|\mathbf{v}\|_1\).

\[
CI = \frac{\lambda_{\max}-n}{n-1},\quad
CR = \frac{CI}{RI(n)}.
\]

For \(n=4\), \(RI\approx 0.90\). **Acceptance rule:** \(CR < 0.1\). Matrices failing this threshold are revised with stakeholders—not silently used.

Published lean config (illustrative): \(\mathbf{w}\approx[0.480,\,0.074,\,0.204,\,0.242]\), \(CR\approx 0.019\), \(\lambda_{\max}\approx 4.051\).

### 9.4 Runtime injection

Weights load at process start from `ahp_weights.json` (or env overrides). Emergency vector is stored alongside and applied only on emergency routes / health triggers.

---

## 10. Method: explainability (XAI)

For each ranked caregiver, the system exposes:

1. **Factor breakdown** \((s_{\mathrm{cbf}}, s_{\mathrm{cf}}, s_{\mathrm{geo}}, s_{\mathrm{trust}})\) visualised as bars.
2. **Dominant contributor** \(\arg\max_i (M_{c,i}\, w_i)\) mapped to a human sentence (skill match / similar patients / proximity / trust).
3. **Optional localisation** of explanation strings for si/ta/en UI language.
4. **Latency badge** \(latency\_ms\) for transparency of the systems claim.

Explanations are **faithful to the fusion arithmetic** (post-hoc factor attribution), not free-form LLM rationalisations of why a caregiver was chosen. This distinction should be stated explicitly in the thesis to avoid overclaiming “LLM explainability.”

---

## 11. Method: emergency dynamic re-matching

### 11.1 Trigger sources

- Dialogue EMERGENCY route from voice/text.
- Wearable / vitals anomaly pipeline (TimescaleDB window rules or learned detector) publishing a health-critical event.

### 11.2 Procedure

1. Persist anomaly / emergency context.
2. Invoke VEHMF with \(\mathbf{w}_{\mathrm{em}}\) (medical/content dominance).
3. Push results over WebSocket and optional FCM.
4. Record `MatchRun.emergency=true` for evaluation segmentation.

### 11.3 Evaluation angle (RQ5)

Compare top-\(k\) specialty/certification hit-rate and mean \(s_{\mathrm{cbf}}\) under \(\mathbf{w}\) vs \(\mathbf{w}_{\mathrm{em}}\) on held-out emergency scenarios; report latency of re-match path separately.

---

## 12. Method: concurrency-safe scheduling (supporting capability)

Although secondary to ranking, scheduling race conditions threaten validity of “matched caregiver is bookable.” Methodology:

1. Acquire **Redis Redlock** mutex keyed by caregiver + slot.
2. Check shift overlap in PostgreSQL (+ optional travel buffer).
3. Commit winner; loser receives **409** with VEHMF **next-best** suggestion.

This operationalises a systems contribution: matching quality is useless if double-booking silently corrupts assignments.

---

## 13. Experimental methodology

### 13.1 Datasets and corpora

| Dataset | Role | Notes |
|---------|------|------|
| Seeded Sri Lanka caregiver profiles | CBF/geo/trust candidates | Languages, cities (Colombo, Kandy, Galle, Jaffna, …), specialties |
| Condition vocabulary | Intent grounding | Multilingual synonyms → slugs |
| Synthetic / logged interactions | CF training | `seed_interactions` + production event logs |
| Voice turn fixtures | ASR/intent regression | Text + audio samples where licensed |
| Stakeholder AHP survey | Weight elicitation | Pairwise matrices; report CR |

**Ethics note.** Prefer synthetic or consented logs for offline IR metrics when real patient audio/PHI cannot be published. Document de-identification if any field study data are used.

### 13.2 Baselines

1. **Random** ordering of eligible caregivers.
2. **CBF-only** (\(\alpha=1\)).
3. **CBF+Geo+Trust** (`CF_ENABLED=false` redistribution).
4. **Full VEHMF** (AHP weights + CF).
5. **Legacy-style** (if reconstructed): classical ML classifier + optional LLM re-rank — used only as historical contrast; **not** the proposed system.

### 13.3 Offline ranking metrics

For each query \(q\) with graded or binary relevance labels \(rel(q,c)\):

\[
\mathrm{DCG@}k = \sum_{i=1}^{k} \frac{2^{rel_i}-1}{\log_2(i+1)},\quad
\mathrm{NDCG@}k = \frac{\mathrm{DCG@}k}{\mathrm{IDCG@}k}
\]

\[
\mathrm{AP@}k = \frac{1}{\min(k,R)}\sum_{i=1}^{k} P@i\cdot \mathbf{1}[rel_i>0],\quad
\mathrm{MAP@}k = \mathrm{mean}_q\,\mathrm{AP@}k
\]

Also report HitRate@k / Recall@k for binary labels. Prefer **paired** comparisons (same queries) and report mean ± CI or Wilcoxon signed-rank where sample size allows.

**Label construction options (state which you used):**

- Expert panel relevance grades for a fixed query set.
- Proxy labels from held-out accept/complete/rate outcomes (interaction-derived).
- Specialty/language hard-constraint satisfaction as weak labels for ablation sanity checks.

### 13.4 Systems metrics

- End-to-end `MatchRun.latency_ms`: p50, p95, p99; slice by emergency vs normal; CF on vs off.
- Resource: peak RSS of backend under load; confirm lean budget narrative.
- ASR/intent: field completion rate, clarify-loop length, language confusion matrix (si/ta/en).
- Dialogue router: confusion matrix on annotated turn situations; **constraint** that MATCH never returns LLM-chosen IDs (unit/integration tests as methodological evidence).

### 13.5 Ablation matrix (recommended thesis table)

| Variant | CBF | CF | Geo | Trust | Weights |
|---------|-----|----|-----|-------|---------|
| A0 Random | – | – | – | – | – |
| A1 CBF | ✓ | | | | \(\alpha=1\) |
| A2 +Geo | ✓ | | ✓ | | equal or AHP w/ β=0 |
| A3 +Trust | ✓ | | ✓ | ✓ | `CF_ENABLED=false` |
| A4 Full VEHMF | ✓ | ✓ | ✓ | ✓ | AHP \(\mathbf{w}\) |
| A5 Emergency | ✓ | ✓ | ✓ | ✓ | \(\mathbf{w}_{\mathrm{em}}\) |

### 13.6 Online / user study protocol (optional but strong for RQ3/RQ6)

**Participants.** Sri Lankan patients/family caregivers and professional caregivers; stratified by language preference (si/ta/en). Target sample sized for within-subject design if possible.

**Tasks.**

1. Express a care need by voice (and by typed baseline).
2. Interpret top-3 cards with vs without factor bars/XAI text.
3. Apply one refine utterance and verify list changes.

**Measures.** Task success (correct specialty/language in top-3), time-to-match, subjective trust and clarity Likert scales, SUS/UMUX for Neural Core, preference forced-choice vs score-only UI. Pre-register hypotheses where feasible.

**Controls.** Counterbalance condition order; fix caregiver catalogue during sessions; log latency and routes automatically.

### 13.7 Statistical reporting standards

- Pre-specify primary metric (e.g., NDCG@10) and \(k\) values (5, 10).
- Multiple-comparison awareness when many ablations are shown.
- Separate **development** seed profiles from **evaluation** query sets to reduce overfitting narrative.

---

## 14. Implementation environment (for Methods “tools” subsection)

| Component | Choice | Role in method |
|-----------|--------|----------------|
| Backend | Django 4.2, DRF, Channels (ASGI) | APIs, WS push, auth/RBAC |
| Match compute | NumPy + FAISS + CF artefact | VEHMF |
| AHP | NumPy eigendecomposition | Weight solving + CR |
| DB | PostgreSQL + PostGIS + TimescaleDB | Geo, OLTP, vitals |
| Cache/locks | Redis + Redlock | Scheduling, sessions |
| Async | Celery worker + beat | CF train, trust recompute, expiry |
| Web | React 18, Vite, R3F Neural Core | Perception UI + results |
| NLP | Gemini Flash (schema JSON) + stubs | Intent/chat only |
| ASR/TTS | faster-whisper / Piper / Gemini TTS / browser | Multilingual I/O |

---

## 15. Ethics, privacy, and compliance methodology

1. **Consent gate.** AI voice processing and matching require explicit consent scopes before `/voice/turn/` and `/match/` proceed.
2. **Audit trail.** Immutable logs for consent changes, match runs, admin actions; exportable for compliance review.
3. **RBAC.** Patient, caregiver, admin, auditor roles; auditors read-only where specified.
4. **Data minimisation.** Prefer structured intent over retaining raw audio longer than needed; document retention.
5. **Clinical disclaimer.** Serah chat is guidance, not diagnosis; policy documented (`DIALOGUE_POLICY.md`).
6. **PDPA-oriented practices.** Field encryption roadmap for sensitive health fields; encryption keys via env, not source control.
7. **Human oversight.** Hire lifecycle (request/accept) remains human-confirmed; the model recommends, it does not auto-assign care without workflow consent.

---

## 16. Threats to validity and mitigations

| Threat | Risk | Mitigation |
|--------|------|------------|
| **Internal — label noise** | Weak relevance labels inflate NDCG | Expert subset + sensitivity analysis |
| **Internal — train/serve skew** | CF trained on synthetic interactions | Report synthetic vs logged separately |
| **External — geography** | Seed cities ≠ island-wide demand | Stratify metrics by region; disclose |
| **External — ASR quality** | Lab mics ≠ home noise | Noise-augmented tests; field pilot |
| **Construct — “explainability”** | Users may trust fluent but wrong text | Use fusion-faithful XAI only; user study |
| **Construct — latency** | Warm cache vs cold start | Report both; exclude one-off model download |
| **Conclusion — LLM leakage** | Accidental Gemini ranking | Automated tests + dialogue policy lock |
| **Conclusion — CR cherry-picking** | Tweaking matrix until CR passes | Publish full pairwise matrix + CR |

---

## 17. Limitations (to state candidly)

- Lean FAISS exact search will not scale linearly to millions of caregivers without HNSW/sharding (full profile).
- CF quality depends on interaction density; early deployments are CBF-heavy.
- Geo scores may ignore traffic, public transport, and last-mile realities.
- Gemini intent quality depends on API availability; stub mode underestimates real multilingual NLP error modes unless local models are evaluated too.
- User-study results (if not yet run) should be labelled **proposed protocol** vs **completed findings**.

---

## 18. Summary of methodological contribution

This research methodology specifies a **reproducible, explainable, multilingual caregiver matching pipeline** in which:

1. Speech is reduced to a **validated structured intent**;
2. Caregivers are scored by a **hybrid four-factor model (VEHMF)**;
3. Factor importance is elicited via **AHP with explicit consistency checks**;
4. Emergencies **re-weight** rather than replace the model;
5. Generative AI is confined to **language understanding and conversation**, never opaque ranking;
6. Claims are tested with **IR metrics, systems latency, ablations, and (optionally) human evaluation** under Sri Lankan linguistic and geographic constraints.

---

## Appendix A — Notation quick reference

| Symbol | Meaning |
|--------|---------|
| \(q\) | Patient query / intent state |
| \(c\) | Caregiver candidate |
| \(\alpha,\beta,\gamma,\delta\) | AHP weights for CBF, CF, Geo, Trust |
| \(S(q,c)\) | Fused score |
| \(CR\) | AHP consistency ratio |
| \(k\) | Cut-off for ranking metrics |
| \(\mathbf{w}_{\mathrm{em}}\) | Emergency weight vector |

## Appendix B — Suggested thesis subsection mapping

| Thesis heading | Use sections |
|----------------|--------------|
| Research design | §1 |
| Problem formulation | §2 |
| System design / architecture method | §3 |
| Voice & NLP method | §4 |
| VEHMF components | §5–§10 |
| Emergency & scheduling | §11–§12 |
| Experiments & evaluation | §13 |
| Tools & environment | §14 |
| Ethics | §15 |
| Validity & limitations | §16–§17 |

---

*Aligned with Care Plus architecture and implementation (VEHMF, AHP config, dialogue policy, lean Docker profile). Update numerical results tables after you run the final evaluation suite for the dissertation.*
