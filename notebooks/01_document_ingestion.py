# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Document Ingestion (Phase 1)
# MAGIC Creates governance objects, loads the regulatory corpus, chunks it
# MAGIC (EU AI Act by article/annex, NIST by subcategory), lands it in Delta.
# MAGIC Run top-to-bottom; pause at the UPLOAD CHECKPOINT.
# git folder sync verified — session 2. 
# COMMAND ----------

# MAGIC %pip install --quiet pypdf pymupdf

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import pymupdf as fitz

# COMMAND ----------

# ── Config — canonical identifiers (single source of truth) ─────────────
CATALOG = "ai_governance"
SCHEMA = "compliance_navigator"
VOLUME = "raw_docs"
VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"

DOC_FILES = {
    "eu_ai_act": "eu_ai_act.pdf",
    "nist_ai_rmf": "nist_ai_rmf.pdf",
    "nist_playbook": "nist_playbook.pdf",  # optional — skipped if absent
}

from datetime import date

# VERIFY before demo: versions/dates below are recorded metadata, not legal fact.
# Check EUR-Lex (Art. 113) for EU dates; NIST publication pages for NIST dates.
SOURCE_META = {
    "eu_ai_act": {
        "name": "EU AI Act — Regulation (EU) 2024/1689",
        "version": "OJ L, 2024/1689, 12.7.2024",
        "effective_date": date(2024, 8, 1),   # entry into force — VERIFY
        "url": "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
    },
    "nist_ai_rmf": {
        "name": "NIST AI RMF 1.0 (NIST AI 100-1)",
        "version": "1.0 (2023-01-26); note: RMF revision in progress",
        "effective_date": date(2023, 1, 26),
        "url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
    },
    "nist_playbook": {
        "name": "NIST AI RMF Playbook",
        "version": "Complete version (2023-03-30) — VERIFY current on AIRC",
        "effective_date": date(2023, 3, 30),
        "url": "https://airc.nist.gov/docs/AI_RMF_Playbook.pdf",
    },
}

# COMMAND ----------

# ── Create governance objects ────────────────────────────────────────────
# On Free Edition you are the workspace admin, so CREATE CATALOG should work.
# If it fails with a permissions error, tell your copilot — fallback is the
# default catalog, changed in ONE place (the CATALOG constant above).
spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"USE CATALOG {CATALOG}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
spark.sql(f"USE SCHEMA {SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {VOLUME}")
print(f"Ready: {CATALOG}.{SCHEMA}, volume at {VOLUME_PATH}")

# COMMAND ----------

# ── Delta tables ─────────────────────────────────────────────────────────
spark.sql("""
CREATE TABLE IF NOT EXISTS raw_documents (
    document_id STRING NOT NULL,
    source STRING,
    document_name STRING,
    version STRING,
    effective_date DATE,
    raw_text STRING,
    pdf_path STRING,
    ingestion_timestamp TIMESTAMP,
    CONSTRAINT raw_documents_pk PRIMARY KEY (document_id)
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')  -- audit trail on the corpus
""")

spark.sql("""
CREATE TABLE IF NOT EXISTS regulatory_chunks (
    chunk_id STRING NOT NULL,
    document_id STRING,
    source STRING,
    document_section STRING,
    section_title STRING,
    chunk_text STRING,
    chunk_index INT,
    risk_tier STRING,
    applicable_role STRING,
    compliance_deadline STRING,
    framework_function STRING,
    category_id STRING,
    subcategory_id STRING,
    source_url STRING,
    token_count INT,
    embedding_model STRING,        -- populated in Phase 2 (managed embeddings)
    created_timestamp TIMESTAMP,
    CONSTRAINT regulatory_chunks_pk PRIMARY KEY (chunk_id)
) USING DELTA
""")
print("Tables created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## ⏸ UPLOAD CHECKPOINT
# MAGIC In the left nav: **Catalog → ai_governance → compliance_navigator →
# MAGIC Volumes → raw_docs → Upload to this volume.**
# MAGIC Upload `eu_ai_act.pdf` and `nist_ai_rmf.pdf` (and `nist_playbook.pdf` if you have it),
# MAGIC named exactly as in `DOC_FILES`. Then run the next cell to confirm.

# COMMAND ----------

display(dbutils.fs.ls(VOLUME_PATH))

# COMMAND ----------

# ── Extraction + cleaning ────────────────────────────────────────────────
import re
import fitz  # PyMuPDF — handles EUR-Lex kerning; pypdf inserted intra-word spaces

NOISE_PATTERNS = [
    r"^\s*EN\s*$",              # EUR-Lex language marker
    r"ELI:\s*http\S+",          # EUR-Lex footer
    r"^\s*OJ\s+L.*\d{4}\s*$",   # OJ header line
    r"^\s*\d+\s*/\s*\d+\s*$",   # "page x/y"
]

def extract_pdf_text(path: str) -> str:
    with fitz.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)

