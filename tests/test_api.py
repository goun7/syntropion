"""
Tests for FastAPI REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from syntropion_core.api import app
from syntropion_core.database import db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_seed():
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


def test_health_and_metrics():
    res_h = client.get("/healthz")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "HEALTHY"

    res_m = client.get("/metrics")
    assert res_m.status_code == 200
    data = res_m.json()
    assert data["total_domain_experts"] >= 5
    assert data["active_micro_saas_ventures"] >= 5
    assert data["portfolio_total_mrr_usd"] > 40000.0


def test_proposal_submission_and_retrieval():
    payload = {
        "expert": {
            "email": "dr.cerrah@cerrahpasa.edu.tr",
            "full_name": "Doç. Dr. Kaan Özdemir",
            "phone_number": "+905331112244",
            "industry_domain": "healthcare",
            "years_of_experience": 14,
            "iban": "TR330006100512345678901234",
            "ip_assignment_signed": True,
            "fsek_terms_version": "v1.0-2026"
        },
        "title": "Laparoskopik Ameliyat Süresi ve Komplikasyon Erken Uyarı Ajanı",
        "problem_statement": "Laparoskopi sırasında trokar giriş hataları ve iç kanama belirtileri erken fark edilmezse hasta riske giriyor.",
        "target_audience": "Genel cerrahi klinikleri ve üniversite hastaneleri",
        "current_workaround": "Asistan hekimin manuel vital takibi",
        "stake_amount_usd": 10.00,
        "stripe_payment_method_id": "pm_card_visa_test",
        "fsek_clickwrap_accepted": True
    }

    res = client.post("/api/v1/proposals/submit", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["stake_status"] == "HELD_IN_ESCROW"
    assert len(data["fsek_contract_hash"]) == 64

    # Fetch proposal details
    res_get = client.get(f"/api/v1/proposals/{data['idea_id']}")
    assert res_get.status_code == 200
    assert res_get.json()["idea"]["title"] == payload["title"]


def test_socratic_interview_endpoints():
    res_q = client.get("/api/v1/interview/question/1")
    assert res_q.status_code == 200
    assert "Darboğaz" in res_q.json()["question"]["title"]

    step_payload = {
        "idea_id": "idea-pilot-001-radtrack",
        "step": 1,
        "expert_response": "RECIST 1.1 kriterlerine göre lezyon boyutlarının BT ve MR raporlarında kıyaslanması günde 2.5 saat almaktadır."
    }
    res_step = client.post("/api/v1/interview/step", json=step_payload)
    assert res_step.status_code == 200
    assert res_step.json()["score"] > 0.50


def test_ventures_and_vesting_endpoints():
    res_v = client.get("/api/v1/ventures")
    assert res_v.status_code == 200
    assert len(res_v.json()) >= 5

    # Milestone unlock
    unlock_payload = {
        "venture_id": "ven-pilot-001-radtrack",
        "expert_id": "exp-pilot-001-radiologist",
        "tier": 1,
        "proof_data": {"test_cases_validated": 10}
    }
    res_u = client.post("/api/v1/vesting/unlock", json=unlock_payload)
    assert res_u.status_code == 200
    assert res_u.json()["unlocked"] is True

    # Quota check
    res_q = client.get("/api/v1/quotas/exp-pilot-001-radiologist/ven-pilot-001-radtrack")
    assert res_q.status_code == 200
    assert res_q.json()["free_token_limit"] == 5000000


def test_revenue_and_pilots_endpoints():
    # Revenue split
    rev_payload = {
        "venture_id": "ven-pilot-001-radtrack",
        "billing_period": "2026-09",
        "gross_revenue_usd": 8358.00,
        "infra_costs_usd": 358.00
    }
    res_r = client.post("/api/v1/revenue/calculate", json=rev_payload)
    assert res_r.status_code == 200
    assert res_r.json()["net_profit_usd"] == 8000.00
    assert res_r.json()["expert_rev_share_usd"] == 1600.00  # 20%
    assert res_r.json()["treasury_share_usd"] == 6000.00    # 75%

    # Vertical pilot endpoints
    res_rad = client.post("/api/v1/pilots/radtrack", json={"baseline_mm": 25.0, "follow_up_mm": 15.0})
    assert res_rad.status_code == 200
    assert "PR" in res_rad.json()["recist_classification"]

    res_lex = client.post("/api/v1/pilots/lexnotice", json={
        "delivery_date": "2026-09-01", "current_date": "2026-09-07", "invoice_amount_try": 50000.0
    })
    assert res_lex.status_code == 200
    assert res_lex.json()["days_passed"] == 6

    res_gtm = client.get("/api/v1/gtm/simulate?leads=50")
    assert res_gtm.status_code == 200
    assert res_gtm.json()["leads_targeted"] == 50
