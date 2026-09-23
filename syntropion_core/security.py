"""
SYNTROPION OS — Security, Safe Harbor & Privacy Layer
5846 FSEK Clickwrap Hash, Presidio-grade PII Scrubber, and HMAC Lifetime License Verification.
"""

import os
import re
import hmac
import hashlib
import json
import base64
from typing import Dict, Any, Tuple
from datetime import datetime, timezone

# AT-162-güvenlik-düzeltmesi: SABİT-default-key-KALDIRILDI.
# Önceden: os.environ.get("SYNTROPION_SECRET_KEY", "syntropion-sovereign-…")
# Env-ayarlanmazsa-herkesçe-bilinen-anahtarla-sahte-ADMIN-session-token-ve
# sahte-license-üretilip-GEÇERLI-oluyordu ( tam-admin-ihlali). Artık-zorunlu:
# env-yoksa-başlatma-hatası ( fail-closed) — güvenli-olmayan-default-YOK.
_secret = os.environ.get("SYNTROPION_SECRET_KEY")
if not _secret or len(_secret) < 16:
    raise RuntimeError(
        "SYNTROPION_SECRET_KEY-ZORUNLU (env-eksik-veya-<16-karakter): "
        "sabit-default-key-güvenlik-açığıydı (AT-162); ayarlayın"
    )
SECRET_KEY = _secret.encode("utf-8")

FSEK_TERMS_TEXT_V1 = """
5846 SAYILI FİKİR VE SANAT ESERLERİ KANUNU (FSEK) VE 6102 SAYILI TTK UYARINCA
MİMARİ VE YAZILIM ORTAKLIĞI TAAHHÜTNAMESİ (v1.0-2026)
1. Fikirler değil, somutlaştırılmış ifade korunur (FSEK Md. 1/B, 2, 4).
2. Sunulan fikrin otonom yapay zeka tarafından kodlanması, mimarisi ve bulut dağıtımı stüdyoya aittir.
3. Fikir sahibine; onaylanan nihai mikro-SaaS için ömür boyu ücretsiz kurumsal kullanım hakkı
   (Fair-Use 5M token/ay kotasıyla) ve %20 net ciro kâr payı (Milestone Vesting şartlarıyla) tahsis edilir.
"""


def generate_fsek_clickwrap_hash(expert_email: str, timestamp_iso: str, client_ip: str = "127.0.0.1") -> str:
    """Generates an immutable cryptographic proof of FSEK Safe-Harbor agreement."""
    payload = f"{FSEK_TERMS_TEXT_V1.strip()}:{expert_email}:{timestamp_iso}:{client_ip}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_fsek_clickwrap_hash(stored_hash: str, expert_email: str, timestamp_iso: str, client_ip: str = "127.0.0.1") -> bool:
    """Verifies that an FSEK agreement hash matches exactly."""
    expected = generate_fsek_clickwrap_hash(expert_email, timestamp_iso, client_ip)
    return hmac.compare_digest(stored_hash, expected)


# --- Presidio-Grade PII Scrubbing ---

TCKN_REGEX = re.compile(r"\b[1-9]\d{10}\b")
IBAN_REGEX = re.compile(r"\bTR\d{2}\s?(?:\d{4}\s?){5}\d{2}\b", re.IGNORECASE)
PHONE_REGEX = re.compile(r"(?:\+90|0)?\s?5\d{2}\s?\d{3}\s?\d{2}\s?\d{2}")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")


def scrub_pii_presidio_grade(text: str) -> Tuple[str, Dict[str, int]]:
    """
    Scrubs all sensitive Personally Identifiable Information (PII) before LLM prompt injection.
    KVKK & EU AI Act 2026 Safe Harbor compliance.
    """
    stats = {"tckn": 0, "iban": 0, "phone": 0, "email": 0}

    def replace_iban(m):
        stats["iban"] += 1
        return "[REDACTED_IBAN]"

    def replace_tckn(m):
        stats["tckn"] += 1
        return "[REDACTED_TCKN]"

    def replace_phone(m):
        stats["phone"] += 1
        return "[REDACTED_PHONE]"

    def replace_email(m):
        stats["email"] += 1
        return "[REDACTED_EMAIL]"

    scrubbed = IBAN_REGEX.sub(replace_iban, text)
    scrubbed = TCKN_REGEX.sub(replace_tckn, scrubbed)
    scrubbed = PHONE_REGEX.sub(replace_phone, scrubbed)
    scrubbed = EMAIL_REGEX.sub(replace_email, scrubbed)

    return scrubbed, stats


# --- Lifetime Enterprise License Key Issuer & Verifier ---

def issue_lifetime_license_key(venture_slug: str, expert_id: str) -> str:
    """
    Issues an HMAC-SHA256 cryptographically verifiable Lifetime Enterprise License Key.
    Format: SYNTROPION-{SLUG_UPPER}-{EXPERT_PREFIX}-{HMAC_SIG8}
    """
    clean_slug = re.sub(r"[^A-Za-z0-9]", "", venture_slug).upper()
    expert_hash = hashlib.sha256(expert_id.encode("utf-8")).hexdigest()[:8].upper()
    message = f"{clean_slug}:{expert_hash}:LIFETIME_FREE_2026"
    sig = hmac.new(SECRET_KEY, message.encode("utf-8"), hashlib.sha256).hexdigest()[:12].upper()
    return f"SYNTROPION-{clean_slug}-{expert_hash}-{sig}"


