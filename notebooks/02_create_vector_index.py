# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Vector Search Index (Phase 2)
# MAGIC Creates the AI Search endpoint, a Delta Sync index over regulatory_chunks
# MAGIC with managed BGE embeddings, syncs it, and runs the gate retrieval test.
# MAGIC Endpoint is created from code (canonical name) — not by hand — so the
# MAGIC repo is the source of truth.

# COMMAND ----------

# MAGIC %pip install --quiet databricks-vectorsearch
# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------

# ── Config — canonical identifiers ───────────────────────────────────────
CATALOG = "ai_governance"
SCHEMA = "compliance_navigator"
SOURCE_TABLE = f"{CATALOG}.{SCHEMA}.regulatory_chunks"
INDEX_NAME = f"{CATALOG}.{SCHEMA}.regulatory_chunks_index"
ENDPOINT_NAME = "compliance-navigator-endpoint"
EMBEDDING_ENDPOINT = "databricks-bge-large-en"   # verified 1024-dim
EMBEDDING_DIM = 1024
PRIMARY_KEY = "chunk_id"
EMBEDDING_SOURCE_COLUMN = "chunk_text"

# COMMAND ----------

# ── Prerequisite: Delta Sync requires Change Data Feed on the source ────
# raw_documents got CDF at creation; regulatory_chunks did not. Enable it now.
# Without CDF, create_delta_sync_index fails — the index tracks row changes
# via the change feed to sync incrementally.
spark.sql(f"ALTER TABLE {SOURCE_TABLE} SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')")
print("CDF enabled on regulatory_chunks.")

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient
vsc = VectorSearchClient()

# ── Create endpoint (idempotent) ─────────────────────────────────────────
# Free-tier quota is 1 endpoint — this is the one. Standard type: our ~455-row
# corpus is far below Storage-Optimized's billion-row threshold.
existing = [e["name"] for e in vsc.list_endpoints().get("endpoints", [])]
if ENDPOINT_NAME in existing:
    print(f"Endpoint '{ENDPOINT_NAME}' already exists — reusing.")
else:
    print(f"Creating endpoint '{ENDPOINT_NAME}' (a few minutes)...")
    vsc.create_endpoint(name=ENDPOINT_NAME, endpoint_type="STANDARD")

# Block until the endpoint is ONLINE before creating the index
vsc.wait_for_endpoint(name=ENDPOINT_NAME, timeout=1800)
print(f"Endpoint '{ENDPOINT_NAME}' is online.")

# COMMAND ----------

# ── Create Delta Sync index with managed BGE embeddings (idempotent) ────
def index_exists(vsc, endpoint, index_name) -> bool:
    try:
        vsc.get_index(endpoint_name=endpoint, index_name=index_name).describe()
        return True
    except Exception:
        return False

if index_exists(vsc, ENDPOINT_NAME, INDEX_NAME):
    print(f"Index '{INDEX_NAME}' already exists — reusing.")
else:
    print(f"Creating index '{INDEX_NAME}' with managed embeddings...")
    vsc.create_delta_sync_index(
        endpoint_name=ENDPOINT_NAME,
        index_name=INDEX_NAME,
        source_table_name=SOURCE_TABLE,
        pipeline_type="TRIGGERED",              # manual sync for MVP; cheaper than CONTINUOUS
        primary_key=PRIMARY_KEY,
        embedding_source_column=EMBEDDING_SOURCE_COLUMN,
        embedding_model_endpoint_name=EMBEDDING_ENDPOINT,   # Databricks auto-embeds via BGE
    )
    print("Index created.")

# COMMAND ----------

# ── Sync + wait until ready ──────────────────────────────────────────────
idx = vsc.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME)
idx.sync()
print("Sync triggered. Waiting for index to come online (embeds 455 chunks)...")
idx.wait_until_ready(timeout=1800)
print("Index is ready.")

# COMMAND ----------

# ── GATE TEST: 'insurance creditworthiness scoring' must surface high-risk ──
results = idx.similarity_search(
    query_text="insurance creditworthiness scoring for loan and premium decisions",
    columns=["chunk_id", "source", "document_section", "section_title", "risk_tier"],
    num_results=10,
)
rows = results["result"]["data_array"]
print(f"Returned {len(rows)} chunks:\n")
for r in rows:
    # column order matches the `columns` list above
    print(f"  [{r[1]}] {r[2]} | tier={r[4]} | {r[3][:60]}")

# COMMAND ----------

# ── Filtered retrieval test: risk-tier filter must be respected ──────────
# Phase 2 gate: retrieval respects risk-tier filters.
filtered = idx.similarity_search(
    query_text="insurance creditworthiness scoring",
    columns=["document_section", "source", "risk_tier"],
    filters={"source": "eu_ai_act", "risk_tier": ["high_risk", "all"]},
    num_results=10,
)
frows = filtered["result"]["data_array"]
print(f"Filtered (eu_ai_act, high_risk|all): {len(frows)} chunks")
tiers = {r[2] for r in frows}
print(f"Tiers present: {tiers}  (must be subset of {{high_risk, all}})")
assert tiers.issubset({"high_risk", "all"}), f"Filter leaked tiers: {tiers}"
print("Filter respected ✓")