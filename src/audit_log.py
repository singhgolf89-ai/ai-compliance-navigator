"""
Assessment audit log writer — the v2 audit spine.

Every live-mode assessment is recorded with its full rule trail
(all_matches), the classifier ruleset version, retrieved chunk IDs, and
the Delta version of regulatory_chunks at assessment time — making any
determination reproducible via time travel:

    SELECT chunk_text FROM ...regulatory_chunks VERSION AS OF <v>
    WHERE chunk_id = '<id from the log>'

Design decisions (phase-gate documented):
- Failures are logged too (synthesis_status: ok | parse_error | fallback).
- Demo mode writes nothing — the log lives where the governed backend lives.
- user_id is pseudonymous ("local-dev" until auth ships); raw email never
  enters the log.
- Logging never breaks the product: log_assessment swallows its own errors.
  (A regulated production system might invert this — write-before-serve;
  deliberate MVP choice, worth naming in interviews.)
"""

import json
import uuid

from src.utils import (CATALOG, SCHEMA, CLASSIFIER_VERSION, APP_VERSION,
                       EMBEDDING_ENDPOINT, LLM_ENDPOINT, LLM_TEMPERATURE,
                       get_sql_connection)

TABLE = f"{CATALOG}.{SCHEMA}.assessment_log"
_ensured = False

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    assessment_id        STRING NOT NULL,
    created_at           TIMESTAMP,
    user_id              STRING,
    session_id           STRING,
    app_version          STRING,
    demo_mode            BOOLEAN,
    intake               STRING,
    system_name          STRING,
    domain               STRING,
    risk_tier            STRING,
    primary_basis        STRING,
    applicable_role      STRING,
    compliance_deadline  STRING,
    confidence           STRING,
    all_matches          ARRAY<STRING>,
    classifier_version   STRING,
    retrieval_query      STRING,
    eu_chunk_ids         ARRAY<STRING>,
    nist_chunk_ids       ARRAY<STRING>,
    corpus_table_version BIGINT,
    embedding_endpoint   STRING,
    llm_endpoint         STRING,
    llm_temperature      DOUBLE,
    report               STRING,
    synthesis_status     STRING,
    latency_ms           BIGINT,
    CONSTRAINT assessment_log_pk PRIMARY KEY (assessment_id)
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
"""


def _sq(s):
    """Escape single quotes for the few inlined literals (array elements)."""
    return str(s).replace("'", "''")


def _arr(items):
    if not items:
        return "array()"
    return "array(" + ", ".join(f"'{_sq(i)}'" for i in items) + ")"


def ensure_table(cursor):
    global _ensured
    if not _ensured:
        cursor.execute(DDL)
        _ensured = True


def _corpus_version(cursor) -> int:
    cursor.execute(f"DESCRIBE HISTORY {CATALOG}.{SCHEMA}.regulatory_chunks LIMIT 1")
    row = cursor.fetchone()
    cols = [d[0] for d in cursor.description]
    return int(row[cols.index("version")])


def _chunk_ids(rows, columns):
    if not rows or "chunk_id" not in columns:
        return []
    i = columns.index("chunk_id")
    return [r[i] for r in rows]


def log_assessment(intake, clf, retrieved, report,
                   synthesis_status, latency_ms,
                   user_id="local-dev", session_id=None):
    """Write one audit row. Returns assessment_id, or None on logging failure.
    Never raises — the product must not break because the log did."""
    assessment_id = str(uuid.uuid4())
    try:
        conn = get_sql_connection()
        cur = conn.cursor()
        ensure_table(cur)

        eu_ids = _chunk_ids((retrieved or {}).get("eu_ai_act", []),
                            (retrieved or {}).get("eu_columns", []))
        nist_ids = _chunk_ids((retrieved or {}).get("nist_rmf", []),
                              (retrieved or {}).get("nist_columns", []))
        corpus_v = _corpus_version(cur)

        params = {
            "assessment_id": assessment_id,
            "user_id": user_id,
            "session_id": session_id or "n/a",
            "app_version": APP_VERSION,
            "intake": json.dumps(intake.__dict__),
            "system_name": intake.system_name,
            "domain": intake.domain,
            "risk_tier": clf.risk_tier.value,
            "primary_basis": clf.primary_basis,
            "applicable_role": clf.applicable_role.value,
            "compliance_deadline": clf.compliance_deadline,
            "confidence": clf.confidence,
            "classifier_version": CLASSIFIER_VERSION,
            "retrieval_query": (retrieved or {}).get("query", ""),
            "embedding_endpoint": EMBEDDING_ENDPOINT,
            "llm_endpoint": LLM_ENDPOINT,
            "llm_temperature": float(LLM_TEMPERATURE),
            "report": json.dumps(report or {}),
            "synthesis_status": synthesis_status,
            "latency_ms": int(latency_ms),
        }

        cur.execute(f"""
            INSERT INTO {TABLE} VALUES (
                :assessment_id, current_timestamp(), :user_id, :session_id,
                :app_version, false,
                :intake, :system_name, :domain,
                :risk_tier, :primary_basis, :applicable_role,
                :compliance_deadline, :confidence,
                {_arr(clf.all_matches)}, :classifier_version,
                :retrieval_query, {_arr(eu_ids)}, {_arr(nist_ids)},
                {corpus_v}, :embedding_endpoint,
                :llm_endpoint, :llm_temperature, :report,
                :synthesis_status, :latency_ms
            )""", params)
        cur.close()
        conn.close()
        return assessment_id
    except Exception as e:
        print(f"[audit_log] write failed (app unaffected): {e}")
        return None

# ── Read path + diff (v2 Phase 3: assessment history) ────────────────────

def list_assessments(user_id="local-dev", limit=50):
    """Light listing for the history tab — no report payloads."""
    conn = get_sql_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT assessment_id, created_at, system_name, domain, risk_tier,
                   primary_basis, classifier_version, corpus_table_version,
                   synthesis_status
            FROM {TABLE}
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT {int(limit)}
        """, {"user_id": user_id})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


