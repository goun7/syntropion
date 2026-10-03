"""
SYNTROPION OS — Dürüst (Honest) Metrik Çerçevesi
AT-HONEST-001 — "fabricated MRR -> 0 DB rows" (C notu) kök-neden ölçüm modülü.

Akademik dayanak (arastirma-2026):
  - arXiv:2609.34496 MASTraceBench : yalnizca nihai sonuc (MRR) raporlamak
    teshise izin vermez; "proposal trajectory" (adim-adim ilerleyis) +
    Collaboration Gain + Token Cost gerekir.
  - arXiv:2609.34701 ResonAct     : streaming "operational metrics"
    (task progress, context health, tool reliability) ile runtime'da
    teshis. "0 DB rows" tarzi bos iddialarin yakalanmasi mekanizmasi.
  - arXiv:2609.34821 CEO Arena    : matched-replacement degerlendirme —
    cogu otonom ajan NEGATIF ortalama getiri verir; sentetik MRR
    iddalari gerceklilikten kopuktur.

DURUST'LUK SOZLESMESI (bu modul icin):
  1.Bu modülde HIÇBIR metrik uydurulmaz, varsayilan (default) olarak
    0/None mesajlari cikarilmaz. Butun sayilar GERCEK SQL COUNT/SUM
    sorgularindan gelir.
  2."basari" (trace_based_success) MRR'ye DEGIL, gercek trajectory'e
    (socratic_interviews satirlari +DDS +son durum) baglidir.
  3.MRR iddialari, abonelik tablosundan DOGRULANIR (mrr_provenance);
    dogrulanmayan deger "SIMULATED" olarak etiketlenir, ASLA silinmez.

Yazar: Syntropion Autonomous Studio (3. dalga gece vardiyesi)
"""

from contextlib import contextmanager
import hashlib
import json
from typing import Dict, Any, List, Optional

from syntropion_core.database import db

# Metriklerin olustugu gercek tablo adi beyaz-listesi (SQL enjeksiyon korumasi).
# Tablo listesi SQLite katalogundan canli okunur; asla sabit kodlanmaz.


def _known_tables() -> List[str]:
    """sqlite_master katalogundan guncel tablo listesini doner (canli sorgu)."""
    rows = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [r["name"] for r in rows]


def _require_known_table(table_name: str) -> str:
    """Tablo adini kataloga karsi dogrular; bilinmeyen ad kabul edilmez."""
    tables = _known_tables()
    if table_name not in tables:
        raise ValueError(
            f"Bilinmeyen tablo: {table_name!r}. Bilinen tablolar: {sorted(tables)}"
        )
    return table_name


# ---------------------------------------------------------------------------
# 1) db_row_count — GERCEK DB satir sayisi (ResonAct: "0 DB rows" teshisi)
# ---------------------------------------------------------------------------
def db_row_count(table_name: str) -> int:
    """
    Belirtilen tablodaki GERCEK satir sayisini doner (COUNT(*) sorgusu).

    Bu, "fabricated MRR -> 0 DB rows" teshisinin kanit nidasi:
    b2b_subscriptions icin 0 donuyorsa, hic gercen odemeli abone YOK demektir
    ve ventures tablosundaki MRR degerleri veri Kaynagi'ndan yoksundur.
    """
    _require_known_table(table_name)
    row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM {table_name}")
    return int(row["cnt"])


def db_row_counts() -> Dict[str, int]:
    """Tum tablolar icin GERCEK satir sayilari; '0' da gercektir, gizlenmez."""
    return {t: db_row_count(t) for t in sorted(_known_tables())}


# ---------------------------------------------------------------------------
# 2) tool_invocation_count — GERCEK araç cagri sayisi (ResonAct: tool reliability)
# ---------------------------------------------------------------------------
# Sayima dahil edilen gercek sistem-olay tipleri (audit_ledger'da kayitli).
# CONCURRENCY_TEST_EVENT test kokenli oldugundan uretim sayilmasina dahil
# edilmez; parametre ile acikca istenirse sayilir.
TOOL_INVOCATION_EVENT_TYPES = [
    "STAKE_ESCROW_HELD",
    "STAKE_REFUND_EXECUTED",
    "STAKE_CAPTURED_TO_EQUITY",
    "VENTURE_SYNTHESIZED",
    "MILESTONE_TIER_1_UNLOCKED",
    "MILESTONE_TIER_2_UNLOCKED",
    "REVENUE_SPLIT_PROCESSED",
    "PLUGIN_HOT_MOUNTED",
    "EMERGENCY_KILL_SWITCH_ACTIVATED",
    "EMERGENCY_KILL_SWITCH_DEACTIVATED",
    "CIRCUIT_BREAKER_TRIPPED",
]


