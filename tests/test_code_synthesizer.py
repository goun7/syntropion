"""
Tests for Spec-Driven Code Synthesizer, AST security validation, and 5 Vertical Pilot Engines.
"""

import pytest
from syntropion_core.database import db
from syntropion_core.code_synthesizer import (
    code_synthesizer,
    validate_python_code_ast,
    pilot_engines
)


@pytest.fixture(autouse=True)
def setup_seed():
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


def test_ast_security_validation_clean_code():
    clean_code = """
def calculate_vat(amount: float) -> float:
    return amount * 0.20
"""
    assert validate_python_code_ast(clean_code) is True


def test_ast_security_validation_rejects_unsafe_operations():
    unsafe_eval = "def exploit():\n    return eval('2 + 2')"
    with pytest.raises(ValueError, match="Forbidden call"):
        validate_python_code_ast(unsafe_eval)

    unsafe_system = "import os\ndef exploit():\n    os.system('rm -rf /')"
    with pytest.raises(ValueError, match="Forbidden call"):
        validate_python_code_ast(unsafe_system)


def test_code_synthesis_pipeline():
    import uuid
    idea_id = f"idea-test-synth-{uuid.uuid4().hex[:8]}"
    db.execute(
        """
        INSERT OR REPLACE INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            stake_amount_usd, stake_payment_status, status, domain_depth_score, created_at, updated_at
        ) VALUES (?, 'exp-pilot-001-radiologist', 'Surgical Pathology Bot', 'Problem statement for pathology',
                  'Pathologists', 10.00, 'CAPTURED_TO_EQUITY', 'APPROVED_FOR_SYNTHESIS', 0.92, '2026-01-01', '2026-01-01')
        """,
        (idea_id,)
    )

    result = code_synthesizer.synthesize_venture(idea_id, custom_slug="pathology-bot")
    assert result["venture_id"].startswith("ven-")
    assert result["ast_validation_passed"] is True
    assert "fastapi_router_code" in result
    assert result["openapi_spec"]["openapi"] == "3.1.0"

    venture = db.fetchone("SELECT * FROM ventures WHERE venture_id = ?", (result["venture_id"],))
    assert venture["status"] == "ALPHA_TEST"


# --- 5 Deep Vertical Pilots Tests ---

def test_pilot_radtrack_recist():
    # 1. Partial Response (<= -30%)
    res_pr = pilot_engines.execute_radtrack_recist(baseline_mm=20.0, follow_up_mm=12.0)
    assert res_pr["recist_classification"].startswith("PR")
    assert res_pr["percentage_change"] == -40.0

    # 2. Progressive Disease (>= 20% and >= 5mm)
    res_pd = pilot_engines.execute_radtrack_recist(baseline_mm=20.0, follow_up_mm=26.0)
    assert res_pd["recist_classification"].startswith("PD")
    assert res_pd["percentage_change"] == 30.0

    # 3. Complete Response
    res_cr = pilot_engines.execute_radtrack_recist(baseline_mm=15.0, follow_up_mm=0.0)
    assert res_cr["recist_classification"].startswith("CR")


def test_pilot_lexnotice_ttb():
    # 5 days passed: Obvious defect expired (2 days), hidden defect still valid (8 days)
    res = pilot_engines.execute_lexnotice_ttb("2026-09-01", "2026-09-06", 100_000.0)
    assert res["days_passed"] == 5
    assert res["is_obvious_notice_expired"] is True
    assert res["is_hidden_notice_expired"] is False
    assert res["accrued_interest_try"] > 0
    assert "İHTARNAME" in res["draft_legal_notice"]


def test_pilot_taxcross_reconciliation():
    # Matched
    res_ok = pilot_engines.execute_taxcross_reconciliation(50000.0, 50000.0)
    assert res_ok["is_fully_reconciled"] is True
    assert res_ok["potential_penalty_risk_try"] == 0.0

    # Discrepancy
    res_err = pilot_engines.execute_taxcross_reconciliation(50000.0, 40000.0)
    assert res_err["is_fully_reconciled"] is False
    assert res_err["discrepancy_try"] == 10000.0
    assert res_err["potential_penalty_risk_try"] > 0


def test_pilot_tarifa_customs():
    res_poly = pilot_engines.execute_tarifa_customs_gtip("Polietilen plastik granül hammadde", "CN")
    assert res_poly["determined_gtip_12_digit"] == "3901.10.10.00.11"
    assert res_poly["standard_duty_pct"] == 6.5

    res_steel = pilot_engines.execute_tarifa_customs_gtip("Sıcak haddelenmiş rulo çelik sac", "DE")
    assert res_steel["preferential_origin_applied"] is True
    assert res_steel["effective_duty_pct"] == 0.0


def test_pilot_demurrage_shield():
    # Within free-time (5 days out of 7 allowed)
    res_clean = pilot_engines.execute_demurrage_calculation("2026-09-01", "2026-09-06", 7, 180.0)
    assert res_clean["billable_demurrage_days"] == 0
    assert res_clean["total_demurrage_usd"] == 0.0

    # Penalty (10 days out of 7 allowed = 3 billable days * $180 = $540)
    res_penalty = pilot_engines.execute_demurrage_calculation("2026-09-01", "2026-09-11", 7, 180.0)
    assert res_penalty["billable_demurrage_days"] == 3
    assert res_penalty["total_demurrage_usd"] == 540.0
