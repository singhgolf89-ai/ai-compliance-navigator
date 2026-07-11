# AI Compliance Navigator — Databricks MVP Architecture

## A RAG-powered regulatory mapping tool for EU AI Act and NIST AI RMF

**Built by:** Aryaveer Singh
**Stack:** Databricks Lakehouse + Unity Catalog + Vector Search + Foundation Model APIs + Streamlit
**Status:** Portfolio project (MVP)
---

## Executive Summary

This document provides a Databricks-native architecture for the AI Compliance Navigator MVP. It prioritizes features for maximum demo impact within a constrained timeline and leverages Databricks' unified platform to minimize integration complexity while creating a compelling enterprise-grade story.

---

## MVP Feature Prioritization Analysis

### Feature Stack Ranking

Based on timeline constraints (21 total hours), demo impact, and AIGP exam synergy, here's the recommended prioritization:

| Priority | Feature | Hours | Rationale |
|----------|---------|-------|-----------|
| **P0** | EU AI Act Risk Classification Engine | 3 | Core differentiator — deterministic, auditable. Most demo impact. |
| **P0** | Document Ingestion Pipeline | 4 | Foundation for everything. Forces deep reading for AIGP. |
| **P0** | RAG Retrieval (EU AI Act) | 3 | Essential for compliance mapping. |
| **P0** | LLM Synthesis with Citations | 3 | Non-negotiable for credibility. |
| **P0** | Streamlit Frontend (Basic) | 3 | Intake form + tabbed output. |
| **P1** | NIST AI RMF Basic Mapping | 2 | Cross-framework story is valuable for interviews. |
| **P1** | Cross-Framework Checklist (Simplified) | 1.5 | Shows practical implementation thinking. |
| **P2** | Markdown Export | 1 | Nice to have for demo shareability. |
| **P2** | NIST AI 600-1 GenAI Profile | — | **DEFER to v2** — Not essential for MVP demo. |
| **P2** | PDF Export | — | **DEFER to v2** — Markdown sufficient for MVP. |

**Total P0 + P1 Hours: ~19.5 hours** (fits within 21-hour budget with buffer)

### MVP Scope Summary

**IN SCOPE (Build These):**
1. AI System Intake Form (structured + free text)
2. Deterministic EU AI Act Risk Classification (Prohibited / High-Risk / Limited / Minimal)
3. RAG retrieval against EU AI Act + NIST AI RMF corpus
4. LLM-generated compliance report with source citations
5. Basic NIST AI RMF subcategory mapping
6. Simplified cross-framework checklist
7. Markdown export
**OUT OF SCOPE (Defer to v2):**
- NIST AI 600-1 GenAI Profile mapping
- ISO 42001 mapping
- PDF export with formatting
- Conversational follow-up interface
- User accounts / persistence
---

## Databricks Architecture Overview

### Why Databricks for This MVP

| Capability | Benefit for This Project |
|------------|-------------------------|
| **Unity Catalog** | Governance story for interviews — shows you understand enterprise AI governance |
| **Vector Search** | Native integration, no external dependencies like Pinecone/Chroma |
| **Foundation Model APIs** | Pay-per-token access to Claude/GPT without managing API keys in code |
| **Delta Lake** | Versioned regulatory corpus — critical for compliance audit trails |
| **Databricks Apps** | Native deployment option (alternative to Streamlit Cloud) |
| **MLflow** | Experiment tracking for prompt iterations — shows MLOps maturity |

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATABRICKS LAKEHOUSE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐     ┌─────────────────────┐                       │
│  │  Unity Catalog      │     │  Delta Lake         │                       │
│  │  ─────────────────  │     │  ─────────────────  │                       │
│  │  • compliance_db    │     │  • raw_documents    │                       │
│  │  • regulatory_docs  │◄────│  • chunked_corpus   │                       │
│  │  • vector_index     │     │  • chunk_metadata   │                       │
│  └─────────────────────┘     └─────────────────────┘                       │
│            │                           │                                    │
│            ▼                           ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │              Databricks Vector Search                        │           │
│  │  ─────────────────────────────────────────────────────────   │           │
│  │  • eu_ai_act_index (Delta Sync)                              │           │
│  │  • nist_rmf_index (Delta Sync)                               │           │
│  │  • Embedding: Databricks BGE or OpenAI text-embedding-3-small│           │
│  └─────────────────────────────────────────────────────────────┘           │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │         Foundation Model APIs (Model Serving)                │           │
│  │  ─────────────────────────────────────────────────────────   │           │
│  │  • Claude 3.5 Sonnet (via External Model) OR                 │           │
│  │  • DBRX / Llama 3.1 70B (native)                             │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │ Streamlit    │    │ Classification│    │ RAG Pipeline │                  │
│  │ Frontend     │───▶│ Engine       │───▶│ (Retrieval + │                  │
│  │              │    │ (Rule-based) │    │  Synthesis)  │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                                        │                          │
│         └────────────────────────────────────────┘                          │
│                              │                                              │
│                              ▼                                              │
│                    ┌──────────────────┐                                    │
│                    │ Report Generator │                                    │
│                    │ (Structured JSON │                                    │
│                    │  + Markdown)     │                                    │
│                    └──────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Implementation Details

### 1. Data Layer: Unity Catalog + Delta Lake

#### Catalog Structure

```sql
-- Create the compliance catalog and schema
CREATE CATALOG IF NOT EXISTS ai_governance;
USE CATALOG ai_governance;

CREATE SCHEMA IF NOT EXISTS compliance_navigator;
USE SCHEMA compliance_navigator;
```

#### Delta Tables

**Table 1: Raw Documents**

