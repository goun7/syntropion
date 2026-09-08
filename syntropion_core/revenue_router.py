"""
SYNTROPION OS — Autonomous Revenue Distribution Engine
Automates the 20% Expert / 75% Treasury / 5% Reserve revenue split.
Applies cost deductions, records distribution ledger, and dispatches IPC telemetry.
"""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from syntropion_core.database import db, get_current_iso_time
from syntropion_core.shared_memory_ipc import shm_ipc_bridge


def quantize_currency(value: float) -> float:
    """Rounds currency to 2 decimal places using Decimal ROUND_HALF_UP."""
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(d)


class RevenueRouter:
    """Calculates and executes monthly micro-SaaS dividend distributions."""

    EXPERT_SHARE_PCT = 0.20
    TREASURY_SHARE_PCT = 0.75
    RESERVE_SHARE_PCT = 0.05

    def calculate_and_record_split(
        self,
        venture_id: str,
        billing_period: str,
        gross_revenue_usd: float,
        infra_costs_usd: float = 0.0
    ) -> Dict[str, Any]:
        """Calculates exact shares and persists distribution record."""
        venture = db.fetchone("SELECT * FROM ventures WHERE venture_id = ?", (venture_id,))
        if not venture:
            raise ValueError(f"Venture not found: {venture_id}")

        if gross_revenue_usd < 0 or infra_costs_usd < 0:
            raise ValueError("Revenues and costs cannot be negative")

        net_profit = max(0.0, gross_revenue_usd - infra_costs_usd)
        expert_share = quantize_currency(net_profit * self.EXPERT_SHARE_PCT)
        treasury_share = quantize_currency(net_profit * self.TREASURY_SHARE_PCT)
        reserve_share = quantize_currency(net_profit * self.RESERVE_SHARE_PCT)

        dist_id = f"dist-{uuid.uuid4().hex[:10]}"
        now = get_current_iso_time()
        transfer_id = f"tr_stripe_connect_{uuid.uuid4().hex[:12]}"

        db.execute(
            """
            INSERT INTO revenue_distributions (
                distribution_id, venture_id, billing_period, gross_revenue_usd,
                infra_and_llm_costs_usd, net_profit_usd, expert_rev_share_usd,
                treasury_share_usd, reserve_fund_usd, stripe_transfer_id,
                transferred_at, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSED', ?)
            """,
            (
                dist_id, venture_id, billing_period,
                quantize_currency(gross_revenue_usd),
                quantize_currency(infra_costs_usd),
                quantize_currency(net_profit),
                expert_share, treasury_share, reserve_share,
                transfer_id, now, now
            )
        )

        # Update Venture current MRR
        db.execute(
            "UPDATE ventures SET current_monthly_mrr_usd = ?, updated_at = ? WHERE venture_id = ?",
            (quantize_currency(gross_revenue_usd), now, venture_id)
        )

        # Dispatch Zero-Copy Shared Memory Telemetry to Project 15 Treasury
        ipc_success = shm_ipc_bridge.push_revenue_telemetry(
            venture_slug=venture["code_slug"],
            gross_usd=gross_revenue_usd,
            net_profit_usd=net_profit,
            treasury_usd=treasury_share
        )

        db.log_audit_event(
            event_type="REVENUE_SPLIT_PROCESSED",
            actor="SYSTEM_REVENUE_ROUTER",
            payload={
                "distribution_id": dist_id,
                "venture_slug": venture["code_slug"],
                "gross": gross_revenue_usd,
                "net": net_profit,
                "expert_share": expert_share,
                "treasury_share": treasury_share,
                "ipc_dispatched": ipc_success
            }
        )

        return {
            "distribution_id": dist_id,
            "venture_id": venture_id,
            "venture_slug": venture["code_slug"],
            "billing_period": billing_period,
            "gross_revenue_usd": quantize_currency(gross_revenue_usd),
            "infra_and_llm_costs_usd": quantize_currency(infra_costs_usd),
            "net_profit_usd": quantize_currency(net_profit),
            "expert_rev_share_usd": expert_share,
            "treasury_share_usd": treasury_share,
            "reserve_fund_usd": reserve_share,
            "stripe_transfer_id": transfer_id,
            "status": "PROCESSED",
            "ipc_telemetry_dispatched": ipc_success
        }

    def get_venture_history(self, venture_id: str) -> list:
        """Returns all past monthly distributions for a venture."""
        return db.fetchall(
            """
            SELECT * FROM revenue_distributions
            WHERE venture_id = ?
            ORDER BY billing_period DESC
            """,
            (venture_id,)
        )


revenue_router = RevenueRouter()