def clean_text(t: str) -> str:
    lines = [
        ln for ln in t.splitlines()
        if not any(re.search(p, ln) for p in NOISE_PATTERNS)
    ]
    out = "\n".join(lines)
    out = re.sub(r"-\n(?=[a-z])", "", out)   # re-join hyphenated line breaks
    out = re.sub(r"\n{3,}", "\n\n", out)
    # normalize any residual kerning splits in the tokens our chunkers key on
    out = re.sub(r"\bA\s?r\s?t\s?i\s?c\s?l\s?e\b", "Article", out)
    out = re.sub(r"\bA\s?N\s?N\s?E\s?X\b", "ANNEX", out)
    return out

# COMMAND ----------

# ── EU AI Act chunker: by article + annex, with applicability metadata ──
CHARS_PER_TOKEN = 4      # sizing heuristic only
EU_MAX_TOKENS = 500      # long articles get paragraph-split with context header

def get_article_applicability(n: int) -> tuple:
    """Article number -> (risk_tier, applicable_role). Mirrors architecture doc."""
    if n == 5:
        return "prohibited", "all"
    if 6 <= n <= 15:
        return "high_risk", "provider"
    if n == 26:
        return "high_risk", "deployer"
    if n == 50:
        return "limited_risk", "all"
    if 51 <= n <= 56:                     # GPAI provisions
        return "all", "provider"
    return "all", "all"

def get_deadline(n: int, tier: str):
    """VERIFY against EUR-Lex Art. 113 before any demo. NOTE: the architecture
    doc listed limited_risk as 2025-08-02; that appears to conflate the GPAI
    date — Art. 50 sits under general application. Confirm at the source."""
    if 51 <= n <= 56:
        return "2025-08-02 (GPAI) [verify]"
    return {
        "prohibited":   "2025-02-02 (in effect) [verify]",
        "high_risk":    "2026-08-02 [verify]",
        "limited_risk": "2026-08-02 [verify]",
    }.get(tier)

ANNEX_APPLICABILITY = {
    "III": ("high_risk", "all"),        # the high-risk use-case list itself
    "IV":  ("high_risk", "provider"),   # technical documentation
}

def _split_paragraphs(block: str, header: str, base: dict) -> list:
    chunks, i = [], 0
    for p in re.split(r"\n\s*\n", block):
        p = p.strip()
        if len(p) < 50:
            continue
        chunks.append({**base, "chunk_text": f"{header}\n\n{p}", "chunk_index": i})
        i += 1
    return chunks

def _find_article_headings(text: str) -> list:
    """Return [(char_offset, article_number), ...] for REAL headings only.
    A heading line starts with 'Article N', is short, isn't a cross-reference
    like 'Article 6(1)', and article numbers must increase monotonically."""
    heads, last_n = [], 0
    for m in re.finditer(r"(?m)^Article\s+(\d{1,3})\b(?!\s*\()", text):
        n = int(m.group(1))
        line_end = text.find("\n", m.start())
        line = text[m.start(): line_end if line_end != -1 else len(text)]
        if len(line) > 80:                     # headings are short; wrapped prose isn't
            continue
        if not (last_n < n <= last_n + 5):     # tolerate a missed heading, reject
            continue                           # out-of-sequence cross-references
        heads.append((m.start(), n))
        last_n = n
    return heads

