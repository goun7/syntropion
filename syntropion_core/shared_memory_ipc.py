"""
SYNTROPION OS — Zero-Copy POSIX Shared Memory IPC Bridge
Ultra-low-latency binary telemetry bridge to Project 15 (NeoBank Treasury).
Uses memory-mapped POSIX /dev/shm buffers with struct packing and SHA-256 integrity checksums.
"""

import os
import mmap
import struct
import time
import hashlib
from typing import Dict, Any, Optional

SHM_PATH = os.environ.get("SHM_IPC_PATH", "/dev/shm/syntropion_treasury_ipc")
FALLBACK_SHM_PATH = os.path.join(os.path.dirname(__file__), ".fallback_shm_ipc.bin")
BUFFER_SIZE = 4096  # 4 KB page
PACKET_FORMAT = "<d32sddd64s"  # timestamp (8B), slug (32B), gross (8B), net (8B), treasury (8B), sha256 (64B)
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)  # 128 bytes


class SharedMemoryIPCBridge:
    """Manages memory-mapped binary telemetry for instant zero-copy fund notifications."""

    def __init__(self, shm_path: str = SHM_PATH):
        self.shm_path = shm_path
        self._mmap_obj: Optional[mmap.mmap] = None
        self._file_obj = None
        self._initialize_buffer()

    def _initialize_buffer(self) -> None:
        """Attempts to initialize memory-mapped buffer on /dev/shm with fallback."""
        target_path = self.shm_path
        try:
            # Check if /dev/shm is writable
            self._file_obj = open(target_path, "a+b")
        except (PermissionError, FileNotFoundError, OSError):
            target_path = FALLBACK_SHM_PATH
            self._file_obj = open(target_path, "a+b")

        self.active_path = target_path
        self._file_obj.seek(0, os.SEEK_END)
        current_len = self._file_obj.tell()
        if current_len < BUFFER_SIZE:
            self._file_obj.write(b"\x00" * (BUFFER_SIZE - current_len))
            self._file_obj.flush()

        self._mmap_obj = mmap.mmap(self._file_obj.fileno(), BUFFER_SIZE, access=mmap.ACCESS_WRITE)

    def push_revenue_telemetry(
        self,
        venture_slug: str,
        gross_usd: float,
        net_profit_usd: float,
        treasury_usd: float
    ) -> bool:
        """Packs and writes binary revenue telemetry packet into shared memory slot 0."""
        if not self._mmap_obj:
            return False

        try:
            ts = time.time()
            clean_slug = venture_slug.encode("utf-8")[:32].ljust(32, b"\x00")
            payload_for_hash = f"{ts}:{venture_slug}:{gross_usd:.2f}:{net_profit_usd:.2f}:{treasury_usd:.2f}"
            chksum = hashlib.sha256(payload_for_hash.encode("utf-8")).hexdigest().encode("utf-8")

            packet = struct.pack(
                PACKET_FORMAT,
                ts,
                clean_slug,
                float(gross_usd),
                float(net_profit_usd),
                float(treasury_usd),
                chksum
            )

            self._mmap_obj.seek(0)
            self._mmap_obj.write(packet)
            self._mmap_obj.flush()
            return True
        except Exception:
            return False

    def read_latest_telemetry(self) -> Optional[Dict[str, Any]]:
        """Reads and unpacks the latest packet from the shared memory buffer."""
        if not self._mmap_obj:
            return None

        try:
            self._mmap_obj.seek(0)
            raw = self._mmap_obj.read(PACKET_SIZE)
            if not raw or raw == b"\x00" * PACKET_SIZE:
                return None

            ts, raw_slug, gross, net, treasury, chksum = struct.unpack(PACKET_FORMAT, raw)
            slug = raw_slug.decode("utf-8").rstrip("\x00")

            # Verify checksum
            expected_payload = f"{ts}:{slug}:{gross:.2f}:{net:.2f}:{treasury:.2f}"
            expected_chk = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()

            is_valid = (chksum.decode("utf-8") == expected_chk)

            return {
                "timestamp": ts,
                "venture_slug": slug,
                "gross_usd": round(gross, 2),
                "net_profit_usd": round(net, 2),
                "treasury_usd": round(treasury, 2),
                "checksum_valid": is_valid,
                "buffer_path": self.active_path
            }
        except Exception:
            return None

    def close(self) -> None:
        """Closes memory map and file descriptor cleanly."""
        if self._mmap_obj:
            self._mmap_obj.close()
            self._mmap_obj = None
        if self._file_obj:
            self._file_obj.close()
            self._file_obj = None


shm_ipc_bridge = SharedMemoryIPCBridge()
