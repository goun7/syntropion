"""Test-only ortam sabitleri ( production dosyalarına DOKUNULMAZ).

syntropion_core/security.py import-anında SYNTROPION_SECRET_KEY zorunlu
kılar ( AT-162: sabit-default-key güvenlik açığıydı). Bu conftest yalnızca
test oturumunda eksikse bir TEST-ANAHTARI set eder — gerçek üretim secret'ini
asla içermeyen, setdefault ile varolan env değerine dokunmayan bir sabittir.
"""
import os

# Test-only: 16+ karakter, üretim-değeri içermeyen yerel anahtar.
# setdefault → dışarıdan verilmiş (ör. CI) gerçek anahtarı EZMEZ.
os.environ.setdefault(
    "SYNTROPION_SECRET_KEY",
    "syntropion-test-only-secret-key-0000",
)
