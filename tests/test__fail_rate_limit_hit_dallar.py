"""test__fail_rate_limit_hit_dallar.py — syntropion_core/security.py

AT-182-BULGU-1 düzeltmesinin azaltma-katmanı: tenant-başına hatalı-deneme
sayaçlarının 60-sn pencerede 100 limitini aşıp-aşmadığını döner.

TÜM DALLAR ( her-iddia-bir-çalıştırmayla-doğrulanır):
  1. pencere-dolu-değil → sayaç-kararını-döndür ( clear-YOK)
  2. pencere-doldu ( now-reset > 60.0) → clear + reset=now
  3. sınır: 99 → False / 100 → True / 101 → True ( >=-boundary)
  4. anahtar-yok → default-0 → False
  5. tenant-izolasyonu ( anahtarlar-bağımsız)
  6. unicode/mercekTR anahtarları
  7. sabitler: _VERIFY_FAIL_LIMIT=100, _VERIFY_FAIL_WINDOW_S=60.0

GÜVENLİK-ODAK: bu-dal-testleri azaltma-katmanının BYPASS-EDİLEMEMESINI
doğrular — bir-tenant 100-denemeden-sonra RED-alır ve komşu-tenant'ı
etkilenmez. Gerçek-zaman kullanılmaz ( time.monotonic monkeypatch).
"""
import time

import pytest

from syntropion_core import security
from syntropion_core.security import (
    _fail_rate_limit_hit,
    _record_verify_failure,
)

LIMIT = security._VERIFY_FAIL_LIMIT
WINDOW = security._VERIFY_FAIL_WINDOW_S


@pytest.fixture(autouse=True)
def _isolate_fail_counters():
    """Modül-seviyesi global sayacı her-testten-önce sıfırla ( sızıntı-YOK).

    reset=1000.0 → fake_clock'un-varsayılan-t=1000.0 ile AYNI-pencede;
    böylece "pencere-içi" varsayılır ve pencere-dolu-testleri AÇIKÇA eski
    bir reset-değeri set ederek o dalı seçer ( aksi-halde clear boşaltır).
    """
    security._verify_fail_counts.clear()
    security._verify_fail_reset = 1000.0
    yield
    security._verify_fail_counts.clear()
    security._verify_fail_reset = 0.0


@pytest.fixture
def fake_clock(monkeypatch):
    """time.monotonic'i dondur — deterministik pencere-testleri için."""
    state = {"t": 1000.0}

    def _fake_monotonic():
        return state["t"]

    monkeypatch.setattr(time, "monotonic", _fake_monotonic)
    return state


# ---------------------------------------------------------------------------
# 0) sabitler — azaltma-katmanı kontratı
# ---------------------------------------------------------------------------

def test_limit_sabiti_100():
    assert LIMIT == 100


def test_window_sabiti_60(self=None):
    assert WINDOW == 60.0


# ---------------------------------------------------------------------------
# 1) sınır-değerleri ( >=-boundary) — 99/100/101
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n, beklenen", [
    (0, False),
    (1, False),
    (50, False),
    (98, False),
    (99, False),   # sınırın-bir-altı → hâlâ açık
    (100, True),   # tam-sınır → KAPALI ( >=)
    (101, True),   # sınırın-bir-üstü
    (150, True),
    (9999, True),
])
def test_sinir_degerleri(fake_clock, n, beklenen):
    security._verify_fail_counts["tenant-a"] = n
    assert _fail_rate_limit_hit("tenant-a") is beklenen


def test_sifir_sayac_acik(fake_clock):
    assert _fail_rate_limit_hit("tenant-a") is False


# ---------------------------------------------------------------------------
# 2) anahtar-yok → default-0 → False
# ---------------------------------------------------------------------------

def test_anahtar_yok_default_sifir(fake_clock):
    security._verify_fail_counts["baska"] = 500
    assert _fail_rate_limit_hit("yok-boyle-bir-tenant") is False


