#!/usr/bin/env python3
"""syntropion MCP sunucusu - Model Context Protocol 2025-06-18 over stdio.

SYNTROPION OS'in dorust-metrik ve venture-yonetim-cekirdegini AI
ajanlarina MCP araclari olarak sunar. Tamga/sester/pacta MCP
sunucularinin ayni deseni ( stdio JSON-RPC, uc-sonuc kaniti,
exception-YOK).

Tasarim-ilkesi:
  - SAF STDLIB - hicbir pip bagimliligi; sunucu syntropion modullerini
    SUBPROCESS-LEVEL'da cagirir, import etmez - surum-cakismasi yok.
  - UC-SONUC - her arac GREEN/RED/INDETERMINE JSON kaniti dondurur;
    ASLA exception firlatmaz.
  - Dorust-metrik - honest-metrics araci SIMULATED/LIVE-verdiktini
    gercek DB-satir-sayimlarina dayanir ( uy durumu gizlenmez).

Araclar:
  honest_metrics  dorust-metrik-raporu ( SIMULATED-verdiktisiyle)
  list_ventures   aktif-venture listesi ( MRR + abone-sayilari)

Calistirma:
  python3 mcp/server.py                    # stdio JSON-RPC
  (istemci tarafi: "command": "python", "args": ["<repo>/mcp/server.py"])
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "syntropion"
SERVER_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[1]
MAX_TIMEOUT = 120  # saniye


def _e(msg: str) -> dict:
    return {"jsonrpc": "2.0", "error": {"code": -32602, "message": msg}}


def _result(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _text(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _run_cli(args: list) -> dict:
    """syntropion CLI'ini SUBPROCESS olarak cagir, cikisini JSON kanita cevir.

    Fail-closed: her hata ( zaman-asimi, exception, bozuk-cikis) bir RED
    kanitidir - traceback DEGIL, JSON doner. CLI insan-okunur basar;
    bu yuzden cikis bir JSON-kanitina sarilir.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "syntropion_core.cli", *args],
            capture_output=True, text=True, timeout=MAX_TIMEOUT, cwd=str(ROOT),
            env=_env_with_secret())
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "zaman-asimi: %ds" % MAX_TIMEOUT}
    except Exception as e:  # cephedeki her hata JSON kaniti olmali
        return {"ok": False, "reason": "calistirma-hatasi: %s" % e}
    out = (proc.stdout or "").strip()
    return {
        "ok": proc.returncode == 0,
        "rc": proc.returncode,
        "report": out[:2000],
        "stderr": (proc.stderr or "").strip()[:300],
    }


def _env_with_secret() -> dict:
    """CLI zorunlu SYNTROPION_SECRET_KEY ister; MCP-ortaminda varsayilan

    gelistirme-anahtari kullanilir ( uretim-degil). Meydan-okuma:
    anahtar uretim-ortamindan-gelebilir - burada SADECE eksikse-default.
    """
    import os
    env = dict(os.environ)
    if not env.get("SYNTROPION_SECRET_KEY"):
        env["SYNTROPION_SECRET_KEY"] = (
            "mcp-dev-anahtari-0123456789abcdef0123456789abcdef")
    return env


def _tool_honest_metrics(args: dict) -> dict:
    return _run_cli(["honest-metrics"])


def _tool_list_ventures(args: dict) -> dict:
    return _run_cli(["list-ventures"])


TOOL_IMPLS = {
    "honest_metrics": _tool_honest_metrics,
    "list_ventures": _tool_list_ventures,
}

TOOLS_LIST = [
    {
        "name": "honest_metrics",
        "description": (
            "SYNTROPION dorust-metrik-raporu - iddia-MRR ile DOGRULANAN-MRR "
            "arasindaki farki olcer ve SIMULATED/LIVE verdiktisi doner. "
            "Veri-yoksa gizlenmez, rapor-edilir. JSON kanit doner."),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_ventures",
        "description": (
            "Aktif micro-SaaS venture'lerinin listesini doner "
            "( slug, durum, MRR, abone-sayisi). Simulasyon-isaretli "
            "kayitlar acik-sekilde-etiketlenir."),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def _tools_list_result() -> dict:
    return {"tools": TOOLS_LIST}


def _handle_call(req_id, params: dict) -> dict | None:
    name = params.get("name")
    if not isinstance(name, str) or not name:
        return _result(req_id, _e("arac-adi-zorunlu"))
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": "bilinmeyen-arac: %s" % name},
        }
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        return _result(req_id, _e("arguments-bir-nesne-olmali"))
    try:
        payload = impl(args)
    except Exception as e:  # fail-closed: traceback degil JSON kaniti
        payload = {"ok": False, "reason": "arac-hatasi: %s" % e}
    return _result(req_id, _text(payload))


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_e("gecersiz-json")) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(req, dict):
            sys.stdout.write(json.dumps(_e("istek-bir-nesne-degil")) + "\n")
            sys.stdout.flush()
            continue
        method = req.get("method")
        req_id = req.get("id")
        if method == "initialize":
            sys.stdout.write(json.dumps(_result(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "instructions": (
                        "SYNTROPION OS dorust-metrik sunucusu. "
                        "honest_metrics -> SIMULATED/LIVE-verdiktisi; "
                        "list_ventures -> venture-listesi. "
                        "Her arac JSON kaniti doner, asla exception firlatmaz."),
                }})) + "\n")
        elif method == "notifications/initialized":
            continue  # bildirim - yanit yok
        elif method == "tools/list":
            sys.stdout.write(json.dumps(_result(req_id, _tools_list_result())) + "\n")
        elif method == "tools/call":
            resp = _handle_call(req_id, req.get("params") or {})
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        elif method == "ping":
            sys.stdout.write(json.dumps(_result(req_id, {})) + "\n")
        elif req_id is not None:
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": "bilinmeyen-method: %s" % method}
            }) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