def get_assessment(assessment_id):
    """Full row (intake + report JSON) for reopening a stored assessment."""
    conn = get_sql_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {TABLE} WHERE assessment_id = :aid",
                    {"aid": assessment_id})
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))
    finally:
        cur.close()
        conn.close()


def current_corpus_version():
    conn = get_sql_connection()
    cur = conn.cursor()
    try:
        return _corpus_version(cur)
    finally:
        cur.close()
        conn.close()


def _articles(report):
    return {str(ob.get("article", "")).strip()
            for ob in (report or {}).get("eu_ai_act_obligations", [])
            if ob.get("article")}


def _subcats(report):
    return {str(m.get("subcategory", "")).strip()
            for m in (report or {}).get("nist_rmf_mapping", [])
            if m.get("subcategory")}


def diff_assessments(old_row, old_report, new_clf, new_report,
                     new_classifier_version, new_corpus_version):
    """Stored vs fresh. Tier/basis/versions are deterministic signals;
    obligation-level deltas can also reflect synthesis variability."""
    old_arts, new_arts = _articles(old_report), _articles(new_report)
    old_sub, new_sub = _subcats(old_report), _subcats(new_report)
    return {
        "tier_old": old_row["risk_tier"],
        "tier_new": new_clf.risk_tier.value,
        "tier_changed": old_row["risk_tier"] != new_clf.risk_tier.value,
        "basis_old": old_row["primary_basis"],
        "basis_new": new_clf.primary_basis,
        "basis_changed": old_row["primary_basis"] != new_clf.primary_basis,
        "classifier_old": old_row["classifier_version"],
        "classifier_new": new_classifier_version,
        "corpus_old": old_row["corpus_table_version"],
        "corpus_new": new_corpus_version,
        "eu_added": sorted(new_arts - old_arts),
        "eu_removed": sorted(old_arts - new_arts),
        "nist_added": sorted(new_sub - old_sub),
        "nist_removed": sorted(old_sub - new_sub),
    }