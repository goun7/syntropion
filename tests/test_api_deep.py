"""
Deep API endpoint tests covering all branches, edge cases, error handlers, and pilot runners.
"""

import pytest
from fastapi.testclient import TestClient
from syntropion_core.api import app
from syntropion_core.database import db

client = TestClient(app)


def test_api_proposals_list_and_not_found():
    res = client.get("/api/v1/proposals/non-existent-idea-12345")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

    res_all = client.get("/api/v1/proposals")
    assert res_all.status_code == 200
    assert isinstance(res_all.json(), list)


def test_api_socratic_invalid_step():
    res = client.get("/api/v1/interview/question/99")
    assert res.status_code == 400


def test_api_venture_details_and_not_found():
    res = client.get("/api/v1/ventures/ven-non-existent-999")
    assert res.status_code == 404

    # Existing venture
    res_ok = client.get("/api/v1/ventures/ven-pilot-001-radtrack")
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert "venture" in data
    assert "vestings" in data


def test_api_pilots_all_five():
    # 1. RadTrack
    r1 = client.post("/api/v1/pilots/radtrack", json={"baseline_mm": 20.0, "follow_up_mm": 25.0})
    assert r1.status_code == 200

    # 2. LexNotice
    r2 = client.post("/api/v1/pilots/lexnotice", json={
        "delivery_date": "2026-09-01", "current_date": "2026-09-03", "invoice_amount_try": 25000.0
    })
    assert r2.status_code == 200

    # 3. TaxCrossAudit
    r3 = client.post("/api/v1/pilots/taxcross", json={
        "gib_invoices_total_try": 80000.0, "accounting_ledger_total_try": 80000.0
    })
    assert r3.status_code == 200
    assert r3.json()["is_fully_reconciled"] is True

    # 4. TarifaCustoms
    r4 = client.post("/api/v1/pilots/tarifa", json={
        "product_description": "Antibiyotik kapsül ilaç", "country_of_origin": "TR"
    })
    assert r4.status_code == 200
    assert "3004" in r4.json()["determined_gtip_12_digit"]

    # 5. DemurrageShield
    r5 = client.post("/api/v1/pilots/demurrage", json={
        "discharge_date": "2026-09-01", "gate_out_date": "2026-09-08", "free_time_days": 7, "daily_rate_usd": 200.0
    })
    assert r5.status_code == 200
    assert r5.json()["total_demurrage_usd"] == 0.0


def test_api_gtm_campaign_all_domains():
    for dom, slug in [("healthcare", "radtrack-ai"), ("legal", "lexnotice-ai"), ("tax", "taxcross-audit"), ("general", "demo-saas")]:
        res = client.post("/api/v1/gtm/campaign", json={
            "venture_id": "ven-pilot-001-radtrack",
            "target_industry": dom,
            "sample_prospect_company": f"Corp {dom.capitalize()}",
            "decision_maker_title": "Direktör"
        })
        assert res.status_code == 200
        assert res.json()["deliverability_score"] >= 0.90


def test_api_shared_memory_telemetry_endpoint():
    res = client.get("/api/v1/revenue/telemetry/latest")
    assert res.status_code == 200
    assert "latest_shm_packet" in res.json()