def test_bos_anahtar_acik(fake_clock):
    security._verify_fail_counts[""] = 100
    assert _fail_rate_limit_hit("") is True


# ---------------------------------------------------------------------------
# 3) tenant-izolasyonu — komşu-aşım-sızıntısı-YOK
# ---------------------------------------------------------------------------

def test_tenant_izolasyonu_komsu_acik(fake_clock):
    """tenant-a 500-deneme → KAPALI; tenant-b'nin-sayaçı-dokunulmamış → AÇIK."""
    security._verify_fail_counts["tenant-a"] = 500
    security._verify_fail_counts["tenant-b"] = 0
    assert _fail_rate_limit_hit("tenant-a") is True
    assert _fail_rate_limit_hit("tenant-b") is False


@pytest.mark.parametrize("anahtar", [
    "tenant-a", "tenant-b", "TENANT-A", "tenant_a",
])
def test_anahtar_buyuk_kucuk_hassas(fake_clock, anahtar):
    """Case-sensitive-bucket: 'TENANT-A' ≠ 'tenant-a' ( sözlük-anahtarı)."""
    security._verify_fail_counts["tenant-a"] = LIMIT
    assert _fail_rate_limit_hit(anahtar) is (anahtar == "tenant-a")


# ---------------------------------------------------------------------------
# 4) pencere-doldu → clear + reset ( dal-1)
# ---------------------------------------------------------------------------

def test_pencere_doldu_clear_ve_reset(fake_clock):
    security._verify_fail_counts["tenant-a"] = 500
    security._verify_fail_reset = 1.0            # eski-reset
    fake_clock["t"] = 1_000.0                    # 999-sn-geçmiş > 60

    assert _fail_rate_limit_hit("tenant-a") is False   # clear-sonrası 0
    assert security._verify_fail_counts == {}          # tamamen-boşaltıldı
    assert security._verify_fail_reset == 1_000.0      # reset=now


def test_pencere_doldu_diger_tenant_da_temizlenir(fake_clock):
    security._verify_fail_counts = {"a": 100, "b": 200, "c": 1}
    security._verify_fail_reset = 0.0
    fake_clock["t"] = 100.0                        # 100-sn > 60

    assert _fail_rate_limit_hit("a") is False
    assert security._verify_fail_counts == {}


def test_pencere_dolmadi_clear_yok(fake_clock):
    """Pencere-içinde → clear-YAPILMAZ, sayaç-korunur."""
    security._verify_fail_counts["tenant-a"] = LIMIT
    security._verify_fail_reset = 950.0
    fake_clock["t"] = 1_000.0                      # 50-sn < 60

    assert _fail_rate_limit_hit("tenant-a") is True
    assert security._verify_fail_counts["tenant-a"] == LIMIT
    assert security._verify_fail_reset == 950.0    # reset-değişmedi


@pytest.mark.parametrize("delta, beklenen_reset", [
    (59.999, 950.0),       # tam-dolmamış → reset-YOK
    (60.0, 950.0),         # tam-60 → '>'-değil → reset-YOK ( boundary)
    (60.001, 950.0 + 60.001),  # 60-bir-tik-üstü → reset ( float-toplam)
    (120.0, 950.0 + 120.0),    # açıkça-dolu → reset
])
def test_pencere_boundary_buyuk_kucuk(fake_clock, delta, beklenen_reset):
    security._verify_fail_reset = 950.0
    fake_clock["t"] = 950.0 + delta

    _fail_rate_limit_hit("herhangi")

    assert security._verify_fail_reset == beklenen_reset


def test_ilk_cagri_pencere_sifirdan_reset(fake_clock):
    """İlk-çağrıda reset=0.0 → now-0 > 60 → reset=now ( açılış-dalı)."""
    security._verify_fail_counts["tenant-a"] = 999
    security._verify_fail_reset = 0.0           # açılış-öncesi: hiç-reset-yok
    fake_clock["t"] = 500.0

    assert _fail_rate_limit_hit("tenant-a") is False
    assert security._verify_fail_reset == 500.0


