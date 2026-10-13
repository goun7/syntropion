"""test_shared_memory_ipc_dallar.py — syntropion_core/shared_memory_ipc.py dal-kesen testleri

Zero-copy POSIX shared-memory telemetri-köprüsü: mmap buffer üretimi +
fallback-yolu, struct-paketleme + SHA-256 checksum,原子 flock kilit,
okuma/yazma simetri ve hata-dalları.

TÜM DALLAR:
  modül-sabitleri:
    1.  BUFFER_SIZE=4096, PACKET_SIZE=128, PACKET_FORMAT
    2.  SHM_PATH env'den-okunur ( yoksa /dev/shm/syntropion_treasury_ipc)
    3.  FALLBACK_SHM_PATH paket-dizininde (.fallback_shm_ipc.bin)
  _initialize_buffer:
    4.  dosya-yaratılır + 4096'a-padlenir + mmap hazırlanır
    5.  hedef-açılamazsa ( yok-dizin) FALLBACK_SHM_PATH'e-düşer
    6.  mevcut-4096'lık dosyada tekrar-açma çalışır
  push_revenue_telemetry:
    7.  True döner + simetrik-okuma ( değerler + checksum_valid True)
    8.  slug 32-byte kırpılır ( 40 → 32)
    9.  DAL-GÖZÜ: >32 karakterli slug → checksum_valid False
        ( hash TAM-slug ile, okuma 32-karakterle-yeniden-hesaplar)
    10. tam-32 karakter → checksum_valid True; 33 karakter → False
    11. negatif/sıfır değerler ile çalışır
    12. değerler 2-basamak yuvarlanır
    13. kapalı-köprü → False
    14. struct.pack hatası → False ( except-dalı)
  read_latest_telemetry:
    15. boş-buffer ( sıfır-bayt) → None
    16. kapalı-köprü → None
    17. gross-bölgesi değişince → checksum_valid False
    18. slug/checksum-bölgesi bozulunca → None ( UTF-8 decode-hatası)
    19. struct.unpack hatası → None ( except-dalı)
    20. buffer_path = active_path
  close:
    21. mmap + file None olur; idempotent
    22. sonrasında push False / read None
  singleton:
    23. shm_ipc_bridge örneği-hazır ( kapatılmış-haliyle push False)

Kural-1: SADECE-yeni-dosya. Kural-4: tmp_path mmap-dosyaları ( repo-dışı),
gerçek /dev/shm'ye DOKUNULMAZ ( env-yönlendirme + yok-dizin fallback-testi).
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import pytest

# --- Kural-4: import-anında gerçek /dev/shm'ye DOKUNMA ------------------------
# shared_memory_ipc module-level `shm_ipc_bridge = SharedMemoryIPCBridge()`
# üretir → mmap-dosyası yazar. Henüz-import-edilmemişse SHM_IPC_PATH'i /tmp'ye
# yönlendir; tam-suite'te zaten-import-edildiği-için DOKUNMA.
_TMPDIR = tempfile.mkdtemp(prefix="syntropion-dallar-shm-")
if "syntropion_core.shared_memory_ipc" not in sys.modules:
    os.environ.setdefault("SHM_IPC_PATH", os.path.join(_TMPDIR, "shm.bin"))

from syntropion_core import shared_memory_ipc as shm
from syntropion_core.shared_memory_ipc import (
    BUFFER_SIZE,
    FALLBACK_SHM_PATH,
    PACKET_FORMAT,
    PACKET_SIZE,
    SHM_PATH,
    SharedMemoryIPCBridge,
)

# <d32sddd64s> yerleşimi: ts(0-7) slug(8-39) gross(40-47) net(48-55)
# treasury(56-63) checksum(64-127)
OFFSET_GROSS = 40
OFFSET_SLUG = 8
OFFSET_CHECKSUM = 64


@pytest.fixture
def bridge(tmp_path):
    """Taze tmp mmap-köprüsü ( repo-dışı — Kural-4). Test-sonunda kapatılır."""
    b = SharedMemoryIPCBridge(str(tmp_path / "shm_dallar.bin"))
    yield b
    b.close()


# ---------------------------------------------------------------------------
# modül-sabitleri
# ---------------------------------------------------------------------------
class TestModulSabitleri:
    def test_buffer_ve_packet_boyutu(self):
        assert BUFFER_SIZE == 4096
        assert PACKET_SIZE == 128
        assert PACKET_FORMAT == "<d32sddd64s"
        import struct
        assert struct.calcsize(PACKET_FORMAT) == PACKET_SIZE

    def test_shm_path_envden_okunur(self):
        assert SHM_PATH == os.environ.get("SHM_IPC_PATH", "/dev/shm/syntropion_treasury_ipc")

    def test_fallback_yolu_paket_dizininde(self):
        assert FALLBACK_SHM_PATH.endswith(".fallback_shm_ipc.bin")
        assert os.path.dirname(FALLBACK_SHM_PATH) == os.path.dirname(shm.__file__)


# ---------------------------------------------------------------------------
# _initialize_buffer
# ---------------------------------------------------------------------------
class TestInitializeBuffer:
    def test_dosya_yaratilir_ve_padlenir(self, bridge, tmp_path):
        yol = str(tmp_path / "shm_dallar.bin")
        assert bridge.active_path == yol
        assert os.path.exists(yol)
        assert os.path.getsize(yol) == BUFFER_SIZE

    def test_mmap_hazir(self, bridge):
        assert bridge._mmap_obj is not None
        assert bridge._file_obj is not None
        assert len(bridge._mmap_obj) == BUFFER_SIZE

    def test_hedef_acilamazsa_fallback(self, tmp_path, monkeypatch):
        """Olmayan-dizin → FileNotFoundError → FALLBACK_SHM_PATH'e-düşer."""
        fallback = str(tmp_path / "fallback_dallar.bin")
        monkeypatch.setattr(shm, "FALLBACK_SHM_PATH", fallback)
        yok_dizin = str(tmp_path / "olmayan-dizin" / "x.bin")

        b = SharedMemoryIPCBridge(yok_dizin)
        try:
            assert b.active_path == fallback
            assert os.path.exists(fallback)
            assert b.push_revenue_telemetry("fb-test", 1.0, 0.5, 0.5) is True
            okunan = b.read_latest_telemetry()
            assert okunan["venture_slug"] == "fb-test"
        finally:
            b.close()

    def test_mevcut_buffer_yeniden_acilir(self, tmp_path):
        yol = str(tmp_path / "mevcut.bin")
        b1 = SharedMemoryIPCBridge(yol)
        assert b1.push_revenue_telemetry("iki-kez", 10.0, 2.0, 1.0) is True
        b1.close()
        # aynı-dosyada ikici-köprü veriyi-görür
        b2 = SharedMemoryIPCBridge(yol)
        try:
            okunan = b2.read_latest_telemetry()
            assert okunan["venture_slug"] == "iki-kez"
            assert okunan["gross_usd"] == 10.0
        finally:
            b2.close()


