"""
Filtered vector retrieval over the regulatory corpus.
Two-track design (validated in Phase 2): retrieve EU AI Act and NIST AI RMF
SEPARATELY, each source-filtered — a single blind query mixes NIST vocabulary
into EU results and buries the on-point provisions. For EU, also filter by
risk tier so only tier-relevant obligations surface.
"""

from src.utils import VS_ENDPOINT, VS_INDEX, get_vector_search_client


def _tier_filter(risk_tier: str) -> list:
    """Chunks tagged for this tier OR tagged 'all' (apply-to-everything)."""
    return [risk_tier, "all"]


def retrieve_compliance_requirements(
    system_description: str,
    risk_tier: str,
    num_results: int = 10,
) -> dict:
    """
    Retrieve relevant regulatory chunks for a system description + risk tier.
    Returns EU AI Act and NIST AI RMF chunks separately.

    Args:
        system_description: description + intended purpose (richer query = better ranking)
        risk_tier: engine output ('prohibited'|'high_risk'|'limited_risk'|'minimal_risk')
        num_results: chunks per source
    """
    vsc = get_vector_search_client()
    index = vsc.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)

    # Rich query: system + tier + intent keywords. Phase 2 showed terse queries
    # rank procedural 'all'-tier articles above the substantive tier articles.
    query = (
        f"{system_description} "
        f"risk classification: {risk_tier}. "
        f"applicable regulatory requirements, obligations, and compliance controls"
    )

    # Track 1 — EU AI Act, source- AND tier-filtered
    eu = index.similarity_search(
        query_text=query,
        columns=["chunk_id", "document_section", "section_title", "chunk_text",
                 "risk_tier", "applicable_role", "compliance_deadline", "source_url"],
        filters={"source": "eu_ai_act", "risk_tier": _tier_filter(risk_tier)},
        num_results=num_results,
    )

    # Track 2 — NIST (RMF + Playbook), source-filtered (no tier concept)
    nist = index.similarity_search(
        query_text=query,
        columns=["chunk_id", "document_section", "section_title", "chunk_text",
                 "framework_function", "subcategory_id", "source_url"],
        filters={"source": ["nist_ai_rmf", "nist_playbook"]},
        num_results=num_results,
    )

    return {
        "eu_ai_act": eu["result"]["data_array"],
        "eu_columns": [c["name"] for c in eu["manifest"]["columns"]],
        "nist_rmf": nist["result"]["data_array"],
        "nist_columns": [c["name"] for c in nist["manifest"]["columns"]],
    }