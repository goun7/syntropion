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