def chunk_eu_ai_act(text: str) -> list:
    chunks = []
    heads = _find_article_headings(text)
    if not heads:
        raise ValueError("No article headings found — run the diagnostic cell.")

    # peel off annexes: real annex headings are UPPERCASE at line start;
    # in-text references ('Annex III') are title case, so they don't match
    am = re.search(r"(?m)^ANNEX\s+[IVXLC]+\b", text[heads[0][0]:])
    annex_start = heads[0][0] + am.start() if am else len(text)
    annex_region = text[annex_start:]

    # slice article blocks between consecutive validated headings
    bounds = [h[0] for h in heads] + [annex_start]
    for (pos, n), end in zip(heads, bounds[1:]):
        block = text[pos:end].strip()
        first_line, _, rest = block.partition("\n")
        title = re.sub(r"^Article\s+\d{1,3}\s*[:.\-–]?\s*", "", first_line).strip()
        if not title:                          # title was on the next line
            title = rest.lstrip().split("\n", 1)[0].strip()
        tier, role = get_article_applicability(n)
        base = {
            "document_section": f"Article {n}",
            "section_title": title[:200],
            "risk_tier": tier,
            "applicable_role": role,
            "compliance_deadline": get_deadline(n, tier),
        }
        if len(block) / CHARS_PER_TOKEN > EU_MAX_TOKENS:
            chunks += _split_paragraphs(block, f"EU AI Act — Article {n} ({title})", base)
        else:
            chunks.append({**base, "chunk_text": block, "chunk_index": 0})

    for block in re.split(r"(?m)^(?=ANNEX\s+[IVXLC]+\b)", annex_region):
        m = re.match(r"ANNEX\s+([IVXLC]+)", block)
        if not m:
            continue
        numeral = m.group(1)
        tier, role = ANNEX_APPLICABILITY.get(numeral, ("all", "all"))
        base = {
            "document_section": f"Annex {numeral}",
            "section_title": f"Annex {numeral}",
            "risk_tier": tier,
            "applicable_role": role,
            "compliance_deadline": get_deadline(0, tier),
        }
        chunks += _split_paragraphs(block, f"EU AI Act — Annex {numeral}", base)
    return chunks

# COMMAND ----------

# ── NIST chunker: by subcategory (RMF core and Playbook share ID scheme) ─
NIST_SUBCAT = re.compile(r"(GOVERN|MAP|MEASURE|MANAGE)\s+(\d+\.\d+)")
NIST_MAX_TOKENS = 700

def chunk_nist(text: str) -> list:
    """Regex-split grabs ToC lines and inline cross-references too, so we
    keep the LONGEST span per subcategory ID — in practice, the real entry."""
    sections = NIST_SUBCAT.split(text)
    best = {}
    for i in range(1, len(sections) - 2, 3):
        sub_id = f"{sections[i]} {sections[i+1]}"
        content = sections[i + 2].strip()
        if len(content) < 40:
            continue
        if len(content) > len(best.get(sub_id, "")):
            best[sub_id] = content

    chunks = []
    for sub_id, content in sorted(best.items()):
        func = sub_id.split()[0]
        outcome = re.match(r"[:\s]*([^.]+\.)", content)
        base = {
            "document_section": sub_id,
            "section_title": (outcome.group(1).strip()[:200] if outcome else sub_id),
            "framework_function": func,
            "category_id": f"{func} {sub_id.split()[1].split('.')[0]}",
            "subcategory_id": sub_id,
        }
        body = f"{sub_id}\n\n{content}"
        if len(body) / CHARS_PER_TOKEN > NIST_MAX_TOKENS:
            chunks += _split_paragraphs(content, sub_id, base)
        else:
            chunks.append({**base, "chunk_text": body, "chunk_index": 0})
    return chunks

# COMMAND ----------

# ── Run ingestion ────────────────────────────────────────────────────────
import os
from datetime import datetime

now = datetime.now()
raw_rows, chunk_rows = [], []

for source, fname in DOC_FILES.items():
    fpath = f"{VOLUME_PATH}/{fname}"
    if not os.path.exists(fpath):
        print(f"SKIPPED (not uploaded): {source} — {fpath}")
        continue

    text = clean_text(extract_pdf_text(fpath))
    meta = SOURCE_META[source]
    doc_id = f"doc_{source}"
    raw_rows.append((doc_id, source, meta["name"], meta["version"],
                     meta["effective_date"], text, fpath, now))

    parsed = chunk_eu_ai_act(text) if source == "eu_ai_act" else chunk_nist(text)
    for c in parsed:
        section_slug = c["document_section"].lower().replace(" ", "_").replace(".", "_")
        chunk_rows.append({
            # deterministic ID -> idempotent reloads, stable citation keys
            "chunk_id": f"{source}:{section_slug}:{c['chunk_index']}",
            "document_id": doc_id,
            "source": source,
            "document_section": c["document_section"],
            "section_title": c.get("section_title"),
            "chunk_text": c["chunk_text"][:8000],
            "chunk_index": c["chunk_index"],
            "risk_tier": c.get("risk_tier"),
            "applicable_role": c.get("applicable_role"),
            "compliance_deadline": c.get("compliance_deadline"),
            "framework_function": c.get("framework_function"),
            "category_id": c.get("category_id"),
            "subcategory_id": c.get("subcategory_id"),
            "source_url": meta["url"],
            "token_count": int(len(c["chunk_text"]) / CHARS_PER_TOKEN),
            "embedding_model": None,
            "created_timestamp": now,
        })
    print(f"Chunked {source}: {sum(1 for r in chunk_rows if r['source'] == source)} chunks")

