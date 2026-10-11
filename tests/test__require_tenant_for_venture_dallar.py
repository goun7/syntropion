"""test__require_tenant_for_venture_dallar.py — syntropion_core/api.py

AT-166-güvenlik-düzeltmesi: tenant-isolasyon-yardımcısı. Bearer-token'dan
tenant-çöz-ve-venture-ile-EŞLEŞTİR ( fail-closed).

TÜM DALLAR ( her-iddia-bir-çalıştırmayla-doğrulanır):
  1. Authorization-YOK / boş / "Bearer "-öneki-DEĞİL → 401
  2. token-geçersiz ( imza-hatalı/bozuk) → 401 "Invalid session token"
  3. tenant_id-YOK → 403 ( token-geçerli-AMA-tenant-boş)
  4. token-venture ≠ istenen-venture → 403 ( cross-tenant-erişim-KAPALI)
  5. token-venture == istenen-venture → tenant_id-döner ( mutlu-yol)
  6. "Bearer "-önek-ayrıştırma ( tam-uzunluk kesimi)
  7. claims-venture None → venture-kontrolü-atlanır ( eski-tokenlar)

GÜVENLİK-ODAK: A-tenant'ın-B-venture'ın-verisini-okuması KAPATILMIŞTIR;
bu-testler o kapanışı doğrular ( her-başarısızlık 401/403 ile fail-closed).
Gerçek HTTP-YOK — doğrudan-fonksiyon-çağrısı + gerçek-HMAC-token.
"""
import time

import pytest
from fastapi import HTTPException

from syntropion_core import api
from syntropion_core.security import create_tenant_session_token

TARGET = api._require_tenant_for_venture


@pytest.fixture(autouse=True)
def _isolate_fail_counters():
    """verify-token'ın rate-limit sayacı testler-arasında sızmasın."""
    from syntropion_core import security
    security._verify_fail_counts.clear()
    security._verify_fail_reset = 0.0
    yield
    security._verify_fail_counts.clear()
    security._verify_fail_reset = 0.0


def _bearer(tenant: str, venture: str, ttl: int = 3600) -> str:
    """Geçerli-imzalı Bearer başlığı üret ( gerçek-HMAC, üretim-secret'i)."""
    return "Bearer " + create_tenant_session_token(tenant, venture, ttl_seconds=ttl)


# ---------------------------------------------------------------------------
# 1) Authorization-YOK / boş / yanlış-öneki → 401
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("auth", [
    None,                    # header-yok
    "",                      # boş
    "Basic dXNlcjpwYXNz",   # Bearer-değil ( Basic)
    "bearer " + "x",         # küçük-harf 'bearer' → önek-ESLEŞMIYOR
    "Bear abc",              # "Bearer "-değil
    "   ",                   # boşluk
])
def test_auth_yanlis_401(auth):
    with pytest.raises(HTTPException) as e:
        TARGET(auth, "ven-1")
    assert e.value.status_code == 401
    assert "Authorization Bearer token required" in e.value.detail


def test_auth_none_detay_mesaji():
    with pytest.raises(HTTPException) as e:
        TARGET(None, "ven-1")
    assert "AT-166" in e.value.detail


# ---------------------------------------------------------------------------
# 2) token-geçersiz → 401 "Invalid session token"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("token", [
    "Bearer abc.def.ghi",                 # 3-parça-ama-imza-hatalı
    "Bearer sadece-bir-parca",            # parça-sayısı-hatalı
    "Bearer " + "a" * 200,                # uzun-ama-geçersiz
    "Bearer .",                           # bozuk
])
def test_token_gecersiz_401(token):
    with pytest.raises(HTTPException) as e:
        TARGET(token, "ven-1")
    assert e.value.status_code == 401
    assert "Invalid session token" in e.value.detail


