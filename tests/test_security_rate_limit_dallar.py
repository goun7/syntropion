"""18-Syntropion security._fail_rate_limit_hit/_record_verify_failure dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (global-modul-sayac + monkeypatch; network/DB YASAK).

ORTAM-ANATOMI:
- _fail_rate_limit_hit(tenant_key): pencere (>60s) -> clear+reset; sayac >= 100 -> True
- _record_verify_failure(tenant_key): sayaci +1 artirir
- Sabitler: _VERIFY_FAIL_LIMIT=100, _VERIFY_FAIL_WINDOW_S=60.0
"""
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
from syntropion_core import security as sec  # noqa: E402


@pytest.fixture(autouse=True)
def _temiz_sayac():
    """Global sayaci sifirla + reset'i mevcut monotonic'e sabitle
    (test sirasinda pencere-temizligi tetiklenmesin)."""
    import time as _t
    sec._verify_fail_counts.clear()
    sec._verify_fail_reset = _t.monotonic()
    yield
    sec._verify_fail_counts.clear()
    sec._verify_fail_reset = 0.0


# == _record_verify_failure =============================================================================

def test_artis():
    sec._record_verify_failure("t1")
    assert sec._verify_fail_counts["t1"] == 1


def test_coklu_artis():
    for _ in range(5):
        sec._record_verify_failure("t1")
    assert sec._verify_fail_counts["t1"] == 5


def test_tenant_izolasyon():
    """ORTAM: tenant-basi sayac — diger tenant etkilenmez."""
    sec._record_verify_failure("t1")
    sec._record_verify_failure("t2")
    sec._record_verify_failure("t2")
    assert sec._verify_fail_counts["t1"] == 1
    assert sec._verify_fail_counts["t2"] == 2


def test_donus_none():
    assert sec._record_verify_failure("t1") is None


def test_bos_anahtar():
    sec._record_verify_failure("")
    assert sec._verify_fail_counts[""] == 1


def test_none_anahtar():
    """ORTAM: None anahtar dict'te kullanilabilir."""
    sec._record_verify_failure(None)
    assert sec._verify_fail_counts[None] == 1


def test_stabil():
    sec._record_verify_failure("t1")
    once = sec._verify_fail_counts["t1"]
    sec._record_verify_failure("t1")
    assert sec._verify_fail_counts["t1"] == once + 1


@pytest.mark.parametrize("n", [1, 5, 50, 99, 100, 101, 200])
def test_artis_matrix(n):
    for _ in range(n):
        sec._record_verify_failure("t1")
    assert sec._verify_fail_counts["t1"] == n


# == _fail_rate_limit_hit ===============================================================================

def test_baslangicta_limit_yok():
    assert sec._fail_rate_limit_hit("t1") is False


def test_hic_deneme_yok():
    assert sec._fail_rate_limit_hit("yeni-tenant") is False


def test_limitin_altinda():
    for _ in range(99):
        sec._record_verify_failure("t1")
    assert sec._fail_rate_limit_hit("t1") is False


def test_limit_tam_sinirda():
    """ORTAM: >= 100 -> True (limit 100)."""
    for _ in range(100):
        sec._record_verify_failure("t1")
    assert sec._fail_rate_limit_hit("t1") is True


def test_limit_ustunde():
    for _ in range(150):
        sec._record_verify_failure("t1")
    assert sec._fail_rate_limit_hit("t1") is True


def test_limit_sinir_matematiği():
    """ORTAM-OGRENDI: tam sinirda True (>=), bir eksikte False."""
    sec._verify_fail_counts["t1"] = 99
    assert sec._fail_rate_limit_hit("t1") is False
    sec._verify_fail_counts["t1"] = 100
    assert sec._fail_rate_limit_hit("t1") is True


def test_tenant_izolasyon_limit():
    """ORTAM: t1 limitte olsa t2 KISITLANMAZ."""
    sec._verify_fail_counts["t1"] = 100
    assert sec._fail_rate_limit_hit("t1") is True
    assert sec._fail_rate_limit_hit("t2") is False


def test_pencere_sonu_sifirlar(monkeypatch):
    sec._verify_fail_reset = 0.0
    """ORTAM-OGRENDI: >60s gecince sayac TEMIZLENIR (sliding-window-reset)."""
    import time as _time
    t0 = [_Time.monotonic() for _Time in [None]] if False else [0.0]

    def sahte_monotonic():
        return t0[0]

    monkeypatch.setattr(_time, "monotonic", sahte_monotonic)
    monkeypatch.setattr("time.monotonic", sahte_monotonic, raising=False)
    sec._verify_fail_counts["t1"] = 100
    t0[0] = 100.0  # 100s sonra
    assert sec._fail_rate_limit_hit("t1") is False
    assert sec._verify_fail_counts == {}