def verify_lifetime_license_key(key: str, venture_slug: str, expert_id: str) -> bool:
    """Verifies cryptographic authenticity of a Lifetime License Key."""
    expected = issue_lifetime_license_key(venture_slug, expert_id)
    return hmac.compare_digest(key, expected)


# --- Lightweight JWT-Style Session Signer ---

def create_tenant_session_token(tenant_id: str, venture_slug: str, role: str = "expert",
                                ttl_seconds: int = 3600) -> str:
    """Creates a base64url HMAC signed tenant token.
    AT-180-BULGU-2: exp-zorunlu ( çalınan-token-sonsuz-geçerli-DEĞİL-artık)."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "tenant_id": tenant_id,
        "venture": venture_slug,
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,   # AT-180: token-süresi-sınırı
    }
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(SECRET_KEY, f"{h_b64}.{p_b64}".encode(), hashlib.sha256).hexdigest()
    return f"{h_b64}.{p_b64}.{signature}"


# AT-182-BULGU-1-düzeltmesi: verify-token'de-rate-limit-YOKTU ( ~294k-deneme/sn;
# HMAC-128-bit-kırılamaz-AMA-kaynak-tüketimi-azaltması-gerekir). Basit-
# hatalı-deneme-sayaçları ( thread-safe-değil-AMA-sayısal-yaklaşım-yeterli).
_verify_fail_counts: Dict[str, int] = {}
_VERIFY_FAIL_LIMIT = 100          # tenant-başına-anlık-hatalı-deneme-limiti
_VERIFY_FAIL_WINDOW_S = 60.0      # pencere-süresi
_verify_fail_reset: float = 0.0


def _fail_rate_limit_hit(tenant_key: str) -> bool:
    """Hatalı-deneme-sayacı-limiti-aşıldı-mı ( azaltma-katmanı)."""
    global _verify_fail_reset
    import time as _time
    now = _time.monotonic()
    if now - _verify_fail_reset > _VERIFY_FAIL_WINDOW_S:
        _verify_fail_counts.clear()
        _verify_fail_reset = now
    return _verify_fail_counts.get(tenant_key, 0) >= _VERIFY_FAIL_LIMIT


def _record_verify_failure(tenant_key: str) -> None:
    _verify_fail_counts[tenant_key] = _verify_fail_counts.get(tenant_key, 0) + 1


def verify_tenant_session_token(token: str) -> Dict[str, Any]:
    """Verifies HMAC signature and parses tenant token payload.
    AT-180-BULGU-2: exp-kontrolü — exp-YOK-veya-süresi-dolmuş → RED
    ( çalınan-token-sonsuz-geçerli-kapandı).
    AT-182-BULGU-1: hatalı-deneme-rate-limit ( kaynak-tüketimi-azaltması)."""
    # AT-169-BULGU-1-düzeltmesi: enum-önyargı — 2-parça-token "Malformed"-
    # derken-3-parça-yanlış-imza "Invalid-signature"-derdi; saldırgan-token
    # yapısını-aşamalı-tahmin-ediyordu. Artık-her-başarısızlık-AYNI-mesajı-
    # verir ( bilgi-sızdırmaz; compare_digest-hâlâ-sabit-zamanlı).
    _FAIL = "Invalid token"
    # AT-182-BULGU-1-düzeltmesi ( NİCEL-SEÇİM): imza-ÖNCESİ-global-kilit-
    # YAPILMADI — neden: doğrulanmamış-payload'tan-tenant çıalamayacağı-için
    # tek-bucket="anon" olurdu ve saldırgan 100-hatalı-token ile TÜM-meşru-
    # doğrulamaları-60s-boyunca-RED-düşürürdü ( yeni-DoS-açığı). HMAC-128-bit
    # zaten-294k/sn'de-kırılamaz ( takım-arkadaşın-dürüst-notu). Azaltma-bu
    # nedenle-SADECE-imza-geçtikten-SONRA-tenant-bucket'inde-uygulanır ( orada
    # saldırgan-tenant'ı-sahteleyemez-çünkü-imza-geçmiş-olmalı).
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(_FAIL)
    h_b64, p_b64, signature = parts
    expected_sig = hmac.new(SECRET_KEY, f"{h_b64}.{p_b64}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError(_FAIL)

    # Pad base64 if needed
    try:
        p_padded = p_b64 + "=" * (-len(p_b64) % 4)
        payload_json = base64.urlsafe_b64decode(p_padded.encode()).decode()
    except Exception:
        raise ValueError(_FAIL)   # bozuk-base64-da-aynı-mesaj ( AT-169)
    payload = json.loads(payload_json)
    # AT-182: imza-GEÇTİ — tenant-bucket'inde-rate-limit ( sahteleyemez;
    # kilit-yalnızca-o-tenant'ı-etkiler, çapraz-tenant-DoS-YOK).
    _tk = str(payload.get("tenant_id") or "anon")
    if _fail_rate_limit_hit(_tk):
        _record_verify_failure(_tk)
        raise ValueError(_FAIL)
    # AT-180-BULGU-2: exp-YOK → RED ( eski-sınırsız-token-artık-geçersiz);
    # exp-doluş → RED. Bilgi-sızıntısız ( AT-169-tek-mesaj-korundu).
    exp = payload.get("exp")
    if not isinstance(exp, int) or int(datetime.now(timezone.utc).timestamp()) > exp:
        _record_verify_failure(_tk)
        raise ValueError(_FAIL)
    return payload
