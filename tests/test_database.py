"""
Tests for database persistence, transactions, and Merkle hash chain audit ledger.
"""

import os
import pytest
import tempfile
from syntropion_core.database import DatabaseManager


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    yield db
    if os.path.exists(path):
        os.remove(path)


def test_database_initialization(test_db):
    """Verifies tables are created with proper schema."""
    tables = test_db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [t["name"] for t in tables]
    assert "domain_experts" in table_names
    assert "domain_ideas" in table_names
    assert "ventures" in table_names
    assert "milestone_vestings" in table_names
    assert "token_quotas" in table_names
    assert "revenue_distributions" in table_names
    assert "audit_ledger" in table_names


def test_transaction_rollback_on_error(test_db):
    """Verifies that failures roll back uncommitted changes."""
    with pytest.raises(Exception):
        with test_db.transaction() as conn:
            conn.execute(
                "INSERT INTO domain_experts (expert_id, email, full_name, industry_domain, created_at, updated_at) "
                "VALUES ('exp-test-rb', 'rollback@test.com', 'Test Expert', 'legal', '2026-01-01', '2026-01-01')"
            )
            # Intentionally cause constraint violation
            conn.execute("INSERT INTO domain_experts (expert_id) VALUES (NULL)")

    row = test_db.fetchone("SELECT * FROM domain_experts WHERE expert_id = 'exp-test-rb'")
    assert row is None


def test_audit_ledger_merkle_hash_chain(test_db):
    """Verifies sequential hash chaining of audit events."""
    h1 = test_db.log_audit_event("TEST_EVENT_1", "actor-1", {"key": "val1"})
    h2 = test_db.log_audit_event("TEST_EVENT_2", "actor-2", {"key": "val2"})
    assert h1 != h2

    rows = test_db.fetchall("SELECT * FROM audit_ledger ORDER BY id ASC")
    assert len(rows) == 2
    assert rows[0]["previous_hash"].startswith("GENESIS_HASH")
    assert rows[1]["previous_hash"] == rows[0]["current_hash"]


def test_seed_pilots_execution(test_db):
    """Verifies deep vertical pilots are seeded properly."""
    test_db.seed_deep_vertical_pilots()
    ventures = test_db.fetchall("SELECT * FROM ventures")
    assert len(ventures) == 5
    mrr_total = sum(v["current_monthly_mrr_usd"] for v in ventures)
    assert mrr_total > 40000.00


def test_checkpoint_wal(test_db):
    """Verifies PRAGMA wal_checkpoint truncation executes cleanly."""
    test_db.checkpoint_wal()
    # Ensure database is still queryable
    row = test_db.fetchone("SELECT COUNT(*) as cnt FROM ventures")
    assert row["cnt"] >= 0