# ---------------------------------------------------------------------------
# 5) çoklu-çağrı-zamanlaması — reset-bir-kez, sonra-pencere-içi
# ---------------------------------------------------------------------------

def test_reset_bir_kez_sonra_pencere_icinde(fake_clock):
    fake_clock["t"] = 1_000.0
    _fail_rate_limit_hit("tenant-a")               # açılış-reseti
    assert security._verify_fail_reset == 1_000.0

    security._verify_fail_counts["tenant-a"] = LIMIT
    fake_clock["t"] = 1_030.0                      # +30-sn → hâlâ-pencerede
    assert _fail_rate_limit_hit("tenant-a") is True
    assert security._verify_fail_counts["tenant-a"] == LIMIT  # clear-YOK


def test_pencere_dolunca_yeniden_reset(fake_clock):
    fake_clock["t"] = 1_000.0
    _fail_rate_limit_hit("tenant-a")
    security._verify_fail_counts["tenant-a"] = LIMIT

    fake_clock["t"] = 1_061.0                      # +61-sn → dolu
    assert _fail_rate_limit_hit("tenant-a") is False
    assert security._verify_fail_counts == {}


def test_sayac_artisi_limit_gecisi(fake_clock):
    """_record_verify_failure ile artış → 100'de-kapanış ( entegrasyon)."""
    security._verify_fail_reset = fake_clock["t"]
    for _ in range(99):
        _record_verify_failure("tenant-x")
    assert _fail_rate_limit_hit("tenant-x") is False

    _record_verify_failure("tenant-x")             # 100.
    assert security._verify_fail_counts["tenant-x"] == LIMIT
    assert _fail_rate_limit_hit("tenant-x") is True


# ---------------------------------------------------------------------------
# 6) unicode/TR anahtarları — sözlük-anahtarı olarak düzgün-çalışır
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("anahtar", [
    "kiracı-çiftçi-ğüıöşç",
    "istanbul-şubesi",
    "üniversite-akademi",
    "emoji-😀-tenant",
    "кириллица-tenant",
])
def test_unicode_anahtarlar(fake_clock, anahtar):
    security._verify_fail_counts[anahtar] = LIMIT
    assert _fail_rate_limit_hit(anahtar) is True
    assert _fail_rate_limit_hit(anahtar + "-yok") is False


def test_unicode_anahtar_pencere_doldu_temizlenir(fake_clock):
    security._verify_fail_counts["kiracı-çiftçi"] = LIMIT
    security._verify_fail_reset = 0.0
    fake_clock["t"] = 1_000.0

    assert _fail_rate_limit_hit("kiracı-çiftçi") is False
    assert security._verify_fail_counts == {}


# ---------------------------------------------------------------------------
# 7) doğrudan-değişmez-transactionnel: artan-kiracı-sıralı
# ---------------------------------------------------------------------------

def test_cok_tenantli_karisik_sira(fake_clock):
    security._verify_fail_reset = fake_clock["t"]
    security._verify_fail_counts.update({
        "t1": 99, "t2": 100, "t3": 101, "t4": 0,
    })
    assert _fail_rate_limit_hit("t1") is False
    assert _fail_rate_limit_hit("t2") is True
    assert _fail_rate_limit_hit("t3") is True
    assert _fail_rate_limit_hit("t4") is False


def test_sayac_donduruldu_monotonic_cagrildi(monkeypatch):
    """time.monotonic kullanıldığını doğrula ( gerçek-zaman-sızıntısı-YOK)."""
    cagri = {"n": 0}

    def _fake():
        cagri["n"] += 1
        return 5.0

    monkeypatch.setattr(time, "monotonic", _fake)
    security._verify_fail_reset = 0.0              # 5-0=5 < 60 → reset-yok
    _fail_rate_limit_hit("tenant-a")
    assert cagri["n"] == 1
