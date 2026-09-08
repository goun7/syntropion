"""
Tests for 20% Expert / 75% Treasury / 5% Reserve revenue split calculation and ledger.
"""

import pytest
from syntropion_core.database import db
from syntropion_core.revenue_router import revenue_router, quantize_currency


@pytest.fixture(autouse=True)
def setup_seed():
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


def test_quantize_currency():
    assert quantize_currency(123.456) == 123.46
    assert quantize_currency(100.0) == 100.00


def test_revenue_split_exact_proportions():
    venture_id = "ven-pilot-001-radtrack"
    period = "2026-09"
    gross = 10_000.00
    infra_costs = 1_000.00
    # Net = 9,000.00
    # Expert 20% = 1,800.00
    # Treasury 75% = 6,750.00
    # Reserve 5% = 450.00

    res = revenue_router.calculate_and_record_split(
        venture_id=venture_id,
        billing_period=period,
        gross_revenue_usd=gross,
        infra_costs_usd=infra_costs
    )

    assert res["net_profit_usd"] == 9_000.00
    assert res["expert_rev_share_usd"] == 1_800.00
    assert res["treasury_share_usd"] == 6_750.00
    assert res["reserve_fund_usd"] == 450.00
    assert res["status"] == "PROCESSED"
    assert res["ipc_telemetry_dispatched"] is True

    # Check database persistence
    history = revenue_router.get_venture_history(venture_id)
    assert len(history) >= 1
    assert any(h["billing_period"] == period for h in history)
    match_row = next(h for h in history if h["billing_period"] == period)
    assert match_row["net_profit_usd"] == 9_000.00


def test_revenue_split_invalid_negative_values():
    with pytest.raises(ValueError, match="cannot be negative"):
        revenue_router.calculate_and_record_split("ven-pilot-001-radtrack", "2026-09", -500.0, 100.0)
