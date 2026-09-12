"""
Tests for Autonomous B2B Programmatic GTM Swarm and spam filter scoring.
"""

import pytest
from syntropion_core.gtm_swarm import gtm_swarm


def test_gtm_campaign_generation_and_spam_cleanliness():
    campaign = gtm_swarm.generate_campaign(
        venture_slug="radtrack-ai",
        prospect_company="Acıbadem Sağlık Grubu",
        decision_maker_title="Radyoloji Anabilim Dalı Başkanı",
        industry_domain="healthcare"
    )

    assert campaign["campaign_id"].startswith("cmp-")
    assert "Acıbadem" in campaign["cold_email_subject"]
    assert "RECIST" in campaign["cold_email_body"]
    assert campaign["spam_score_penalty"] == 0.0
    assert campaign["deliverability_score"] >= 0.95
    assert campaign["projected_conversion_rate"] > 0.05


def test_gtm_funnel_simulation():
    funnel = gtm_swarm.simulate_pipeline_conversion(leads_count=200)
    assert funnel["leads_targeted"] == 200
    assert funnel["contacted"] > 180
    assert funnel["opened"] > 80
    assert funnel["demos_booked"] > 15
    assert funnel["paid_subscribers"] >= 5
    assert funnel["funnel_conversion_pct"] > 0


def test_gtm_campaign_all_domains_and_spam_scoring():
    # Legal domain
    legal_camp = gtm_swarm.generate_campaign(
        venture_slug="lexnotice-legal",
        prospect_company="Bora Hukuk Bürosu",
        decision_maker_title="Yönetici Avukat",
        industry_domain="legal"
    )
    assert "TTK Md. 23" in legal_camp["cold_email_subject"]

    # Tax domain
    tax_camp = gtm_swarm.generate_campaign(
        venture_slug="taxcross-audit",
        prospect_company="Ernst Denetim",
        decision_maker_title="Kıdemli Vergi Müdürü",
        industry_domain="tax"
    )
    assert "KDV2" in tax_camp["cold_email_subject"]

    # Generic domain
    gen_camp = gtm_swarm.generate_campaign(
        venture_slug="custom-logistics",
        prospect_company="Ekol Logistics",
        decision_maker_title="Operasyon Direktörü",
        industry_domain="logistics"
    )
    assert "Operasyonel Verimlilik" in gen_camp["cold_email_subject"]

    # Simulate spam penalty trigger
    from syntropion_core.gtm_swarm import SPAM_TRIGGER_WORDS
    spammy_title = "Kazan 100% garanti ücretsiz zengin ol"
    spam_camp = gtm_swarm.generate_campaign(
        venture_slug="spammer-ai",
        prospect_company="Any Corp",
        decision_maker_title=spammy_title,
        industry_domain="other"
    )
    assert spam_camp["spam_score_penalty"] >= 0.10
