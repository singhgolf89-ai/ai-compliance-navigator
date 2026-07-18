# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — End-to-End Pipeline Test (Phase 3 gate)
# MAGIC classify (deterministic) -> retrieve (filtered) -> synthesize (grounded, cited).
# MAGIC Runs the insurance scenario, checks schema-valid JSON x3, and the
# MAGIC starved-retrieval anti-hallucination test.

# COMMAND ----------

# MAGIC %pip install --quiet databricks-vectorsearch
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------

# Make src/ importable. Git folder path — adjust if your workspace user differs.
# Make src/ importable — derive repo root from this notebook's own path
# (no hardcoded user/email; works for anyone who clones the repo).
import sys, os
_nb_path = (dbutils.notebook.entry_point.getDbutils()
            .notebook().getContext().notebookPath().get())
# notebook is at <repo>/notebooks/03_test_pipeline.py → repo root is two levels up
REPO = "/Workspace" + os.path.dirname(os.path.dirname(_nb_path))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
print("Repo root on path:", REPO)

from src.classification_engine import classify_risk_tier, SystemIntake
from src.retrieval import retrieve_compliance_requirements
from src.llm_synthesis import synthesize_compliance_report
import json

# COMMAND ----------

# ── Build the demo scenario: insurance claims triage (must be High-Risk) ──
intake = SystemIntake(
    system_name="Claims Triage Model",
    description="Automated triage of insurance claims, scoring claims for "
                "eligibility and fraud risk assessment",
    domain="insurance",
    ai_type="classification",
    decision_impact="fully_automated",
    data_types=["personal", "financial"],
    intended_purpose="Accelerate insurance claims processing decisions",
    deployment_geography=["EU"],
)

# STEP 1 — deterministic classification
clf = classify_risk_tier(intake)
print(f"Tier:  {clf.risk_tier.value}")
print(f"Basis: {clf.primary_basis}")
print(f"Role:  {clf.applicable_role.value}")
assert clf.risk_tier.value == "high_risk", "Expected high_risk for insurance triage"

# COMMAND ----------

# STEP 2 — filtered retrieval
retrieved = retrieve_compliance_requirements(
    system_description=f"{intake.description}. Purpose: {intake.intended_purpose}",
    risk_tier=clf.risk_tier.value,
)
print(f"EU chunks:   {len(retrieved['eu_ai_act'])}")
print(f"NIST chunks: {len(retrieved['nist_rmf'])}")
assert len(retrieved["eu_ai_act"]) > 0, "No EU chunks retrieved"

# COMMAND ----------

# STEP 3 — grounded synthesis
report = synthesize_compliance_report(
    system_description=f"{intake.system_name}: {intake.description}",
    classification={
        "risk_tier": clf.risk_tier.value,
        "primary_basis": clf.primary_basis,
        "reasoning": clf.reasoning,
    },
    retrieved=retrieved,
)
print(json.dumps(report, indent=2)[:3000])

# COMMAND ----------

# ── GATE 1: schema-valid JSON on 3 consecutive runs ─────────────────────
REQUIRED_KEYS = {"risk_classification", "eu_ai_act_obligations",
                 "nist_rmf_mapping", "cross_framework_checklist"}

def validate(rep: dict) -> tuple:
    if "_parse_error" in rep:
        return False, f"JSON parse failed: {rep['_parse_error']}"
    missing = REQUIRED_KEYS - set(rep.keys())
    if missing:
        return False, f"Missing keys: {missing}"
    return True, "ok"

print("Schema validity across 3 runs:")
all_valid = True
for i in range(3):
    r = synthesize_compliance_report(
        system_description=f"{intake.system_name}: {intake.description}",
        classification={"risk_tier": clf.risk_tier.value,
                        "primary_basis": clf.primary_basis,
                        "reasoning": clf.reasoning},
        retrieved=retrieved,
    )
    ok, msg = validate(r)
    all_valid &= ok
    print(f"  run {i+1}: {'PASS' if ok else 'FAIL — ' + msg}")
print("GATE 1:", "PASS ✓" if all_valid else "FAIL")

# COMMAND ----------

# ── GATE 2: citation coverage — every requirement carries a citation ────
def citation_coverage(rep: dict) -> tuple:
    uncited = []
    for ob in rep.get("eu_ai_act_obligations", []):
        if not ob.get("citation", "").strip():
            uncited.append(f"EU obligation: {ob.get('requirement','?')}")
    for m in rep.get("nist_rmf_mapping", []):
        if not m.get("citation", "").strip():
            uncited.append(f"NIST mapping: {m.get('subcategory','?')}")
    return len(uncited) == 0, uncited

covered, uncited = citation_coverage(report)
print("GATE 2 (citation coverage):", "PASS ✓" if covered else f"FAIL — {uncited}")

# COMMAND ----------

# ── GATE 3: starved-retrieval anti-hallucination test ───────────────────
# Feed EMPTY retrieval. The model must NOT invent articles — it must use the
# "not addressed" behavior or return empty obligation lists.
empty_retrieved = {"eu_ai_act": [], "eu_columns": [],
                   "nist_rmf": [], "nist_columns": []}
starved = synthesize_compliance_report(
    system_description="Some AI system with no retrieved context",
    classification={"risk_tier": "high_risk",
                    "primary_basis": "test", "reasoning": "test"},
    retrieved=empty_retrieved,
)
print(json.dumps(starved, indent=2)[:2000])

# Heuristic check: with no context, obligations should be empty OR contain the
# "not addressed" sentence — NOT fabricated article numbers with real summaries.
obs = starved.get("eu_ai_act_obligations", [])
invented = [o for o in obs
            if o.get("summary") and "not addressed" not in o.get("summary", "").lower()
            and o.get("citation", "").startswith("[EU AI Act Art.")]
print("GATE 3 (no invention on empty retrieval):",
      "PASS ✓" if not invented else f"REVIEW — possible invention: {invented}")