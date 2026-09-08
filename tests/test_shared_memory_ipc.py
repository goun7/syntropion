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