def tool_invocation_count(
    event_type: Optional[str] = None,
    actor: Optional[str] = None,
    include_test_events: bool = False,
) -> int:
    """
    Hash-zincirli audit_ledger'da kayitli GERCEK sistem/araç cagri sayisini doner.

    Bos iddialarin yakalanmasi mekanizmasi (ResonAct): "1000 siparis var"
    iddia eden bir Task186 trace icin audit zincirinde kac olay GERCEK
    kayitliysa o sayilir. Filtreler:
      event_type          : yalnizca belirli olay tipi
      actor               : yalnizca belirli faktor (actor)
      include_test_events : CONCURRENCY_TEST_EVENT test kokenli olaylari dahil et
    """
    clauses: List[str] = []
    params: List[Any] = []

    if event_type is not None:
        clauses.append("event_type = ?")
        params.append(event_type)
    elif not include_test_events:
        placeholders = ",".join("?" for _ in TOOL_INVOCATION_EVENT_TYPES)
        clauses.append(f"event_type IN ({placeholders})")
        params.extend(TOOL_INVOCATION_EVENT_TYPES)

    if actor is not None:
        clauses.append("actor = ?")
        params.append(actor)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM audit_ledger {where}", tuple(params))
    return int(row["cnt"])


def verify_audit_chain() -> Dict[str, Any]:
    """
    audit_ledger SHA-256 Merkle zincirini bastan sona DOGRULAR (ResonAct:
    context health). Zincir kirik (biri tarafindan sonradan degistirilmis
    veya eszamanli yazarlarca yaristigi icin kopuk) ise
    {"is_valid": False, ...} doner.

    Not: arastirma bu DB'de kirik baglarin tamamina yakininin
    CONCURRENCY_TEST_EVENT (test stress yazarlari) oldugunu buldu —
    uretim olay tipleri zincirleme calisiyor. "broken_by_event_type"
    bu ayrimi korur, boylece uretim kokenli sayilar guvenilmez ilan
    edilmez.
    """
    rows = db.fetchall(
        "SELECT id, event_type, actor, payload_json, timestamp, previous_hash, current_hash "
        "FROM audit_ledger ORDER BY id ASC"
    )
    prev = "GENESIS_HASH_0000000000000000000000000000000000000000000000000000000000000000"
    broken_at: List[int] = []
    broken_by_type: Dict[str, int] = {}

    for r in rows:
        to_hash = f"{prev}:{r['event_type']}:{r['actor']}:{r['timestamp']}:{r['payload_json']}"
        recomputed = hashlib.sha256(to_hash.encode("utf-8")).hexdigest()
        if recomputed != r["current_hash"] or r["previous_hash"] != prev:
            broken_at.append(r["id"])
            broken_by_type[r["event_type"]] = broken_by_type.get(r["event_type"], 0) + 1
        prev = r["current_hash"]

    broken_count = len(broken_at)
    is_valid = broken_count == 0
    if is_valid:
        note = "audit zinciri saglam: tool_invocation_count degerleri degistirilmemis"
    else:
        prod_broken = sum(
            n for t, n in broken_by_type.items() if t in TOOL_INVOCATION_EVENT_TYPES
        )
        note = (
            f"audit zinciri {broken_count} noktada kirik ({dict(broken_by_type)}); "
            f"uretim olaylarindan kirik: {prod_broken}. "
            + ("uretim kokenli sayilar guvenilmez." if prod_broken else "kiriklar yalnizca test kokenli.")
        )

    return {
        "is_valid": is_valid,
        "verified_events": len(rows),
        "broken_count": broken_count,
        "broken_by_event_type": broken_by_type,
        "broken_at_ids": broken_at[:20],  # kapak: ilk 20 (cok buyuk listeyi bosuna tasma)
        "note": note,
    }


