"""
SYNTROPION OS — Socratic Interrogation & Domain Depth Scoring (DDS)
5-Step deep questioner evaluating operational depth, edge cases, statutory rules, and WTP.
Threshold: DDS >= 0.75 required to pass into autonomous code synthesis.
"""

import uuid
import re
import json
from typing import Dict, Any, List, Optional
from syntropion_core.database import db, get_current_iso_time
from syntropion_core.stake_gate import stake_gate

SOCRATIC_QUESTIONS = {
    1: {
        "title": "Operasyonel Darboğaz ve Başarısızlık Maliyeti",
        "text": "Bu operasyonel darboğazı ve sahadaki mevcut manuel geçici çözümünüzü (workaround) ayrıntılı açıklayınız. Çözülmediğinde oluşan haftalık/aylık zaman veya nakit kaybı nedir?"
    },
    2: {
        "title": "İstisnalar, Uç Vakalar ve Kirli Veri Kuralları",
        "text": "Saha operasyonunda en sık karşılaşılan 3 istisna (edge case) ve eksik/hatalı veri durumunda sistemin uyması gereken katı iş kuralı nedir?"
    },
    3: {
        "title": "Yasal Mevzuat, Yaptırımlar ve Uyumluluk Zırhı",
        "text": "Bu süreçte geçerli kanunlar (örn. 5846 FSEK, 6102 TTK, 6698 KVKK, Gümrük Kanunu, Tıbbi Cihaz / EU AI Act 2026) ve uyumsuzluk halinde doğacak cezai/tazminat sorumluluğu nedir?"
    },
    4: {
        "title": "Girdi ve Çıktı Veri Sözleşmesi (Data Contract)",
        "text": "Sisteme aktarılacak ham girdi verilerinin formatları (PDF, XML, DICOM, Excel, API json) ve üretilecek nihai çıktının (rapor, ihtarname, düzeltme fişi) kesin yapısı nedir?"
    },
    5: {
        "title": "B2B Fiyatlama ve Ödeme İştahı (Willingness-to-Pay & ROI)",
        "text": "Bu modül için hedef kurumsal müşterinin aylık ödemeye hazır olduğu lisans tutarı (MRR) nedir ve satın alma onayını sağlayan somut yatırım getirisi (ROI) formülü nedir?"
    }
}

# Domain keywords indicative of authentic high-depth practitioner insight
HIGH_DEPTH_LEXICON = {
    "healthcare": ["recist", "dicom", "lezyon", "metastaz", "bt", "mr", "epikriz", "radyoloji", "pacs", "onkoloji"],
    "legal": ["ttk", "tbk", "ihtarname", "zamanaşımı", "ayıp", "uyap", "noter", "tenzili", "feragat", "haksız rekabet"],
    "accounting_tax": ["kdv2", "ba-bs", "gib", "tevkifat", "matrah", "izaha davet", "muhtasar", "vergi ziyaı", "e-fatura"],
    "customs_trade": ["gtip", "wco", "btk", "menşe", "antrepo", "konşimento", "beyanname", "4458", "dolaşım belgesi"],
    "maritime_logistics": ["demurraj", "ardiye", "free-time", "konşimento", "armatör", "teu", "liman", "navlun", "ordino"]
}

REGULATORY_MARKERS = [
    "fsek", "ttk", "kvkk", "tbk", "eu ai act", "ceza", "tazminat", "yönetmelik", "mevzuat", "kanun", "ihlal", "sorumluluk"
]