def test_pencere_reset_tekrar_sayar(monkeypatch):
    sec._verify_fail_reset = 0.0
    import time as _time
    t0 = [0.0]
    monkeypatch.setattr(_time, "monotonic", lambda: t0[0])
    monkeypatch.setattr("time.monotonic", lambda: t0[0], raising=False)
    sec._verify_fail_reset = 0.0
    sec._verify_fail_counts["t1"] = 100
    t0[0] = 100.0
    sec._fail_rate_limit_hit("t1")  # reset
    sec._record_verify_failure("t1")
    assert sec._verify_fail_counts["t1"] == 1


def test_pencere_icinde_temizlik_yok(monkeypatch):
    sec._verify_fail_reset = 0.0
    """ORTAM: <60s -> eski sayac KORUNUR."""
    import time as _time
    t0 = [0.0]
    monkeypatch.setattr(_time, "monotonic", lambda: t0[0])
    monkeypatch.setattr("time.monotonic", lambda: t0[0], raising=False)
    sec._verify_fail_counts["t1"] = 50
    t0[0] = 30.0
    sec._fail_rate_limit_hit("t1")
    assert sec._verify_fail_counts["t1"] == 50


def test_reset_zamani_guncellenir(monkeypatch):
    sec._verify_fail_reset = 0.0
    import time as _time
    t0 = [10.0]
    monkeypatch.setattr(_time, "monotonic", lambda: t0[0])
    monkeypatch.setattr("time.monotonic", lambda: t0[0], raising=False)
    t0[0] = 100.0
    sec._fail_rate_limit_hit("t1")
    assert sec._verify_fail_reset == 100.0


def test_ilk_cagrida_reset_ayarlanir(monkeypatch):
    sec._verify_fail_reset = 0.0
    """ORTAM: _verify_fail_reset=0.0 ile ilk cagri -> mutlaka reset."""
    import time as _time
    t0 = [100.0]
    monkeypatch.setattr(_time, "monotonic", lambda: t0[0])
    monkeypatch.setattr("time.monotonic", lambda: t0[0], raising=False)
    sec._fail_rate_limit_hit("t1")
    assert sec._verify_fail_reset == 100.0


def test_bos_anahtar():
    sec._verify_fail_counts[""] = 100
    assert sec._fail_rate_limit_hit("") is True


def test_none_anahtar():
    sec._verify_fail_counts[None] = 100
    assert sec._fail_rate_limit_hit(None) is True


@pytest.mark.parametrize("n,beklenen", [(0, False), (1, False), (99, False),
                                        (100, True), (101, True), (500, True)])
def test_limit_matrix(n, beklenen):
    sec._verify_fail_counts["t1"] = n
    assert sec._fail_rate_limit_hit("t1") is beklenen


@pytest.mark.parametrize("delta,beklenen", [(59.0, True), (60.0, True), (61.0, False),
                                            (120.0, False), (9999.0, False)])
def test_pencere_matrix(monkeypatch, delta, beklenen):
    """ORTAM: >60s -> sifirlama; ==60s -> hala limitte (karsilastirma >)."""
    import time as _time
    t0 = [0.0]
    monkeypatch.setattr(_time, "monotonic", lambda: t0[0])
    monkeypatch.setattr("time.monotonic", lambda: t0[0], raising=False)
    sec._verify_fail_reset = 0.0
    sec._verify_fail_counts["t1"] = 100
    t0[0] = delta
    assert sec._fail_rate_limit_hit("t1") is beklenen


# == karakterizasyon ====================================================================================

def test_sabit_degerler():
    """ORTAM: guvenlik-politikasi sabitleri pin'lendi (AT-182-BULGU-1)."""
    assert sec._VERIFY_FAIL_LIMIT == 100
    assert sec._VERIFY_FAIL_WINDOW_S == 60.0


def test_dogrulama_akisi_entegre():
    """ORTAM-OGRENDI: _record_verify_failure -> _fail_rate_limit_hit akisi:
    100 hatali denemeden sonra tenant rate-limit'e takilir (azaltma katmani)."""
    for _ in range(99):
        sec._record_verify_failure("t1")
        assert sec._fail_rate_limit_hit("t1") is False
    sec._record_verify_failure("t1")
    assert sec._fail_rate_limit_hit("t1") is True


def test_global_kilit_yok_dogrulanir():
    """ORTAM-OGRENDI (AT-182-NİCEL-SEÇİM): imza-ONCESI global kilitleme YOK —
    sadece tenant-basi bucket. Dogrulanmamis payload'tan tenant cikamayacagi
    icin tek-bucket='anon' olsaydi saldirgan 100 denemeyle TUM meşru
    dogrulamalari 60s RED duserdi (DoS). Bu tasarim karari pin'lendi."""
    sec._verify_fail_counts["t1"] = 100
    assert sec._fail_rate_limit_hit("t2") is False
