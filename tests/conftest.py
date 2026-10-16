"""Test-only ortam sabitleri ( production dosyalarına DOKUNULMAZ).

syntropion_core/security.py import-anında SYNTROPION_SECRET_KEY zorunlu
kılar ( AT-162: sabit-default-key güvenlik açığıydı). Bu conftest yalnızca
test oturumunda eksikse bir TEST-ANAHTARI set eder — gerçek üretim secret'ini
asla içermeyen, setdefault ile varolan env değerine dokunmayan bir sabittir.
"""
import os
import tempfile

# Test-only: 16+ karakter, üretim-değeri içermeyen yerel anahtar.
# setdefault → dışarıdan verilmiş (ör. CI) gerçek anahtarı EZMEZ.
os.environ.setdefault(
    "SYNTROPION_SECRET_KEY",
    "syntropion-test-only-secret-key-0000",
)

# DALGA-C-2-BULGU (SYNTROPION-DB-IZOLASYONU): syntropion_core.database
# import-aninda DEFAULT_DB_PATH ('syntropion.db' — goreceli) aciyordu;
# testlerin cogu ( API/CLI/socratic/engine) bu DB'ye YAZIYORDU — takip-edilen
# syntropion.db 1.998.848 -> 2.232.320 B oldu ( 522 socratic_interviews,
# 4.981 audit_ledger — cogu test-uretimi). Kural: testler takip edilen
# production-DB'sine YAZMAZ. *_dallar.py dosyalari zaten /tmp'ye
# yonlendiriyordu — bu desen burada genellenir.
# ( subprocess'ler env'i miras alir → hepsi izole olur.)
os.environ.setdefault(
    "SYNTROPION_DB_PATH",
    os.path.join(tempfile.mkdtemp(prefix="syntropion-test-"), "test.sqlite3"),
)
