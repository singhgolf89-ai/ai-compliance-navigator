# AI Compliance Navigator — v2 Build Plan

**Theme:** v1 built a tool that makes auditable determinations. v2 makes the tool *accountable for itself and measurable* — every assessment logged and reproducible, retrieval quality measured not assumed, the public app traction-tested — while closing the one known classifier gap (GPAI).

**Budget:** ~$5 hard cap total (Phase 1 LLM key). Everything else runs on Free Edition / free tiers.
**Time:** ~21 build hours across 7 phases (0–6), mirroring the v1 cadence of 3–4 h/week.
**Branch strategy:** all v2 work on branch `v2`; `main` stays frozen as the working deployed app (Streamlit Cloud deploys from `main`, so the live URL can never break mid-build). Merges to `main` are releases.

---

## v2 scope

**IN:** traction instrumentation + LinkedIn launch; live-lite public hardening (in-process retrieval + capped-key synthesis); assessment audit log with rule trail, classifier version, and corpus Delta version; lightweight Google auth (`st.login`) for attribution; assessment history with re-run-and-diff; golden-set retrieval eval with MLflow-logged baseline + one tuning iteration; GPAI overlay classification (Art. 51–56); housekeeping (databricks-ai-search migration, Playbook noise strip, retrieval query tuning).