# COMMAND ----------

text = clean_text(extract_pdf_text(f"{VOLUME_PATH}/eu_ai_act.pdf"))
i = text.find("Article 1")
print("first 'Article 1' at char:", i, "of", len(text))
print(repr(text[max(0, i-300): i+300]))

# COMMAND ----------

import re
hits = [m.group(0) for m in re.finditer(r"(?m)^.{0,60}Article\s+\d{1,3}.{0,20}", text)][:15]
print("\n".join(hits) if hits else "no line-start Article hits")
print("---")
print("total 'Article' occurrences:", len(re.findall(r"Article\s+\d", text)))

# COMMAND ----------

# ── Write to Delta (truncate + reload; Delta versioning keeps history) ──
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                               TimestampType, DateType)

RAW_SCHEMA = StructType([
    StructField("document_id", StringType(), False),
    StructField("source", StringType(), True),
    StructField("document_name", StringType(), True),
    StructField("version", StringType(), True),
    StructField("effective_date", DateType(), True),
    StructField("raw_text", StringType(), True),
    StructField("pdf_path", StringType(), True),
    StructField("ingestion_timestamp", TimestampType(), True),
])

CHUNK_SCHEMA = StructType([
    StructField("chunk_id", StringType(), False),
    StructField("document_id", StringType(), True),
    StructField("source", StringType(), True),
    StructField("document_section", StringType(), True),
    StructField("section_title", StringType(), True),
    StructField("chunk_text", StringType(), True),
    StructField("chunk_index", IntegerType(), True),
    StructField("risk_tier", StringType(), True),
    StructField("applicable_role", StringType(), True),
    StructField("compliance_deadline", StringType(), True),
    StructField("framework_function", StringType(), True),
    StructField("category_id", StringType(), True),
    StructField("subcategory_id", StringType(), True),
    StructField("source_url", StringType(), True),
    StructField("token_count", IntegerType(), True),
    StructField("embedding_model", StringType(), True),
    StructField("created_timestamp", TimestampType(), True),
])

spark.sql(f"TRUNCATE TABLE {CATALOG}.{SCHEMA}.raw_documents")
spark.sql(f"TRUNCATE TABLE {CATALOG}.{SCHEMA}.regulatory_chunks")

spark.createDataFrame(raw_rows, schema=RAW_SCHEMA) \
    .write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.raw_documents")
spark.createDataFrame([tuple(r[f.name] for f in CHUNK_SCHEMA.fields) for r in chunk_rows],
                      schema=CHUNK_SCHEMA) \
    .write.mode("append").saveAsTable(f"{CATALOG}.{SCHEMA}.regulatory_chunks")

print(f"Loaded {len(raw_rows)} documents, {len(chunk_rows)} chunks.")

# COMMAND ----------

# ── VERIFY 1: counts (record these — Phase 1 DoD item) ──────────────────
display(spark.sql(f"""
SELECT source,
       COUNT(*) AS chunks,
       COUNT(DISTINCT document_section) AS sections,
       SUM(token_count) AS approx_tokens
FROM {CATALOG}.{SCHEMA}.regulatory_chunks
GROUP BY source ORDER BY source
"""))

# COMMAND ----------

# ── VERIFY 2: EU spot-checks — Article 5, Article 9, Annex III ──────────
display(spark.sql(f"""
SELECT document_section, chunk_index, section_title, risk_tier,
       applicable_role, compliance_deadline, LEFT(chunk_text, 300) AS preview
FROM {CATALOG}.{SCHEMA}.regulatory_chunks
WHERE source = 'eu_ai_act'
  AND document_section IN ('Article 5', 'Article 9', 'Annex III')
ORDER BY document_section, chunk_index
"""))

# COMMAND ----------

# ── VERIFY 3: NIST spot-checks — one GOVERN, one MANAGE ─────────────────
display(spark.sql(f"""
SELECT source, subcategory_id, framework_function, section_title,
       LEFT(chunk_text, 300) AS preview
FROM {CATALOG}.{SCHEMA}.regulatory_chunks
WHERE subcategory_id IN ('GOVERN 1.1', 'MANAGE 1.1')
ORDER BY source, subcategory_id
"""))

# COMMAND ----------

