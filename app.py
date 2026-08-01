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

def _render_stored(row):
    """Render a stored assessment from its log row (strings, not objects)."""
    st.subheader(f"{row['system_name']}  ·  {str(row['created_at'])[:19]} UTC")
    badge = {"prohibited": "🔴", "high_risk": "🟠",
             "limited_risk": "🟡", "minimal_risk": "🟢"}
    st.markdown(f"{badge.get(row['risk_tier'], '⚪')} "
                f"**{row['risk_tier'].replace('_', ' ').title()}** — {row['primary_basis']}")
    st.caption(f"Classifier {row['classifier_version']} · corpus v{row['corpus_table_version']} · "
               f"synthesis {row['synthesis_status']} · id {row['assessment_id']}")

    am = row.get("all_matches")
    am = list(am) if am is not None else []   # connector may return a numpy array
    if am:
        st.markdown("**Rule trail:** " + " ; ".join(str(x) for x in am))

    rep = {}
    try:
        rep = json.loads(row["report"]) if row.get("report") else {}
    except Exception:
        pass
    if row["synthesis_status"] != "ok" or not rep.get("eu_ai_act_obligations"):
        st.info(f"No synthesized report stored (synthesis status: {row['synthesis_status']}).")
        return
    with st.expander("EU AI Act obligations", expanded=True):
        for ob in rep.get("eu_ai_act_obligations", []):
            st.markdown(f"- **{ob.get('article', '')}** — {ob.get('requirement', '')}  \n"
                        f"  {ob.get('summary', '')}  \n  *{ob.get('citation', '')}*")
    with st.expander("NIST AI RMF mapping"):
        for m in rep.get("nist_rmf_mapping", []):
            st.markdown(f"- **{m.get('subcategory', '')}** — {m.get('outcome', '')}")
    with st.expander("Cross-framework checklist"):
        rows_ = rep.get("cross_framework_checklist", [])
        if rows_:
            st.table([{"EU": r.get("eu_requirement", ""),
                       "NIST": r.get("nist_mapping", ""),
                       "Action": r.get("implementation_action", "")} for r in rows_])

# ── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.warning(f"**Disclaimer**\n\n{DISCLAIMER}")
    st.markdown("---")
    st.markdown("**Built on Databricks**")
    st.caption("BGE embeddings · Llama 3.3 70B synthesis · deterministic classifier")
    st.markdown("---")
    st.markdown("**Feedback**")
    st.markdown(
        "Found this useful, have questions, or want a walkthrough? "
        "[Reach out on LinkedIn](https://www.linkedin.com/in/YOUR-LINKEDIN)"
    )
    if not DEMO_MODE:
        st.caption("Assessments are logged for audit and reproducibility.")

st.title("⚖️ AI Compliance Navigator")
st.markdown("*Regulatory mapping for the EU AI Act and NIST AI RMF*")
st.markdown("---")

if DEMO_MODE:
    tab_intake, tab_report = st.tabs(["📝 System Intake", "📊 Compliance Report"])
else:
    tab_intake, tab_report, tab_history = st.tabs(
        ["📝 System Intake", "📊 Compliance Report", "📜 Past Assessments"])

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
                import time as _time
                from src.audit_log import log_assessment
                if "sid" not in st.session_state:
                    import uuid as _uuid
                    st.session_state.sid = str(_uuid.uuid4())[:8]
                t0 = _time.perf_counter()
                retrieved, report, status = None, None, "fallback"
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
                    status = "parse_error" if "_parse_error" in report else "ok"
                    st.session_state.update(clf=clf, report=report,
                                            system_name=system_name, demo=False)
                    st.success("Analysis complete — see the Compliance Report tab.")
                except Exception as e:
                    sample = _load_sample_report()
                    st.session_state.update(clf=clf, report=sample["report"],
                                            system_name=system_name, demo=True)
                    report = {"_error": str(e)[:500]}
                    st.warning("Live backend unavailable — showing a pre-generated sample "
                               "report. (Run locally with Databricks credentials for live analysis.)")
                    st.caption(f"Backend detail: {str(e)[:200]}")

                latency_ms = (_time.perf_counter() - t0) * 1000
                aid = log_assessment(intake, clf, retrieved, report, status,
                                     latency_ms, session_id=st.session_state.sid)
                if aid:
                    st.caption(f"Assessment logged: {aid}")

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

