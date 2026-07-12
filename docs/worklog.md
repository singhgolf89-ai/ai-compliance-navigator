\# AI Compliance Navigator — Work Log



\## Session 1 — Friday, July 11, 2026 | 2:00 PM – 3:30 PM ET (1.5 hrs)

\*\*Phase 1 — Data Foundation: COMPLETE (gate passed)\*\*



\### Completed

\- Created local repo skeleton (`notebooks/`, `src/`, `tests/`, `data/`, `.streamlit/`) per target structure

\- Added `.gitignore` with secrets exclusion; verified with `git check-ignore` (secrets-exclusion DoD item)

\- Scrubbed PII from `architecture.md` header (removed employer/title; neutralized status line); set GitHub noreply email as commit identity

\- Initialized git, first commit, pushed to private GitHub repo `ai-compliance-navigator`

\- Downloaded corpus from official sources: EU AI Act (EUR-Lex, Reg. 2024/1689), NIST AI RMF 1.0 (AI 100-1), NIST AI RMF Playbook

\- Stood up Databricks Free Edition workspace (serverless)

\- Created Unity Catalog objects: `ai\_governance.compliance\_navigator` + `raw\_docs` volume

\- Created Delta tables `raw\_documents` (Change Data Feed enabled) and `regulatory\_chunks`

\- Uploaded 3 PDFs to volume; ran full ingestion notebook `01\_document\_ingestion.py`

\- Verified spot-checks: Article 5 = prohibited, Article 9 = high\_risk/provider, Annex III = high\_risk, GOVERN 1.1 / MANAGE 1.1 clean in both NIST sources



\### Chunk counts (recorded per DoD)

| source | chunks | sections | approx\_tokens |

|---|---|---|---|

| eu\_ai\_act | 185 | 124 | 87,918 |

| nist\_ai\_rmf | 85 | 72 | 12,037 |

| nist\_playbook | 185 | 72 | 78,459 |



Note: 72 NIST sections = exact RMF core subcategory count, independently

reproduced by RMF and Playbook parses — cross-validates both.



\### Issues hit \& resolutions (interview knowledge)

1\. \*\*PowerShell vs bash syntax\*\* — original commands were bash; translated to

&#x20;  PowerShell (`New-Item`, comma-separated `mkdir`).

2\. \*\*git push 403\*\* — cached credential belonged to a different GitHub account

&#x20;  than the repo owner. Lesson: HTTPS pushes authenticate via the cached token,

&#x20;  not the remote URL.

3\. \*\*GH007 email-privacy rejection\*\* — commit authored with real email while

&#x20;  GitHub privacy protection enabled. Fixed with noreply address +

&#x20;  `git commit --amend --reset-author`.

4\. \*\*Serverless session setup error (XX000)\*\* — transient platform issue after

&#x20;  `restartPython()`; resolved by detaching/reattaching compute.

5\. \*\*pypdf kerning artifact (the big one)\*\* — EUR-Lex letter-spaced typography

&#x20;  made pypdf insert intra-word spaces ("Ar ticle"), breaking all heading

&#x20;  regexes. Swapped extraction to PyMuPDF; added keyword normalization in

&#x20;  `clean\_text` as a guard. Lesson: PDF extraction fidelity is a first-class

&#x20;  engineering decision — always eyeball extracted text before trusting parsers.

6\. \*\*Chunker hardening\*\* — replaced naive `Article N` splitting with validated

&#x20;  headings (short-line check + monotonic article-number sequence) so inline

&#x20;  cross-references can't fragment chunks. Added annex chunking (not in

&#x20;  original architecture doc) since Annex III retrieval is a Phase 2 gate.



\### Open items / watch list

\- Playbook chunks contain residual page furniture ("5 of 142") — add noise

&#x20; pattern next time the notebook is touched

\- Some Playbook chunks are pure reference lists — monitor retrieval quality in Phase 2

