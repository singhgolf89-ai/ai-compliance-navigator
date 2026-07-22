"""
Deterministic EU AI Act risk classification engine.
Rule-based and auditable — NOT LLM-dependent. The LLM never classifies;
it only retrieves and synthesizes. This file is the reason that sentence
is true.

Deadline strings are placeholders pending verification against EUR-Lex
(Regulation (EU) 2024/1689, Art. 113). Never present as legal fact.
"""

from dataclasses import dataclass, field
from typing import List
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
    domain: str                          # insurance, banking, healthcare, HR, law_enforcement, education, government, general
    ai_type: str                         # classification, prediction, generative, recommendation, computer_vision, nlp, other
    decision_impact: str                 # fully_automated, human_in_loop, advisory
    data_types: List[str]                # personal, biometric, health, financial, criminal, children, none
    intended_purpose: str
    deployment_geography: List[str]      # EU, US, both, other

    interacts_with_humans: bool = False
    generates_synthetic_content: bool = False
    is_safety_component: bool = False


@dataclass
class ClassificationResult:
    """Output of the classification engine."""
    risk_tier: RiskTier
    primary_basis: str                   # e.g., "Annex III(5)(b)"
    applicable_articles: List[str]
    applicable_role: Role
    compliance_deadline: str
    reasoning: str
    confidence: str                      # 'high', 'medium', 'requires_review'
    all_matches: List[str] = field(default_factory=list)  # every rule that fired


def _text(intake: SystemIntake) -> str:
    """Search surface: description + intended purpose, lowercased."""
    return f"{intake.description} {intake.intended_purpose}".lower()