```sql
CREATE TABLE IF NOT EXISTS raw_documents (
    document_id STRING,
    source STRING,              -- 'eu_ai_act', 'nist_ai_rmf', 'nist_playbook'
    document_name STRING,
    version STRING,
    effective_date DATE,
    raw_text STRING,
    pdf_path STRING,
    ingestion_timestamp TIMESTAMP,
    PRIMARY KEY (document_id)
) USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true'  -- For audit trail
);
```

**Table 2: Chunked Corpus (Vector Search Source)**

```sql
CREATE TABLE IF NOT EXISTS regulatory_chunks (
    chunk_id STRING,
    document_id STRING,
    source STRING,
    document_section STRING,        -- 'Article 9', 'GOVERN 1.1'
    section_title STRING,
    chunk_text STRING,
    chunk_index INT,

    -- EU AI Act specific metadata
    risk_tier STRING,               -- 'prohibited', 'high_risk', 'limited_risk', 'minimal_risk', 'all'
    applicable_role STRING,         -- 'provider', 'deployer', 'importer', 'all'
    compliance_deadline STRING,

    -- NIST specific metadata
    framework_function STRING,      -- 'GOVERN', 'MAP', 'MEASURE', 'MANAGE'
    category_id STRING,
    subcategory_id STRING,

    -- Common metadata
    source_url STRING,
    token_count INT,
    embedding_model STRING,
    created_timestamp TIMESTAMP,

    PRIMARY KEY (chunk_id)
) USING DELTA;
```

**Table 3: Cross-Framework Mappings (Pre-computed)**

```sql
CREATE TABLE IF NOT EXISTS framework_mappings (
    mapping_id STRING,
    eu_article STRING,
    eu_requirement_summary STRING,
    nist_subcategory STRING,
    nist_outcome STRING,
    implementation_action STRING,
    mapping_rationale STRING,
    PRIMARY KEY (mapping_id)
) USING DELTA;
```

### 2. Document Ingestion Pipeline

#### Chunking Strategy (Domain-Specific)

The chunking approach preserves the hierarchical structure of regulatory text:

```python
# Databricks Notebook: 01_document_ingestion

from pyspark.sql import functions as F
from pyspark.sql.types import *
import re

# EU AI Act Chunking Logic
def chunk_eu_ai_act(text: str, article_pattern: str = r"Article\s+(\d+)") -> list:
    """
    Chunk EU AI Act by article. Each article is a self-contained obligation.
    For long articles (>500 tokens), chunk by paragraph with article context.
    """
    chunks = []
    articles = re.split(r'(?=Article\s+\d+)', text)

    for article in articles:
        if not article.strip():
            continue

        # Extract article number and title
        match = re.match(r'Article\s+(\d+)\s*[:\.\-]?\s*(.+?)(?:\n|$)', article)
        if match:
            article_num = match.group(1)
            article_title = match.group(2).strip()

            # Determine applicable risk tier and role from article number
            risk_tier, role = get_article_applicability(article_num)

            # Check token count (approximate: 1 token ≈ 4 chars)
            if len(article) / 4 > 500:
                # Chunk by paragraph for long articles
                paragraphs = article.split('\n\n')
                for i, para in enumerate(paragraphs):
                    if len(para.strip()) > 50:  # Skip very short fragments
                        chunks.append({
                            'document_section': f'Article {article_num}',
                            'section_title': article_title,
                            'chunk_text': f"Article {article_num} - {article_title}\n\n{para.strip()}",
                            'risk_tier': risk_tier,
                            'applicable_role': role,
                            'chunk_index': i
                        })
            else:
                chunks.append({
                    'document_section': f'Article {article_num}',
                    'section_title': article_title,
                    'chunk_text': article.strip(),
                    'risk_tier': risk_tier,
                    'applicable_role': role,
                    'chunk_index': 0
                })

    return chunks

def get_article_applicability(article_num: str) -> tuple:
    """Map EU AI Act articles to risk tiers and roles."""
    article_num = int(article_num)

    # Prohibited practices
    if article_num == 5:
        return 'prohibited', 'all'

    # High-risk system requirements (provider obligations)
    if article_num in [6, 7, 8, 9, 10, 11, 12, 13, 14, 15]:
        return 'high_risk', 'provider'

    # Deployer obligations
    if article_num == 26:
        return 'high_risk', 'deployer'

    # Transparency obligations (limited risk)
    if article_num == 50:
        return 'limited_risk', 'all'

    # GPAI provisions
    if article_num in range(51, 57):
        return 'all', 'provider'

    return 'all', 'all'


# NIST AI RMF Chunking Logic
def chunk_nist_rmf(text: str) -> list:
    """
    Chunk NIST AI RMF by subcategory.
    Each subcategory has: ID, outcome statement, description.
    """
    chunks = []
    # Pattern matches: GOVERN 1.1, MAP 2.3, MEASURE 1.2, MANAGE 4.1
    subcategory_pattern = r'(GOVERN|MAP|MEASURE|MANAGE)\s+(\d+\.\d+)'

    sections = re.split(subcategory_pattern, text)

    i = 0
    while i < len(sections) - 2:
        function = sections[i+1]  # GOVERN, MAP, etc.
        subcategory_num = sections[i+2]  # 1.1, 2.3, etc.
        content = sections[i+3] if i+3 < len(sections) else ""

        # Extract outcome statement (usually first sentence)
        outcome_match = re.match(r'[:\s]*([^.]+\.)', content)
        outcome = outcome_match.group(1).strip() if outcome_match else ""

        chunks.append({
            'document_section': f'{function} {subcategory_num}',
            'section_title': outcome[:100],  # Truncate for title
            'chunk_text': f"{function} {subcategory_num}\n\n{content.strip()}",
            'framework_function': function,
            'category_id': f"{function} {subcategory_num.split('.')[0]}",
            'subcategory_id': f"{function} {subcategory_num}",
            'chunk_index': 0
        })
        i += 3

    return chunks
```

