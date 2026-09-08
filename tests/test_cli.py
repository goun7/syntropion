"""
Tests for CLI commands.
"""

import subprocess
import pytest


def test_cli_help():
    res = subprocess.run(["./syntropion", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "SYNTROPION OS" in res.stdout


def test_cli_list_ventures():
    res = subprocess.run(["./syntropion", "list-ventures"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "radtrack-ai" in res.stdout
    assert "lexnotice-ai" in res.stdout


def test_cli_dist_revenue():
    res = subprocess.run([
        "./syntropion", "dist-revenue",
        "--venture-id", "ven-pilot-001-radtrack",
        "--period", "2026-10",
        "--gross", "5000",
        "--costs", "500"
    ], capture_output=True, text=True)
    assert res.returncode == 0
    assert "PROCESSED" in res.stdout
    assert "900.0" in res.stdout  # 20% of 4500 = 900
