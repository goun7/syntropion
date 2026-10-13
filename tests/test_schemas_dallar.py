"""test_schemas_dallar.py — syntropion_core/schemas.py dal-kesen testleri

17 pydantic-v2 veri-sözleşmesinin TÜM doğrulama-dalları: pattern/min/max/
ge/le/gt kısıtlamaları, Literal-tipleri, varsayılan-değerler, iç içe-model
doğrulaması, Optional-None varsayılanları ve serileştirme gidiş-dönüşü.
( Modül saf-tır: db/IPC/ağ YOK — Kural-4 otomatik-sağlanır.)

TÜM DALLAR ( her-model):
  - geçerli-kurulum + tüm-alanlar-doğru
  - varsayılan-değerler ( Optional=None, bool=False, liste=[], sayısal-sabitler)
  - sınır-değerleri ( min/max dahil-hariç)
  - pattern / Literal / iç içe-doğrulama istisnaları
  - model_dump → model_validate gidiş-dönüşü

Modeller:
  1. DomainExpertCreate ( email-pattern, 2-150 ad, 2-100 domain, 0-70 yıl)
  2. ProposalSubmitRequest ( iç içe-expert, 5-255 başlık, ≥20 problem, 5-100 stake)
  3. ProposalSubmitResponse ( Literal SUCCESS|FAILED)
  4. SocraticStepRequest ( step 1-5, ≥10 yanıt)
  5. SocraticEvaluationResult ( score 0-1, Literal 3-durum)
  6. StakeStatusResponse ( Literal 4-durum)
  7. VentureSynthesizeRequest ( auto_deploy False varsayılan)
  8. VentureResponse ( tagline Optional)
  9. GeneratedCodeArtifact ( openapi Dict, ast bool)
  10. MilestoneUnlockRequest ( tier 1-3, proof_data {})
  11. VestingStatusResponse ( active_milestones [])
  12. QuotaConsumeRequest ( tokens > 0)
  13. QuotaStatusResponse ( Literal 3-uyarı)
  14. RevenueCalculateRequest ( gross ≥ 0, infra 0)
  15. RevenueDistributionResponse ( tüm-alanlar-zorunlu)
  16. OutboundLeadCampaignRequest
  17. LeadOutreachResponse

Kural-1: SADECE-yeni-dosya. Kural-4: saf-in-memory ( yan-etki-YOK).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from syntropion_core import schemas
from syntropion_core.schemas import (
    DomainExpertCreate,
    GeneratedCodeArtifact,
    LeadOutreachResponse,
    MilestoneUnlockRequest,
    OutboundLeadCampaignRequest,
    ProposalSubmitRequest,
    ProposalSubmitResponse,
    QuotaConsumeRequest,
    QuotaStatusResponse,
    RevenueCalculateRequest,
    RevenueDistributionResponse,
    SocraticEvaluationResult,
    SocraticStepRequest,
    StakeStatusResponse,
    VentureResponse,
    VentureSynthesizeRequest,
    VestingStatusResponse,
)

GECERLI_EXPERT = {
    "email": "ahmet.yilmaz@hastane.com.tr",
    "full_name": "Dr. Ahmet Yılmaz",
    "industry_domain": "healthcare",
    "years_of_experience": 16,
}


# ---------------------------------------------------------------------------
# 1. DomainExpertCreate
# ---------------------------------------------------------------------------
class TestDomainExpertCreate:
    def test_gecerli_kurulum(self):
        e = DomainExpertCreate(**GECERLI_EXPERT)
        assert e.email == "ahmet.yilmaz@hastane.com.tr"
        assert e.full_name == "Dr. Ahmet Yılmaz"
        assert e.industry_domain == "healthcare"
        assert e.years_of_experience == 16

    def test_varsayilan_degerler(self):
        e = DomainExpertCreate(**GECERLI_EXPERT)
        assert e.phone_number is None
        assert e.iban is None
        assert e.ip_assignment_signed is True
        assert e.fsek_terms_version == "v1.0-2026"

    @pytest.mark.parametrize(
        "email",
        ["duz-adres", "a@b", "@b.com", "a b@c.com", "a@b.com ", "ahmet@yok"],
    )
    def test_gecersiz_email_pattern(self, email):
        with pytest.raises(ValidationError) as hata:
            DomainExpertCreate(**{**GECERLI_EXPERT, "email": email})
        assert hata.value.errors()[0]["type"] == "string_pattern_mismatch"

    @pytest.mark.parametrize(
        "email", ["a@b.io", "x+y@z.com.tr", "1_2.3-4@sub.domain.co"]
    )
    def test_gecerli_email_pattern(self, email):
        assert DomainExpertCreate(**{**GECERLI_EXPERT, "email": email}).email == email

    @pytest.mark.parametrize(
        "alan, deger, beklenen_tip",
        [
            ("full_name", "A", "string_too_short"),          # < 2
            ("full_name", "k" * 151, "string_too_long"),     # > 150
            ("industry_domain", "a", "string_too_short"),    # < 2
            ("industry_domain", "k" * 101, "string_too_long"),
        ],
    )
    def test_uzunluk_kisitlamalari(self, alan, deger, beklenen_tip):
        with pytest.raises(ValidationError) as hata:
            DomainExpertCreate(**{**GECERLI_EXPERT, alan: deger})
        assert hata.value.errors()[0]["type"] == beklenen_tip

    @pytest.mark.parametrize("yil, gecerli", [(-1, False), (0, True), (70, True), (71, False)])
    def test_yil_deneyimi_sinirlari(self, yil, gecerli):
        if gecerli:
            assert DomainExpertCreate(
                **{**GECERLI_EXPERT, "years_of_experience": yil}
            ).years_of_experience == yil
        else:
            with pytest.raises(ValidationError) as hata:
                DomainExpertCreate(**{**GECERLI_EXPERT, "years_of_experience": yil})
            assert hata.value.errors()[0]["type"] in {
                "greater_than_equal", "less_than_equal",
            }

    def test_eksik_zorunlu_alan(self):
        with pytest.raises(ValidationError) as hata:
            DomainExpertCreate(email="a@b.io")
        assert len(hata.value.errors()) == 3  # full_name, industry_domain, years


# ---------------------------------------------------------------------------
# 2. ProposalSubmitRequest
# ---------------------------------------------------------------------------
class TestProposalSubmitRequest:
    GECSIZ = {
        "expert": dict(GECERLI_EXPERT),
        "title": "RadTrack AI Lezyon Kıyaslama",
        "problem_statement": "Radyologlar raporları elle kıyaslıyor.",
        "target_audience": "Onkoloji klinikleri",
    }

    def test_gecerli_kurulum(self):
        p = ProposalSubmitRequest(**self.GECSIZ)
        assert p.expert.email == "ahmet.yilmaz@hastane.com.tr"
        assert p.title == "RadTrack AI Lezyon Kıyaslama"
        assert p.current_workaround is None

    def test_stake_varsayilan_ve_sinirlar(self):
        assert ProposalSubmitRequest(**self.GECSIZ).stake_amount_usd == 10.00
        assert ProposalSubmitRequest(**{**self.GECSIZ, "stake_amount_usd": 5.00}).stake_amount_usd == 5.00
        assert ProposalSubmitRequest(**{**self.GECSIZ, "stake_amount_usd": 100.00}).stake_amount_usd == 100.00

    @pytest.mark.parametrize("stake", [4.99, 100.01, -5.0])
    def test_stake_disinda_hata(self, stake):
        with pytest.raises(ValidationError):
            ProposalSubmitRequest(**{**self.GECSIZ, "stake_amount_usd": stake})

    @pytest.mark.parametrize(
        "alan, deger",
        [
            ("title", "Kısa"),                                    # < 5
            ("problem_statement", "çok kısa problem"),             # < 20
            ("target_audience", "Az"),                            # < 5
        ],
    )
    def test_uzunluk_alt_sinirlari(self, alan, deger):
        with pytest.raises(ValidationError) as hata:
            ProposalSubmitRequest(**{**self.GECSIZ, alan: deger})
        assert hata.value.errors()[0]["type"] == "string_too_short"

    def test_baslik_255_ust_sinir(self):
        uzun = {**self.GECSIZ, "title": "k" * 256}
        with pytest.raises(ValidationError) as hata:
            ProposalSubmitRequest(**uzun)
        assert hata.value.errors()[0]["type"] == "string_too_long"
        # 255 tam-sınır geçerli
        assert ProposalSubmitRequest(**{**self.GECSIZ, "title": "k" * 255})

    def test_ice_ice_expert_dogrulama_yayilir(self):
        gecersiz = {**self.GECSIZ, "expert": {**GECERLI_EXPERT, "email": "kotu"}}
        with pytest.raises(ValidationError) as hata:
            ProposalSubmitRequest(**gecersiz)
        assert hata.value.errors()[0]["loc"] == ("expert", "email")

    def test_fsek_ve_stripe_varsayilanlari(self):
        p = ProposalSubmitRequest(**self.GECSIZ)
        assert p.fsek_clickwrap_accepted is True
        assert p.stripe_payment_method_id == "pm_mock_card_test_success"


# ---------------------------------------------------------------------------
# 3. ProposalSubmitResponse
# ---------------------------------------------------------------------------
class TestProposalSubmitResponse:
    TUM = {
        "status": "SUCCESS", "idea_id": "idea-1", "expert_id": "exp-1",
        "stake_status": "HELD_IN_ESCROW", "amount_held_usd": 10.0,
        "next_step": "interview", "interview_session_url": "https://x/y",
        "fsek_contract_hash": "abc123",
    }

    @pytest.mark.parametrize("durum", ["SUCCESS", "FAILED"])
    def test_gecerli_durumlar(self, durum):
        assert ProposalSubmitResponse(**{**self.TUM, "status": durum}).status == durum

    def test_gecersiz_durum_literal(self):
        with pytest.raises(ValidationError) as hata:
            ProposalSubmitResponse(**{**self.TUM, "status": "PENDING"})
        assert hata.value.errors()[0]["type"] == "literal_error"

    def test_eksik_alan_hatasi(self):
        with pytest.raises(ValidationError) as hata:
            ProposalSubmitResponse(status="SUCCESS")
        assert len(hata.value.errors()) == 7


# ---------------------------------------------------------------------------
# 4. SocraticStepRequest
# ---------------------------------------------------------------------------
class TestSocraticStepRequest:
    def test_gecerli_kurulum(self):
        r = SocraticStepRequest(idea_id="idea-1", step=3,
                                expert_response="Detaylı bir yanıt metni")
        assert r.step == 3

    @pytest.mark.parametrize("adim, gecerli",
                             [(0, False), (1, True), (5, True), (6, False)])
    def test_adim_sinirlari_1_5(self, adim, gecerli):
        if gecerli:
            assert SocraticStepRequest(
                idea_id="i", step=adim, expert_response="yeterince uzun yanıt"
            ).step == adim
        else:
            with pytest.raises(ValidationError) as hata:
                SocraticStepRequest(idea_id="i", step=adim,
                                    expert_response="yeterince uzun yanıt")
            assert hata.value.errors()[0]["type"] in {
                "greater_than_equal", "less_than_equal",
            }

    def test_kisa_yanit_hatasi(self):
        with pytest.raises(ValidationError) as hata:
            SocraticStepRequest(idea_id="i", step=1, expert_response="kısa")
        assert hata.value.errors()[0]["type"] == "string_too_short"


# ---------------------------------------------------------------------------
# 5. SocraticEvaluationResult
# ---------------------------------------------------------------------------
class TestSocraticEvaluationResult:
    TUM = {
        "step": 1, "question_text": "Soru?", "score": 0.85,
        "domain_depth_score_running": 1.70, "is_completed": False,
        "status": "IN_PROGRESS", "feedback": "İyi",
    }

    def test_gecerli_kurulum_ve_varsayilanlar(self):
        r = SocraticEvaluationResult(**self.TUM)
        assert r.regulatory_flags == []
        assert r.edge_cases_identified == []
        assert r.next_question is None

    @pytest.mark.parametrize("skor, gecerli",
                             [(-0.01, False), (0.0, True), (1.0, True), (1.01, False)])
    def test_skor_sinirlari_0_1(self, skor, gecerli):
        if gecerli:
            assert SocraticEvaluationResult(**{**self.TUM, "score": skor}).score == skor
        else:
            with pytest.raises(ValidationError):
                SocraticEvaluationResult(**{**self.TUM, "score": skor})

    @pytest.mark.parametrize("durum", ["IN_PROGRESS", "PASSED_THRESHOLD", "REJECTED_LOW_SCORE"])
    def test_status_literal_uc_deger(self, durum):
        assert SocraticEvaluationResult(**{**self.TUM, "status": durum}).status == durum

    def test_status_gecersiz(self):
        with pytest.raises(ValidationError) as hata:
            SocraticEvaluationResult(**{**self.TUM, "status": "DRAFT"})
        assert hata.value.errors()[0]["type"] == "literal_error"

    def test_liste_alanlari_doldurulur(self):
        r = SocraticEvaluationResult(**{**self.TUM, "regulatory_flags": ["KVKK"],
                                        "edge_cases_identified": ["x"],
                                        "next_question": "Sonraki?"})
        assert r.regulatory_flags == ["KVKK"]
        assert r.next_question == "Sonraki?"


# ---------------------------------------------------------------------------
# 6. StakeStatusResponse
# ---------------------------------------------------------------------------
class TestStakeStatusResponse:
    TUM = {"idea_id": "idea-1", "stake_amount_usd": 10.0, "status": "HELD_IN_ESCROW"}

    @pytest.mark.parametrize("durum",
                             ["PENDING", "HELD_IN_ESCROW", "REFUNDED", "CAPTURED_TO_EQUITY"])
    def test_dort_durum_literal(self, durum):
        assert StakeStatusResponse(**{**self.TUM, "status": durum}).status == durum

    def test_gecersiz_durum(self):
        with pytest.raises(ValidationError) as hata:
            StakeStatusResponse(**{**self.TUM, "status": "BILINMIYOR"})
        assert hata.value.errors()[0]["type"] == "literal_error"

    def test_optional_varsayilanlar_none(self):
        r = StakeStatusResponse(**self.TUM)
        assert r.stripe_charge_id is None
        assert r.refund_transaction_id is None
        assert r.decision_reason is None


# ---------------------------------------------------------------------------
# 7. VentureSynthesizeRequest
# ---------------------------------------------------------------------------
class TestVentureSynthesizeRequest:
    def test_gecerli_ve_varsayilanlar(self):
        r = VentureSynthesizeRequest(idea_id="idea-1")
        assert r.idea_id == "idea-1"
        assert r.target_slug is None
        assert r.auto_deploy_container is False

    def test_ozel_slug_ve_deploy(self):
        r = VentureSynthesizeRequest(idea_id="i", target_slug="ozel", auto_deploy_container=True)
        assert r.target_slug == "ozel"
        assert r.auto_deploy_container is True

    def test_idea_id_zorunlu(self):
        with pytest.raises(ValidationError) as hata:
            VentureSynthesizeRequest()
        assert hata.value.errors()[0]["loc"] == ("idea_id",)


# ---------------------------------------------------------------------------
# 8. VentureResponse
# ---------------------------------------------------------------------------
class TestVentureResponse:
    TUM = {
        "venture_id": "ven-1", "idea_id": "idea-1", "code_slug": "radtrack-ai",
        "display_name": "RadTrack AI", "api_prefix_path": "/api/v1/plugins/radtrack-ai",
        "status": "PRODUCTION_LIVE", "current_monthly_mrr_usd": 8358.0,
        "active_b2b_subscribers": 47, "created_at": "2026-01-01T00:00:00+00:00",
    }

    def test_gecerli_kurulum(self):
        v = VentureResponse(**self.TUM)
        assert v.code_slug == "radtrack-ai"
        assert v.tagline is None

    def test_tagline_opsiyonel(self):
        v = VentureResponse(**{**self.TUM, "tagline": "Lezyon kıyaslama"})
        assert v.tagline == "Lezyon kıyaslama"

    def test_eksik_zorunlu_alan(self):
        with pytest.raises(ValidationError) as hata:
            VentureResponse(venture_id="ven-1")
        assert len(hata.value.errors()) == 8


# ---------------------------------------------------------------------------
# 9. GeneratedCodeArtifact
# ---------------------------------------------------------------------------
class TestGeneratedCodeArtifact:
    TUM = {
        "venture_slug": "radtrack-ai", "openapi_spec": {"openapi": "3.1.0"},
        "fastapi_router_code": "router = 1", "test_suite_code": "def t(): pass",
        "ast_validation_passed": True,
    }

    def test_gecerli_kurulum(self):
        a = GeneratedCodeArtifact(**self.TUM)
        assert a.openapi_spec == {"openapi": "3.1.0"}
        assert a.ast_validation_passed is True

    def test_openapi_spec_bos_dict_gecerli(self):
        assert GeneratedCodeArtifact(**{**self.TUM, "openapi_spec": {}}).openapi_spec == {}

    def test_eksik_alan_hatasi(self):
        with pytest.raises(ValidationError) as hata:
            GeneratedCodeArtifact(venture_slug="x")
        assert len(hata.value.errors()) == 4


# ---------------------------------------------------------------------------
# 10. MilestoneUnlockRequest
# ---------------------------------------------------------------------------
class TestMilestoneUnlockRequest:
    def test_gecerli_ve_varsayilan(self):
        r = MilestoneUnlockRequest(venture_id="v1", expert_id="e1", tier=2)
        assert r.tier == 2
        assert r.proof_data == {}

    @pytest.mark.parametrize("tier, gecerli", [(0, False), (1, True), (3, True), (4, False)])
    def test_tier_sinirlari_1_3(self, tier, gecerli):
        if gecerli:
            assert MilestoneUnlockRequest(
                venture_id="v", expert_id="e", tier=tier
            ).tier == tier
        else:
            with pytest.raises(ValidationError):
                MilestoneUnlockRequest(venture_id="v", expert_id="e", tier=tier)

    def test_proof_data_doldurulur(self):
        r = MilestoneUnlockRequest(venture_id="v", expert_id="e", tier=1,
                                   proof_data={"month": "2026-09"})
        assert r.proof_data == {"month": "2026-09"}


# ---------------------------------------------------------------------------
# 11. VestingStatusResponse
# ---------------------------------------------------------------------------
class TestVestingStatusResponse:
    TUM = {"venture_id": "v1", "expert_id": "e1", "unlocked_rev_share_pct": 20.0}

    def test_gecerli_ve_varsayilanlar(self):
        r = VestingStatusResponse(**self.TUM)
        assert r.lifetime_license_key is None
        assert r.active_milestones == []

    def test_milestone_listesi_doldurulur(self):
        r = VestingStatusResponse(**{**self.TUM, "active_milestones": [{"tier": 1}],
                                    "lifetime_license_key": "SYNTROPION-LIFETIME-X"})
        assert r.active_milestones == [{"tier": 1}]
        assert r.lifetime_license_key == "SYNTROPION-LIFETIME-X"


# ---------------------------------------------------------------------------
# 12. QuotaConsumeRequest
# ---------------------------------------------------------------------------
class TestQuotaConsumeRequest:
    def test_gecerli_kurulum(self):
        assert QuotaConsumeRequest(
            expert_id="e", venture_id="v", tokens_requested=10
        ).tokens_requested == 10

    @pytest.mark.parametrize("adet, gecerli", [(0, False), (1, True), (-5, False)])
    def test_tokens_sifirdan_buyuk(self, adet, gecerli):
        if gecerli:
            assert QuotaConsumeRequest(
                expert_id="e", venture_id="v", tokens_requested=adet
            ).tokens_requested == adet
        else:
            with pytest.raises(ValidationError) as hata:
                QuotaConsumeRequest(expert_id="e", venture_id="v", tokens_requested=adet)
            assert hata.value.errors()[0]["type"] in {"greater_than", "greater_than_equal"}


# ---------------------------------------------------------------------------
# 13. QuotaStatusResponse
# ---------------------------------------------------------------------------
class TestQuotaStatusResponse:
    TUM = {
        "expert_id": "e", "venture_id": "v", "billing_month": "2026-09",
        "free_token_limit": 5_000_000, "used_tokens": 1_420_500,
        "remaining_free_tokens": 3_579_500, "overflow_tokens": 0,
        "overflow_billed_usd": 0.0, "is_throttled": False,
    }

    @pytest.mark.parametrize("uyari", ["NORMAL", "WARNING_80_PCT", "DEPLETED_100_PCT"])
    def test_uc_uyari_seviyesi(self, uyari):
        assert QuotaStatusResponse(**{**self.TUM, "alert_level": uyari}).alert_level == uyari

    def test_gecersiz_uyari(self):
        with pytest.raises(ValidationError) as hata:
            QuotaStatusResponse(**{**self.TUM, "alert_level": "KRITIK"})
        assert hata.value.errors()[0]["type"] == "literal_error"

    def test_throttled_true(self):
        assert QuotaStatusResponse(
            **{**self.TUM, "is_throttled": True, "alert_level": "DEPLETED_100_PCT"}
        ).is_throttled is True


# ---------------------------------------------------------------------------
# 14. RevenueCalculateRequest
# ---------------------------------------------------------------------------
class TestRevenueCalculateRequest:
    def test_gecerli_ve_varsayilan(self):
        r = RevenueCalculateRequest(venture_id="v", billing_period="2026-09",
                                    gross_revenue_usd=1000.0)
        assert r.infra_costs_usd == 0.0

    @pytest.mark.parametrize("gross, gecerli", [(-0.01, False), (0.0, True), (1000.0, True)])
    def test_gross_negatif_hata(self, gross, gecerli):
        if gecerli:
            assert RevenueCalculateRequest(
                venture_id="v", billing_period="p", gross_revenue_usd=gross
            ).gross_revenue_usd == gross
        else:
            with pytest.raises(ValidationError):
                RevenueCalculateRequest(venture_id="v", billing_period="p",
                                        gross_revenue_usd=gross)

    def test_infra_negatif_hata(self):
        with pytest.raises(ValidationError):
            RevenueCalculateRequest(venture_id="v", billing_period="p",
                                    gross_revenue_usd=10.0, infra_costs_usd=-1.0)


# ---------------------------------------------------------------------------
# 15. RevenueDistributionResponse
# ---------------------------------------------------------------------------
class TestRevenueDistributionResponse:
    TUM = {
        "distribution_id": "dist-1", "venture_id": "v1", "billing_period": "2026-09",
        "gross_revenue_usd": 1000.0, "infra_and_llm_costs_usd": 200.0,
        "net_profit_usd": 800.0, "expert_rev_share_usd": 160.0,
        "treasury_share_usd": 480.0, "reserve_fund_usd": 160.0,
        "status": "DISTRIBUTED", "ipc_telemetry_dispatched": True,
    }

    def test_gecerli_kurulum(self):
        r = RevenueDistributionResponse(**self.TUM)
        assert r.status == "DISTRIBUTED"
        assert r.ipc_telemetry_dispatched is True

    def test_durum_metin_serbest(self):
        """status Literal DEĞİL — herhangi bir-metin geçerli ( dal-gözü)."""
        assert RevenueDistributionResponse(
            **{**self.TUM, "status": "IPC_REJECTED"}
        ).status == "IPC_REJECTED"

    def test_eksik_alan_hatasi(self):
        with pytest.raises(ValidationError) as hata:
            RevenueDistributionResponse(distribution_id="x")
        assert len(hata.value.errors()) == 10


# ---------------------------------------------------------------------------
# 16. OutboundLeadCampaignRequest / 17. LeadOutreachResponse
# ---------------------------------------------------------------------------
class TestGTMContracts:
    def test_campaign_gecerli(self):
        c = OutboundLeadCampaignRequest(
            venture_id="v1", target_industry="logistics",
            sample_prospect_company="Nakliye A.Ş.", decision_maker_title="Lojistik Müdürü",
        )
        assert c.target_industry == "logistics"

    def test_campaign_eksik_alan(self):
        with pytest.raises(ValidationError) as hata:
            OutboundLeadCampaignRequest(venture_id="v1")
        assert len(hata.value.errors()) == 3

    def test_lead_response_gecerli(self):
        r = LeadOutreachResponse(
            campaign_id="c1", prospect_company="Nakliye A.Ş.",
            cold_email_subject="Konu", cold_email_body="Gövde",
            spam_score_penalty=0.2, deliverability_score=0.95,
            projected_conversion_rate=0.12, pipeline_stage="SENT",
        )
        assert r.pipeline_stage == "SENT"

    def test_lead_response_eksik_alan(self):
        with pytest.raises(ValidationError) as hata:
            LeadOutreachResponse(campaign_id="c1")
        assert len(hata.value.errors()) == 7


# ---------------------------------------------------------------------------
# Serileştirme gidiş-dönüşü + modül-ğüzerinden-erişim
# ---------------------------------------------------------------------------
class TestSerilestirme:
    @pytest.mark.parametrize("model, veri", [
        (DomainExpertCreate, GECERLI_EXPERT),
        (SocraticStepRequest, {"idea_id": "i", "step": 2,
                               "expert_response": "yeterince uzun yanıt"}),
        (QuotaConsumeRequest, {"expert_id": "e", "venture_id": "v", "tokens_requested": 5}),
        (VentureSynthesizeRequest, {"idea_id": "i"}),
        (MilestoneUnlockRequest, {"venture_id": "v", "expert_id": "e", "tier": 1}),
    ])
    def test_dump_validate_gidis_donusu(self, model, veri):
        orijinal = model(**veri)
        donen = model.model_validate(orijinal.model_dump())
        assert donen.model_dump() == orijinal.model_dump()

    def test_json_serilestirme_gidis_donusu(self):
        p = ProposalSubmitRequest(
            expert=DomainExpertCreate(**GECERLI_EXPERT),
            title="RadTrack AI Kıyaslama", problem_statement="yirmi karakterlik problem",
            target_audience="onkoloji klinikleri",
        )
        json_str = p.model_dump_json()
        donen = ProposalSubmitRequest.model_validate_json(json_str)
        assert donen == p

    def test_on_yedi_model_modulde_mevcut(self):
        for ad in [
            "DomainExpertCreate", "ProposalSubmitRequest", "ProposalSubmitResponse",
            "SocraticStepRequest", "SocraticEvaluationResult", "StakeStatusResponse",
            "VentureSynthesizeRequest", "VentureResponse", "GeneratedCodeArtifact",
            "MilestoneUnlockRequest", "VestingStatusResponse", "QuotaConsumeRequest",
            "QuotaStatusResponse", "RevenueCalculateRequest", "RevenueDistributionResponse",
            "OutboundLeadCampaignRequest", "LeadOutreachResponse",
        ]:
            assert isinstance(getattr(schemas, ad), type)