#### Embedding Generation

```python
# Using Databricks Foundation Model APIs for embeddings
from databricks.vector_search.client import VectorSearchClient

# Option 1: Databricks BGE (recommended for cost)
def generate_embeddings_databricks(texts: list) -> list:
    """Generate embeddings using Databricks Foundation Model endpoint."""
    import mlflow.deployments

    client = mlflow.deployments.get_deploy_client("databricks")

    response = client.predict(
        endpoint="databricks-bge-large-en",
        inputs={"input": texts}
    )

    return [item["embedding"] for item in response["data"]]

# Option 2: OpenAI (higher quality, more cost)
def generate_embeddings_openai(texts: list) -> list:
    """Generate embeddings using OpenAI via External Model endpoint."""
    import mlflow.deployments

    client = mlflow.deployments.get_deploy_client("databricks")

    response = client.predict(
        endpoint="openai-text-embedding-3-small",  # Configure in Model Serving
        inputs={"input": texts}
    )

    return [item["embedding"] for item in response["data"]]
```

### 3. Databricks Vector Search Setup

#### Create Vector Search Endpoint

```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create endpoint (one-time setup)
vsc.create_endpoint(
    name="compliance-navigator-endpoint",
    endpoint_type="STANDARD"  # Use STANDARD for production-like behavior
)
```

#### Create Delta Sync Index

```python
# Create vector index that syncs from Delta table
vsc.create_delta_sync_index(
    endpoint_name="compliance-navigator-endpoint",
    index_name="ai_governance.compliance_navigator.regulatory_chunks_index",
    source_table_name="ai_governance.compliance_navigator.regulatory_chunks",
    pipeline_type="TRIGGERED",  # Manual sync for MVP; use CONTINUOUS for production
    primary_key="chunk_id",
    embedding_source_column="chunk_text",
    embedding_model_endpoint_name="databricks-bge-large-en",  # Auto-generate embeddings
    embedding_dimension=1024  # BGE-large dimension
)

# Sync the index
vsc.get_index(
    endpoint_name="compliance-navigator-endpoint",
    index_name="ai_governance.compliance_navigator.regulatory_chunks_index"
).sync()
```

#### Retrieval Function

```python
def retrieve_compliance_requirements(
    system_description: str,
    risk_tier: str,
    num_results: int = 15
) -> dict:
    """
    Retrieve relevant regulatory chunks based on system description and risk tier.
    Returns EU AI Act and NIST AI RMF chunks separately.
    """
    from databricks.vector_search.client import VectorSearchClient

    vsc = VectorSearchClient()
    index = vsc.get_index(
        endpoint_name="compliance-navigator-endpoint",
        index_name="ai_governance.compliance_navigator.regulatory_chunks_index"
    )

    # Build query with context
    query = f"""
    AI System Description: {system_description}
    Risk Classification: {risk_tier}
    Find: applicable regulatory requirements, obligations, and compliance controls
    """

    # Build filter for risk tier
    # Include chunks that apply to this tier OR apply to all tiers
    tier_filter = {
        "risk_tier": ["high_risk", "all"] if risk_tier == "high_risk" else [risk_tier, "all"]
    }

    # Retrieve EU AI Act chunks
    eu_results = index.similarity_search(
        query_text=query,
        columns=["chunk_id", "document_section", "section_title", "chunk_text",
                 "risk_tier", "applicable_role", "source_url"],
        filters={"source": "eu_ai_act", **tier_filter},
        num_results=10
    )

    # Retrieve NIST AI RMF chunks
    nist_results = index.similarity_search(
        query_text=query,
        columns=["chunk_id", "document_section", "section_title", "chunk_text",
                 "framework_function", "subcategory_id", "source_url"],
        filters={"source": ["nist_ai_rmf", "nist_playbook"]},
        num_results=10
    )

    return {
        "eu_ai_act": eu_results["result"]["data_array"],
        "nist_rmf": nist_results["result"]["data_array"]
    }
```

### 4. Classification Engine (Deterministic)

This is the most critical component for credibility. The classification MUST be rule-based, not LLM-generated.

