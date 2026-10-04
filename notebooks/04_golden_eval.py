# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Golden-Set Retrieval Evaluation (Phase 4)
# MAGIC Scores retrieval against the FROZEN golden set (tests/golden_set.json,
# MAGIC freeze commit ab3f361) and logs a baseline to MLflow.
# MAGIC
# MAGIC **Eval-honesty rules enforced here:**
# MAGIC - The golden set is read-only input. Nothing in this notebook writes it.
# MAGIC - Metric definitions live in code comments next to their functions —
# MAGIC   no silent redefinition to flatter a number.
# MAGIC - Every reported number traces to the MLflow run this notebook logs.

# COMMAND ----------

# MAGIC %pip install databricks-vectorsearch

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# ── Config + imports ─────────────────────────────────────────────────────
import sys, json, re, time

user = spark.sql("SELECT current_user()").first()[0]
REPO = f"/Workspace/Users/{user}/ai-compliance-navigator"
sys.path.append(REPO)

from src.classification_engine import classify_risk_tier, SystemIntake
from src.retrieval import retrieve_compliance_requirements
from src.llm_synthesis import synthesize_compliance_report
from src.utils import (CLASSIFIER_VERSION, EMBEDDING_ENDPOINT, LLM_ENDPOINT,
                       VS_INDEX, LLM_TEMPERATURE)

GOLDEN_PATH = f"{REPO}/tests/golden_set.json"
FREEZE_COMMIT = "ab3f361"          # provable from git history: precedes this run
QUERY_TEMPLATE_VERSION = "v1-app-parity"   # query built exactly as app.py builds it
# QUERY_TEMPLATE_VERSION = "v2-nist-governance-framing"   # P4E: tried, regressed 0.2308->0.1923, reverted

with open(GOLDEN_PATH) as f:
    GOLDEN = json.load(f)
print(f"Golden set loaded: {len(GOLDEN)} entries (freeze {FREEZE_COMMIT})")

# COMMAND ----------

# ── Metric definitions (P4C-02 — honest, in code, next to the math) ──────
#
# hit_rate@k (per track, per entry):
#     |expected sections that appear anywhere in the top-k retrieved| / |expected|
#   - "appear" = the chunk_id's SECTION SLUG equals the expected slug.
#     chunk_id format: "<source>:<section_slug>:<chunk_index>"
#     e.g. "eu_ai_act:article_6:1" -> slug "article_6".
#   - k is NOT chosen by this notebook; it is whatever the app's retrieval
#     returns (observed and logged as a param). Scoring at observed-k means
#     we measure the system as the product actually runs it.
#   - Aggregate = mean of per-entry hit rates (macro average: every system
#     counts equally, so 13 small exams, not one pooled one).
#
# citation_coverage (per entry, synthesis stage):
#     |report items with a non-empty 'citation' field| / |report items|
#   where report items = eu_ai_act_obligations + nist_rmf_mapping entries.
#   Computed only over entries whose synthesis returned schema-valid JSON
#   (status 'ok'); the count of ok entries is logged alongside.
#
# must_not_include violations (per entry, synthesis stage — the G-min-01 check):
#     an entry violates if any BANNED article number appears as an
#     obligation's article in the synthesized report. Matching is by
#     article NUMBER token ("Article 9" == "article 9(1)" != "Article 90"),
#     so cross-references inside quoted text don't false-positive, and
#     numbering variants don't false-negative.

def _slug(chunk_id: str) -> str:
    parts = str(chunk_id).split(":")
    return parts[1] if len(parts) >= 2 else str(chunk_id)

def _slugify_nist(subcat: str) -> str:
    # "GOVERN 1.1" -> "govern_1_1" (mirrors the ingestion slug rule)
    return subcat.lower().replace(" ", "_").replace(".", "_")

def _article_num(s: str):
    m = re.match(r"\s*article\s+(\d+[a-z]?)", str(s).lower())
    return m.group(1) if m else None

def hit_rate(expected_slugs, retrieved_chunk_ids):
    if not expected_slugs:
        return None                    # nothing expected -> metric undefined, not 100%
    got = {_slug(c) for c in retrieved_chunk_ids}
    hits = [e for e in expected_slugs if e in got]
    return len(hits) / len(expected_slugs), hits

# COMMAND ----------

# ── Run: retrieval + synthesis per golden entry ──────────────────────────
results = []
t_start = time.time()

