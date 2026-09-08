"""
Tests for Fair-Use Token Quota Governor, usage ratios, and overflow metering.
"""

import pytest
from syntropion_core.database import db
from syntropion_core.quota_governor import quota_governor


@pytest.fixture(autouse=True)
def setup_seed():
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


def test_token_quota_within_free_limit():
    expert_id = "exp-pilot-001-radiologist"
    venture_id = "ven-pilot-002-lexnotice"

    db.execute("DELETE FROM token_quotas WHERE expert_id = ? AND venture_id = ?", (expert_id, venture_id))

    # Initial status: 0 tokens used, 5,000,000 remaining
    status = quota_governor.get_status(expert_id, venture_id)
    assert status["free_token_limit"] == 5_000_000
    assert status["used_tokens"] == 0
    assert status["alert_level"] == "NORMAL"

    # Consume 1,000,000 tokens
    updated = quota_governor.consume_tokens(expert_id, venture_id, 1_000_000)
    assert updated["used_tokens"] == 1_000_000
    assert updated["remaining_free_tokens"] == 4_000_000
    assert updated["overflow_tokens"] == 0
    assert updated["alert_level"] == "NORMAL"


def test_token_quota_warning_at_80_percent():
    expert_id = "exp-pilot-002-lawyer"
    venture_id = "ven-pilot-003-taxcross"

    # Consume 4,200,000 tokens (84% of 5M)
    updated = quota_governor.consume_tokens(expert_id, venture_id, 4_200_000)
    assert updated["usage_ratio_pct"] >= 80.0
    assert updated["alert_level"] in ["WARNING_80_PCT", "DEPLETED_100_PCT"]


def test_token_quota_overflow_billing():
    expert_id = "exp-pilot-003-accountant"
    venture_id = "ven-pilot-004-tarifa"

    # Consume 5,500,000 tokens (500k overflow)
    updated = quota_governor.consume_tokens(expert_id, venture_id, 5_500_000)
    assert updated["used_tokens"] >= 5_000_000
    assert updated["remaining_free_tokens"] == 0
    assert updated["overflow_tokens"] > 0
    assert updated["overflow_billed_usd"] > 0
    assert updated["alert_level"] == "DEPLETED_100_PCT"
