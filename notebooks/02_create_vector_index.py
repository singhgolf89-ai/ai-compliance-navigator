# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Vector Search Index (Phase 2, hardened Phase 4)
# MAGIC Creates the AI Search endpoint and a Delta Sync index over
# MAGIC `regulatory_chunks` with managed BGE embeddings, syncs it, verifies it,
# MAGIC and runs the retrieval gate tests.
# MAGIC
# MAGIC **Reclamation-aware:** Databricks Free Edition reclaims idle AI Search
# MAGIC endpoints (observed twice: ~6 weeks and ~2 weeks idle). Reclamation can
# MAGIC leave an orphaned Unity Catalog index registration with no serving
# MAGIC backend — and the orphan is not reliably visible to `get_index()`,
# MAGIC which is endpoint-scoped. This notebook therefore treats **creation as
# MAGIC the probe**: attempt create; on a name collision, delete the UC entity
# MAGIC and retry until the name frees. Safe to run top-to-bottom at any time:
# MAGIC healthy resources are reused, missing ones are rebuilt.

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

# ── Prerequisite: Delta Sync requires Change Data Feed on the source ─────
# Idempotent; CDF is also the corpus audit trail.
spark.sql(f"ALTER TABLE {SOURCE_TABLE} SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')")
print("CDF enabled on regulatory_chunks.")

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient
vsc = VectorSearchClient()

# ── Create endpoint (idempotent; rebuilt after reclamation) ──────────────
# Free-tier quota is 1 endpoint — this is the one. STANDARD type: 455 rows
# is far below Storage-Optimized territory.
existing = [e["name"] for e in vsc.list_endpoints().get("endpoints", [])]
if ENDPOINT_NAME in existing:
    print(f"Endpoint '{ENDPOINT_NAME}' already exists — reusing.")
else:
    print(f"Creating endpoint '{ENDPOINT_NAME}' (a few minutes)...")
    vsc.create_endpoint(name=ENDPOINT_NAME, endpoint_type="STANDARD")

vsc.wait_for_endpoint(name=ENDPOINT_NAME, timeout=1800)
print(f"Endpoint '{ENDPOINT_NAME}' is online.")

# COMMAND ----------

# ── Create Delta Sync index — collision-driven, final design ─────────────
# Lesson from two reclamation incidents: get_index() is ENDPOINT-scoped, so
# no probe reliably sees an orphaned UC registration. Only UC's answer gates
# creation — so creation IS the probe:
#   healthy fast-path: index serving on this endpoint -> reuse
#   otherwise: try create; on name collision, delete the UC entity and
#   retry until the name frees (deletion is async — returns on ACCEPTANCE).
import time

def _is_serving(vsc, endpoint, index_name) -> bool:
    """True only if BOTH authorities agree: describe() works AND the endpoint
    lists the index. Never tear down a live index on notebook re-run."""
    try:
        vsc.get_index(endpoint_name=endpoint, index_name=index_name).describe()
        names = [i.get("name") for i in
                 vsc.list_indexes(name=endpoint).get("vector_indexes", [])]
        return index_name in names
    except Exception:
        return False

def _create(vsc):
    vsc.create_delta_sync_index(
        endpoint_name=ENDPOINT_NAME,
        index_name=INDEX_NAME,
        source_table_name=SOURCE_TABLE,
        pipeline_type="TRIGGERED",              # manual sync; cheaper than CONTINUOUS
        primary_key=PRIMARY_KEY,
        embedding_source_column=EMBEDDING_SOURCE_COLUMN,
        embedding_model_endpoint_name=EMBEDDING_ENDPOINT,   # managed BGE embeddings
    )

if _is_serving(vsc, ENDPOINT_NAME, INDEX_NAME):
    print(f"Index '{INDEX_NAME}' already serving — reusing.")
else:
    print(f"Ensuring index '{INDEX_NAME}' (create; clean up collisions)...")
    deleted_once = False
    for attempt in range(31):                       # up to ~5 min of retries
        try:
            _create(vsc)
            print("Index created.")
            break
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "pending deletion" in msg:
                if not deleted_once:
                    print("  Name held in UC (orphan or teardown) — requesting deletion...")
                    try:
                        vsc.delete_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME)
                    except Exception as de:
                        print(f"  delete_index: {de}")   # mid-teardown is fine
                    deleted_once = True
                print(f"  [{attempt}] name not free yet — waiting 10s...")
                time.sleep(10)
            else:
                raise                                # a real error — surface it
    else:
        raise TimeoutError("Index name not free after ~5 min — investigate manually.")

# COMMAND ----------

# ── Wait for provisioning, then sync, then poll to READY ─────────────────
# A fresh Delta Sync index must finish PROVISIONING before sync() is legal,
# and wait_until_ready's signature has drifted across SDK versions —
# so we poll describe() manually for both waits. All control-plane
# transitions on this platform are async: poll, never assume.

def _detailed_state(vsc):
    d = vsc.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME).describe()
    return str(d.get("status", {}).get("detailed_state", "UNKNOWN")).upper(), d

# Phase 1: wait until the index will accept a sync (provisioning done)
print("Waiting for index provisioning...")
for i in range(90):                                  # up to ~30 min
    state, desc = _detailed_state(vsc)
    print(f"  [{i}] {state}")
    if "PROVISION" not in state:
        break
    time.sleep(20)

# Phase 2: trigger the sync (a first build often starts one automatically)
try:
    vsc.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME).sync()
    print("Sync triggered.")
except Exception as e:
    print(f"Sync trigger: {e}  (fine if a first sync is already in flight)")

# Phase 3: poll to READY/ONLINE
print("Waiting for index to come online (embedding 455 chunks)...")
for i in range(90):                                  # up to ~30 min
    state, desc = _detailed_state(vsc)
    print(f"  [{i}] {state}")
    if "ONLINE" in state or "READY" in state:
        rc = desc.get("status", {}).get("indexed_row_count", "?")
        print(f"Index is READY — indexed rows: {rc}")
        break
    if "FAIL" in state or "ERROR" in state:
        raise RuntimeError(f"Index entered failure state: {state} — investigate.")
    time.sleep(20)
else:
    raise TimeoutError("Index not ready after ~30 min — investigate manually.")

# COMMAND ----------

# ── Verify: final state + row count (ENV evidence line) ──────────────────
d = vsc.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME).describe()
print("state:", d.get("status", {}).get("detailed_state"),
      "| indexed rows:", d.get("status", {}).get("indexed_row_count"))

# COMMAND ----------

# ── GATE TEST: 'insurance creditworthiness scoring' retrieval ────────────
idx = vsc.get_index(endpoint_name=ENDPOINT_NAME, index_name=INDEX_NAME)
results = idx.similarity_search(
    query_text="insurance creditworthiness scoring for loan and premium decisions",
    columns=["chunk_id", "source", "document_section", "section_title", "risk_tier"],
    num_results=10,
)
rows = results["result"]["data_array"]
print(f"Returned {len(rows)} chunks:\n")
for r in rows:
    print(f"  [{r[1]}] {r[2]} | tier={r[4]} | {str(r[3])[:60]}")

# COMMAND ----------

# ── GATE TEST: risk-tier filter integrity ────────────────────────────────
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