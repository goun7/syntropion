"""G42: README test-count pin - stale claims fail the build."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _collected_total(res_stdout: str) -> int:
    m = re.search(r"(\d+)\s+tests?\s+collected", res_stdout)
    if m:
        return int(m.group(1))
    total = 0
    for mm in re.finditer(r"^tests?/[\w./-]+\.py:\s*(\d+)\s*$", res_stdout, re.M):
        total += int(mm.group(1))
    return total


def test_readme_test_count_is_not_stale():
    assert README.exists(), "README.md yok"
    readme = README.read_text(encoding="utf-8")
    m = re.search(r"\*\*(\d[\d.,]*)\s*passed", readme)
    assert m, "README test-sayisi-satiri-bulunamadi"
    claimed = int(m.group(1).replace(".", "").replace(",", ""))

    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    collected = _collected_total(res.stdout)
    assert collected > 0, f"collect-okunamadi: {res.stdout[-400:]}"
    assert collected == claimed, (
        "README-stale-test-sayisi: iddia=%d gercek=%d" % (claimed, collected)
    )
