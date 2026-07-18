"""
Central configuration + shared helpers for the AI Compliance Navigator.
All catalog names, endpoint names, and model identifiers live here — one
place to change them. Canonical identifiers must match the notebooks.

VERIFY at build time (they drift): endpoint names via the Serving/Playground
UI; regulatory dates via EUR-Lex (Reg. (EU) 2024/1689, Art. 113).
"""

# ── Databricks catalog / schema ──────────────────────────────────────────
CATALOG = "ai_governance"
SCHEMA = "compliance_navigator"

# ── Vector Search (AI Search) ────────────────────────────────────────────
VS_ENDPOINT = "compliance-navigator-endpoint"
VS_INDEX = f"{CATALOG}.{SCHEMA}.regulatory_chunks_index"

# ── Model endpoints (all Databricks-hosted; verified reachable) ──────────
EMBEDDING_ENDPOINT = "databricks-bge-large-en"           # 1024-dim, used by the index
# Free Edition exposes no pay-per-token Claude; using Databricks-hosted OSS.
# One-line swap to "databricks-claude-sonnet-4-5" on an entitled workspace.
LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
LLM_FALLBACK = "databricks-meta-llama-3-1-8b-instruct"   # if 70B is rate-limited

# ── Synthesis params ─────────────────────────────────────────────────────
LLM_MAX_TOKENS = 4000
LLM_TEMPERATURE = 0.1   # low for consistent, reproducible structured output


def get_deploy_client():
    """Databricks MLflow deployments client — the single call site."""
    import mlflow.deployments
    return mlflow.deployments.get_deploy_client("databricks")