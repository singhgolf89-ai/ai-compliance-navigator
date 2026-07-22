"""
AI Compliance Navigator — Streamlit frontend.
Intake form -> deterministic classification -> filtered retrieval ->
grounded LLM synthesis -> tabbed report with Markdown export.

Run locally:  streamlit run app.py
Auth: reads Databricks host + token from .streamlit/secrets.toml (gitignored).
"""

import sys, os
from datetime import datetime

# Make src/ importable when run from the repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from src.classification_engine import classify_risk_tier, SystemIntake

st.set_page_config(page_title="AI Compliance Navigator", page_icon="⚖️", layout="wide")

DISCLAIMER = (
    "This tool provides regulatory mapping for informational purposes only. "
    "It does not constitute legal advice. Consult qualified legal counsel for "
    "compliance determinations."
)

import json

def _load_sample_report():
    """Load the pre-generated demo report (real pipeline output, captured offline)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample_report.json")
    with open(path) as f:
        return json.load(f)

# Demo mode: set DEMO_MODE = "true" in secrets to force sample output (e.g. public
# deployment), OR the app falls back to the sample automatically if the backend fails.
DEMO_MODE = str(st.secrets.get("DEMO_MODE", "false")).lower() == "true"

def _to_markdown(name, clf, report):
    md = [f"# AI Compliance Report: {name}",
          f"\n*Generated: {datetime.now():%Y-%m-%d %H:%M}*\n",
          "> **Disclaimer:** " + DISCLAIMER + "\n", "---\n",
          "## Risk Classification\n",
          f"- **Tier:** {clf.risk_tier.value.replace('_',' ').title()}",
          f"- **Basis:** {clf.primary_basis}",
          f"- **Role:** {clf.applicable_role.value.title()}",
          f"- **Deadline:** {clf.compliance_deadline}\n"]
    rc = report.get("risk_classification", {})
    if rc.get("plain_language"):
        md.append(f"**In plain language:** {rc['plain_language']}\n")
    md.append("---\n## EU AI Act Obligations\n")
    for ob in report.get("eu_ai_act_obligations", []):
        md += [f"### {ob.get('article','')}: {ob.get('requirement','')}",
               f"{ob.get('summary','')}\n",
               f"- Role: {str(ob.get('role','')).title()}",
               f"- Citation: {ob.get('citation','')}\n"]
    md.append("---\n## NIST AI RMF Mapping\n")
    for m in report.get("nist_rmf_mapping", []):
        md += [f"### {m.get('subcategory','')}", f"**Outcome:** {m.get('outcome','')}\n"]
        for a in m.get("suggested_actions", []):
            md.append(f"- {a}")
        md.append(f"\n*Citation: {m.get('citation','')}*\n")
    md.append("---\n## Cross-Framework Checklist\n")
    md.append("| EU AI Act Requirement | NIST RMF Mapping | Implementation Action |")
    md.append("|---|---|---|")
    for r in report.get("cross_framework_checklist", []):
        md.append(f"| {r.get('eu_requirement','')} | {r.get('nist_mapping','')} | {r.get('implementation_action','')} |")
    md.append("\n---\n*Informational only; not legal advice.*")
    return "\n".join(md)


# ── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.warning(f"**Disclaimer**\n\n{DISCLAIMER}")
    st.markdown("---")
    st.markdown("**Built on Databricks**")
    st.caption("BGE embeddings · Llama 3.3 70B synthesis · deterministic classifier")

st.title("⚖️ AI Compliance Navigator")
st.markdown("*Regulatory mapping for the EU AI Act and NIST AI RMF*")
st.markdown("---")

tab_intake, tab_report = st.tabs(["📝 System Intake", "📊 Compliance Report"])

# ── Intake form ──────────────────────────────────────────────────────────
with tab_intake:
    st.header("Describe your AI system")
    c1, c2 = st.columns(2)
    with c1:
        system_name = st.text_input("System Name", placeholder="e.g., Claims Triage Model")
        domain = st.selectbox("Domain / Industry",
            ["insurance", "banking", "financial", "healthcare", "HR",
             "law_enforcement", "education", "government", "general"])
        ai_type = st.selectbox("AI Type",
            ["classification", "prediction", "generative", "recommendation",
             "computer_vision", "nlp", "other"])
        decision_impact = st.selectbox("Decision Impact",
            ["fully_automated", "human_in_loop", "advisory"],
            format_func=lambda x: {"fully_automated": "Fully Automated",
                "human_in_loop": "Human-in-the-Loop", "advisory": "Advisory / Support"}[x])
    with c2:
        data_types = st.multiselect("Data Types Processed",
            ["personal", "biometric", "health", "financial", "criminal",
             "children", "none"], default=["none"])
        deployment_geography = st.multiselect("Deployment Geography",
            ["EU", "US", "both", "other"], default=["EU"])
        interacts = st.checkbox("Interacts directly with humans (chatbot, voice assistant)")
        synthetic = st.checkbox("Generates synthetic content (text, images, video)")

    description = st.text_area("System Description",
        placeholder="What the system does, how it decides, its intended use case...",
        height=140)
    intended_purpose = st.text_area("Intended Purpose",
        placeholder="What problem it solves; who the end users are...", height=90)

    if st.button("🔍 Analyze Compliance Requirements", type="primary", use_container_width=True):
        if not system_name or not description:
            st.error("Please provide at least a system name and description.")
        else:
            intake = SystemIntake(
                system_name=system_name, description=description, domain=domain,
                ai_type=ai_type, decision_impact=decision_impact,
                data_types=data_types or ["none"], intended_purpose=intended_purpose,
                deployment_geography=deployment_geography or ["EU"],
                interacts_with_humans=interacts, generates_synthetic_content=synthetic,
            )
            # Step 1: deterministic classification (instant, no backend)
            clf = classify_risk_tier(intake)

           # Steps 2-3 hit Databricks. Demo-mode (or backend failure) serves a
            # pre-generated real report so the public URL always works.
            if DEMO_MODE:
                sample = _load_sample_report()
                st.session_state.update(clf=clf, report=sample["report"],
                                        system_name=system_name, demo=True)
                st.info("Demo mode: showing a pre-generated sample report. "
                        "Run locally with Databricks credentials for live analysis.")
                st.success("Sample report ready — see the Compliance Report tab.")
            else:
                try:
                    with st.spinner("Retrieving regulatory provisions and synthesizing report..."):
                        from src.retrieval import retrieve_compliance_requirements
                        from src.llm_synthesis import synthesize_compliance_report
                        retrieved = retrieve_compliance_requirements(
                            system_description=f"{description}. Purpose: {intended_purpose}",
                            risk_tier=clf.risk_tier.value)
                        report = synthesize_compliance_report(
                            system_description=f"{system_name}: {description}",
                            classification={"risk_tier": clf.risk_tier.value,
                                "primary_basis": clf.primary_basis, "reasoning": clf.reasoning},
                            retrieved=retrieved)
                    st.session_state.update(clf=clf, report=report,
                                            system_name=system_name, demo=False)
                    st.success("Analysis complete — see the Compliance Report tab.")
                except Exception as e:
                    # Backend unreachable -> fall back to the sample rather than erroring
                    sample = _load_sample_report()
                    st.session_state.update(clf=clf, report=sample["report"],
                                            system_name=system_name, demo=True)
                    st.warning("Live backend unavailable — showing a pre-generated sample "
                               "report. (Run locally with Databricks credentials for live analysis.)")
                    st.caption(f"Backend detail: {str(e)[:200]}")

# ── Report ───────────────────────────────────────────────────────────────
with tab_report:
    if "report" not in st.session_state:
        st.info("Submit an AI system in the Intake tab to generate a report.")
    else:
        clf = st.session_state["clf"]
        report = st.session_state["report"]
        name = st.session_state["system_name"]

        if "_parse_error" in report:
            st.error("The model returned malformed output. Please re-run the analysis.")
            st.caption(f"Parse error: {report['_parse_error']}")
            st.stop()

        st.header(f"Compliance Report: {name}")
        badge = {"prohibited": "🔴", "high_risk": "🟠",
                 "limited_risk": "🟡", "minimal_risk": "🟢"}
        tier = clf.risk_tier.value
        st.subheader(f"{badge.get(tier,'⚪')} Risk Classification: {tier.replace('_',' ').title()}")
        c1, c2 = st.columns(2)
        c1.markdown(f"**Basis:** {clf.primary_basis}")
        c1.markdown(f"**Role:** {clf.applicable_role.value.title()}")
        c2.markdown(f"**Deadline:** {clf.compliance_deadline}")
        c2.markdown(f"**Confidence:** {clf.confidence.title()}")
        rc = report.get("risk_classification", {})
        if rc.get("plain_language"):
            st.info(f"**In plain language:** {rc['plain_language']}")
        st.markdown("---")

        t1, t2, t3, t4 = st.tabs(["EU AI Act Obligations", "NIST RMF Mapping",
                                  "Cross-Framework Checklist", "Export"])
        with t1:
            for ob in report.get("eu_ai_act_obligations", []):
                with st.expander(f"📜 {ob.get('article','')}: {ob.get('requirement','')}"):
                    st.markdown(f"**Summary:** {ob.get('summary','')}")
                    st.markdown(f"**Role:** {str(ob.get('role','')).title()}")
                    st.caption(f"Citation: {ob.get('citation','')}")
        with t2:
            for m in report.get("nist_rmf_mapping", []):
                with st.expander(f"🔷 {m.get('subcategory','')}: {str(m.get('outcome',''))[:60]}"):
                    st.markdown(f"**Function:** {m.get('function','')}")
                    st.markdown(f"**Outcome:** {m.get('outcome','')}")
                    for a in m.get("suggested_actions", []):
                        st.markdown(f"- {a}")
                    st.caption(f"Citation: {m.get('citation','')}")
        with t3:
            rows = report.get("cross_framework_checklist", [])
            if rows:
                st.table([{"EU AI Act Requirement": r.get("eu_requirement",""),
                           "NIST RMF Mapping": r.get("nist_mapping",""),
                           "Implementation Action": r.get("implementation_action","")}
                          for r in rows])
        with t4:
            md = _to_markdown(name, clf, report)
            st.download_button("📥 Download as Markdown", data=md,
                file_name=f"{name.replace(' ','_')}_compliance_report.md",
                mime="text/markdown")
            with st.expander("Preview"):
                st.code(md, language="markdown")