\- VERIFY regulatory dates against EUR-Lex Art. 113 before any demo (arch doc's

&#x20; limited-risk deadline of 2025-08-02 appears to conflate the GPAI date)

\- PyMuPDF is AGPL — note in README dependencies



\### Next session (Phase 2 — Vector Search + Classification)

\- Pre-work (2 min): confirm in workspace UI that Vector Search create option

&#x20; and a BGE/GTE embedding serving endpoint exist on Free Edition

\- Create AI Search endpoint + Delta Sync index over `regulatory\_chunks`

\- Build `src/classification\_engine.py`; test 4 seed systems across all 4 risk tiers
---

## Session 2 — Friday, July 11, 2026 | Evening (~1.5 hrs)
**Git hygiene + single source of truth: COMPLETE**

### Completed
- Diagnosed commit misattribution: commits were authored with a placeholder
  noreply ID (12345678+...) which GitHub resolved to a stranger's account
  (shubh2294). Confirmed via `git log` that all commits were mine — no foreign
  access, no compromise.
- Rewrote all commit authorship with real noreply address
  (301088062+singhgolf89-ai@users.noreply.github.com) via
  `git rebase -r --root --exec "git commit --amend --reset-author --no-edit"`;
  force-pushed with `--force-with-lease`. Verified avatars on GitHub.
- Relocated repo OneDrive → C:\Users\singh\code after OneDrive file locks
  corrupted two rebase attempts (orphaned .git/rebase-merge state); recovered
  via manual marker cleanup + `git reset --hard origin/main` + fresh clone
  (un-nested the clone-into-same-name folder).
- Fixed repo visibility: created public by mistake → now Private; verified
  Collaborators = 0 ("only you can contribute").
- Databricks Git integration: fine-grained PAT (single repo, Contents r/w,
  ~90-day expiry) + Git provider email set to real noreply address.
- Consolidated workspace to one git-backed Git folder; removed old
  standalone/imported copies (resolved "repo already exists" collision).
- Round-trip verified end-to-end: edit in Databricks Git folder → Commit &
  push → visible on GitHub under my avatar → `git pull` locally (fast-forward,
  d1988be..d4a014e).

### Issues hit & resolutions (interview knowledge)
1. **Commit attribution is metadata, not access control** — GitHub maps the
   self-declared author email to an account; a stranger's avatar meant email
   mix-up, not intrusion. Public/private governs reads; commits always require
   write access. Enterprise answer for provable authorship: signed commits.
2. **Never keep git repos in synced folders** — OneDrive held locks during
   rebase's rewind/replay cycle and half-deleted .git/rebase-merge, producing
   "rebasing but no rebase exists" limbo. GitHub is the backup; a sync agent
   on .git is pure liability.
3. **git clone creates its own directory** — cloning into an existing
   same-named folder nests the repo one level deep.
4. **Commit messages are not commands** — dialog text goes in dialogs;
   PowerShell only gets git commands.

### Open items (carried forward)
- Playbook chunks: strip page furniture ("N of 142") next notebook touch
- VERIFY regulatory dates vs EUR-Lex Art. 113 before any demo
- PyMuPDF AGPL note for README dependencies section

### Next session — Phase 2 kickoff (Vector Search + Classification)
- Pre-work: entitlement check — Compute → Vector Search "Create" option?
  Serving → BGE/GTE embedding endpoint listed? Report before dependent code.
- Constraint: free tier = 1 vector search endpoint max; create nothing early.
- Build: Delta Sync index over regulatory_chunks; src/classification_engine.py;
  4 seed systems spanning all 4 risk tiers.
---

## Session 3 — Sunday, July 12, 2026 | Phase 2: Vector Search + Classification — PASSED

### Completed
- Entitlement check: AI Search (create) available; databricks-bge-large-en +
  databricks-gte-large-en embedding endpoints confirmed working (1024-dim).
  Fully managed vector track — no fallback needed.
- classification_engine.py: deterministic 4-tier EU AI Act classifier; passes
  4 seed systems (prohibited/high-risk/limited/minimal). Fixed arch-doc bug
  (None leaking into applicable_articles for non-deployers); added all_matches
  audit field.
- Delta Sync vector index over regulatory_chunks with managed BGE embeddings:
  455 rows indexed, ONLINE_NO_PENDING_UPDATE.
- Retrieval verified: EU-filtered query surfaces Art. 6/8/9/12 high_risk;
  risk-tier filter respected (no forbidden tiers leak).

### Issues hit & resolutions (interview knowledge)
1. Enabled Change Data Feed on regulatory_chunks (required for Delta Sync;
   only raw_documents had it at creation).
2. SDK renamed databricks-vectorsearch → databricks-ai-search; wait_until_ready
   signature changed (expects timedelta, not int) → replaced with manual
   describe()-polling loop (more robust anyway).
3. Corrupted index from interrupted build ("not ready" on both query AND sync)
   → delete_index + recreate clean. Lesson: Delta Sync index has two phases
   (create + sync); interrupted sync leaves "exists but not ready" state that
   only drop/recreate fixes.
4. Free Edition throttles pipeline provisioning: PROVISIONING_PIPELINE_RESOURCES
   took ~15 min. Managed vector search is convenient but tier-gated; local FAISS
   is the fallback story.
5. Empty-file trap: src/ and tests/ were Length-0 placeholders; pasted code went
   to chat not disk. python imports empty module silently → NameError, no output.
   Always verify Length > 0 after populating a file.
6. Mispaste: test code landed in notebooks/03_test_pipeline.py → git restore.

### Open items (carried forward)
- Retrieval ranking is query-phrasing sensitive — Phase 3 retrieval function
  must build a rich query (description + classification context)
- Migrate to databricks-ai-search package name before Phase 6
- Playbook page-furniture noise ("N of 142") still present
- VERIFY regulatory dates vs EUR-Lex Art. 113 before demo
- Cost/quota: vector index is the resource to tear down between sessions if
  Free Edition quota is hit

### Next: Phase 3 — LLM Synthesis (~4h)
- Pre-work: check AI Gateway page for Claude/LLM endpoint availability
  (GenAI models moved there per Serving-page banner)
- Build retrieval.py (the two-track filtered retrieval function),
  llm_synthesis.py (grounded synthesis, citation-per-requirement, JSON output)
- Gate: schema-valid JSON on 3 runs; every requirement cited; starved-retrieval
  test produces "not addressed in retrieved sources" not invention