# ---------------------------------------------------------------------------
# push_revenue_telemetry
# ---------------------------------------------------------------------------
class TestPush:
    def test_push_true_ve_simetrik_okuma(self, bridge):
        assert bridge.push_revenue_telemetry("radtrack-ai", 1000.0, 200.0, 50.0) is True
        okunan = bridge.read_latest_telemetry()
        assert okunan["venture_slug"] == "radtrack-ai"
        assert okunan["gross_usd"] == 1000.0
        assert okunan["net_profit_usd"] == 200.0
        assert okunan["treasury_usd"] == 50.0
        assert okunan["checksum_valid"] is True
        assert okunan["buffer_path"] == bridge.active_path
        assert okunan["timestamp"] > 0

    def test_slug_32_karakter_kirpilir(self, bridge):
        assert bridge.push_revenue_telemetry("k" * 40, 10.0, 1.0, 1.0) is True
        okunan = bridge.read_latest_telemetry()
        assert okunan["venture_slug"] == "k" * 32

    def test_uzun_slug_checksum_gecersiz(self, bridge):
        """DAL-GÖZÜ: >32 karakterli slug → checksum_valid False.

        push hash'i TAM-slug ile-hesaplar ama yalnızca ilk-32-byte'ı yazar;
        okuma 32-karakterlik-slug ile-hash'i yeniden-hesapladığı-için
        değerler-birbirini-tutmaz. Simetri yalnızca ≤32-karakterli-slug'lar
        için-geçerlidir.
        """
        assert bridge.push_revenue_telemetry("k" * 33, 10.0, 1.0, 1.0) is True
        assert bridge.read_latest_telemetry()["checksum_valid"] is False

    @pytest.mark.parametrize("uzunluk, gecerli", [(31, True), (32, True), (33, False)])
    def test_slug_uzunluk_esigi(self, bridge, uzunluk, gecerli):
        bridge.push_revenue_telemetry("s" * uzunluk, 10.0, 1.0, 1.0)
        assert bridge.read_latest_telemetry()["checksum_valid"] is gecerli

    def test_negatif_ve_sifir_degerler(self, bridge):
        assert bridge.push_revenue_telemetry("ozel", 0.0, -5.25, 0.0) is True
        okunan = bridge.read_latest_telemetry()
        assert okunan["gross_usd"] == 0.0
        assert okunan["net_profit_usd"] == -5.25
        assert okunan["treasury_usd"] == 0.0
        assert okunan["checksum_valid"] is True

    def test_degerler_iki_basamak_yuvarlanir(self, bridge):
        bridge.push_revenue_telemetry("yuvar", 1000.999, 1.005, 333.333)
        okunan = bridge.read_latest_telemetry()
        # round(x, 2) aynı-çift-kesinlikle-tekrar-edilir
        assert okunan["gross_usd"] == round(1000.999, 2)
        assert okunan["net_profit_usd"] == round(1.005, 2)
        assert okunan["treasury_usd"] == round(333.333, 2)

    def test_kapali_kopru_push_false(self, bridge):
        bridge.close()
        assert bridge.push_revenue_telemetry("x", 1.0, 1.0, 1.0) is False

    def test_pack_hatasi_false(self, bridge, monkeypatch):
        def _patlat(*args):
            raise RuntimeError("struct-patladı")

        monkeypatch.setattr(shm.struct, "pack", _patlat)
        assert bridge.push_revenue_telemetry("x", 1.0, 1.0, 1.0) is False

    def test_flock_kilidi_serbest_birakilir(self, bridge):
        """Art-arda push'lar kilit-birikmesi olmadan-çalışır."""
        for i in range(5):
            assert bridge.push_revenue_telemetry(f"slug-{i}", float(i), 1.0, 1.0) is True
        assert bridge.read_latest_telemetry()["venture_slug"] == "slug-4"


