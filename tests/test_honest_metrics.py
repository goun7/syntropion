"""
SYNTROPION OS — Dürüst Metrik Çerçevesi Testleri (AT-HONEST-001)

Akademik dayanak: MASTraceBench (arXiv:2609.34496), ResonAct
(arXiv:2609.34701), CEO Arena (arXiv:2609.34821).

Bu testler uydurma deger URETMEZ; her olcumun GERCEK bir SQL
COUNT/SUM'dan geldigini dogrular. Mevcut 53-test baseline'ina
(89-passed) ZARAR VERMEZ.
"""

import uuid
import sqlite3

import pytest

from syntropion_core.database import db
from syntropion_core import honest_metrics as hm


@pytest.fixture(autouse=True)
def setup_schema_and_pilots():
    """Var olan test fixture aliskanligi: sema + 5 pilot seed."""
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


# ---------------------------------------------------------------------------
# 1) db_row_count — GERCEK satir sayisi verir (0 ise 0 döner)
# ---------------------------------------------------------------------------
def test_db_row_count_returns_real_numbers_including_zero():
    """db_row_count gerçek sayı döndürmeli; b2b_subscriptions için 0 (gerçek)."""
    # b2b_subscriptions: pilotlar icin GERCEKTEN 0 satir — abonelik YOK.
    subs = hm.db_row_count("b2b_subscriptions")
    assert subs == 0, "b2b_subscriptions 0 olmali (gercek abonelik yok)"

    # ventures seed sonrasi gercekten >=5 satir iceriyor.
    assert hm.db_row_count("ventures") >= 5

    # Tablo listesi canli katalogdan geliyor; bilinmeyen tablo REDDEDILIR.
    with pytest.raises(ValueError):
        hm.db_row_count("bu_tablo_yok_12345")

    # db_row_counts butun tablolari icerir ve hepsi int'dir (float/None degil).
    counts = hm.db_row_counts()
    assert "b2b_subscriptions" in counts
    assert all(isinstance(v, int) and v >= 0 for v in counts.values())

    # Bagimsiz baglanti ile ayni deger (modul uydurmuyor).
    direct = sqlite3.connect(db.db_path)
    try:
        direct.row_factory = sqlite3.Row
        expected = direct.execute("SELECT COUNT(*) FROM b2b_subscriptions").fetchone()[0]
        assert subs == expected == 0
    finally:
        direct.close()


# ---------------------------------------------------------------------------
# 2) tool_invocation_count — GERCEK araç cagri sayisini sayar
# ---------------------------------------------------------------------------
def test_tool_invocation_count_counts_real_audit_events():
    """tool_invocation_count hash-zincirli audit_ledger'dan GERCEK sayar."""
    before = hm.tool_invocation_count()

    # Gercen bir sistem olayi yaz (bu bir araç cagrisidir).
    db.log_audit_event(
        event_type="STAKE_ESCROW_HELD",
        actor="test-honest-metrics",
        payload={"idea_id": "idea-honest-test", "amount_usd": "10.00"},
    )

    after = hm.tool_invocation_count()
    assert after == before + 1, f"sayi artmadi: {before} -> {after}"

    # event_type filtresi calisir.
    assert hm.tool_invocation_count(event_type="STAKE_ESCROW_HELD") >= 1
    assert hm.tool_invocation_count(event_type="VENTURE_SYNTHESIZED") >= 0

    # actor filtresi calisir; baska actor gizli sayilara dahil olmaz.
    assert hm.tool_invocation_count(actor="test-honest-metrics") >= 1
    assert hm.tool_invocation_count(actor="no-such-actor-zzz") == 0

    # Test kokenli olaylar varsayilan olarak HARIC tutulur (uretim sayisi).
    prod_count = hm.tool_invocation_count()
    all_count = hm.tool_invocation_count(include_test_events=True)
    assert all_count >= prod_count