class SocraticEngine:
    """Evaluates domain depth with algorithmic rigor to filter out shallow AI chatter."""

    DDS_THRESHOLD = 0.75

    def get_question(self, step: int) -> Dict[str, str]:
        """Returns the question text for a specific step."""
        if step not in SOCRATIC_QUESTIONS:
            raise ValueError(f"Invalid Socratic step: {step}. Must be 1 to 5.")
        return SOCRATIC_QUESTIONS[step]

    def evaluate_response_depth(self, step: int, response_text: str, domain_hint: str = "") -> Dict[str, Any]:
        """
        Calculates depth score for a single step response.
        Factors: length, quantified data presence, domain jargon, regulatory consciousness.
        """
        cleaned = response_text.strip()
        words = re.findall(r"\b\w+\b", cleaned.lower())
        word_count = len(words)

        if word_count < 8:
            return {
                "score": 0.15,
                "regulatory_flags": [],
                "edge_cases": [],
                "feedback": "Yanıt çok yüzeysel ve kısa. Lütfen saha gerçeklerini detaylandırınız."
            }

        # 1. Base substance score (0.45 to 0.55 for complete professional answers)
        length_score = min(0.55, 0.35 + (word_count / 50.0 * 0.20))

        # 2. Quantified metrics / numbers / currency / time / ROI (up to 0.20)
        has_metrics = len(re.findall(r"\b(?:\d+[\.,]?\d*|\$|€|tl|saat|dakika|gün|hafta|%|mrr|roi)\b", cleaned.lower()))
        metric_score = min(0.20, has_metrics * 0.05)

        # 3. Domain Terminology Depth (up to 0.25)
        matched_domain_terms = []
        all_terms = [t for sublist in HIGH_DEPTH_LEXICON.values() for t in sublist]
        for term in set(all_terms):
            if term in cleaned.lower():
                matched_domain_terms.append(term)
        domain_score = min(0.25, len(matched_domain_terms) * 0.08)

        # 4. Regulatory, Compliance & Liability (up to 0.20)
        found_reg_flags = [r for r in REGULATORY_MARKERS if r in cleaned.lower()]
        reg_score = min(0.20, len(found_reg_flags) * 0.08)

        # 5. Technical Data Formats & Architecture (DICOM, FHIR, JSON, XML, PDF, API, HL7) (up to 0.20)
        tech_formats = ["dicom", "fhir", "hl7", "json", "xml", "pdf", "api", "csv", "excel", "sql"]
        found_tech = [fmt for fmt in tech_formats if fmt in cleaned.lower()]
        tech_score = min(0.20, len(found_tech) * 0.08)

        # 6. Edge cases heuristic
        edge_cases = []
        for line in cleaned.split("\n"):
            if any(k in line.lower() for k in ["eğer", "fakat", "istisna", "ancak", "durumunda", "çökerse", "bozuksa", "eksikse"]):
                edge_cases.append(line.strip()[:100])
        edge_score = min(0.15, len(edge_cases) * 0.08)

        total_score = round(min(1.0, length_score + metric_score + domain_score + reg_score + tech_score + edge_score), 3)

        return {
            "score": total_score,
            "regulatory_flags": found_reg_flags,
            "edge_cases": edge_cases[:3],
            "feedback": f"Derinlik Skoru: {total_score:.2f} ({word_count} kelime, {len(matched_domain_terms)} terim, {len(found_reg_flags)} mevzuat atfı)."
        }

    def process_step(self, idea_id: str, step: int, expert_response: str) -> Dict[str, Any]:
        """Processes an expert response, records log, and calculates running DDS score."""
        idea = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (idea_id,))
        if not idea:
            raise ValueError(f"Idea not found: {idea_id}")

        expert = db.fetchone("SELECT * FROM domain_experts WHERE expert_id = ?", (idea["expert_id"],))
        domain_hint = expert["industry_domain"] if expert else ""

        q_info = self.get_question(step)
        eval_res = self.evaluate_response_depth(step, expert_response, domain_hint)

        now = get_current_iso_time()
        interview_id = f"int-{uuid.uuid4().hex[:10]}"

        db.execute(
            """
            INSERT INTO socratic_interviews (
                interview_id, idea_id, question_step, question_text,
                expert_response, ai_evaluation_score, regulatory_flags, edge_cases_identified, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interview_id, idea_id, step, q_info["text"],
                expert_response, eval_res["score"],
                json.dumps(eval_res["regulatory_flags"]),
                json.dumps(eval_res["edge_cases"]),
                now
            )
        )

        # Calculate running average DDS across completed steps
        past_steps = db.fetchall(
            "SELECT ai_evaluation_score FROM socratic_interviews WHERE idea_id = ?", (idea_id,)
        )
        scores = [row["ai_evaluation_score"] for row in past_steps]
        running_dds = round(sum(scores) / len(scores), 3)

        is_completed = (step == 5)
        next_q = None
        status = "IN_PROGRESS"

        if not is_completed:
            next_q = self.get_question(step + 1)["text"]
            db.execute(
                "UPDATE domain_ideas SET status = 'IN_INTERVIEW', domain_depth_score = ?, updated_at = ? WHERE idea_id = ?",
                (running_dds, now, idea_id)
            )
        else:
            # Step 5 completed: Check final threshold
            if running_dds >= self.DDS_THRESHOLD:
                status = "PASSED_THRESHOLD"
                stake_gate.capture_stake_to_venture(idea_id)
                db.execute(
                    "UPDATE domain_ideas SET status = 'APPROVED_FOR_SYNTHESIS', domain_depth_score = ?, updated_at = ? WHERE idea_id = ?",
                    (running_dds, now, idea_id)
                )
            else:
                status = "REJECTED_LOW_SCORE"
                rejection_msg = f"DDS Skoru ({running_dds:.2f}) kabul eşiği olan {self.DDS_THRESHOLD:.2f} altında kaldı."
                stake_gate.process_automated_refund(idea_id, reason=rejection_msg)

        return {
            "step": step,
            "question_text": q_info["text"],
            "score": eval_res["score"],
            "domain_depth_score_running": running_dds,
            "regulatory_flags": eval_res["regulatory_flags"],
            "edge_cases_identified": eval_res["edge_cases"],
            "is_completed": is_completed,
            "status": status,
            "feedback": eval_res["feedback"],
            "next_question": next_q
        }


socratic_engine = SocraticEngine()