# ---------------------------------------------------------------------------
# read_latest_telemetry
# ---------------------------------------------------------------------------
class TestRead:
    def test_bos_buffer_none(self, bridge):
        """Hiç-yazılmamış sıfır-buffer → None ( boş-slot)."""
        assert bridge.read_latest_telemetry() is None

    def test_kapali_kopru_none(self, bridge):
        bridge.close()
        assert bridge.read_latest_telemetry() is None

    def test_gross_degisince_checksum_gecersiz(self, bridge):
        bridge.push_revenue_telemetry("integrity", 1000.0, 200.0, 50.0)
        # gross-bölgesini ( offset-40) farklı bir-double ile-boz
        import struct
        bridge._mmap_obj.seek(OFFSET_GROSS)
        bridge._mmap_obj.write(struct.pack("<d", 9999.0))
        okunan = bridge.read_latest_telemetry()
        assert okunan is not None
        assert okunan["checksum_valid"] is False
        assert okunan["gross_usd"] == 9999.0

    @pytest.mark.parametrize("offset", [OFFSET_SLUG, OFFSET_CHECKSUM])
    def test_bolge_bozulunca_none(self, bridge, offset):
        """slug/checksum bölgesine 0xFF → UTF-8 decode-hatası → None."""
        bridge.push_revenue_telemetry("boz", 1000.0, 200.0, 50.0)
        bridge._mmap_obj.seek(offset)
        bridge._mmap_obj.write(b"\xff" * 8)
        assert bridge.read_latest_telemetry() is None

    def test_unpack_hatasi_none(self, bridge, monkeypatch):
        bridge.push_revenue_telemetry("unpack", 1.0, 1.0, 1.0)

        def _patlat(fmt, veri):
            raise RuntimeError("unpack-patladı")

        monkeypatch.setattr(shm.struct, "unpack", _patlat)
        assert bridge.read_latest_telemetry() is None

    def test_timestamp_paketten_okunur(self, bridge):
        bridge.push_revenue_telemetry("ts", 1.0, 1.0, 1.0)
        okunan = bridge.read_latest_telemetry()
        assert isinstance(okunan["timestamp"], float)
        assert abs(okunan["timestamp"] - time.time()) < 5.0


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------
class TestClose:
    def test_close_mmap_ve_file_none(self, bridge):
        bridge.close()
        assert bridge._mmap_obj is None
        assert bridge._file_obj is None

    def test_close_idempotent(self, bridge):
        bridge.close()
        bridge.close()  # ikinci-çağrı hata-vermez

    def test_close_sonrasi_push_false_read_none(self, bridge):
        bridge.push_revenue_telemetry("once", 1.0, 1.0, 1.0)
        bridge.close()
        assert bridge.push_revenue_telemetry("sonra", 1.0, 1.0, 1.0) is False
        assert bridge.read_latest_telemetry() is None


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_shm_ipc_bridge_hazir(self):
        assert isinstance(shm.shm_ipc_bridge, SharedMemoryIPCBridge)

    def test_kapali_singleton_push_false(self, monkeypatch):
        """Singleton'a gerçek-yazma-YAPILMAZ ( Kural-4) — iç-durum taklit-edilir."""
        monkeypatch.setattr(shm.shm_ipc_bridge, "_mmap_obj", None)
        monkeypatch.setattr(shm.shm_ipc_bridge, "_file_obj", None)
        assert shm.shm_ipc_bridge.push_revenue_telemetry("x", 1.0, 1.0, 1.0) is False
        assert shm.shm_ipc_bridge.read_latest_telemetry() is None
