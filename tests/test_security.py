"""
Tests for security, FSEK clickwrap hash, PII scrubber, and HMAC lifetime license keys.
"""

import pytest
from syntropion_core.security import (
    generate_fsek_clickwrap_hash,
    verify_fsek_clickwrap_hash,
    scrub_pii_presidio_grade,
    issue_lifetime_license_key,
    verify_lifetime_license_key,
    create_tenant_session_token,
    verify_tenant_session_token
)


def test_fsek_clickwrap_hash_verification():
    email = "avukat@hukuk.com"
    ts = "2026-09-08T12:00:00Z"
    ip = "192.168.1.50"

    h = generate_fsek_clickwrap_hash(email, ts, ip)
    assert len(h) == 64
    assert verify_fsek_clickwrap_hash(h, email, ts, ip) is True
    # Tampered timestamp must fail
    assert verify_fsek_clickwrap_hash(h, email, "2026-09-08T12:00:01Z", ip) is False


def test_presidio_grade_pii_scrubber():
    dirty_text = (
        "Doktor Ahmet Bey TC No: 12345678901, IBAN: TR33 0006 1005 1234 5678 9012 34 "
        "ve telefon 0532 111 22 33 ile iletisim@hastane.com.tr adresinden bildirdi."
    )

    scrubbed, stats = scrub_pii_presidio_grade(dirty_text)
    assert stats["tckn"] == 1
    assert stats["iban"] == 1
    assert stats["phone"] == 1
    assert stats["email"] == 1

    assert "12345678901" not in scrubbed
    assert "[REDACTED_TCKN]" in scrubbed
    assert "[REDACTED_IBAN]" in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed


def test_lifetime_license_key_hmac():
    slug = "radtrack-ai"
    expert_id = "exp-999-oncologist"

    key = issue_lifetime_license_key(slug, expert_id)
    assert key.startswith("SYNTROPION-RADTRACKAI-")
    assert verify_lifetime_license_key(key, slug, expert_id) is True

    # Tampered slug or expert must fail
    assert verify_lifetime_license_key(key, "other-saas", expert_id) is False
    assert verify_lifetime_license_key(key, slug, "other-expert") is False


def test_tenant_session_token():
    token = create_tenant_session_token("tenant-123", "radtrack", "operator")
    payload = verify_tenant_session_token(token)
    assert payload["tenant_id"] == "tenant-123"
    assert payload["venture"] == "radtrack"
    assert payload["role"] == "operator"

    with pytest.raises(ValueError, match="Invalid cryptographic token signature"):
        verify_tenant_session_token(token + "corrupted")

    with pytest.raises(ValueError, match="Malformed token structure"):
        verify_tenant_session_token("only-one-part-no-dots")
