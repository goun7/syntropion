"""
SYNTROPION OS — Stake-to-Propose & Escrow Gate
Controls the $10 anti-spam financial commitment, authorization holds, and automated refunds.
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from syntropion_core.database import db, get_current_iso_time


class StakeGate:
    """Manages the $10 financial stake escrow to eliminate non-serious spam ideas with Decimal precision."""

    DEFAULT_STAKE_USD = Decimal("10.00")

    def hold_stake_in_escrow(
        self,
        idea_id: str,
        expert_id: str,
        amount_usd: Any = Decimal("10.00"),
        payment_method_id: str = "pm_card_mock"
    ) -> Dict[str, Any]:
        """Places the $10 stake in an escrow hold state."""
        stake_dec = Decimal(str(amount_usd)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        charge_id = f"ch_mock_escrow_{uuid.uuid4().hex[:12]}"
        now = get_current_iso_time()

        db.execute(
            """
            UPDATE domain_ideas
            SET stake_amount_usd = ?,
                stake_payment_status = 'HELD_IN_ESCROW',
                stripe_charge_id = ?,
                updated_at = ?
            WHERE idea_id = ?
            """,
            (float(stake_dec), charge_id, now, idea_id)
        )

        db.log_audit_event(
            event_type="STAKE_ESCROW_HELD",
            actor=expert_id,
            payload={"idea_id": idea_id, "amount_usd": str(stake_dec), "charge_id": charge_id}
        )

        return {
            "idea_id": idea_id,
            "status": "HELD_IN_ESCROW",
            "amount_usd": float(stake_dec),
            "charge_id": charge_id,
            "escrow_timestamp": now
        }

    def process_automated_refund(
        self,
        idea_id: str,
        reason: str = "Socratic score below DDS threshold 0.75"
    ) -> Dict[str, Any]:
        """Automatically refunds the $10 stake to expert's card if rejected."""
        idea = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (idea_id,))
        if not idea:
            raise ValueError(f"Idea not found: {idea_id}")

        if idea["stake_payment_status"] == "REFUNDED":
            return {"idea_id": idea_id, "status": "ALREADY_REFUNDED"}

        refund_tx_id = f"re_mock_{uuid.uuid4().hex[:12]}"
        now = get_current_iso_time()

        db.execute(
            """
            UPDATE domain_ideas
            SET stake_payment_status = 'REFUNDED',
                rejection_reason = ?,
                status = 'REJECTED',
                updated_at = ?
            WHERE idea_id = ?
            """,
            (reason, now, idea_id)
        )

        db.log_audit_event(
            event_type="STAKE_REFUND_EXECUTED",
            actor="SYSTEM_ESCROW_DAEMON",
            payload={"idea_id": idea_id, "refund_tx_id": refund_tx_id, "reason": reason}
        )

        return {
            "idea_id": idea_id,
            "status": "REFUNDED",
            "refund_tx_id": refund_tx_id,
            "amount_refunded_usd": idea["stake_amount_usd"],
            "reason": reason,
            "timestamp": now
        }

    def capture_stake_to_venture(self, idea_id: str) -> Dict[str, Any]:
        """Transfers held stake into venture capital deposit upon approved synthesis."""
        now = get_current_iso_time()
        db.execute(
            """
            UPDATE domain_ideas
            SET stake_payment_status = 'CAPTURED_TO_EQUITY',
                status = 'APPROVED_FOR_SYNTHESIS',
                updated_at = ?
            WHERE idea_id = ?
            """,
            (now, idea_id)
        )

        db.log_audit_event(
            event_type="STAKE_CAPTURED_TO_EQUITY",
            actor="SYSTEM_SYNTHESIZER",
            payload={"idea_id": idea_id, "action": "converted_to_seed_deposit"}
        )

        return {"idea_id": idea_id, "status": "CAPTURED_TO_EQUITY", "timestamp": now}

    def get_status(self, idea_id: str) -> Optional[Dict[str, Any]]:
        """Returns current stake status for an idea."""
        row = db.fetchone("SELECT * FROM domain_ideas WHERE idea_id = ?", (idea_id,))
        if not row:
            return None
        return {
            "idea_id": row["idea_id"],
            "stake_amount_usd": row["stake_amount_usd"],
            "status": row["stake_payment_status"],
            "stripe_charge_id": row["stripe_charge_id"],
            "decision_reason": row["rejection_reason"]
        }


stake_gate = StakeGate()
