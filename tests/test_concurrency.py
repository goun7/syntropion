"""
Concurrency Stress Tests for SYNTROPION OS.
Validates:
1. SQLite WAL mode + busy_timeout=60000 + exponential backoff retry under parallel multi-threaded write load (Mergen #3990).
2. Shared Memory IPC fcntl.flock process-safety under parallel reader/writer contention.
3. Circuit Breaker thread-safety under concurrent call recording.
"""

import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from syntropion_core.database import db, get_current_iso_time
from syntropion_core.shared_memory_ipc import shm_ipc_bridge
from syntropion_core.circuit_breaker import CircuitBreaker


def test_sqlite_concurrent_transactions():
    """Validates that concurrent writes do not fail with 'database is locked' errors."""
    iterations_per_thread = 15
    num_threads = 6
    errors = []

    def worker(worker_id: int):
        for i in range(iterations_per_thread):
            try:
                db.log_audit_event(
                    event_type="CONCURRENCY_TEST_EVENT",
                    actor=f"worker-{worker_id}",
                    payload={"iteration": i, "token": uuid.uuid4().hex}
                )
            except Exception as e:
                errors.append(f"Worker {worker_id} failed on iteration {i}: {e}")

    threads = []
    for wid in range(num_threads):
        t = threading.Thread(target=worker, args=(wid,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrency errors occurred: {errors}"

    # Verify rows were indeed written
    written = db.fetchall(
        "SELECT COUNT(*) as cnt FROM audit_ledger WHERE event_type = 'CONCURRENCY_TEST_EVENT'"
    )
    expected = num_threads * iterations_per_thread
    assert written[0]["cnt"] >= expected


def test_shared_memory_concurrent_push_and_read():
    """Validates that atomic fcntl.flock prevents torn writes and corruption under parallel contention."""
    num_writers = 4
    iterations_per_writer = 10
    write_errors = []
    read_errors = []

    def writer(wid: int):
        for i in range(iterations_per_writer):
            success = shm_ipc_bridge.push_revenue_telemetry(
                venture_slug=f"concurrent-{wid}",
                gross_usd=1000.0 + wid * 10 + i,
                net_profit_usd=800.0 + wid * 10 + i,
                treasury_usd=600.0 + wid * 10 + i
            )
            if not success:
                write_errors.append(f"Writer {wid} failed on iteration {i}")

    def reader():
        for _ in range(iterations_per_writer * 2):
            pkt = shm_ipc_bridge.read_latest_telemetry()
            if pkt is not None:
                # Validate packet structure and cryptographic checksum
                if "venture_slug" not in pkt or not pkt.get("checksum_valid"):
                    read_errors.append(f"Corrupt packet read: {pkt}")

    with ThreadPoolExecutor(max_workers=num_writers + 2) as executor:
        futures = []
        for w in range(num_writers):
            futures.append(executor.submit(writer, w))
        futures.append(executor.submit(reader))
        futures.append(executor.submit(reader))

        for f in as_completed(futures):
            f.result()

    assert len(write_errors) == 0, f"SHM Write errors: {write_errors}"
    assert len(read_errors) == 0, f"SHM Read corruption: {read_errors}"


def test_circuit_breaker_concurrent_call_recording():
    """Validates thread-safety of sliding window and state transitions under heavy concurrent load."""
    cb = CircuitBreaker(failure_threshold_pct=30.0, window_size=50)
    num_threads = 8
    calls_per_thread = 25

    def recorder(tid: int):
        for i in range(calls_per_thread):
            # 80% success, 20% failure
            success = (i % 5 != 0)
            cb.record_call(success=success)
            _ = cb.get_status()

    threads = [threading.Thread(target=recorder, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    status = cb.get_status()
    assert status["window_calls_count"] == 50  # window_size is capped at 50
    assert 0.0 <= status["recent_failure_rate_pct"] <= 100.0
