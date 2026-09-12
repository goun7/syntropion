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


def test_database_retry_loop_on_locked_error(test_db):
    """Verifies backoff retry loop when database is locked (Mergen #3990)."""
    import sqlite3
    attempts = 0
    original_get_connection = test_db.get_connection

    class MockLockConn:
        def __init__(self, real_conn, should_fail):
            self._real = real_conn
            self._should_fail = should_fail
        def commit(self):
            if self._should_fail:
                raise sqlite3.OperationalError("database is locked")
            return self._real.commit()
        def rollback(self):
            return self._real.rollback()
        def close(self):
            return self._real.close()
        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

    # 1. Recovers on retry
    def mock_recovering_conn():
        nonlocal attempts
        attempts += 1
        real = original_get_connection()
        return MockLockConn(real, should_fail=(attempts == 1))

    test_db.get_connection = mock_recovering_conn
    test_db.run_transaction(lambda conn: conn.execute("SELECT 1"))
    assert attempts == 2

    # 2. Exceeds max retries and re-raises
    attempts = 0
    def mock_always_locked():
        nonlocal attempts
        attempts += 1
        real = original_get_connection()
        return MockLockConn(real, should_fail=True)

    test_db.get_connection = mock_always_locked
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        test_db.run_transaction(lambda conn: conn.execute("SELECT 1"))
    assert attempts == 3

    test_db.get_connection = original_get_connection


def test_transaction_successful_commit(test_db):
    """Verifies that transaction commits properly on normal exit."""
    with test_db.transaction() as conn:
        conn.execute("INSERT INTO domain_experts (expert_id, email, full_name, industry_domain, created_at, updated_at) "
                     "VALUES ('exp-test-success', 'success@test.com', 'Success Expert', 'legal', '2026-01-01', '2026-01-01')")
    row = test_db.fetchone("SELECT * FROM domain_experts WHERE expert_id = 'exp-test-success'")
    assert row is not None
    assert row["full_name"] == "Success Expert"


def test_run_transaction_general_exception_rollback(test_db):
    """Verifies run_transaction rolls back on general non-OperationalError."""
    def _bad_callback(conn):
        conn.execute("INSERT INTO domain_experts (expert_id, email, full_name, industry_domain, created_at, updated_at) "
                     "VALUES ('exp-test-fail-gen', 'fail@test.com', 'Fail Expert', 'legal', '2026-01-01', '2026-01-01')")
        raise ValueError("General unhandled business logic error")

    with pytest.raises(ValueError, match="General unhandled business logic error"):
        test_db.run_transaction(_bad_callback)

    row = test_db.fetchone("SELECT * FROM domain_experts WHERE expert_id = 'exp-test-fail-gen'")
    assert row is None
