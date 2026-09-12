"""
Tests for 5-Step Socratic Interrogation and Domain Depth Score (DDS) evaluation.
"""

import pytest
from syntropion_core.database import db
from syntropion_core.socratic_engine import socratic_engine


@pytest.fixture(autouse=True)
def setup_seed():
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


def test_socratic_shallow_response_low_score():
    """Verifies that short, shallow, generic responses receive low scores."""
    res = socratic_engine.evaluate_response_depth(
        step=1,
        response_text="Bu problem çok zor ve zaman alıyor.",
        domain_hint="healthcare"
    )
    assert res["score"] < 0.40


def test_socratic_expert_deep_response_high_score():
    """Verifies that rich responses with metrics, domain terms and laws receive high depth scores."""
    deep_response = (
        "Onkoloji hastalarında RECIST 1.1 kriterlerine göre lezyon çaplarının BT ve MR raporlarında "
        "milimetrik kıyaslanması radyoloğun günde 2.5 saatini almaktadır. 2 mm'lik gözden kaçan bir "
        "progresyon hastada metastaz riskini %35 artırır. 6102 sayılı TTK, Sağlık Bakanlığı ve EU AI Act "
        "2026 düzenlemeleri uyarınca hekim hatası durumunda 1.500.000 TL malpraktis tazminat riski doğmaktadır. "
        "Eğer hastanın önceki tetkik DICOM görüntüleri eksik ise sistem epikriz PDF'lerini taramalıdır."
    )
    res = socratic_engine.evaluate_response_depth(
        step=1,
        response_text=deep_response,
        domain_hint="healthcare"
    )
    assert res["score"] >= 0.80
    assert len(res["regulatory_flags"]) > 0


def test_socratic_5_step_end_to_end_pass():
    """Verifies 5-step interrogation flow ending with DDS >= 0.75 approval."""
    import uuid
    expert_id = "exp-pilot-001-radiologist"
    idea_id = f"idea-test-socratic-pass-{uuid.uuid4().hex[:8]}"

    db.execute(
        """
        INSERT OR IGNORE INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            stake_amount_usd, stake_payment_status, status, created_at, updated_at
        ) VALUES (?, ?, 'Rad AI Engine', 'Problem', 'Audience', 10.00, 'HELD_IN_ESCROW', 'SUBMITTED', '2026-01-01', '2026-01-01')
        """,
        (idea_id, expert_id)
    )

    steps_responses = [
        "Onkoloji hastalarında RECIST 1.1 kriterlerinde BT ve MR lezyonlarının milimetrik ölçümü radyoloğun günde 2.5 saatini alıyor. 6698 KVKK ve EU AI Act 2026 düzenlemeleri uyarınca veri güvenliği ve malpraktis sorumluluğu şarttır.",
        "İstisna olarak lezyon nekroze olmuşsa veya kavitasyonel ise çap değil hacim hesabı gerekir. Eğer veri eksikse veya DICOM serisi bozuksa sistem hekime uyarı vermelidir.",
        "5846 FSEK ve Sağlık Bakanlığı teşhis protokolleri geçerlidir. Hatalı tanı durumunda 2.000.000 TL tazminat ve cezai sorumluluk riski bulunmaktadır.",
        "Girdi formatı PACS DICOM ve epikriz PDF metinleridir. Çıktı ise HL7 FHIR uyumlu JSON ve onaylanmış rapor taslağıdır.",
        "Klinik başına aylık $199 MRR kabul görmektedir. Radyolog başına ayda 50 saat kazandırdığı için ROI %400 üzerinde ölçülmüştür."
    ]

    for step_num, resp in enumerate(steps_responses, start=1):
        step_res = socratic_engine.process_step(idea_id, step_num, resp)
        if step_num < 5:
            assert step_res["is_completed"] is False
            assert step_res["status"] == "IN_PROGRESS"
        else:
            assert step_res["is_completed"] is True
            assert step_res["status"] == "PASSED_THRESHOLD"
            assert step_res["domain_depth_score_running"] >= 0.75

    updated_idea = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (idea_id,))
    assert updated_idea["stake_payment_status"] == "CAPTURED_TO_EQUITY"


def test_socratic_5_step_rejection_flow():
    import uuid
    from syntropion_core.database import get_current_iso_time
    now = get_current_iso_time()
    idea_id = f"idea-reject-{uuid.uuid4().hex[:6]}"
    expert_id = f"exp-rej-{uuid.uuid4().hex[:6]}"

    db.execute(
        "INSERT INTO domain_experts (expert_id, email, full_name, industry_domain, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (expert_id, f"rej_{uuid.uuid4().hex[:6]}@domain.com", "Rej Expert", "general", now, now)
    )
    db.execute(
        """
        INSERT INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            stake_amount_usd, stake_payment_status, status, created_at, updated_at
        ) VALUES (?, ?, 'Weak Idea', 'Short problem', 'Anyone', 10.00, 'HELD_IN_ESCROW', 'IN_INTERVIEW', ?, ?)
        """,
        (idea_id, expert_id, now, now)
    )

    # 5 shallow steps with minimal 1-word answers
    for s in range(1, 6):
        res = socratic_engine.process_step(idea_id, s, "Yok")

    assert res["status"] == "REJECTED_LOW_SCORE"
    assert res["domain_depth_score_running"] < 0.75

    # Verify refund was recorded
    updated_idea = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (idea_id,))
    assert updated_idea["stake_payment_status"] == "REFUNDED"


def test_socratic_nonexistent_idea():
    with pytest.raises(ValueError, match="Idea not found"):
        socratic_engine.process_step("non-existent-idea-404", 1, "Some response")