for e in GOLDEN:
    intake = SystemIntake(**e["intake"])
    clf = classify_risk_tier(intake)

    # Retrieval — query built with app parity (description + purpose, tier filter)
    retrieved = retrieve_compliance_requirements(
        system_description=f"{intake.description}. Purpose: {intake.intended_purpose}",
        risk_tier=clf.risk_tier.value)

    eu_ids = [r[retrieved["eu_columns"].index("chunk_id")] for r in retrieved["eu_ai_act"]]
    nist_ids = [r[retrieved["nist_columns"].index("chunk_id")] for r in retrieved["nist_rmf"]]

    eu_hr = hit_rate(e["expected_eu_sections"], eu_ids)
    nist_hr = hit_rate([_slugify_nist(s) for s in e["expected_nist_subcats"]], nist_ids)

    # Synthesis — for citation coverage + must_not_include (G-min-01)
    status, report = "fallback", {}
    try:
        report = synthesize_compliance_report(
            system_description=f"{intake.system_name}: {intake.description}",
            classification={"risk_tier": clf.risk_tier.value,
                            "primary_basis": clf.primary_basis,
                            "reasoning": clf.reasoning},
            retrieved=retrieved)
        status = "parse_error" if "_parse_error" in report else "ok"
    except Exception as ex:
        report = {"_error": str(ex)[:300]}

    cited = total = 0
    violations = []
    if status == "ok":
        items = (report.get("eu_ai_act_obligations", []) +
                 report.get("nist_rmf_mapping", []))
        total = len(items)
        cited = sum(1 for it in items if str(it.get("citation", "")).strip())
        banned_nums = {_article_num(b) for b in e.get("must_not_include_in_report", [])}
        banned_nums.discard(None)
        for ob in report.get("eu_ai_act_obligations", []):
            n = _article_num(ob.get("article", ""))
            if n and n in banned_nums:
                violations.append(ob.get("article"))

    results.append({
        "id": e["id"], "name": e["name"], "tier": clf.risk_tier.value,
        "eu_hit_rate": None if eu_hr is None else eu_hr[0],
        "eu_hits": None if eu_hr is None else eu_hr[1],
        "eu_expected": e["expected_eu_sections"], "eu_k": len(eu_ids),
        "nist_hit_rate": None if nist_hr is None else nist_hr[0],
        "nist_hits": None if nist_hr is None else nist_hr[1],
        "nist_expected": e["expected_nist_subcats"], "nist_k": len(nist_ids),
        "synthesis_status": status,
        "citation_coverage": (cited / total) if total else None,
        "cited": cited, "total_items": total,
        "must_not_violations": violations,
    })
    hr_txt = lambda v: "n/a" if v is None else f"{v[0]:.2f}"
    print(f"{e['id']} {clf.risk_tier.value:13} eu={hr_txt(eu_hr)} nist={hr_txt(nist_hr)} "
          f"synth={status} cited={cited}/{total} viol={violations or '-'}")

print(f"\nDone in {time.time()-t_start:.0f}s")

# COMMAND ----------

# ── Aggregate ────────────────────────────────────────────────────────────
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None

eu_rates = [r["eu_hit_rate"] for r in results]
nist_rates = [r["nist_hit_rate"] for r in results]
cov_rates = [r["citation_coverage"] for r in results]

agg = {
    "eu_hit_rate_mean": _mean(eu_rates),
    "nist_hit_rate_mean": _mean(nist_rates),
    "citation_coverage_mean": _mean(cov_rates),
    "n_entries": len(results),
    "n_synthesis_ok": sum(1 for r in results if r["synthesis_status"] == "ok"),
    "n_must_not_violations": sum(len(r["must_not_violations"]) for r in results),
    "entries_with_violations": [r["id"] for r in results if r["must_not_violations"]],
}
print(json.dumps(agg, indent=2))
print("\nG-min-01 (G-04 SpamGuard) violation:",
      next((r["must_not_violations"] for r in results if r["id"] == "G-04"), "entry missing"))

# COMMAND ----------

# ── Log the run to MLflow (P4D) ──────────────────────────────────────────
import mlflow

mlflow.set_experiment(f"/Users/{user}/acn_golden_eval")
with mlflow.start_run(run_name="baseline-v1") as run:
    mlflow.log_params({
        "run_kind": "baseline",
        "query_template_version": QUERY_TEMPLATE_VERSION,
        "golden_set_size": len(GOLDEN),
        "golden_set_freeze_commit": FREEZE_COMMIT,
        "classifier_version": CLASSIFIER_VERSION,
        "embedding_endpoint": EMBEDDING_ENDPOINT,
        "vs_index": VS_INDEX,
        "llm_endpoint": LLM_ENDPOINT,
        "llm_temperature": LLM_TEMPERATURE,
        "observed_k_eu": results[0]["eu_k"],
        "observed_k_nist": results[0]["nist_k"],
    })
    mlflow.log_metrics({
        "eu_hit_rate": agg["eu_hit_rate_mean"],
        "nist_hit_rate": agg["nist_hit_rate_mean"],
        "citation_coverage": agg["citation_coverage_mean"],
        "must_not_violations": agg["n_must_not_violations"],
        "n_synthesis_ok": agg["n_synthesis_ok"],
    })
    mlflow.log_dict({"aggregate": agg, "per_entry": results}, "per_entry_results.json")
    print("BASELINE RUN ID:", run.info.run_id)

# COMMAND ----------

# ── Fetch per-entry detail for any run ───────────────────────────────────
import mlflow, json
RUN_ID = "5fdecb73715042edaf3fbcbf90c5232f"   # paste a run ID here to inspect it
if RUN_ID:
    p = mlflow.artifacts.download_artifacts(run_id=RUN_ID, artifact_path="per_entry_results.json")
    per = json.load(open(p))["per_entry"]
    for r in per:
        print(f"{r['id']} {r['tier']:13} eu={r['eu_hit_rate']} hits={r['eu_hits']} "
              f"| nist={r['nist_hit_rate']} k={r['nist_k']} | viol={r['must_not_violations'] or '-'}")

# COMMAND ----------