# ---------------------------------------------------------------------------
# 3) trace_based_success — GERCEK proposal trajectory (MASTraceBench)
# ---------------------------------------------------------------------------
def trace_based_success(idea_id: str) -> Dict[str, Any]:
    """
    Bir fikir icin GERCEK trajectory tabanli basari olcer.

    MASTraceBench (arXiv:2609.34496): yalnizca SONUC (MRR) raporlamak
    teshise izin vermez; proposal trajectory (adim-adim ilerleyis) gerekir.

    Basari kriteri (MRR DISLANIR — yanlis-pozitif koruma):
      1) 5 Sokratik adimin HEPSI icin gercen kayitli yanit var
      2) kayitli DDS >= 0.75 esigi (socratic_engine ile ayni esik)
      3) fikir durumu APPROVED_FOR_SYNTHESIS veya SYNTHESIZED

    Yanlis-negatif koruma: trajectory'si tam ve esik gecilmis bir fikir,
    MRR'i 0 olsa da BASARILI sayilmak ZORUNDADIR. MRR basarinin
    kriteri DEGILDIR; sadece bilgilendirme amacli raporlanir.
    """
    idea = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (idea_id,))
    if not idea:
        raise ValueError(f"Fikir bulunamadi: {idea_id}")

    trajectory = db.fetchall(
        "SELECT question_step, ai_evaluation_score, expert_response, regulatory_flags, edge_cases_identified "
        "FROM socratic_interviews WHERE idea_id = ? ORDER BY question_step ASC",
        (idea_id,),
    )

    steps_completed = sorted({int(r["question_step"]) for r in trajectory})
    per_step_scores = {int(r["question_step"]): float(r["ai_evaluation_score"]) for r in trajectory}
    n_regulatory_flags = 0
    n_edge_cases = 0
    for r in trajectory:
        try:
            n_regulatory_flags += len(json.loads(r["regulatory_flags"] or "[]"))
            n_edge_cases += len(json.loads(r["edge_cases_identified"] or "[]"))
        except (ValueError, TypeError):
            # Bozuk JSON kalanini sayma; ama istisna firlatip olcumu durdurma.
            continue

    final_dds = idea["domain_depth_score"]
    final_status = idea["status"]
    dds_threshold = 0.75

    is_trajectory_complete = steps_completed == [1, 2, 3, 4, 5]
    is_dds_passed = final_dds is not None and float(final_dds) >= dds_threshold
    is_status_terminal_success = final_status in ("APPROVED_FOR_SYNTHESIS", "SYNTHESIZED")

    is_successful = bool(is_trajectory_complete and is_dds_passed and is_status_terminal_success)

    # Bilgilendirme: venture'un iddia ettigi MRR — basari kriterine DAHIL DEGIL.
    venture = db.fetchone(
        "SELECT current_monthly_mrr_usd FROM ventures WHERE idea_id = ?", (idea_id,)
    )
    claimed_mrr_usd = float(venture["current_monthly_mrr_usd"]) if venture else 0.0

    return {
        "idea_id": idea_id,
        "final_status": final_status,
        "steps_completed": steps_completed,
        "trajectory_steps": len(trajectory),
        "per_step_scores": per_step_scores,
        "final_dds": float(final_dds) if final_dds is not None else None,
        "dds_threshold": dds_threshold,
        "regulatory_flags_total": n_regulatory_flags,
        "edge_cases_total": n_edge_cases,
        "is_successful": is_successful,
        "success_provenance": {
            "trajectory_complete": is_trajectory_complete,
            "dds_passed": is_dds_passed,
            "status_terminal_success": is_status_terminal_success,
            "criteria": "trajectory(5/5 adim) + DDS>=0.75 + terminal durum; MRR basarida kriter DEGILDIR",
        },
        # DURUST: MRR basari gosterimi DEGILDIR — sadece iddia raporu.
        "claimed_mrr_usd_NOT_a_success_criterion": round(claimed_mrr_usd, 2),
    }


# ---------------------------------------------------------------------------
# 4) token_cost — GERCEK token maliyeti (MASTraceBench: Token Cost)
# ---------------------------------------------------------------------------
# Maliyet gecusi (at-cost pass-through) ile ayni fiyat — quota_governor ile
# birebir tutarli: $0.0005 per 1k token.
OVERFLOW_PRICE_PER_1K_TOKENS = 0.0005