```python
# classification_engine.py

from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

class RiskTier(Enum):
    PROHIBITED = "prohibited"
    HIGH_RISK = "high_risk"
    LIMITED_RISK = "limited_risk"
    MINIMAL_RISK = "minimal_risk"

class Role(Enum):
    PROVIDER = "provider"
    DEPLOYER = "deployer"
    IMPORTER = "importer"

@dataclass
class SystemIntake:
    """Structured input from the intake form."""
    system_name: str
    description: str
    domain: str                          # insurance, banking, healthcare, HR, law_enforcement, general
    ai_type: str                         # classification, prediction, generative, recommendation, cv, nlp
    decision_impact: str                 # fully_automated, human_in_loop, advisory
    data_types: List[str]                # personal, biometric, health, financial, criminal, children, none
    intended_purpose: str
    deployment_geography: List[str]      # EU, US, both, other

    # Additional fields for classification
    interacts_with_humans: bool = False
    generates_synthetic_content: bool = False
    is_safety_component: bool = False

@dataclass
class ClassificationResult:
    """Output of the classification engine."""
    risk_tier: RiskTier
    primary_basis: str                   # e.g., "Annex III, Category 4(a)"
    applicable_articles: List[str]
    applicable_role: Role
    compliance_deadline: str
    reasoning: str
    confidence: str                      # 'high', 'medium', 'requires_review'


def classify_risk_tier(intake: SystemIntake) -> ClassificationResult:
    """
    Rule-based EU AI Act risk classification.
    Deterministic and auditable — NOT LLM-dependent.
    """

    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: Check Prohibited Practices (Article 5)
    # ═══════════════════════════════════════════════════════════════════

    prohibited_checks = []

    # Art 5(1)(a): Subliminal manipulation
    if "subliminal" in intake.description.lower() or "manipulat" in intake.description.lower():
        prohibited_checks.append(("Art. 5(1)(a)", "Subliminal manipulation techniques"))

    # Art 5(1)(b): Exploiting vulnerabilities
    vulnerable_keywords = ["vulnerable", "disability", "elderly", "children"]
    if any(kw in intake.description.lower() for kw in vulnerable_keywords) and "exploit" in intake.description.lower():
        prohibited_checks.append(("Art. 5(1)(b)", "Exploitation of vulnerabilities"))

    # Art 5(1)(c): Social scoring by government
    if intake.domain == "government" and "social scor" in intake.description.lower():
        prohibited_checks.append(("Art. 5(1)(c)", "Social scoring by public authorities"))

    # Art 5(1)(d): Real-time biometric identification for law enforcement
    if (intake.domain == "law_enforcement" and
        "biometric" in intake.data_types and
        "real-time" in intake.description.lower()):
        prohibited_checks.append(("Art. 5(1)(d)", "Real-time biometric ID for law enforcement"))

    # Art 5(1)(f): Emotion recognition in workplace/education
    emotion_keywords = ["emotion recognition", "emotion detection", "emotional state", "sentiment analysis"]
    if (any(kw in intake.description.lower() for kw in emotion_keywords) and
        intake.domain in ["HR", "education", "workplace"]):
        prohibited_checks.append(("Art. 5(1)(f)", "Emotion recognition in workplace/education"))

    if prohibited_checks:
        return ClassificationResult(
            risk_tier=RiskTier.PROHIBITED,
            primary_basis=prohibited_checks[0][0],
            applicable_articles=["Article 5"],
            applicable_role=Role.PROVIDER,
            compliance_deadline="February 2, 2025 (already in effect)",
            reasoning=f"System falls under prohibited practice: {prohibited_checks[0][1]}",
            confidence="high"
        )

    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: Check High-Risk via Annex III Categories
    # ═══════════════════════════════════════════════════════════════════

    high_risk_matches = []

    # Category 1: Biometric identification and categorization
    if "biometric" in intake.data_types:
        if "identification" in intake.description.lower():
            high_risk_matches.append(("Annex III(1)(a)", "Remote biometric identification"))
        if "categori" in intake.description.lower():
            high_risk_matches.append(("Annex III(1)(b)", "Biometric categorization"))

    # Category 2: Critical infrastructure
    critical_infra_keywords = ["energy", "water", "gas", "heating", "traffic", "transport"]
    if any(kw in intake.description.lower() for kw in critical_infra_keywords):
        if intake.is_safety_component:
            high_risk_matches.append(("Annex III(2)", "Safety component of critical infrastructure"))

    # Category 3: Education and vocational training
    if intake.domain == "education":
        education_keywords = ["admission", "assessment", "exam", "grade", "learning outcome"]
        if any(kw in intake.description.lower() for kw in education_keywords):
            high_risk_matches.append(("Annex III(3)", "Access to or assessment in education"))

    # Category 4: Employment and workers management (COMMON)
    if intake.domain in ["HR", "employment", "workforce"]:
        hr_keywords = ["recruit", "hiring", "screening", "candidate", "resume", "cv",
                       "task allocation", "monitor", "evaluat", "promotion", "termination"]
        if any(kw in intake.description.lower() for kw in hr_keywords):
            high_risk_matches.append(("Annex III(4)(a)", "Recruitment and selection"))

    # Category 5: Access to essential services (VERY COMMON for insurance/banking)
    if intake.domain in ["insurance", "banking", "financial"]:
        essential_keywords = ["creditworth", "credit scor", "insurance pric", "risk assessment",
                              "premium", "underwriting", "claims", "eligibility"]
        if any(kw in intake.description.lower() for kw in essential_keywords):
            high_risk_matches.append(("Annex III(5)(b)", "Creditworthiness/insurance risk assessment"))

    # Category 6: Law enforcement
    if intake.domain == "law_enforcement":
        le_keywords = ["risk assessment", "evidence", "crime predict", "profil"]
        if any(kw in intake.description.lower() for kw in le_keywords):
            high_risk_matches.append(("Annex III(6)", "Law enforcement AI"))

    # Category 7: Migration, asylum, border control
    migration_keywords = ["asylum", "visa", "border", "migration", "refugee"]
    if any(kw in intake.description.lower() for kw in migration_keywords):
        high_risk_matches.append(("Annex III(7)", "Migration and border control"))

    # Category 8: Administration of justice
    justice_keywords = ["judicial", "sentencing", "court", "legal research", "dispute"]
    if any(kw in intake.description.lower() for kw in justice_keywords):
        high_risk_matches.append(("Annex III(8)", "Administration of justice"))

    if high_risk_matches:
        # Determine role based on deployment context
        role = Role.PROVIDER  # Default
        if "deploy" in intake.description.lower() or "using" in intake.description.lower():
            role = Role.DEPLOYER

        return ClassificationResult(
            risk_tier=RiskTier.HIGH_RISK,
            primary_basis=high_risk_matches[0][0],
            applicable_articles=[
                "Article 6 (High-risk classification)",
                "Article 9 (Risk management system)",
                "Article 10 (Data governance)",
                "Article 11 (Technical documentation)",
                "Article 13 (Transparency)",
                "Article 14 (Human oversight)",
                "Article 15 (Accuracy, robustness, cybersecurity)",
                "Article 26 (Deployer obligations)" if role == Role.DEPLOYER else None
            ],
            applicable_role=role,
            compliance_deadline="August 2, 2026",
            reasoning=f"System matches high-risk use case: {high_risk_matches[0][1]}",
            confidence="high" if len(high_risk_matches) >= 1 else "medium"
        )

    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: Check Limited Risk (Article 50 Transparency)
    # ═══════════════════════════════════════════════════════════════════

    limited_risk_triggers = []

    # Chatbots, voice assistants, customer service AI
    if intake.interacts_with_humans or intake.ai_type in ["generative", "nlp"]:
        interaction_keywords = ["chatbot", "assistant", "customer service", "conversation", "dialogue"]
        if any(kw in intake.description.lower() for kw in interaction_keywords):
            limited_risk_triggers.append(("Art. 50(1)", "Human-interacting AI system"))

    # Synthetic content generation (deepfakes, AI-generated text/images)
    if intake.generates_synthetic_content or intake.ai_type == "generative":
        synthetic_keywords = ["generat", "synthetic", "deepfake", "create content", "produce text"]
        if any(kw in intake.description.lower() for kw in synthetic_keywords):
            limited_risk_triggers.append(("Art. 50(2)", "AI-generated content"))

    if limited_risk_triggers:
        return ClassificationResult(
            risk_tier=RiskTier.LIMITED_RISK,
            primary_basis=limited_risk_triggers[0][0],
            applicable_articles=["Article 50 (Transparency obligations)"],
            applicable_role=Role.PROVIDER,
            compliance_deadline="August 2, 2025",
            reasoning=f"System requires transparency: {limited_risk_triggers[0][1]}",
            confidence="high"
        )

    # ═══════════════════════════════════════════════════════════════════
    # STEP 4: Default to Minimal Risk
    # ═══════════════════════════════════════════════════════════════════

    return ClassificationResult(
        risk_tier=RiskTier.MINIMAL_RISK,
        primary_basis="No specific category matched",
        applicable_articles=["No mandatory requirements (voluntary codes encouraged)"],
        applicable_role=Role.PROVIDER,
        compliance_deadline="N/A",
        reasoning="System does not match prohibited, high-risk, or limited risk criteria",
        confidence="medium"
    )
```

