"""
Grounded LLM synthesis: turns the deterministic classification + retrieved
chunks into a structured, cited compliance report.

Design guarantees (the credibility centerpiece):
- The LLM NEVER classifies — the risk tier is passed in from the rule engine.
- The LLM only synthesizes RETRIEVED text; every requirement carries a citation.
- Missing coverage yields the fixed "not addressed" sentence, never invention.
- Output is strict JSON, parsed defensively (open models fence/pad JSON).
"""

import json
import re
from src.utils import (get_deploy_client, LLM_ENDPOINT, LLM_FALLBACK,
                       LLM_MAX_TOKENS, LLM_TEMPERATURE)

_NOT_ADDRESSED = "Not addressed in retrieved sources — manual review recommended."

SYSTEM_PROMPT = """You are an AI compliance analyst specializing in the EU AI Act \
and the NIST AI Risk Management Framework. Given regulatory text retrieved from \
these frameworks plus a PRE-DETERMINED risk classification, produce a structured \
compliance assessment.

CRITICAL RULES:
1. Use ONLY information present in the provided regulatory text chunks. Do NOT \
invent requirements, articles, or subcategories.
2. EVERY requirement MUST carry a specific citation: [EU AI Act Art. X] or \
[NIST AI RMF FUNCTION X.Y].
3. If the retrieved text lacks relevant information for a section, use exactly: \
"%s"
4. Do NOT provide legal advice. This is a regulatory mapping for review by \
qualified counsel.
5. The risk classification is GIVEN — do not re-classify. Explain the obligations \
that follow from it.
6. Return ONLY valid JSON matching the schema. No prose before or after, no \
markdown code fences.

OUTPUT SCHEMA:
{
  "risk_classification": {
    "tier": "<given tier>",
    "basis": "<given basis>",
    "plain_language": "One sentence a non-specialist understands."
  },
  "eu_ai_act_obligations": [
    {"article": "Article 9", "requirement": "Risk management system",
     "summary": "<from retrieved text>", "role": "provider",
     "citation": "[EU AI Act Art. 9]"}
  ],
  "nist_rmf_mapping": [
    {"subcategory": "GOVERN 1.1", "function": "GOVERN",
     "outcome": "<from retrieved text>",
     "suggested_actions": ["<action>"], "citation": "[NIST AI RMF GOVERN 1.1]"}
  ],
  "cross_framework_checklist": [
    {"eu_requirement": "Risk management [Art. 9]",
     "nist_mapping": "MAP 1.1, MANAGE 1.1",
     "implementation_action": "<concrete action>"}
  ]
}""" % _NOT_ADDRESSED


def _format_chunks(rows: list, columns: list) -> str:
    """Render retrieved rows as labeled context blocks for the prompt."""
    if not rows:
        return "(no relevant chunks retrieved)"
    ci = {name: i for i, name in enumerate(columns)}
    out = []
    for r in rows:
        section = r[ci.get("document_section", ci.get("subcategory_id", 0))]
        title = r[ci["section_title"]] if "section_title" in ci else ""
        text = r[ci["chunk_text"]] if "chunk_text" in ci else ""
        out.append(f"--- {section}: {title} ---\n{text}")
    return "\n\n".join(out)


def _extract_json(text: str) -> dict:
    """Parse JSON defensively — open models sometimes fence or pad output."""
    t = text.strip()
    if "```" in t:                       # strip ```json ... ``` fences
        t = re.sub(r"^```(?:json)?", "", t).strip()
        t = re.sub(r"```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")   # clip to outermost braces
    if start != -1 and end != -1:
        t = t[start:end + 1]
    return json.loads(t)


def synthesize_compliance_report(
    system_description: str,
    classification: dict,   # {'risk_tier','primary_basis','reasoning'}
    retrieved: dict,        # output of retrieve_compliance_requirements
) -> dict:
    """Generate the structured, cited compliance report."""
    client = get_deploy_client()

    eu_ctx = _format_chunks(retrieved["eu_ai_act"], retrieved["eu_columns"])
    nist_ctx = _format_chunks(retrieved["nist_rmf"], retrieved["nist_columns"])

    user_prompt = f"""SYSTEM UNDER ASSESSMENT:
{system_description}

PRE-DETERMINED RISK CLASSIFICATION (from the rule-based engine — do not change):
- Tier: {classification['risk_tier']}
- Basis: {classification['primary_basis']}
- Reasoning: {classification['reasoning']}

RETRIEVED EU AI ACT PROVISIONS:
{eu_ctx}

RETRIEVED NIST AI RMF GUIDANCE:
{nist_ctx}

Produce the compliance report as strict JSON per the schema. Cite every \
requirement. Where retrieved text is insufficient, use the exact "not addressed" \
sentence. Return ONLY the JSON object."""

    def _call(endpoint):
        return client.predict(
            endpoint=endpoint,
            inputs={"messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                 {"role": "user", "content": user_prompt}],
                    "max_tokens": LLM_MAX_TOKENS, "temperature": LLM_TEMPERATURE},
        )

    try:
        resp = _call(LLM_ENDPOINT)
    except Exception:
        resp = _call(LLM_FALLBACK)       # 70B rate-limited -> 8B

    content = resp["choices"][0]["message"]["content"]
    try:
        return _extract_json(content)
    except json.JSONDecodeError as e:
        # Surface raw output so a bad-JSON run is diagnosable, not silent
        return {"_parse_error": str(e), "_raw_output": content[:2000]}