def token_cost(
    venture_id: Optional[str] = None,
    billing_month: Optional[str] = None,
) -> Dict[str, Any]:
    """
    GERCEK token tuketimini ve maliyetini olcer (token_quotas SUM).

    Olculenler (hepsi DB'den gelen gercek degerler):
      used_tokens          : tuketilen token adedi
      free_pool_value_usd  : ucretsiz kotalarin icerdigi deger
      overflow_tokens      : Kotra disi tuketim
      overflow_billed_usd  : Kotra disi icin zaten faturalanmis gercen tutar
      est_overflow_cost_usd: guncul tuketim icin at-cost maliyet tahmini
    """
    clauses: List[str] = []
    params: List[Any] = []
    if venture_id is not None:
        clauses.append("venture_id = ?")
        params.append(venture_id)
    if billing_month is not None:
        clauses.append("billing_cycle_month = ?")
        params.append(billing_month)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    agg = db.fetchone(
        f"""
        SELECT
            COALESCE(SUM(used_tokens), 0)          AS used_tokens,
            COALESCE(SUM(free_token_limit), 0)     AS free_limit,
            COALESCE(SUM(overflow_tokens), 0)      AS overflow_tokens,
            COALESCE(SUM(overflow_billed_usd), 0)  AS overflow_billed_usd,
            COUNT(*)                                AS records
        FROM token_quotas {where}
        """,
        tuple(params),
    )

    used = int(agg["used_tokens"])
    free_limit = int(agg["free_limit"])
    overflow_tokens = int(agg["overflow_tokens"])
    overflow_billed = float(agg["overflow_billed_usd"])

    return {
        "venture_id": venture_id,
        "billing_month": billing_month,
        "quota_records": int(agg["records"]),
        "used_tokens": used,
        "free_pool_limit_tokens": free_limit,
        "free_pool_value_usd": round((min(used, free_limit) / 1000.0) * OVERFLOW_PRICE_PER_1K_TOKENS, 4),
        "overflow_tokens": overflow_tokens,
        "overflow_billed_usd": round(overflow_billed, 4),
        "est_overflow_cost_usd": round((overflow_tokens / 1000.0) * OVERFLOW_PRICE_PER_1K_TOKENS, 4),
        "measurement_basis": "token_quotas SUM — gercek tuketim kayitlari",
    }


class TokenCostMeter:
    """
    Bir gorev suresince GERCEK token tuketimini olcen sayaç (context manager).

    Kullanim:
        with TokenCostMeter(expert_id, venture_id) as meter:
            meter.consume(1250)   # quota_governor uzerinden GERCEK kayit
            ...gorev...
        meter.tokens_consumed  # DB delta'sindan olculdu
        meter.cost_usd         # at-cost fiyat ile

    DURUST: tuketim, DB'deki used_tokens delta'sindan olculur; ne "tahmin"
    edilir ne de modele hint verilir. consume() yapilmazsa 0 doner.
    """

    def __init__(self, expert_id: str, venture_id: str):
        from syntropion_core.quota_governor import quota_governor  # gec import: dongu koruma

        self.expert_id = expert_id
        self.venture_id = venture_id
        self._governor = quota_governor
        self.tokens_consumed = 0
        self.cost_usd = 0.0
        self._before_used = 0
        self._before_overflow_billed = 0.0

    @staticmethod
    def _status(expert_id: str, venture_id: str) -> Dict[str, Any]:
        from syntropion_core.quota_governor import quota_governor

        return quota_governor.get_status(expert_id, venture_id)

    def __enter__(self) -> "TokenCostMeter":
        st = self._status(self.expert_id, self.venture_id)
        self._before_used = int(st["used_tokens"])
        self._before_overflow_billed = float(st["overflow_billed_usd"])
        return self

    def consume(self, token_count: int) -> Dict[str, Any]:
        """Gorev suresi token tuketimini quota_governor ile GERCEGE yazar."""
        res = self._governor.consume_tokens(self.expert_id, self.venture_id, token_count)
        self.tokens_consumed += int(token_count)
        return res

    def __exit__(self, *exc) -> bool:
        st = self._status(self.expert_id, self.venture_id)
        after_used = int(st["used_tokens"])
        after_billed = float(st["overflow_billed_usd"])
        # DURUST olcum: DB'deki GERCEK delta (consume cagrilari ile uyumlu).
        self.tokens_consumed = after_used - self._before_used
        self.cost_usd = round(
            (self.tokens_consumed / 1000.0) * OVERFLOW_PRICE_PER_1K_TOKENS
            + (after_billed - self._before_overflow_billed),
            6,
        )
        return False  # istisna'lari gecir