### 5. LLM Synthesis Layer

#### Foundation Model Configuration

```python
# Option 1: Use Databricks External Model (Claude/GPT via Model Serving)
# This requires setting up an external model endpoint in Databricks

import mlflow.deployments

def create_external_model_endpoint():
    """One-time setup: Create endpoint for Claude via Model Serving."""
    client = mlflow.deployments.get_deploy_client("databricks")

    # Create endpoint pointing to Anthropic
    client.create_endpoint(
        name="claude-sonnet-compliance",
        config={
            "served_entities": [{
                "external_model": {
                    "name": "claude-3-5-sonnet",
                    "provider": "anthropic",
                    "task": "llm/v1/chat",
                    "anthropic_config": {
                        "anthropic_api_key": "{{secrets/compliance-navigator/anthropic-api-key}}"
                    }
                }
            }]
        }
    )
```

#### Synthesis Function with Structured Output

```python
# llm_synthesis.py

import json
from typing import Dict, List
import mlflow.deployments

SYSTEM_PROMPT = """You are an AI compliance analyst specializing in EU AI Act and NIST AI RMF.
Given regulatory text retrieved from these frameworks, generate a structured compliance assessment.

CRITICAL RULES:
1. ONLY use information from the provided regulatory text chunks. Do NOT invent requirements.
2. EVERY requirement MUST include a specific citation: [EU AI Act Art. X(Y)] or [NIST AI RMF FUNCTION X.Y]
3. If retrieved text lacks relevant information, state: "Not addressed in retrieved sources — manual review recommended."
4. Do NOT provide legal advice. Frame outputs as "regulatory mapping for review by qualified counsel."
5. Return ONLY valid JSON matching the specified schema.

OUTPUT SCHEMA:
{
  "risk_classification": {
    "tier": "high_risk",
    "basis": "Annex III, Category 5(b)",
    "citation": "[EU AI Act Art. 6(2), Annex III(5)(b)]",
    "explanation": "Brief explanation of why this classification applies"
  },
  "eu_ai_act_obligations": [
    {
      "article": "Article 9",
      "requirement": "Risk Management System",
      "summary": "Establish and maintain a risk management system...",
      "role": "provider",
      "deadline": "August 2, 2026",
      "citation": "[EU AI Act Art. 9(1)]"
    }
  ],
  "nist_rmf_mapping": [
    {
      "subcategory": "GOVERN 1.1",
      "function": "GOVERN",
      "outcome": "Legal and regulatory requirements are understood...",
      "suggested_actions": ["Action 1", "Action 2"],
      "citation": "[NIST AI RMF GOVERN 1.1]"
    }
  ],
  "cross_framework_checklist": [
    {
      "eu_requirement": "Risk management system [Art. 9]",
      "nist_mapping": "MAP 1.1, MAP 1.5, MANAGE 1.1",
      "implementation_action": "Establish continuous risk identification process"
    }
  ],
  "key_deadlines": [
    {
      "deadline": "August 2, 2026",
      "applies_to": "High-risk AI system requirements",
      "citation": "[EU AI Act Art. 113]"
    }
  ]
}"""


def synthesize_compliance_report(
    system_description: str,
    classification_result: dict,
    retrieved_chunks: dict
) -> dict:
    """
    Generate structured compliance report using LLM synthesis.
    """
    client = mlflow.deployments.get_deploy_client("databricks")

    # Format retrieved chunks for context
    eu_context = "\n\n".join([
        f"--- {chunk['document_section']}: {chunk['section_title']} ---\n{chunk['chunk_text']}"
        for chunk in retrieved_chunks["eu_ai_act"]
    ])

    nist_context = "\n\n".join([
        f"--- {chunk['document_section']} ---\n{chunk['chunk_text']}"
        for chunk in retrieved_chunks["nist_rmf"]
    ])

    user_prompt = f"""
SYSTEM UNDER ASSESSMENT:
{system_description}

PRE-DETERMINED RISK CLASSIFICATION (from rule-based engine):
- Tier: {classification_result['risk_tier']}
- Basis: {classification_result['primary_basis']}
- Reasoning: {classification_result['reasoning']}

RETRIEVED EU AI ACT PROVISIONS:
{eu_context}

RETRIEVED NIST AI RMF GUIDANCE:
{nist_context}

Generate a structured compliance report based on the above. Include specific citations for every requirement.
Return ONLY valid JSON matching the schema in your instructions.
"""

    response = client.predict(
        endpoint="claude-sonnet-compliance",  # Or your configured endpoint
        inputs={
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 4000,
            "temperature": 0.1  # Low temperature for consistency
        }
    )

    # Parse JSON response
    response_text = response["choices"][0]["message"]["content"]

    # Handle potential markdown code blocks
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0]

    return json.loads(response_text.strip())
```