# ---------------------------------------------------------------------------
# 3) trace_based_success — MRR'den bagimsiz; false-negative vermez
# ---------------------------------------------------------------------------
def _deep_response():
    """Sokratik motorun yuksek DDS ile gecirigi bir gercen uzman yaniti."""
    return (
        "Radyoloji onkoloji kliniklerinde RECIST 1.1 kriterlerine gore lezyon "
        "olcumlerini onceki BT/MR tetkiklerle karsilastirmak radyolog basina "
        "gunluk 2.5 saat alir; DICOM serileri PACS uzerinden alinir, JSON data "
        "contract ile epikriz raporu uretilir. Guncel cozumumiz, hastanede 2 "
        "farkli PACS vendor'u oldugu icin iki sistemi yan yana acip milimetrik "
        "olcum yapmaktir; bu surecte %18 zaman kaybi ve 6102 sayili TTK ve "
        "KVKK mevzuatina uyumsuzluk riski doguyor. Eger DICOM serisi eksikse "
        "veya metadata bozuksa sistem 4 saat icinde escrow'a dusmelidir; "
        "kronik bobrek yetmezligi hastalarinda kontrast doz asimi durumunda "
        "otomatik uyarilma katı kuralidir. Aylik 8358 USD lisans maliyeti "
        "karsiliginda 14 saatlik radyolog zamanini gerri kazanir."
    )


def test_trace_based_success_no_false_negative_without_mrr():
    """MASTraceBench: trajectory tam + DDS gectiyse BAŞARILI sayılır —
    MRR = 0 olsa bile false-negative VERILMEZ."""
    # 1) Taze bir expert + idea kur (gercek trajectory icin).
    expert_id = f"exp-honest-{uuid.uuid4().hex[:8]}"
    idea_id = f"idea-honest-{uuid.uuid4().hex[:8]}"
    now = db.fetchone("SELECT COALESCE(MAX(created_at), '') AS c FROM domain_ideas")["c"] or "2026-09-01T00:00:00+00:00"
    db.execute(
        "INSERT INTO domain_experts (expert_id, email, full_name, phone_number, "
        "industry_domain, years_of_experience, ip_assignment_signed, created_at, updated_at) "
        "VALUES (?,?,?,?,'healthcare',12,1,?,?)",
        (expert_id, f"{expert_id}@hastane.com.tr", "Dr. Honest Test", "+905321112299", now, now),
    )
    db.execute(
        "INSERT INTO domain_ideas (idea_id, expert_id, title, problem_statement, "
        "target_audience, current_workaround, stake_amount_usd, stake_payment_status, "
        "status, created_at, updated_at) "
        "VALUES (?,?,?,'problem','audience','workaround',10.00,'HELD_IN_ESCROW','IN_INTERVIEW',?,?)",
        (idea_id, expert_id, "Honest Test Radyoloji Ajanı", now, now),
    )

    # 2) 5 Sokratik adimi da gercek isle — bu proposal trajectory'dir.
    from syntropion_core.socratic_engine import socratic_engine
    for step in range(1, 6):
        res = socratic_engine.process_step(idea_id, step, _deep_response())
        assert res["score"] >= 0.75, f"adim {step} DDS dusuk: {res['score']}"

    # 3) Trajectory-tabanli basari olcumu.
    result = hm.trace_based_success(idea_id)

    assert result["steps_completed"] == [1, 2, 3, 4, 5]
    assert result["trajectory_steps"] == 5
    assert result["final_dds"] is not None and result["final_dds"] >= 0.75
    assert result["is_successful"] is True, "false-negative: trajectory basarili ama rapor degil"

    # 4) MRR basari kriteri DEGIL: bu fikirin venture MRR'i 0 (venture yok)
    #    yine de basarili sayildi — MRR yanlis-pozitiflere hapsolmamali.
    assert result["claimed_mrr_usd_NOT_a_success_criterion"] == 0.0
    assert "MRR" in result["success_provenance"]["criteria"]