def classify_risk_tier(intake: SystemIntake) -> ClassificationResult:
    """
    Rule-based EU AI Act risk classification.
    Evaluation order mirrors the Act's own logic: prohibited practices
    first (Art. 5), then high-risk (Art. 6 / Annex III), then transparency
    (Art. 50), else minimal risk.
    """
    t = _text(intake)

    # ═════════════════════════════════════════════════════════════════
    # STEP 1: Prohibited practices (Article 5)
    # ═════════════════════════════════════════════════════════════════
    prohibited = []

    if "subliminal" in t or "manipulat" in t:
        prohibited.append(("Art. 5(1)(a)", "Subliminal or manipulative techniques"))

    if any(kw in t for kw in ["vulnerable", "disability", "elderly", "children"]) and "exploit" in t:
        prohibited.append(("Art. 5(1)(b)", "Exploitation of vulnerabilities"))

    if intake.domain == "government" and "social scor" in t:
        prohibited.append(("Art. 5(1)(c)", "Social scoring by public authorities"))

    if (intake.domain == "law_enforcement"
            and "biometric" in intake.data_types
            and "real-time" in t):
        prohibited.append(("Art. 5(1)(d)", "Real-time remote biometric ID for law enforcement"))

    if (any(kw in t for kw in ["emotion recognition", "emotion detection", "emotional state"])
            and intake.domain in ["HR", "education", "workplace"]):
        prohibited.append(("Art. 5(1)(f)", "Emotion recognition in workplace/education"))

    if prohibited:
        return ClassificationResult(
            risk_tier=RiskTier.PROHIBITED,
            primary_basis=prohibited[0][0],
            applicable_articles=["Article 5"],
            applicable_role=Role.PROVIDER,
            compliance_deadline="2 February 2025 (in effect; Art. 113(a))",
            reasoning=f"System falls under prohibited practice: {prohibited[0][1]}",
            confidence="high",
            all_matches=[f"{b} — {d}" for b, d in prohibited],
        )

    # ═════════════════════════════════════════════════════════════════
    # STEP 2: High-risk via Annex III categories
    # ═════════════════════════════════════════════════════════════════
    high_risk = []

    if "biometric" in intake.data_types:
        if "identification" in t:
            high_risk.append(("Annex III(1)(a)", "Remote biometric identification"))
        if "categori" in t:
            high_risk.append(("Annex III(1)(b)", "Biometric categorization"))

    if any(kw in t for kw in ["energy", "water", "gas", "heating", "traffic", "transport"]):
        if intake.is_safety_component:
            high_risk.append(("Annex III(2)", "Safety component of critical infrastructure"))

    if intake.domain == "education":
        if any(kw in t for kw in ["admission", "assessment", "exam", "grade", "learning outcome"]):
            high_risk.append(("Annex III(3)", "Access to or assessment in education"))

    if intake.domain in ["HR", "employment", "workforce"]:
        if any(kw in t for kw in ["recruit", "hiring", "screening", "candidate", "resume", "cv",
                                  "task allocation", "monitor", "evaluat", "promotion", "termination"]):
            high_risk.append(("Annex III(4)(a)", "Recruitment and selection / worker management"))

    if intake.domain in ["insurance", "banking", "financial"]:
        if any(kw in t for kw in ["creditworth", "credit scor", "insurance pric", "risk assessment",
                                  "premium", "underwriting", "claims", "eligibility"]):
            high_risk.append(("Annex III(5)(b)", "Creditworthiness / insurance risk assessment"))

    if intake.domain == "law_enforcement":
        if any(kw in t for kw in ["risk assessment", "evidence", "crime predict", "profil"]):
            high_risk.append(("Annex III(6)", "Law enforcement AI"))

    if any(kw in t for kw in ["asylum", "visa", "border", "migration", "refugee"]):
        high_risk.append(("Annex III(7)", "Migration, asylum and border control"))

    if any(kw in t for kw in ["judicial", "sentencing", "court", "legal research", "dispute"]):
        high_risk.append(("Annex III(8)", "Administration of justice"))

    if high_risk:
        role = Role.PROVIDER
        if "deploy" in t or "using" in t or "we use" in t:
            role = Role.DEPLOYER

        articles = [
            "Article 6 (High-risk classification)",
            "Article 9 (Risk management system)",
            "Article 10 (Data and data governance)",
            "Article 11 (Technical documentation)",
            "Article 12 (Record-keeping)",
            "Article 13 (Transparency and provision of information)",
            "Article 14 (Human oversight)",
            "Article 15 (Accuracy, robustness and cybersecurity)",
        ]
        if role == Role.DEPLOYER:
            articles.append("Article 26 (Obligations of deployers)")

        return ClassificationResult(
            risk_tier=RiskTier.HIGH_RISK,
            primary_basis=high_risk[0][0],
            applicable_articles=articles,
            applicable_role=role,
            compliance_deadline="2 August 2026 (Art. 113; general application)",
            reasoning=f"System matches high-risk use case: {high_risk[0][1]}",
            confidence="high",
            all_matches=[f"{b} — {d}" for b, d in high_risk],
        )

    # ═════════════════════════════════════════════════════════════════
    # STEP 3: Limited risk (Article 50 transparency)
    # ═════════════════════════════════════════════════════════════════
    limited = []

    if intake.interacts_with_humans or intake.ai_type in ["generative", "nlp"]:
        if any(kw in t for kw in ["chatbot", "assistant", "customer service", "conversation", "dialogue"]):
            limited.append(("Art. 50(1)", "AI system interacting directly with humans"))

    if intake.generates_synthetic_content or intake.ai_type == "generative":
        if any(kw in t for kw in ["generat", "synthetic", "deepfake", "create content", "produce text"]):
            limited.append(("Art. 50(2)", "AI-generated or manipulated content"))

    if limited:
        return ClassificationResult(
            risk_tier=RiskTier.LIMITED_RISK,
            primary_basis=limited[0][0],
            applicable_articles=["Article 50 (Transparency obligations)"],
            applicable_role=Role.PROVIDER,
            compliance_deadline="2 August 2026 (Art. 50; general application)",
            reasoning=f"System triggers transparency obligations: {limited[0][1]}",
            confidence="high",
            all_matches=[f"{b} — {d}" for b, d in limited],
        )

    # ═════════════════════════════════════════════════════════════════
    # STEP 4: Default — minimal risk
    # ═════════════════════════════════════════════════════════════════
    return ClassificationResult(
        risk_tier=RiskTier.MINIMAL_RISK,
        primary_basis="No prohibited, Annex III, or Art. 50 criteria matched",
        applicable_articles=["No mandatory requirements (voluntary codes encouraged, Art. 95)"],
        applicable_role=Role.PROVIDER,
        compliance_deadline="N/A",
        reasoning="System does not match prohibited, high-risk, or limited-risk criteria",
        confidence="medium",
        all_matches=[],
    )