### 6. Streamlit Frontend

```python
# app.py - Streamlit application

import streamlit as st
import json
from classification_engine import classify_risk_tier, SystemIntake
from retrieval import retrieve_compliance_requirements
from llm_synthesis import synthesize_compliance_report

# Page config
st.set_page_config(
    page_title="AI Compliance Navigator",
    page_icon="⚖️",
    layout="wide"
)

# Header
st.title("⚖️ AI Compliance Navigator")
st.markdown("*Regulatory mapping for EU AI Act and NIST AI RMF*")
st.markdown("---")

# Sidebar disclaimer
with st.sidebar:
    st.warning("""
    **Disclaimer**

    This tool provides regulatory mapping for informational purposes only.
    It does not constitute legal advice. Consult qualified legal counsel
    for compliance determinations.
    """)
    st.markdown("---")
    st.markdown("**Built with:**")
    st.markdown("• Databricks Lakehouse")
    st.markdown("• Vector Search")
    st.markdown("• Foundation Model APIs")

# ═══════════════════════════════════════════════════════════════════
# TAB 1: INTAKE FORM
# ═══════════════════════════════════════════════════════════════════

tab1, tab2 = st.tabs(["📝 System Intake", "📊 Compliance Report"])

with tab1:
    st.header("Describe Your AI System")

    col1, col2 = st.columns(2)

    with col1:
        system_name = st.text_input("System Name", placeholder="e.g., Claims Triage Model")

        domain = st.selectbox(
            "Domain / Industry",
            ["insurance", "banking", "healthcare", "HR", "law_enforcement", "education", "general"]
        )

        ai_type = st.selectbox(
            "AI Type",
            ["classification", "prediction", "generative", "recommendation", "computer_vision", "nlp", "other"]
        )

        decision_impact = st.selectbox(
            "Decision Impact",
            ["fully_automated", "human_in_loop", "advisory"],
            format_func=lambda x: {
                "fully_automated": "Fully Automated Decisions",
                "human_in_loop": "Human-in-the-Loop",
                "advisory": "Advisory / Support Only"
            }[x]
        )

    with col2:
        data_types = st.multiselect(
            "Data Types Processed",
            ["personal", "biometric", "health", "financial", "criminal", "children", "none"],
            default=["none"]
        )

        deployment_geography = st.multiselect(
            "Deployment Geography",
            ["EU", "US", "both", "other"],
            default=["EU"]
        )

        interacts_with_humans = st.checkbox("Interacts directly with humans (chatbot, voice assistant)")
        generates_synthetic = st.checkbox("Generates synthetic content (text, images, video)")

    description = st.text_area(
        "System Description",
        placeholder="Describe what the AI system does, how it makes decisions, and its intended use case...",
        height=150
    )

    intended_purpose = st.text_area(
        "Intended Purpose",
        placeholder="What specific problem does this system solve? Who are the end users?",
        height=100
    )

    # Submit button
    if st.button("🔍 Analyze Compliance Requirements", type="primary", use_container_width=True):
        if not system_name or not description:
            st.error("Please provide at least a system name and description.")
        else:
            with st.spinner("Analyzing regulatory requirements..."):
                # Create intake object
                intake = SystemIntake(
                    system_name=system_name,
                    description=description,
                    domain=domain,
                    ai_type=ai_type,
                    decision_impact=decision_impact,
                    data_types=data_types,
                    intended_purpose=intended_purpose,
                    deployment_geography=deployment_geography,
                    interacts_with_humans=interacts_with_humans,
                    generates_synthetic_content=generates_synthetic
                )

                # Step 1: Classify risk tier (deterministic)
                classification = classify_risk_tier(intake)

                # Step 2: Retrieve relevant chunks
                chunks = retrieve_compliance_requirements(
                    system_description=f"{description}\n\nPurpose: {intended_purpose}",
                    risk_tier=classification.risk_tier.value
                )

                # Step 3: LLM synthesis
                report = synthesize_compliance_report(
                    system_description=f"{system_name}: {description}",
                    classification_result={
                        "risk_tier": classification.risk_tier.value,
                        "primary_basis": classification.primary_basis,
                        "reasoning": classification.reasoning
                    },
                    retrieved_chunks=chunks
                )

                # Store in session state
                st.session_state["classification"] = classification
                st.session_state["report"] = report
                st.session_state["system_name"] = system_name

                st.success("Analysis complete! View results in the Compliance Report tab.")

# ═══════════════════════════════════════════════════════════════════
# TAB 2: COMPLIANCE REPORT
# ═══════════════════════════════════════════════════════════════════

with tab2:
    if "report" not in st.session_state:
        st.info("Submit an AI system for analysis to view the compliance report.")
    else:
        classification = st.session_state["classification"]
        report = st.session_state["report"]
        system_name = st.session_state["system_name"]

        st.header(f"Compliance Report: {system_name}")

        # Risk Classification Banner
        tier_colors = {
            "prohibited": "🔴",
            "high_risk": "🟠",
            "limited_risk": "🟡",
            "minimal_risk": "🟢"
        }

        tier_display = classification.risk_tier.value.replace("_", " ").title()
        st.markdown(f"### {tier_colors.get(classification.risk_tier.value, '⚪')} Risk Classification: **{tier_display}**")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Basis:** {classification.primary_basis}")
            st.markdown(f"**Role:** {classification.applicable_role.value.title()}")
        with col2:
            st.markdown(f"**Compliance Deadline:** {classification.compliance_deadline}")
            st.markdown(f"**Confidence:** {classification.confidence.title()}")

        st.markdown(f"**Reasoning:** {classification.reasoning}")

        st.markdown("---")

        # Sub-tabs for detailed sections
        subtab1, subtab2, subtab3, subtab4 = st.tabs([
            "EU AI Act Obligations",
            "NIST AI RMF Mapping",
            "Cross-Framework Checklist",
            "Export Report"
        ])

        with subtab1:
            st.subheader("Applicable EU AI Act Requirements")
            for obligation in report.get("eu_ai_act_obligations", []):
                with st.expander(f"📜 {obligation['article']}: {obligation['requirement']}"):
                    st.markdown(f"**Summary:** {obligation['summary']}")
                    st.markdown(f"**Applicable Role:** {obligation['role'].title()}")
                    st.markdown(f"**Deadline:** {obligation['deadline']}")
                    st.caption(f"Citation: {obligation['citation']}")

        with subtab2:
            st.subheader("NIST AI RMF Subcategory Mapping")
            for mapping in report.get("nist_rmf_mapping", []):
                with st.expander(f"🔷 {mapping['subcategory']}: {mapping['outcome'][:60]}..."):
                    st.markdown(f"**Function:** {mapping['function']}")
                    st.markdown(f"**Outcome:** {mapping['outcome']}")
                    st.markdown("**Suggested Actions:**")
                    for action in mapping.get("suggested_actions", []):
                        st.markdown(f"- {action}")
                    st.caption(f"Citation: {mapping['citation']}")

        with subtab3:
            st.subheader("Cross-Framework Compliance Checklist")
            checklist_data = []
            for item in report.get("cross_framework_checklist", []):
                checklist_data.append({
                    "EU AI Act Requirement": item["eu_requirement"],
                    "NIST RMF Mapping": item["nist_mapping"],
                    "Implementation Action": item["implementation_action"]
                })
            st.table(checklist_data)

        with subtab4:
            st.subheader("Export Report")

            # Generate Markdown
            markdown_report = generate_markdown_report(
                system_name, classification, report
            )

            st.download_button(
                label="📥 Download as Markdown",
                data=markdown_report,
                file_name=f"{system_name.replace(' ', '_')}_compliance_report.md",
                mime="text/markdown"
            )

            # Preview
            with st.expander("Preview Markdown"):
                st.code(markdown_report, language="markdown")


def generate_markdown_report(system_name: str, classification, report: dict) -> str:
    """Generate markdown export of the compliance report."""

    md = f"""# AI Compliance Report: {system_name}

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## Risk Classification

| Attribute | Value |
|-----------|-------|
| **Risk Tier** | {classification.risk_tier.value.replace("_", " ").title()} |
| **Basis** | {classification.primary_basis} |
| **Role** | {classification.applicable_role.value.title()} |
| **Deadline** | {classification.compliance_deadline} |

**Reasoning:** {classification.reasoning}

---

## EU AI Act Obligations

"""

    for ob in report.get("eu_ai_act_obligations", []):
        md += f"""### {ob['article']}: {ob['requirement']}

{ob['summary']}

- **Role:** {ob['role'].title()}
- **Deadline:** {ob['deadline']}
- **Citation:** {ob['citation']}

"""

    md += """---

## NIST AI RMF Mapping

"""

    for mapping in report.get("nist_rmf_mapping", []):
        md += f"""### {mapping['subcategory']}

**Function:** {mapping['function']}

**Outcome:** {mapping['outcome']}

**Suggested Actions:**
"""
        for action in mapping.get("suggested_actions", []):
            md += f"- {action}\n"
        md += f"\n*Citation: {mapping['citation']}*\n\n"

    md += """---

## Cross-Framework Checklist

| EU AI Act Requirement | NIST RMF Mapping | Implementation Action |
|-----------------------|------------------|----------------------|
"""

    for item in report.get("cross_framework_checklist", []):
        md += f"| {item['eu_requirement']} | {item['nist_mapping']} | {item['implementation_action']} |\n"

    md += """
---

*Disclaimer: This report is for informational purposes only and does not constitute legal advice.*
"""

    return md
```