def test_trace_based_success_rejects_empty_trajectory_despite_mrr():
    """Yanlis-pozitif korumasi: trajectory'siz (5 adim tamamlanmamis) bir
    fikir, venture MRR'i yuksek olsa bile BASARILI sayilmaz."""
    pilot_idea = "idea-pilot-002-lexnotice"  # MRR'si $8,940 iddia edilen pilot

    # Pilot icin socratic_interviews kaydi YOK (seed'te interview acilmamis).
    direct = sqlite3.connect(db.db_path)
    try:
        n = direct.execute(
            "SELECT COUNT(*) FROM socratic_interviews WHERE idea_id = ?",
            (pilot_idea,),
        ).fetchone()[0]
        assert n == 0, "bu test pilot icin bos trajectory gerektirir"
    finally:
        direct.close()

    result = hm.trace_based_success(pilot_idea)
    assert result["is_successful"] is False, "yanlis-pozitif: trajectory yok ama basarili"
    assert result["claimed_mrr_usd_NOT_a_success_criterion"] > 0.0  # iddia var
    assert result["success_provenance"]["trajectory_complete"] is False


# ---------------------------------------------------------------------------
# 4) token_cost — GERCEK token tuketimini ve maliyetini olcer
# ---------------------------------------------------------------------------
def test_token_cost_measures_real_consumption():
    """TokenCostMeter DB delta'sindan olcer; uydurma tahmin degil."""
    expert_id = f"exp-tok-{uuid.uuid4().hex[:8]}"
    venture_id = f"ven-tok-{uuid.uuid4().hex[:8]}"
    idea_id = f"idea-tok-{uuid.uuid4().hex[:8]}"
    now = db.fetchone("SELECT COALESCE(MAX(created_at), '') AS c FROM domain_experts")["c"] or "2026-09-01T00:00:00+00:00"

    db.execute(
        "INSERT INTO domain_experts (expert_id, email, full_name, phone_number, "
        "industry_domain, years_of_experience, ip_assignment_signed, created_at, updated_at) "
        "VALUES (?,?,?,'+905321113344','legal',10,1,?,?)",
        (expert_id, f"{expert_id}@hukuk.av.tr", "Av. Token Test", now, now),
    )
    # ventures.idea_id UNIQUE oldugu icin token olcum venture'ina ozel fikir kurulur.
    db.execute(
        "INSERT INTO domain_ideas (idea_id, expert_id, title, problem_statement, "
        "target_audience, current_workaround, stake_amount_usd, stake_payment_status, "
        "status, created_at, updated_at) "
        "VALUES (?,?,?,'problem','audience','workaround',10.00,'PENDING','SUBMITTED',?,?)",
        (idea_id, expert_id, "Honest Token Test Fikri", now, now),
    )
    # api_prefix_path UNIQUE oldugundan kalici test kalintilarina karsi benzersiz yap.
    unique_path = f"/api/v1/tok-{uuid.uuid4().hex[:8]}"
    db.execute(
        "INSERT INTO ventures (venture_id, idea_id, code_slug, display_name, tagline, "
        "docker_container_name, git_commit_sha, api_prefix_path, status, "
        "target_monthly_mrr_usd, current_monthly_mrr_usd, active_b2b_subscribers, "
        "created_at, updated_at) "
        "VALUES (?,?,?,'Honest Token Venture','tag','ctr','sha',?,'ALPHA_TEST',0,0,0,?,?)",
        (venture_id, idea_id, f"token-venture-{uuid.uuid4().hex[:6]}", unique_path, now, now),
    )

    consumed = 1500
    with hm.TokenCostMeter(expert_id, venture_id) as meter:
        meter.consume(consumed)

    # DURUST olcum: DB delta = gercek tuketilen.
    assert meter.tokens_consumed == consumed, f"delta uyumsuz: {meter.tokens_consumed}"
    # At-cost fiyat: $0.0005 per 1k token.
    expected_cost = round((consumed / 1000.0) * 0.0005, 6)
    assert abs(meter.cost_usd - expected_cost) < 1e-6

    # token_cost() toplami DB ile ayni (SUM).
    agg = hm.token_cost(venture_id=venture_id)
    direct = sqlite3.connect(db.db_path)
    try:
        direct.row_factory = sqlite3.Row
        row = direct.execute(
            "SELECT used_tokens, overflow_billed_usd FROM token_quotas WHERE venture_id = ?",
            (venture_id,),
        ).fetchone()
        assert agg["used_tokens"] == int(row["used_tokens"])
        assert agg["quota_records"] >= 1
        assert "measurement_basis" in agg
    finally:
        direct.close()