def test_token_baska_secret_ile_401():
    """Başka-anahtarla-imzalanmış-token → RED ( imza-doğrulaması)."""
    import hmac
    import hashlib
    import base64
    import json
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(
        {"tenant_id": "t1", "venture": "ven-1", "exp": int(time.time()) + 60}
    ).encode()).decode().rstrip("=")
    sig = hmac.new(b"baska-anahtar-16-karakter", f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    with pytest.raises(HTTPException) as e:
        TARGET(f"Bearer {h}.{p}.{sig}", "ven-1")
    assert e.value.status_code == 401


def test_token_suresi_dolmus_401():
    """exp-geçmiş-token → verify-token RED → 401 ( AT-180)."""
    tok = _bearer("t1", "ven-1", ttl=-10)
    with pytest.raises(HTTPException) as e:
        TARGET(tok, "ven-1")
    assert e.value.status_code == 401


# ---------------------------------------------------------------------------
# 3) venture-EŞLEŞMEZ → 403 ( cross-tenant-erişim-KAPALI)
# ---------------------------------------------------------------------------

def test_venture_eslesmez_403():
    tok = _bearer("tenant-a", "ven-a")
    with pytest.raises(HTTPException) as e:
        TARGET(tok, "ven-b")
    assert e.value.status_code == 403
    assert "tenant-isolation" in e.value.detail


def test_venture_eslesmez_detaylarda_tenant_ve_venture():
    tok = _bearer("tenant-a", "ven-a")
    with pytest.raises(HTTPException) as e:
        TARGET(tok, "ven-b")
    d = e.value.detail
    assert "'tenant-a'" in d
    assert "'ven-b'" in d


@pytest.mark.parametrize("tok_venture, istek, gecerli", [
    ("ven-a", "ven-a", True),
    ("ven-a", "ven-b", False),
    ("ven-x", "ven-x", True),
])
def test_venture_eslesme_matrisi(tok_venture, istek, gecerli):
    tok = _bearer("t1", tok_venture)
    if gecerli:
        assert TARGET(tok, istek) == "t1"
    else:
        with pytest.raises(HTTPException) as e:
            TARGET(tok, istek)
        assert e.value.status_code == 403


def test_buyuk_kucuk_hassas_venture():
    """'ven-a' ≠ 'VEN-A' — case-sensitive-eşleşme ( sıkı-kontrol)."""
    tok = _bearer("t1", "ven-a")
    with pytest.raises(HTTPException) as e:
        TARGET(tok, "VEN-A")
    assert e.value.status_code == 403


# ---------------------------------------------------------------------------
# 4) tenant_id-YOK → 403
# ---------------------------------------------------------------------------

def test_tenant_id_yok_403():
    """İmza-geçerli-AMA-tenant_id-boş → 403 ( kimlik-yok-erişim-yok)."""
    import hmac
    import hashlib
    import base64
    import json
    from syntropion_core.security import SECRET_KEY
    payload = {"venture": "ven-1", "exp": int(time.time()) + 60}  # tenant_id YOK
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET_KEY, f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    with pytest.raises(HTTPException) as e:
        TARGET(f"Bearer {h}.{p}.{sig}", "ven-1")
    assert e.value.status_code == 403


def test_tenant_id_bos_string_403():
    import hmac
    import hashlib
    import base64
    import json
    from syntropion_core.security import SECRET_KEY
    payload = {"tenant_id": "", "venture": "ven-1", "exp": int(time.time()) + 60}
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET_KEY, f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    with pytest.raises(HTTPException) as e:
        TARGET(f"Bearer {h}.{p}.{sig}", "ven-1")
    assert e.value.status_code == 403


# ---------------------------------------------------------------------------
# 5) mutlu-yol → tenant_id döner
# ---------------------------------------------------------------------------

def test_mutlu_yol_tenant_doner():
    tok = _bearer("tenant-42", "ven-1")
    assert TARGET(tok, "ven-1") == "tenant-42"


def test_mutlu_yol_unicode_tenant():
    """TR/unicode tenant-id düzgün-çözülür-ve-döner."""
    tok = _bearer("kiracı-çiftçi-ğüıöşç", "ven-1")
    assert TARGET(tok, "ven-1") == "kiracı-çiftçi-ğüıöşç"


def test_mutlu_yol_uzun_venture():
    venture = "ven-" + "a" * 100
    tok = _bearer("t1", venture)
    assert TARGET(tok, venture) == "t1"


# ---------------------------------------------------------------------------
# 6) "Bearer "-önek-ayrıştırma
# ---------------------------------------------------------------------------

def test_bearer_onek_tam_kesim():
    """"Bearer biz123" → token="biz123" ( len("Bearer ")=7 kesimi)."""
    tok = _bearer("t1", "ven-1")
    # başlığa ekstra-boşluk EKLENMEZ — token-bedeni bozulmadan gelir
    assert TARGET(tok, "ven-1") == "t1"


def test_bearer_oneki_olmadan_token_kismi_401():
    """"Bearer"-yarısı-eksik → önek-ESLEŞMIYOR → 401 ( 403 değil)."""
    with pytest.raises(HTTPException) as e:
        TARGET("Beare r " + "x", "ven-1")
    assert e.value.status_code == 401


# ---------------------------------------------------------------------------
# 7) claims-venture None → venture-kontrolü-atlanır ( eski-tokenlar)
# ---------------------------------------------------------------------------

def test_venture_claim_yoksa_atlanir():
    """token'da 'venture' YOK/None → venture-zorunlu-değil → tenant döner.

    Üretim-davranışı: yalnız tenant_id + ( venture VARSA eşleşme) kontrolü.
    """
    import hmac
    import hashlib
    import base64
    import json
    from syntropion_core.security import SECRET_KEY
    payload = {"tenant_id": "t1", "exp": int(time.time()) + 60}  # venture YOK
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET_KEY, f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    # venture-claimi olmadığı için HERHANGİ venture'e kabul — üremin-bu-davranışı
    assert TARGET(f"Bearer {h}.{p}.{sig}", "ven-herhangi") == "t1"


def test_venture_claim_none_atlanir():
    import hmac
    import hashlib
    import base64
    import json
    from syntropion_core.security import SECRET_KEY
    payload = {"tenant_id": "t1", "venture": None, "exp": int(time.time()) + 60}
    h = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET_KEY, f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    assert TARGET(f"Bearer {h}.{p}.{sig}", "ven-x") == "t1"


# ---------------------------------------------------------------------------
# 8) fonksiyon-unvanı & import-bütünlüğü
# ---------------------------------------------------------------------------

def test_fonksiyon_api_modulunde():
    assert hasattr(api, "_require_tenant_for_venture")
    assert callable(TARGET)


def test_basta_komut_her_zaman_kisa_devre():
    """Önce-Yetki → her-zaman-401 ( venture-kontrolüne-GİTMEDEN)."""
    with pytest.raises(HTTPException) as e:
        TARGET(None, "ven-1")
    assert e.value.status_code == 401
    assert "Authorization Bearer token required for tenant isolation (AT-166)" == e.value.detail