---

## Deployment Options

### Option 1: Streamlit Cloud (Recommended for MVP)

**Pros:** Free, fast deployment, shareable URL
**Cons:** Not Databricks-native, requires API connectivity

```bash
# requirements.txt
streamlit>=1.28.0
databricks-sdk>=0.12.0
mlflow>=2.9.0
pandas>=2.0.0
```

```yaml
# .streamlit/secrets.toml (for Streamlit Cloud)
[databricks]
host = "https://your-workspace.cloud.databricks.com"
token = "your-databricks-token"
```

### Option 2: Databricks Apps (Enterprise Story)

**Pros:** Native Databricks integration, Unity Catalog governance, enterprise-ready
**Cons:** Requires Databricks workspace, slightly more setup

```python
# Deploy as Databricks App
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Create app deployment
w.apps.create(
    name="ai-compliance-navigator",
    description="RAG-powered EU AI Act & NIST AI RMF compliance mapping",
    # ... additional config
)
```

---

## Cost Estimate (MVP)

| Component | Estimated Cost | Notes |
|-----------|---------------|-------|
| Databricks Vector Search | ~$5–10 | Small index, triggered sync |
| Foundation Model APIs (embedding) | ~$2–5 | BGE is very cost-effective |
| Foundation Model APIs (LLM) | ~$5–15 | Depends on testing volume |
| Streamlit Cloud | Free | Community tier |
| **Total** | **$12–30** | For entire MVP development |

