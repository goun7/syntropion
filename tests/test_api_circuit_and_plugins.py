"""
Integration tests for SYNTROPION OS Circuit Breaker & Dynamic Plugin API Endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from syntropion_core.api import app
from syntropion_core.circuit_breaker import circuit_breaker
from syntropion_core.database import db

client = TestClient(app)


def setup_function():
    """Ensure circuit breaker is reset before each test."""
    circuit_breaker.reset()


def teardown_function():
    """Ensure circuit breaker is reset after each test."""
    circuit_breaker.reset()


def test_circuit_breaker_telemetry_endpoint():
    res = client.get("/api/v1/system/circuit-breaker")
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "CLOSED"
    assert data["is_operational"] is True
    assert data["kill_switch_active"] is False


def test_emergency_kill_switch_blocks_mutations():
    # 1. Activate kill-switch
    ks_res = client.post(
        "/api/v1/system/kill-switch",
        json={"operator": "sec-team@syntropion.org", "reason": "Red-Team Security Drill"}
    )
    assert ks_res.status_code == 200
    ks_data = ks_res.json()
    assert ks_data["status"] == "KILL_SWITCH_ENGAGED"
    assert ks_data["circuit_breaker"]["kill_switch_active"] is True

    # 2. Healthz and metrics remain accessible (exempt from shutdown)
    health_res = client.get("/healthz")
    assert health_res.status_code == 200
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200

    # 3. Mutation endpoint must be blocked with HTTP 503
    blocked_res = client.post(
        "/api/v1/proposals/submit",
        json={
            "expert": {
                "email": "blocked@domain.com",
                "full_name": "Blocked User",
                "phone_number": "555-0000",
                "industry_domain": "Health",
                "years_of_experience": 10,
                "iban": "TR0000",
                "ip_assignment_signed": True,
                "fsek_terms_version": "v1.0"
            },
            "title": "Blocked Proposal",
            "problem_statement": "This should be blocked by kill-switch",
            "target_audience": "Hospitals",
            "current_workaround": "Manual sheets"
        }
    )
    assert blocked_res.status_code == 503
    err_data = blocked_res.json()
    assert "Safe Mode active" in err_data["detail"]

    # 4. Deactivate kill-switch
    deact_res = client.post(
        "/api/v1/system/kill-switch/deactivate",
        json={"operator": "sec-team@syntropion.org"}
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["circuit_breaker"]["kill_switch_active"] is False

    # 5. Now operational again
    cb_status = client.get("/api/v1/system/circuit-breaker").json()
    assert cb_status["is_operational"] is True


def test_dynamic_plugin_mounting_and_execution_endpoints():
    # Pick a seeded pilot venture
    venture = db.fetchone("SELECT * FROM ventures LIMIT 1")
    assert venture is not None

    # Mount via API
    mount_res = client.post(f"/api/v1/ventures/{venture['venture_id']}/mount")
    assert mount_res.status_code == 200
    mount_data = mount_res.json()
    assert mount_data["status"] == "MOUNTED"
    assert mount_data["code_slug"] == venture["code_slug"]

    # List loaded plugins
    list_res = client.get("/api/v1/plugins/loaded")
    assert list_res.status_code == 200
    loaded_data = list_res.json()
    assert venture["code_slug"] in loaded_data["loaded_plugins"]

    # Execute direct via API
    exec_res = client.post(
        f"/api/v1/ventures/{venture['venture_id']}/execute",
        json={"payload": {"metric_sample": 108.4, "test_field": "active"}}
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] == "COMPLETED"
    assert exec_data["processed_fields"] == 2
    assert exec_data["tenant_execution"] == "OK"


def test_mount_nonexistent_venture_returns_404():
    mount_res = client.post("/api/v1/ventures/ven-fake-not-found/mount")
    assert mount_res.status_code == 404

    exec_res = client.post("/api/v1/ventures/ven-fake-not-found/execute", json={"payload": {}})
    assert exec_res.status_code == 404
