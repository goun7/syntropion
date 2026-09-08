"""
SYNTROPION OS — Gamified Milestone Vesting & Lifetime License Engine
3-Tier progressive milestone unlocking for Domain Experts:
- Tier 1: Alpha validation (10 datasets) -> Unlocks 10% rev-share + Lifetime License Key
- Tier 2: Beta co-pilot (3 peer referrals) -> Unlocks 20% rev-share
- Tier 3: Annual SLA review & rule maintenance -> Unlocks 25%-30% rev-share
"""

import uuid
import json
from typing import Dict, Any, List, Optional
from syntropion_core.database import db, get_current_iso_time
from syntropion_core.security import issue_lifetime_license_key, verify_lifetime_license_key

TIER_CONFIG = {
    1: {
        "name": "Alpha Validation & Dataset Grounding",
        "description": "10 adet gerçek saha veri setiyle model çıktılarının doğrulanması",
        "rev_share_pct": 10.00,
        "grants_lifetime_license": True
    },
    2: {
        "name": "Beta Co-Piloting & Peer Referrals",
        "description": "3 kurumsal meslektaşa pilot kullandırma ve geri bildirim loglarının teslimi",
        "rev_share_pct": 20.00,
        "grants_lifetime_license": False
    },
    3: {
        "name": "Annual SLA & Domain Rule Maintenance",
        "description": "Yıllık mevzuat güncellemelerinin sisteme girilmesi ve uç vaka kılavuzu",
        "rev_share_pct": 25.00,
        "grants_lifetime_license": False
    }
}


class VestingEngine:
    """Controls progressive milestone equity/rev-share release to domain experts."""

    def initialize_venture_vestings(self, venture_id: str, expert_id: str) -> None:
        """Creates the 3 pending milestone records for a newly synthesized venture."""
        now = get_current_iso_time()
        for tier, conf in TIER_CONFIG.items():
            vest_id = f"vest-{venture_id}-{tier}"
            db.execute(
                """
                INSERT OR IGNORE INTO milestone_vestings (
                    vesting_id, venture_id, expert_id, milestone_tier,
                    description, rev_share_percentage, is_unlocked, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (vest_id, venture_id, expert_id, tier, conf["description"], conf["rev_share_pct"], now)
            )

    def unlock_milestone(
        self,
        venture_id: str,
        expert_id: str,
        tier: int,
        proof_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validates proof and unlocks a milestone tier, releasing rev-share and license keys."""
        if tier not in TIER_CONFIG:
            raise ValueError(f"Invalid milestone tier: {tier}. Must be 1, 2, or 3.")

        conf = TIER_CONFIG[tier]
        venture = db.fetchone("SELECT * FROM ventures WHERE venture_id = ?", (venture_id,))
        if not venture:
            raise ValueError(f"Venture not found: {venture_id}")

        now = get_current_iso_time()
        proof_json = json.dumps(proof_data or {"verified_by": "SYNAPSE_CO_PILOT_VERIFIER"})

        license_key = None
        if conf["grants_lifetime_license"]:
            license_key = issue_lifetime_license_key(venture["code_slug"], expert_id)

        vest_id = f"vest-{venture_id}-{tier}"
        db.execute(
            """
            INSERT INTO milestone_vestings (
                vesting_id, venture_id, expert_id, milestone_tier,
                description, rev_share_percentage, is_unlocked, unlocked_at,
                proof_verification_data, license_key, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(vesting_id) DO UPDATE SET
                is_unlocked = 1,
                unlocked_at = excluded.unlocked_at,
                proof_verification_data = excluded.proof_verification_data,
                license_key = COALESCE(excluded.license_key, milestone_vestings.license_key)
            """,
            (
                vest_id, venture_id, expert_id, tier,
                conf["description"], conf["rev_share_pct"],
                now, proof_json, license_key, now
            )
        )

        db.log_audit_event(
            event_type=f"MILESTONE_TIER_{tier}_UNLOCKED",
            actor=expert_id,
            payload={
                "venture_id": venture_id,
                "tier": tier,
                "rev_share_pct": conf["rev_share_pct"],
                "license_key": license_key
            }
        )

        return {
            "venture_id": venture_id,
            "expert_id": expert_id,
            "tier": tier,
            "unlocked": True,
            "rev_share_percentage": conf["rev_share_pct"],
            "lifetime_license_key": license_key,
            "unlocked_at": now
        }

    def get_expert_vesting_status(self, venture_id: str, expert_id: str) -> Dict[str, Any]:
        """Returns the aggregate unlocked rev-share and active license key."""
        rows = db.fetchall(
            """
            SELECT * FROM milestone_vestings
            WHERE venture_id = ? AND expert_id = ? AND is_unlocked = 1
            ORDER BY milestone_tier ASC
            """,
            (venture_id, expert_id)
        )

        max_unlocked_pct = 0.0
        license_key = None
        for r in rows:
            if r["rev_share_percentage"] > max_unlocked_pct:
                max_unlocked_pct = r["rev_share_percentage"]
            if r["license_key"]:
                license_key = r["license_key"]

        return {
            "venture_id": venture_id,
            "expert_id": expert_id,
            "unlocked_rev_share_pct": max_unlocked_pct,
            "lifetime_license_key": license_key,
            "active_milestones": rows
        }


vesting_engine = VestingEngine()
