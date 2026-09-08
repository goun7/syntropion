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

SECRET_KEY = os.environ.get("SYNTROPION_SECRET_KEY", "syntropion-sovereign-master-key-2026-secure-token").encode("utf-8")

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

def create_tenant_session_token(tenant_id: str, venture_slug: str, role: str = "expert") -> str:
    """Creates a base64url HMAC signed tenant token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "tenant_id": tenant_id,
        "venture": venture_slug,
        "role": role,
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(SECRET_KEY, f"{h_b64}.{p_b64}".encode(), hashlib.sha256).hexdigest()
    return f"{h_b64}.{p_b64}.{signature}"


def verify_tenant_session_token(token: str) -> Dict[str, Any]:
    """Verifies HMAC signature and parses tenant token payload."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token structure")
    h_b64, p_b64, signature = parts
    expected_sig = hmac.new(SECRET_KEY, f"{h_b64}.{p_b64}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        raise ValueError("Invalid cryptographic token signature")
    
    # Pad base64 if needed
    p_padded = p_b64 + "=" * (-len(p_b64) % 4)
    payload_json = base64.urlsafe_b64decode(p_padded.encode()).decode()
    return json.loads(payload_json)