# ---------------------------------------------------------------------------
# 5) mrr_provenance — "fabricated MRR" teshisi (CEO Arena + ResonAct)
# ---------------------------------------------------------------------------
def mrr_provenance() -> Dict[str, Any]:
    """
    Idia edilen MRR ile, odemeli aboneliklerden DOGRULANAN MRR'yi karsilastirir.

    CEO Arena (arXiv:2609.34821) bulgusu: sentetik MRR iddalari
    gerceklilikten kopuktur. Bu fonksiyon "0 DB rows"-tur bos iddialari
    ResonAct tarzinda runtime'da yakalar.

    Kural (DURUST sozlesme #3):
      - b2b_subscriptions_satirlari == 0 iken claimed_mrr_usd > 0 =>
        verdict = "SIMULATED" (uydurma) — deger SILINMEZ, etiketlenir.
      - Dogrulanan deger, ACTIVE aboneliklerin monthly_price_usd toplamidir.
    """
    claimed_row = db.fetchone(
        "SELECT COALESCE(SUM(current_monthly_mrr_usd), 0) AS total FROM ventures"
    )
    claimed_mrr_usd = float(claimed_row["total"])

    verified_row = db.fetchone(
        """
        SELECT COALESCE(SUM(monthly_price_usd), 0) AS total,
               COUNT(*) AS rows
        FROM b2b_subscriptions
        WHERE status = 'ACTIVE'
        """
    )
    verified_mrr_usd = float(verified_row["total"])
    active_subscription_rows = int(verified_row["rows"])

    ventures_with_claim = int(
        db.fetchone(
            "SELECT COUNT(*) AS cnt FROM ventures WHERE current_monthly_mrr_usd > 0"
        )["cnt"]
    )

    is_simulated = bool(claimed_mrr_usd > 0 and active_subscription_rows == 0)

    if is_simulated:
        verdict = "SIMULATED"
        evidence = (
            "ventures tablosu iddia MRR'sini seed sabitlerinden ALIYOR; "
            "b2b_subscriptions tablosunda 0 ACTIVE satir var "
            "(hic gercen odemeli abone yok). Uydurma."
        )
    elif verified_mrr_usd < claimed_mrr_usd:
        verdict = "PARTIALLY_VERIFIED"
        evidence = (
            f"{active_subscription_rows} ACTIVE abonelikten {verified_mrr_usd:.2f} USD "
            f"dogrulandi; iddia {claimed_mrr_usd:.2f} USD — aradaki fark seed/demo kokenli."
        )
    else:
        verdict = "VERIFIED"
        evidence = (
            f"Butun iddia MRR'si {active_subscription_rows} ACTIVE abonelikten dogrulandi."
        )

    return {
        "claimed_mrr_usd": round(claimed_mrr_usd, 2),
        "verified_mrr_usd": round(verified_mrr_usd, 2),
        "active_subscription_rows": active_subscription_rows,
        "b2b_subscriptions_total_rows": db_row_count("b2b_subscriptions"),
        "ventures_with_mrr_claim": ventures_with_claim,
        "verdict": verdict,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# 6) honest_portfolio_snapshot — butun metrikleri tek dürüst raporda toplar
# ---------------------------------------------------------------------------
def honest_portfolio_snapshot() -> Dict[str, Any]:
    """
    Studio'nun dürüst operasyonel raporu. Hicbir deger uydurulmaz;
    "SIMULATED" bulgular oldugu gibi rapor edilir (MASTraceBench + ResonAct).
    """
    token_all = token_cost()
    return {
        "measurement_timestamp": db.fetchone(
            "SELECT COALESCE(MAX(timestamp), '') AS ts FROM audit_ledger"
        )["ts"],
        "db_row_counts": db_row_counts(),
        "mrr_provenance": mrr_provenance(),
        "tool_invocation_count": tool_invocation_count(),
        "audit_chain": verify_audit_chain(),
        "token_cost": token_all,
    }


# ---------------------------------------------------------------------------
# CLI yardimci: raporun insan-okur hali (loglar/ekran icin)
# ---------------------------------------------------------------------------
def render_honest_report() -> str:
    """Dürüst raporun düz-metin hali — CLI/README ciktilarinda kullanilir."""
    snap = honest_portfolio_snapshot()
    prov = snap["mrr_provenance"]
    chain = snap["audit_chain"]
    chain_label = "SAKLAM" if chain["is_valid"] else f"{chain['broken_count']} kirik"
    lines = [
        "=== SYNTROPION — DURUST METRIK RAPORU (AT-HONEST-001) ===",
        f"  db_row_count(b2b_subscriptions) : {prov['b2b_subscriptions_total_rows']}  <- 0 ise abonelik YOK",
        f"  iddia MRR (ventures seed)       : ${prov['claimed_mrr_usd']:,.2f}",
        f"  DOGRULANAN MRR (ACTIVE abonelik): ${prov['verified_mrr_usd']:,.2f}",
        f"  verdict                         : {prov['verdict']}",
        f"  evidence                        : {prov['evidence']}",
        f"  tool_invocation_count (audit)   : {snap['tool_invocation_count']} [zincir {chain_label}]",
        f"  token kullanilan                : {snap['token_cost']['used_tokens']} "
        f"(overflow ${snap['token_cost']['overflow_billed_usd']:.4f})",
        f"  audit-note                      : {chain['note']}",
        "  DURUST: '0 DB rows' gercen degil, gizlenmez; veri olmadigi rapor edilir.",
    ]
    return "\n".join(lines)
