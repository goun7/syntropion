"""
Tests for Gamified Milestone Vesting and Lifetime License Key Issuance.
"""

import pytest
from syntropion_core.database import db
from syntropion_core.vesting_engine import vesting_engine


@pytest.fixture(autouse=True)
def setup_seed():
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


def test_milestone_vesting_unlock_flow():
    venture_id = "ven-pilot-001-radtrack"
    expert_id = "exp-pilot-001-radiologist"

    vesting_engine.initialize_venture_vestings(venture_id, expert_id)

    # 1. Unlock Tier 1 (Alpha Validation)
    res_t1 = vesting_engine.unlock_milestone(
        venture_id=venture_id,
        expert_id=expert_id,
        tier=1,
        proof_data={"dataset_count": 10, "passed": True}
    )
    assert res_t1["unlocked"] is True
    assert res_t1["rev_share_percentage"] == 10.00
    assert res_t1["lifetime_license_key"] is not None
    assert "RADTRACK" in res_t1["lifetime_license_key"]

    # 2. Unlock Tier 2 (Beta Co-pilot)
    res_t2 = vesting_engine.unlock_milestone(
        venture_id=venture_id,
        expert_id=expert_id,
        tier=2,
        proof_data={"referrals": ["Hosp A", "Hosp B", "Hosp C"]}
    )
    assert res_t2["unlocked"] is True
    assert res_t2["rev_share_percentage"] == 20.00

    # 3. Check aggregate status
    status = vesting_engine.get_expert_vesting_status(venture_id, expert_id)
    assert status["unlocked_rev_share_pct"] == 20.00
    assert status["lifetime_license_key"] is not None