def test_api_new_expert_proposal_submission():
    import uuid
    unique_email = f"expert_{uuid.uuid4().hex[:8]}@industry.com"
    res = client.post(
        "/api/v1/proposals/submit",
        json={
            "expert": {
                "email": unique_email,
                "full_name": "Dr. Ayşe Yılmaz",
                "phone_number": "+90 532 111 2233",
                "industry_domain": "Healthcare Oncology",
                "years_of_experience": 14,
                "iban": "TR330006100511123456789012",
                "ip_assignment_signed": True,
                "fsek_terms_version": "v1.0"
            },
            "title": "Onkoloji Otomasyonu",
            "problem_statement": "Lezyon takipleri manuel yapılmaktadır.",
            "target_audience": "Onkologlar",
            "current_workaround": "Excel tablosu",
            "stake_amount_usd": 10.0
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["amount_held_usd"] == 10.0


def test_api_venture_synthesis_flow():
    # Attempting to synthesize unapproved idea raises 400
    res_bad = client.post(
        "/api/v1/ventures/synthesize",
        json={"idea_id": "non-existent-idea-404"}
    )
    assert res_bad.status_code == 400

    # Insert an approved idea
    import uuid
    from syntropion_core.database import get_current_iso_time
    now = get_current_iso_time()
    approved_idea_id = f"idea-approved-{uuid.uuid4().hex[:6]}"
    expert_id = f"exp-test-{uuid.uuid4().hex[:6]}"

    db.execute(
        "INSERT INTO domain_experts (expert_id, email, full_name, industry_domain, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (expert_id, f"synth_{uuid.uuid4().hex[:6]}@domain.com", "Synth Expert", "Customs", now, now)
    )
    db.execute(
        """
        INSERT INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            status, created_at, updated_at
        ) VALUES (?, ?, 'Gümrük Otomasyonu', 'Beyanname takibi zordur', 'Gümrük Müşavirleri', 'APPROVED_FOR_SYNTHESIS', ?, ?)
        """,
        (approved_idea_id, expert_id, now, now)
    )

    res_ok = client.post(
        "/api/v1/ventures/synthesize",
        json={"idea_id": approved_idea_id, "target_slug": f"custom-synth-{uuid.uuid4().hex[:6]}"}
    )
    assert res_ok.status_code == 200
    assert "fastapi_router_code" in res_ok.json()


def test_api_vesting_and_quota_endpoints():
    venture = db.fetchone("SELECT * FROM ventures LIMIT 1")
    assert venture is not None
    venture_id = venture["venture_id"]
    idea = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (venture["idea_id"],))
    assert idea is not None
    expert_id = idea["expert_id"]

    # Vesting status
    vesting_res = client.get(f"/api/v1/vesting/{venture_id}/{expert_id}")
    assert vesting_res.status_code == 200

    # Vesting unlock error (non-existent venture triggers 400 ValueError)
    bad_unlock = client.post(
        "/api/v1/vesting/unlock",
        json={"venture_id": "ven-non-existent-999", "expert_id": expert_id, "tier": 1}
    )
    assert bad_unlock.status_code == 400

    # Quota check
    quota_res = client.get(f"/api/v1/quotas/{expert_id}/{venture_id}")
    assert quota_res.status_code == 200
    assert quota_res.json()["free_token_limit"] == 5_000_000

    # Quota consume
    consume_res = client.post(
        "/api/v1/quotas/consume",
        json={"expert_id": expert_id, "venture_id": venture_id, "tokens_requested": 15000}
    )
    assert consume_res.status_code == 200
    assert consume_res.json()["used_tokens"] >= 15000

    # Quota consume invalid negative tokens rejected by schema
    bad_consume = client.post(
        "/api/v1/quotas/consume",
        json={"expert_id": expert_id, "venture_id": venture_id, "tokens_requested": -500}
    )
    assert bad_consume.status_code == 422


def test_api_revenue_endpoints_and_history():
    venture_id = "ven-pilot-001-radtrack"
    # History
    hist_res = client.get(f"/api/v1/revenue/history/{venture_id}")
    assert hist_res.status_code == 200
    assert isinstance(hist_res.json(), list)

    # Calculate for non-existent venture triggers 400 ValueError
    bad_rev = client.post(
        "/api/v1/revenue/calculate",
        json={
            "venture_id": "ven-non-existent-999",
            "billing_period": "2026-09",
            "gross_revenue_usd": 1000.0,
            "infra_costs_usd": 100.0
        }
    )
    assert bad_rev.status_code == 400


def test_api_pilots_error_handling():
    # RadTrack baseline <= 0
    bad_rad = client.post("/api/v1/pilots/radtrack", json={"baseline_mm": 0.0, "follow_up_mm": 10.0})
    assert bad_rad.status_code == 400

    # LexNotice invalid date
    bad_lex = client.post("/api/v1/pilots/lexnotice", json={
        "delivery_date": "not-a-date", "current_date": "2026-09-03", "invoice_amount_try": 1000.0
    })
    assert bad_lex.status_code == 400

    # Demurrage invalid date
    bad_dem = client.post("/api/v1/pilots/demurrage", json={
        "discharge_date": "invalid-date", "gate_out_date": "2026-09-08", "free_time_days": 7
    })
    assert bad_dem.status_code == 400


def test_api_root_index_serving():
    res = client.get("/")
    assert res.status_code == 200


def test_api_additional_edge_cases():
    import uuid
    from unittest.mock import patch
    from syntropion_core.quota_governor import quota_governor
    from syntropion_core.plugin_loader import plugin_manager

    # 1. Socratic step error with non-existent idea
    bad_step = client.post(
        "/api/v1/interview/step",
        json={"idea_id": "non-existent-idea-404", "step": 1, "expert_response": "Test response"}
    )
    assert bad_step.status_code == 400

    # 2. Quota consume engine ValueError returns 400
    with patch.object(quota_governor, "consume_tokens", side_effect=ValueError("Engine quota overflow fault")):
        bad_quota = client.post(
            "/api/v1/quotas/consume",
            json={"expert_id": "exp-test", "venture_id": "ven-test", "tokens_requested": 100}
        )
        assert bad_quota.status_code == 400

    # 3. Root index when index.html is missing returns JSON fallback
    with patch("os.path.exists", return_value=False):
        res_missing = client.get("/")
        assert res_missing.status_code == 200
        assert "Web UI not found" in res_missing.json()["message"]

    # 4. Venture synthesis auto-mount failure logs warning and returns 200
    fresh_idea_id = f"idea-mount-fail-{uuid.uuid4().hex[:6]}"
    db.execute(
        """
        INSERT INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            current_workaround, stake_amount_usd, stake_payment_status, status,
            domain_depth_score, created_at, updated_at
        ) VALUES (?, 'exp-pilot-001-radiologist', 'Mount Fail Test Idea', 'Problem', 'Audience', 'Workaround', 10.0, 'CAPTURED_TO_EQUITY', 'APPROVED_FOR_SYNTHESIS', 0.95, '2026-09-01', '2026-09-01')
        """,
        (fresh_idea_id,)
    )
    with patch.object(plugin_manager, "load_plugin_from_code", side_effect=Exception("Mocked mount failure")):
        synth_res = client.post("/api/v1/ventures/synthesize", json={"idea_id": fresh_idea_id})
        assert synth_res.status_code == 200
        assert synth_res.json()["ast_validation_passed"] is True
