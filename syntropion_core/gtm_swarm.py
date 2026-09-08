"""
SYNTROPION OS — Autonomous B2B Programmatic GTM & Outbound Lead Swarm
Generates tailored prospect campaigns, scores cold outreach against spam filters,
and tracks conversion pipeline metrics across vertical SaaS markets.
"""

import uuid
import re
from typing import Dict, Any, List, Optional

SPAM_TRIGGER_WORDS = [
    "ücretsiz hemen tıkla", "para kazan", "100% garanti", "milyon kazan",
    "acilen", "hemen al", "zaman daralıyor", "fırsatı kaçırma", "kredi kartı"
]


class GTMSwarmEngine:
    """Orchestrates outbound programmatic sales outreach for synthesized ventures."""

    def generate_campaign(
        self,
        venture_slug: str,
        prospect_company: str,
        decision_maker_title: str,
        industry_domain: str
    ) -> Dict[str, Any]:
        """Generates a high-converting, personalized cold email sequence."""
        campaign_id = f"cmp-{uuid.uuid4().hex[:10]}"

        # Domain specific tailoring
        if "radtrack" in venture_slug or "health" in industry_domain:
            subject = f"{prospect_company} Onkoloji Birimi İçin RECIST 1.1 Raporlama Süresi Optimizasyonu"
            body = (
                f"Sayın {decision_maker_title},\n\n"
                f"{prospect_company} bünyesindeki radyoloji iş yükünde, kontrol MR/BT incelemelerinin önceki "
                f"tetkiklerle lezyon bazında kıyaslanması radyolog başına günde 2.5 saati bulabilmektedir. "
                f"RadTrack AI motorumuz, DICOM serilerini eşleyerek RECIST 1.1 kriterlerine göre milimetrik "
                f"değişim tablosunu 15 saniyede epikriz taslağına dönüştürmektedir.\n\n"
                f"Ekibiniz için 14 günlük ücretsiz kurumsal pilot erişimini aktif edebiliriz. "
                f"Uygun bir gününüzde 10 dakikalık teknik demoyu değerlendirmek ister misiniz?\n\n"
                f"Saygılarımla,\nSyntropion B2B Dağıtım Ajanı"
            )
        elif "lexnotice" in venture_slug or "legal" in industry_domain:
            subject = f"{prospect_company} Ticari Alacaklarda TTK Md. 23 ve Ayıp İhbar Sürelerinin Otomasyonu"
            body = (
                f"Sayın {decision_maker_title},\n\n"
                f"Ticari alım-satımlarda 6102 Sayılı TTK Md. 23 gereği açık ayıplarda 2 gün, gizli ayıplarda 8 günlük "
                f"ihbar sürelerinin operasyonel yoğunlukta kaçırılması şirketleri önemli tazminat riskleriyle baş başa bırakmaktadır. "
                f"LexNotice AI, sözleşme ve sevk irsaliyelerini tarayarak hak düşürücü süreleri otomatik hesaplar.\n\n"
                f"Büronuz bünyesinde pilot çalışma başlatmak için Salı veya Perşembe günü 10 dakikalık bir görüşme planlayabiliriz.\n\n"
                f"Saygılarımla,\nSyntropion Hukuk Çözümleri"
            )
        elif "taxcross" in venture_slug or "tax" in industry_domain:
            subject = f"{prospect_company} KDV2 ve Ba-Bs e-Fatura Matrah Uyumsuzluğu Erken Uyarı Sistemi"
            body = (
                f"Sayın {decision_maker_title},\n\n"
                f"GİB portalı ile muhasebe fişleri arasındaki tevkifat ve KDV2 matrah uyumsuzlukları vergi incelemelerinde "
                f"ciddi izaha davet ve ceza riskleri oluşturabilmektedir. TaxCrossAudit, beyanname öncesinde 14 kritik "
                f"çapraz denetim kuralını otomatik çalıştırarak hata payını sıfırlar.\n\n"
                f"Mali müşavirlik portföyünüzde 1 aylık ücretsiz deneme için sistem kurulumunu 5 dakikada tamamlayabiliriz.\n\n"
                f"Saygılarımla,\nSyntropion Finansal Denetim"
            )
        else:
            subject = f"{prospect_company} Operasyonel Verimlilik ve Otomasyon Entegrasyonu"
            body = (
                f"Sayın {decision_maker_title},\n\n"
                f"{prospect_company} operasyonlarında sektörel darboğazları çözen mikro-SaaS altyapımız ile "
                f"haftalık 15 saatlik manuel veri işleme süresini otonom hale getiriyoruz.\n\n"
                f"10 dakikalık kurumsal demomuz için takvim bağlantımızı iletiyorum.\n\n"
                f"Saygılarımla,\nSyntropion Kurumsal Satış"
            )

        # Spam score inspection
        penalty = 0.0
        for trigger in SPAM_TRIGGER_WORDS:
            if trigger in body.lower():
                penalty += 0.10

        deliverability = round(max(0.70, 0.98 - penalty), 2)
        projected_conversion = round(0.085 * (deliverability / 0.98), 3)

        return {
            "campaign_id": campaign_id,
            "venture_slug": venture_slug,
            "prospect_company": prospect_company,
            "decision_maker_title": decision_maker_title,
            "cold_email_subject": subject,
            "cold_email_body": body,
            "spam_score_penalty": penalty,
            "deliverability_score": deliverability,
            "projected_conversion_rate": projected_conversion,
            "pipeline_stage": "OUTREACH_READY"
        }

    def simulate_pipeline_conversion(self, leads_count: int = 100) -> Dict[str, Any]:
        """Simulates conversion funnel from cold prospect to paying B2B subscriber."""
        contacted = int(leads_count * 0.95)
        opened = int(contacted * 0.46)
        demos_booked = int(opened * 0.22)
        trials = int(demos_booked * 0.65)
        paid_subscribers = max(1, int(trials * 0.55))

        return {
            "leads_targeted": leads_count,
            "contacted": contacted,
            "opened": opened,
            "demos_booked": demos_booked,
            "trials_active": trials,
            "paid_subscribers": paid_subscribers,
            "funnel_conversion_pct": round((paid_subscribers / leads_count) * 100.0, 2)
        }


gtm_swarm = GTMSwarmEngine()
