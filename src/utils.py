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
    """
    MLflow deployments client that works in BOTH environments:
    - Inside a Databricks notebook: implicit auth (no config needed).
    - Locally (Streamlit): reads host + token from st.secrets, sets the env
      vars mlflow expects, then connects.
    """
    import os
    import mlflow.deployments

    # If not already authenticated (i.e. running locally), pull from st.secrets.
    if not os.environ.get("DATABRICKS_HOST"):
        try:
            import streamlit as st
            os.environ["DATABRICKS_HOST"] = st.secrets["databricks"]["host"]
            os.environ["DATABRICKS_TOKEN"] = st.secrets["databricks"]["token"]
        except Exception:
            # No streamlit / no secrets -> assume we're inside Databricks
            pass

    return mlflow.deployments.get_deploy_client("databricks")


def get_vector_search_client():
    """
    VectorSearchClient that works locally and in-notebook. Locally it needs
    explicit host + token; in-notebook it authenticates implicitly.
    """
    import os
    from databricks.vector_search.client import VectorSearchClient

    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    if not host:
        try:
            import streamlit as st
            host = st.secrets["databricks"]["host"]
            token = st.secrets["databricks"]["token"]
            os.environ["DATABRICKS_HOST"] = host
            os.environ["DATABRICKS_TOKEN"] = token
        except Exception:
            pass

    if host and token:
        return VectorSearchClient(workspace_url=host, personal_access_token=token)
    return VectorSearchClient()   # in-notebook: implicit auth