---

## 6-Week Implementation Timeline (Databricks-Specific)

### Week 1: Data Foundation (4 hours)
- [ ] Set up Unity Catalog: `ai_governance.compliance_navigator`
- [ ] Download regulatory PDFs (EU AI Act, NIST AI RMF, Playbook)
- [ ] Create Delta tables: `raw_documents`, `regulatory_chunks`
- [ ] Implement chunking logic (EU AI Act by article, NIST by subcategory)
- [ ] Load initial corpus
### Week 2: Vector Search + Classification (4 hours)
- [ ] Create Vector Search endpoint
- [ ] Create Delta Sync index with BGE embeddings
- [ ] Implement rule-based classification engine
- [ ] Test classification with 4 example systems
- [ ] Verify retrieval quality
### Week 3: LLM Synthesis Pipeline (4 hours)
- [ ] Configure Foundation Model endpoint (Claude or DBRX)
- [ ] Implement synthesis function with structured output
- [ ] Build cross-framework mapping logic
- [ ] Test end-to-end pipeline
- [ ] Log experiments in MLflow
### Week 4: Streamlit Frontend (3 hours)
- [ ] Build intake form with all fields
- [ ] Build tabbed report display
- [ ] Connect to Databricks backend
- [ ] Add basic styling
### Week 5: Testing + Polish (3 hours)
- [ ] Test with 8–10 diverse AI systems
- [ ] Handle edge cases (GPAI, multi-category systems)
- [ ] Implement Markdown export
- [ ] Add disclaimer and citations UI
### Week 6: Deploy + Document (3 hours)
- [ ] Deploy to Streamlit Cloud
- [ ] Create architecture diagram for README
- [ ] Record 5-minute demo video
- [ ] Draft LinkedIn post
- [ ] Push to GitHub
---

## Interview Demo Script (5 minutes)

1. **(30 sec) Problem Statement**
   > "In AI governance consulting, regulatory mapping is the most time-consuming task. Clients need to understand which EU AI Act provisions apply to their specific AI systems and how to implement controls. This tool accelerates that process."
2. **(60 sec) Live Demo: Insurance Claims Triage**
   - Fill out intake form for an automated insurance claims triage model
   - Highlight: domain = insurance, decision_impact = fully_automated, data_types = financial
3. **(90 sec) Show Output**
   - Risk Classification: High-Risk (Annex III, Category 5b)
   - Applicable Articles: Art. 9, 10, 11, 13, 14
   - NIST Mapping: GOVERN 1.1, MAP 1.1, MEASURE 2.2, MANAGE 1.1
   - Cross-Framework Checklist with specific actions
4. **(60 sec) Architecture Highlight**
   > "The classification is deterministic and auditable — it's rule-based, not LLM-generated. The LLM only handles retrieval and synthesis, not the compliance determination. This is critical for governance tooling."
5. **(30 sec) Databricks Value Prop**
   > "Built entirely on Databricks: Delta Lake for versioned regulatory corpus, Vector Search for retrieval, Foundation Model APIs for synthesis, Unity Catalog for governance. The architecture scales to production."
---

## Files and Repository Structure

```
ai-compliance-navigator/
├── README.md
├── architecture.md                 # This document
├── requirements.txt
├── .streamlit/
│   └── config.toml
├── notebooks/
│   ├── 01_document_ingestion.py    # Databricks notebook
│   ├── 02_create_vector_index.py
│   └── 03_test_pipeline.py
├── src/
│   ├── __init__.py
│   ├── classification_engine.py    # Rule-based classifier
│   ├── retrieval.py                # Vector Search retrieval
│   ├── llm_synthesis.py            # LLM synthesis with citations
│   └── utils.py
├── app.py                          # Streamlit frontend
├── data/
│   └── framework_mappings.json     # Pre-computed EU-NIST mappings
└── tests/
    ├── test_classification.py
    └── test_scenarios.json         # 5 test scenarios
```

---

## Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Risk Classification | Rule-based, not LLM | Auditability and determinism required for compliance tooling |
| Vector Store | Databricks Vector Search | Native integration, no external dependencies |
| Embeddings | Databricks BGE | Cost-effective, good quality for regulatory text |
| LLM | Claude Sonnet via External Model | Best structured output quality; DBRX as fallback |
| Chunking | Domain-specific (by article/subcategory) | Preserves regulatory structure, improves retrieval |
| Frontend | Streamlit | Fastest path to demo-ready UI |
| Deployment | Streamlit Cloud (MVP) → Databricks Apps (v2) | Balance speed vs. enterprise story |

---

*Document Version: 1.0*