# ---------------------------------------------------------------------------
# 5) mrr_provenance — "fabricated MRR -> 0 DB rows" teshisi (CEO Arena/ResonAct)
# ---------------------------------------------------------------------------
def test_mrr_provenance_detects_simulation_with_zero_subscription_rows():
    """İddia MRR $44,175 ama b2b_subscriptions=0 → SIMULATED teshisi."""
    prov = hm.mrr_provenance()

    # Teshis: pilot seed MRR'leri 0 abonelikle dogrulanamaz.
    assert prov["claimed_mrr_usd"] > 0.0
    assert prov["active_subscription_rows"] == 0
    assert prov["b2b_subscriptions_total_rows"] == 0
    assert prov["verdict"] == "SIMULATED"
    assert prov["verified_mrr_usd"] == 0.0

    # Simulasyon kaniti rapor'da acikca yazili (silme yok, etiketleme var).
    assert "0" in prov["evidence"] or "yok" in prov["evidence"].lower()

    # ---- Simulasyon kapatma testi: GERCEK bir ACTIVE abonelik eklenince
    #      dogrulanan MRR artar, verdict degisir (uydurma degil olcum).
    sub_id = f"sub-{uuid.uuid4().hex[:10]}"
    ven = db.fetchone("SELECT venture_id FROM ventures WHERE current_monthly_mrr_usd > 0")
    assert ven is not None
    now = db.fetchone("SELECT COALESCE(MAX(created_at), '') AS c FROM ventures")["c"]
    try:
        db.execute(
            "INSERT INTO b2b_subscriptions (subscription_id, venture_id, tenant_id, "
            "customer_company_name, customer_email, plan_tier, monthly_price_usd, "
            "stripe_subscription_id, status, current_period_start, current_period_end, created_at) "
            "VALUES (?,?,?,'Acme Health Inc','ops@acmehealth.com','ENTERPRISE',2500.00, "
            "?, 'ACTIVE', ?, ?, ?)",
            (sub_id, ven["venture_id"], f"tenant-{sub_id[-6:]}", f"sub_stripe_{sub_id}",
             now, now, now),
        )
        prov2 = hm.mrr_provenance()
        assert prov2["active_subscription_rows"] == 1
        assert prov2["verified_mrr_usd"] == 2500.00
        # Hala iddia > dogrulanan → PARTIALLY_VERIFIED (gerceklik payi olculer).
        assert prov2["claimed_mrr_usd"] > prov2["verified_mrr_usd"]
        assert prov2["verdict"] == "PARTIALLY_VERIFIED"
    finally:
        # Diger testleri etkilememesi icin ekleme geri alinir.
        db.execute("DELETE FROM b2b_subscriptions WHERE subscription_id = ?", (sub_id,))

    # Snapshot butun parcalari icerir (tek dürüst rapor).
    snap = hm.honest_portfolio_snapshot()
    assert set(snap.keys()) >= {
        "db_row_counts", "mrr_provenance", "tool_invocation_count",
        "audit_chain", "token_cost",
    }
    assert snap["mrr_provenance"]["b2b_subscriptions_total_rows"] == 0

    # Insan-okur rapor uretiliyor ve DURUST sozunu iceriyor.
    report = hm.render_honest_report()
    assert "DURUST" in report
    assert "SIMULATED" in report or "b2b_subscriptions" in report
