"""Phase 2 gate: 4 seed systems spanning all four risk tiers."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.classification_engine import classify_risk_tier, SystemIntake, RiskTier


def _intake(**kw) -> SystemIntake:
    defaults = dict(
        system_name="x", description="", domain="general", ai_type="classification",
        decision_impact="advisory", data_types=["none"], intended_purpose="",
        deployment_geography=["EU"],
    )
    defaults.update(kw)
    return SystemIntake(**defaults)


def test_prohibited_emotion_recognition_hr():
    r = classify_risk_tier(_intake(
        system_name="MoodTrack",
        domain="HR",
        description="Emotion recognition system monitoring employee emotional state during work hours",
        intended_purpose="Workplace productivity monitoring",
    ))
    assert r.risk_tier == RiskTier.PROHIBITED, r
    assert r.primary_basis == "Art. 5(1)(f)", r


def test_high_risk_insurance_claims_triage():
    # The demo scenario — must classify high-risk under Annex III(5)(b)
    r = classify_risk_tier(_intake(
        system_name="Claims Triage Model",
        domain="insurance",
        ai_type="classification",
        decision_impact="fully_automated",
        data_types=["personal", "financial"],
        description="Automated triage of insurance claims, scoring claims for eligibility and fraud risk assessment",
        intended_purpose="Accelerate claims processing decisions",
    ))
    assert r.risk_tier == RiskTier.HIGH_RISK, r
    assert r.primary_basis == "Annex III(5)(b)", r
    assert any("Article 9" in a for a in r.applicable_articles), r


def test_limited_risk_customer_chatbot():
    r = classify_risk_tier(_intake(
        system_name="HelpBot",
        domain="general",
        ai_type="generative",
        interacts_with_humans=True,
        description="Customer service chatbot answering product questions in natural conversation",
        intended_purpose="Reduce support ticket volume",
    ))
    assert r.risk_tier == RiskTier.LIMITED_RISK, r
    assert r.primary_basis == "Art. 50(1)", r


def test_minimal_risk_inventory_forecast():
    r = classify_risk_tier(_intake(
        system_name="StockCast",
        domain="general",
        ai_type="prediction",
        description="Forecasts warehouse inventory demand from historical sales data",
        intended_purpose="Supply chain planning",
    ))
    assert r.risk_tier == RiskTier.MINIMAL_RISK, r


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}\n      {e}")
    sys.exit(1 if failures else 0)