# ── Past Assessments (v2 Phase 3) — live mode only ───────────────────────
if not DEMO_MODE:
    with tab_history:
        st.header("Past Assessments")
        st.caption("Every live assessment is logged with its rule trail, classifier "
                   "version, and corpus version — reproducible via Delta time travel.")
        from src.audit_log import (list_assessments, get_assessment,
                                   diff_assessments, current_corpus_version,
                                   log_assessment as _log2)
        from src.utils import CLASSIFIER_VERSION

        if st.button("🔄 Load / refresh history"):
            try:
                st.session_state.history_rows = list_assessments()
                st.session_state.pop("opened", None)
                st.session_state.pop("diff", None)
            except Exception as e:
                st.error("Could not reach the assessment log.")
                st.caption(f"Detail: {str(e)[:200]}")

        rows = st.session_state.get("history_rows")
        if rows is None:
            st.info("Click Load / refresh to fetch your assessment history.")
        elif not rows:
            st.info("No assessments logged yet — run one from the System Intake tab.")
        else:
            st.dataframe(
                [{"when": str(r["created_at"])[:19], "system": r["system_name"],
                  "tier": r["risk_tier"], "basis": r["primary_basis"],
                  "classifier": r["classifier_version"], "status": r["synthesis_status"]}
                 for r in rows],
                use_container_width=True, hide_index=True)

            labels = {f"{r['system_name']} · {r['risk_tier']} · clf {r['classifier_version']} · "
                      f"{str(r['created_at'])[:19]} · {r['assessment_id'][:8]}": r["assessment_id"]
                      for r in rows}
            sel = st.selectbox("Open an assessment", list(labels.keys()))
            aid = labels[sel]
            if st.button("📂 Open stored report"):
                st.session_state.opened = get_assessment(aid)
                st.session_state.pop("diff", None)

            opened = st.session_state.get("opened")
            if opened and opened["assessment_id"] == aid:
                _render_stored(opened)
                st.markdown("---")
                st.subheader("Re-run against current rules & corpus")
                st.caption(f"Stored under classifier {opened['classifier_version']}, "
                           f"corpus v{opened['corpus_table_version']}. "
                           f"Current classifier: {CLASSIFIER_VERSION}.")
                if st.button("⚖️ Re-run and diff"):
                    import time as _time
                    intake_d = json.loads(opened["intake"])
                    intake2 = SystemIntake(**intake_d)
                    clf2 = classify_risk_tier(intake2)
                    t0 = _time.perf_counter()
                    status2, retrieved2, report2 = "fallback", None, None
                    try:
                        with st.spinner("Re-running retrieval + synthesis..."):
                            from src.retrieval import retrieve_compliance_requirements
                            from src.llm_synthesis import synthesize_compliance_report
                            retrieved2 = retrieve_compliance_requirements(
                                system_description=f"{intake2.description}. Purpose: {intake2.intended_purpose}",
                                risk_tier=clf2.risk_tier.value)
                            report2 = synthesize_compliance_report(
                                system_description=f"{intake2.system_name}: {intake2.description}",
                                classification={"risk_tier": clf2.risk_tier.value,
                                    "primary_basis": clf2.primary_basis,
                                    "reasoning": clf2.reasoning},
                                retrieved=retrieved2)
                        status2 = "parse_error" if "_parse_error" in report2 else "ok"
                    except Exception as e:
                        report2 = {"_error": str(e)[:500]}
                        st.warning("Backend unavailable — re-run could not complete.")
                    lat2 = (_time.perf_counter() - t0) * 1000
                    aid2 = _log2(intake2, clf2, retrieved2, report2, status2, lat2,
                                 session_id=st.session_state.get("sid"))
                    if aid2:
                        st.caption(f"Re-run logged: {aid2}")
                    old_report = {}
                    try:
                        old_report = json.loads(opened["report"]) if opened.get("report") else {}
                    except Exception:
                        pass
                    st.session_state.diff = diff_assessments(
                        opened, old_report, clf2, report2 or {},
                        CLASSIFIER_VERSION, current_corpus_version())

                d = st.session_state.get("diff")
                if d:
                    st.markdown("#### What changed")
                    st.markdown(("🟢 **Tier:** unchanged — " + d["tier_new"])
                                if not d["tier_changed"]
                                else f"🔴 **Tier CHANGED:** {d['tier_old']} → {d['tier_new']}")
                    st.markdown(("🟢 **Basis:** unchanged — " + d["basis_new"])
                                if not d["basis_changed"]
                                else f"🟠 **Basis CHANGED:** {d['basis_old']} → {d['basis_new']}")
                    st.markdown(f"**Classifier:** {d['classifier_old']} → {d['classifier_new']} "
                                f"&nbsp;|&nbsp; **Corpus:** v{d['corpus_old']} → v{d['corpus_new']}")
                    c3, c4 = st.columns(2)
                    with c3:
                        st.markdown("**EU obligations added**")
                        st.write(d["eu_added"] or "—")
                        st.markdown("**EU obligations removed**")
                        st.write(d["eu_removed"] or "—")
                    with c4:
                        st.markdown("**NIST subcategories added**")
                        st.write(d["nist_added"] or "—")
                        st.markdown("**NIST subcategories removed**")
                        st.write(d["nist_removed"] or "—")
                    st.caption("Tier, basis, and versions are deterministic. Obligation-level "
                               "deltas can also reflect synthesis variability — treat as indicative.")