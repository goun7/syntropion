"""
Tests for Zero-Copy POSIX Shared Memory IPC telemetry packing and unpacking.
"""

import pytest
from syntropion_core.shared_memory_ipc import shm_ipc_bridge


def test_shared_memory_telemetry_push_and_read():
    slug = "taxcross-audit"
    gross = 9790.00
    net = 8790.00
    treasury = 6592.50

    ok = shm_ipc_bridge.push_revenue_telemetry(
        venture_slug=slug,
        gross_usd=gross,
        net_profit_usd=net,
        treasury_usd=treasury
    )
    assert ok is True

    packet = shm_ipc_bridge.read_latest_telemetry()
    assert packet is not None
    assert packet["venture_slug"] == slug
    assert packet["gross_usd"] == gross
    assert packet["net_profit_usd"] == net
    assert packet["treasury_usd"] == treasury
    assert packet["checksum_valid"] is True


def test_shared_memory_close_and_closed_operations():
    from syntropion_core.shared_memory_ipc import SharedMemoryIPCBridge
    custom_bridge = SharedMemoryIPCBridge(shm_path="/dev/shm/test_temp_ipc")
    assert custom_bridge._mmap_obj is not None
    assert custom_bridge._file_obj is not None

    # Test closing
    custom_bridge.close()
    assert custom_bridge._mmap_obj is None
    assert custom_bridge._file_obj is None

    # Operations after close return False/None gracefully
    assert custom_bridge.push_revenue_telemetry("slug", 100.0, 50.0, 30.0) is False
    assert custom_bridge.read_latest_telemetry() is None


def test_shared_memory_fallback_on_unwritable_path(tmp_path):
    from syntropion_core.shared_memory_ipc import SharedMemoryIPCBridge, FALLBACK_SHM_PATH
    # Provide an invalid directory path to trigger OSError fallback
    unwritable_path = "/non_existent_directory_sys_root/impossible_shm_file"
    fallback_bridge = SharedMemoryIPCBridge(shm_path=unwritable_path)
    assert fallback_bridge.active_path == FALLBACK_SHM_PATH
    fallback_bridge.close()


def test_shared_memory_corrupt_packet_handling():
    from syntropion_core.shared_memory_ipc import SharedMemoryIPCBridge
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"garbage_not_a_valid_packet_1234567890" * 4)
        f.flush()
        corrupt_bridge = SharedMemoryIPCBridge(shm_path=f.name)
        # Should gracefully return None or corrupt packet without crashing
        res = corrupt_bridge.read_latest_telemetry()
        # Either None (exception in struct.unpack) or checksum_valid False
        if res is not None:
            assert res["checksum_valid"] is False
        corrupt_bridge.close()