**OUT (v3 backlog):** PDF export; interactive follow-up questioning (if ever built: refines *intake fields* feeding the deterministic engine — never the tier directly); corpus expansion beyond EU + NIST (first candidate: Colorado SB 21-169 or NYDFS 500); ISO/IEC 42001 (paywalled text — can't ingest into a public-repo pipeline); multi-tenancy, roles, payments; paid hosting; Databricks Apps migration (revisit only if the paid-Databricks gate trips).

---

## Canonical identifiers (v2 additions — use these exact names)

| Thing | Name |
|---|---|
| Working branch | `v2` (main = release) |
| Audit table | `ai_governance.compliance_navigator.assessment_log` |
| New modules | `src/audit_log.py`, `src/retrieval_local.py` |
| One-off script | `scripts/embed_corpus_local.py` |
| Eval notebook | `notebooks/04_golden_eval.py` |
| Data artifacts | `data/corpus_embeddings.npz`, `data/corpus_chunks_meta.json` |
| Golden set | `tests/golden_set.json` |
| New constants in `src/utils.py` | `CLASSIFIER_VERSION`, `APP_VERSION`, `PUBLIC_RETRIEVAL` (`"local"` \| `"databricks"`), `LOCAL_EMBED_MODEL = "BAAI/bge-small-en-v1.5"` |
| Cloud secrets keys | `DEMO_MODE` (retained), `[llm] provider / api_key` (Phase 1) |

---

## Verify before building (things that drift — check first, per phase noted)

1. **Free Edition SQL warehouse writes** via `databricks-sql-connector` with a `sql`-scoped PAT (Phase 2 blocker if unavailable).
2. **`st.login` Google provider** — current API shape on the deployed Streamlit version (Phase 2).
3. **RAM fit:** `bge-small-en-v1.5` (~130 MB) + Streamlit + deps under Community Cloud's 1 GB guarantee (Phase 1).
4. **Provider spend-cap mechanics:** confirm the chosen LLM provider offers a *hard* cap or prepaid credits, not just alert emails (Phase 1).
5. **MLflow tracking:** run the eval as a workspace notebook to use managed MLflow (Phase 4); `mlruns/` stays gitignored either way.
6. **Token expiry:** the `streamlit-cloud` PAT expires ~day 90 — the app silently degrades to fallback-sample when it does. Calendar reminder at day 80 (Phase 0 item).

---

## Phase plan and Definitions of Done

**Phase 0 — Launch & Traction Instrumentation (~2h, $0).**
Done when: LinkedIn case-study post published with the live URL, repo link, and one report screenshot; Community Cloud viewer-analytics baseline recorded in the worklog; GitHub Insights → Traffic baseline (unique visitors, clones) recorded; app sidebar carries a feedback/contact link plus a "Want live analysis of your system? Reach out" CTA; numeric traction gates written in the worklog before any data comes in (e.g., ≥50 unique app viewers/week sustained 4 weeks, OR ≥3 inbound live-analysis requests, OR 1 design-partner conversation); the DEMO_MODE=false live behavior is verified in a private window (live report generated; graceful fallback banner on backend failure) or consciously reverted with the reason logged; token-expiry reminder set.

**Phase 1 — Live-Lite Public Hardening (~3h, ≤$5).**
*Trigger: quota throttling observed, reliability complaints, or proactive choice — this phase can run any time after Phase 0.*
Design: the public tier becomes self-contained. Re-embed all 455 chunks **locally** with `bge-small-en-v1.5` via `scripts/embed_corpus_local.py` (one-off); ship `corpus_embeddings.npz` (~a few MB) + `corpus_chunks_meta.json` in the repo; `src/retrieval_local.py` implements the same interface as `retrieval.py` (source + tier filtering included), selected by `PUBLIC_RETRIEVAL`. Query embedded at runtime with the *same local model* — corpus and query must share one embedding space; the local 384-dim set is independent of the Databricks BGE-large index, which remains the entitled-workspace path. Synthesis on the public tier via a provider API key with a **hard $5 cap** set in the provider console, key only in Streamlit Cloud secrets.
Done when: the public URL performs fully live analysis with the Databricks token **removed entirely** from cloud secrets; memory footprint verified under 1 GB (sustained runs without the resource-limit error); per-report cost measured and recorded (<$0.01 target); the spend cap confirmed in the provider console and noted in the worklog; README honest-notes updated ("in-process retrieval on the public tier; drop-in swap to Databricks AI Search on an entitled workspace"); local dev mode still runs the full Databricks path unchanged; S1 (high-risk), S4 (prohibited), and S8 (minimal) render correctly on the public URL.

**Phase 2 — Audit Spine (~4h, $0).**
Done when: `assessment_log` created per the agreed DDL (CDF enabled; PK on `assessment_id`; `all_matches` array; `classifier_version`; retrieved chunk IDs; `corpus_table_version` = Delta version of `regulatory_chunks` at assessment time; `synthesis_status`; latency); `CLASSIFIER_VERSION` and `APP_VERSION` constants added to `utils.py` and stamped on every row; `src/audit_log.py` writes via `databricks-sql-connector` to the serverless SQL warehouse using a **new sql-scoped PAT** (verify item #1 first); the app logs every live-mode assessment **including failures**; logging is deliberately suppressed in demo mode and live-lite public mode (design decision, documented: the audit log lives where the governed backend lives — public live-lite traffic is measured by analytics instead); `st.login` Google auth wired with `user_id` = stable subject identifier, raw email kept out of the log; a one-line privacy notice live in the sidebar ("Assessments are logged for audit and reproducibility"); an erasure runbook committed to `docs/` covering the Delta nuance (right-to-erasure = DELETE **plus** VACUUM past the retention window — time travel retains deleted rows until then); a verification query shows ≥3 logged assessments with populated rule trails and corpus versions.

**Phase 3 — Assessment History + Re-run Diff (~3h, $0).**
Done when: a "Past Assessments" tab lists the signed-in user's rows (id, timestamp, system name, tier); reopening a row renders its stored report; a "Re-run against current corpus" action executes the fresh pipeline and shows a diff view (tier changed yes/no; EU obligations added/removed by article; NIST subcategory delta); at least one demonstrable "the rules/corpus changed → the determination changed" case captured as a screenshot for the story (simulate via a classifier-version bump or a corpus edit + re-sync); clean empty-state when a user has no history; the killer demo line works live: *"the regulation changed — here's exactly what changed in your obligations."*

**Phase 4 — Golden-Set Eval + Retrieval Metrics (~4h, $0–pennies).**
Done when: `tests/golden_set.json` holds 12–15 systems with expert-expected EU articles and NIST subcategories (your judgment, sources noted per entry); `notebooks/04_golden_eval.py` computes retrieval hit-rate@k per track (EU, NIST) plus citation coverage, logging every run to managed MLflow with params (query-template version, k, endpoint); a baseline is recorded; at least one tuning iteration attempted (query construction v2, or a simple rerank) with before/after numbers logged; a results table added to the README; the Q4 interview answer upgraded from "I don't measure relevance rigorously" to actual numbers.

**Phase 5 — GPAI Overlay + Housekeeping (~3h, $0).**
Design note: GPAI (Art. 51–56) is a *parallel regime*, not a fifth tier — a GPAI system still has a use-case tier. Model it as an overlay: add `is_gpai: bool` and `gpai_articles: list` to `ClassificationResult`; detection signals (general-purpose / foundation / base model provided to downstream developers) set the flag, attach Art. 51–56 with the 2 August 2025 applicability date, and note the systemic-risk threshold as a documented sub-case. This is the legally correct shape and preserves the four-tier enum.
Done when: the GPAI overlay is implemented with the modeling choice documented in the module docstring; S10 updated from "documented edge case" to a real assertion (correct tier + `is_gpai=True` + Art. 51–56 present) and passes; the full suite stays green (4 unit + S1–S10); `databricks-vectorsearch` → `databricks-ai-search` migration complete (imports + requirements) with a retrieval regression spot-check; Playbook page-furniture noise patterns ("N of 142") added to `clean_text`, corpus re-ingested, index re-synced, new chunk counts recorded and the delta noted in the worklog.

**Phase 6 — v2 Ship & the Paid-Databricks Decision (~2h, $0).**
Done when: README gains a v2 section (the audit-trail story, the eval numbers table, GPAI coverage); worklog v2 close-out written; demo script refreshed — the audit-log answer woven into Q1/Q2, real eval numbers into Q4; a second LinkedIn post drafted ("shipped the roadmap," leading with one metric); the traction-gate review held against ≥4 weeks of Phase 0 data with a **documented go/no-go on paid Databricks** — and if go, the entry criteria are pre-committed: budget alerts configured, service principal replacing the PAT, and an endpoint-base-cost plan (verified against the current pricing calculator) before any resource is created; `v2` merged to `main`; the deployed app verified working post-merge.

---

## v2 acceptance (final gate)

v2 is done only when all seven phase gates pass AND: the end-to-end audit demo works live (submit an assessment → show its log row → show the rule trail and classifier version → run a time-travel query reproducing the exact corpus text it saw); the eval baseline and tuning delta are quotable from memory; the public URL ran the full traction window with zero hard failures (fallbacks with banners are acceptable; stack traces are not); and the paid-Databricks go/no-go is documented with numbers, not vibes.

---

## Cost & risk guardrails (always on)

- Hard ceiling for all of v2: the $5 provider cap. No subscription of any kind gets created in v2.
- Nothing billable is provisioned on Databricks in v2; if the Phase 6 decision is "go," paid resources are a v3 opening move with the pre-committed entry criteria above.
- `main` never breaks: every merge is preceded by the public-URL smoke test (submit S1, confirm render).
- Any scope beyond the IN list gets named as creep, costed in hours, and parked on the v3 backlog — same rule as v1.
