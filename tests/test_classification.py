"""
Phase 5 gate: full scenario suite (S1-S10) spanning all four risk tiers
and edge cases, loaded from test_scenarios.json, plus the original 4 unit
tests. Run: python tests/test_classification.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.classification_engine import classify_risk_tier, SystemIntake, RiskTier

_SCENARIOS = os.path.join(os.path.dirname(__file__), "test_scenarios.json")


def _intake(**kw) -> SystemIntake:
    defaults = dict(
        system_name="x", description="", domain="general", ai_type="classification",
        decision_impact="advisory", data_types=["none"], intended_purpose="",
        deployment_geography=["EU"],
    )
    defaults.update(kw)
    return SystemIntake(**defaults)


# ── Original 4 unit tests (kept) ─────────────────────────────────────────
def test_prohibited_emotion_recognition_hr():
    r = classify_risk_tier(_intake(system_name="MoodTrack", domain="HR",
        description="Emotion recognition system monitoring employee emotional state during work hours",
        intended_purpose="Workplace productivity monitoring"))
    assert r.risk_tier == RiskTier.PROHIBITED and r.primary_basis == "Art. 5(1)(f)", r


def test_high_risk_insurance_claims_triage():
    r = classify_risk_tier(_intake(system_name="Claims Triage Model", domain="insurance",
        decision_impact="fully_automated", data_types=["personal", "financial"],
        description="Automated triage of insurance claims, scoring claims for eligibility and fraud risk assessment",
        intended_purpose="Accelerate claims processing decisions"))
    assert r.risk_tier == RiskTier.HIGH_RISK and r.primary_basis == "Annex III(5)(b)", r


def test_limited_risk_customer_chatbot():
    r = classify_risk_tier(_intake(system_name="HelpBot", ai_type="generative",
        interacts_with_humans=True,
        description="Customer service chatbot answering product questions in natural conversation",
        intended_purpose="Reduce support ticket volume"))
    assert r.risk_tier == RiskTier.LIMITED_RISK and r.primary_basis == "Art. 50(1)", r


def test_minimal_risk_inventory_forecast():
    r = classify_risk_tier(_intake(system_name="StockCast", ai_type="prediction",
        description="Forecasts warehouse inventory demand from historical sales data",
        intended_purpose="Supply chain planning"))
    assert r.risk_tier == RiskTier.MINIMAL_RISK, r


# ── Scenario suite S1-S10 from JSON ──────────────────────────────────────
def run_scenarios() -> int:
    with open(_SCENARIOS) as f:
        scenarios = json.load(f)

    failures = 0
    print(f"\nScenario suite ({len(scenarios)} scenarios):")
    for s in scenarios:
        intake = _intake(**s["intake"])
        r = classify_risk_tier(intake)
        tier = r.risk_tier.value

        # S10 (GPAI) is a documented edge case — report, don't assert
        if s["expected_tier"] == "documented":
            print(f"  {s['id']} {s['name']}: tier={tier}, basis={r.primary_basis} "
                  f"(edge case — documented, confidence={r.confidence})")
            continue

        tier_ok = tier == s["expected_tier"]
        basis_ok = (s["expected_basis"] is None) or (r.primary_basis == s["expected_basis"])
        ok = tier_ok and basis_ok
        failures += 0 if ok else 1
        status = "PASS" if ok else "FAIL"
        detail = "" if ok else f"  [got tier={tier}, basis={r.primary_basis}]"
        print(f"  {s['id']} {status}: {s['name']} -> {tier} / {r.primary_basis}{detail}")
    return failures


if __name__ == "__main__":
    unit_failures = 0
    print("Unit tests:")
    for name, fn in sorted({k: v for k, v in globals().items()
                            if k.startswith("test_")}.items()):
        try:
            fn(); print(f"  PASS  {name}")
        except AssertionError as e:
            unit_failures += 1; print(f"  FAIL  {name}\n        {e}")

    scenario_failures = run_scenarios()

    total = unit_failures + scenario_failures
    print(f"\n{'='*50}")
    print(f"Unit: {4-unit_failures}/4 pass | Scenarios: check above")
    print("ALL PASS ✓" if total == 0 else f"{total} FAILURE(S) — review above")
    sys.exit(1 if total else 0)