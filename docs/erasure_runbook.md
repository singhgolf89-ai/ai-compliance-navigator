\---



\## Session 8 — v2 Phase 2: Audit Spine — PASSED



\### Completed

\- ENV2-06 gate-keeper: databricks-sql-connector round-trip from laptop —

&#x20; CONNECTED, chunk count 455. One 3-scope token (local-dev-full:

&#x20; sql + model-serving + vector-search; sql scope lives under "BI Tools"

&#x20; in the token dialog).

\- assessment\_log created via idempotent ensure\_table() (CDF on, PK,

&#x20; all\_matches ARRAY, classifier\_version, chunk IDs, corpus\_table\_version,

&#x20; synthesis\_status, latency\_ms).

\- src/audit\_log.py writer: never raises (product > logging); failures

&#x20; logged too. app.py hooks: live-mode logging with ok | parse\_error |

&#x20; fallback status; conditional privacy notice (hidden in demo mode).

\- Verified with row evidence:

&#x20; - S1 live: high\_risk / ok / all\_matches=1 / corpus\_table\_version=5

&#x20;   (id 2a72ab28-...)

&#x20; - Synthetic: minimal\_risk / empty trail by design (id f05eae45-...)

&#x20; - S4 FaceWatch: prohibited (logged under both classifier versions —

&#x20;   see finding 1)

&#x20; - S8 SpamGuard: minimal / ok (id b2aaa2be-...)

\- P2C-03 failure injection: bogus endpoints → yellow fallback banner +

&#x20; row with synthesis\_status='fallback'; restore verified via empty git diff.

\- P2C-05 demo suppression: DEMO\_MODE=true run wrote nothing; counts

&#x20; unchanged; privacy caption correctly hidden.

\- P2V-04 time-travel reproducibility: from the S1 log row alone

&#x20; (version 5, chunk eu\_ai\_act:article\_6:0), VERSION AS OF reproduced the

&#x20; exact Article 6 text the assessment retrieved. Script committed as

&#x20; scripts/reproduce\_assessment.py.

\- Decision D1: st.login DEFERRED — public app is demo mode, nobody to

&#x20; attribute; user\_id="local-dev"; auth ships with the live-public trigger.

\- Final counts at close: ok=5, fallback=1.



\### Findings — both caught by the tool itself (interview gold)

1\. \*\*The corpus caught the classifier.\*\* FaceWatch report's retrieved text

&#x20;  cited Art. 5(1)(h) for real-time RBI exceptions vs the classifier's

&#x20;  5(1)(d) (draft-era numbering from the v1 spec). Corrected the rule,

&#x20;  CLASSIFIER\_VERSION 1.0.0 → 1.0.1, S4 expectation updated, full suite

&#x20;  green. The audit log now holds FaceWatch determinations under BOTH

&#x20;  versions — ruleset-version separation demonstrated in anger.

2\. \*\*The log caught the synthesis.\*\* S8 (minimal-risk) report surfaced

&#x20;  Article 9 (a high-risk obligation). eu\_chunk\_ids in the log showed NO

&#x20;  article\_9 chunk retrieved — tier filter exonerated; the LLM promoted a

&#x20;  cross-reference inside Article 80's text into an obligation entry.

&#x20;  Parked as golden-set case G-min-01 (Phase 4) with candidate prompt fix:

&#x20;  "cite only articles whose own provisions appear in the retrieved

&#x20;  chunks."



\### Release

\- Spine merged to main (b0ff354); docs merge follows this entry.

\- Public smoke (REL2-03/04): pending — demo banner + no logging caption +

&#x20; counts unchanged. Result: \_\_\_



\### Next: v2 Phase 3 — Assessment History + Re-run Diff (\~3h)

\- "Past Assessments" tab from the log; reopen stored reports;

&#x20; re-run against current corpus with tier/obligations diff

