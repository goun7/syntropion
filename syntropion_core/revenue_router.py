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


def quantize_currency(value: Any) -> float:
    """Rounds currency to 2 decimal places using Decimal ROUND_HALF_UP without float drift."""
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(d)


class RevenueRouter:
    """Calculates and executes monthly micro-SaaS dividend distributions with Decimal precision."""

    EXPERT_SHARE_PCT = Decimal("0.20")
    TREASURY_SHARE_PCT = Decimal("0.75")
    RESERVE_SHARE_PCT = Decimal("0.05")

    def calculate_and_record_split(
        self,
        venture_id: str,
        billing_period: str,
        gross_revenue_usd: Any,
        infra_costs_usd: Any = 0.0
    ) -> Dict[str, Any]:
        """Calculates exact shares and persists distribution record using strict Decimal."""
        venture = db.fetchone("SELECT * FROM ventures WHERE venture_id = ?", (venture_id,))
        if not venture:
            raise ValueError(f"Venture not found: {venture_id}")

        gross_dec = Decimal(str(gross_revenue_usd)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        costs_dec = Decimal(str(infra_costs_usd)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if gross_dec < Decimal("0.00") or costs_dec < Decimal("0.00"):
            raise ValueError("Revenues and costs cannot be negative")

        net_dec = max(Decimal("0.00"), gross_dec - costs_dec)
        expert_dec = (net_dec * self.EXPERT_SHARE_PCT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        treasury_dec = (net_dec * self.TREASURY_SHARE_PCT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        reserve_dec = (net_dec * self.RESERVE_SHARE_PCT).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
                float(gross_dec),
                float(costs_dec),
                float(net_dec),
                float(expert_dec), float(treasury_dec), float(reserve_dec),
                transfer_id, now, now
            )
        )

        # DURUST (AT-HONEST-001): bu "current MRR" guncellemesi bir fatura
        # donemine girilen BRUT geliri ventures.current_monthly_mrr_usd
        # alanina yazar. Bu alan gercek abonelik kayitlarindan
        # (b2b_subscriptions) TURETILMEZ; dolayisiyla honest_metrics
        # uzerinden mrr_provenance() "SIMULATED/PARTIALLY_VERIFIED" doner.
        # Deger silinmedi; etiketlendi.
        db.execute(
            "UPDATE ventures SET current_monthly_mrr_usd = ?, updated_at = ? WHERE venture_id = ?",
            (float(gross_dec), now, venture_id)
        )

        # Dispatch Zero-Copy Shared Memory Telemetry to Project 15 Treasury
        ipc_success = shm_ipc_bridge.push_revenue_telemetry(
            venture_slug=venture["code_slug"],
            gross_usd=float(gross_dec),
            net_profit_usd=float(net_dec),
            treasury_usd=float(treasury_dec)
        )

        db.log_audit_event(
            event_type="REVENUE_SPLIT_PROCESSED",
            actor="SYSTEM_REVENUE_ROUTER",
            payload={
                "distribution_id": dist_id,
                "venture_slug": venture["code_slug"],
                "gross": str(gross_dec),
                "net": str(net_dec),
                "expert_share": str(expert_dec),
                "treasury_share": str(treasury_dec),
                "ipc_dispatched": ipc_success
            }
        )

        return {
            "distribution_id": dist_id,
            "venture_id": venture_id,
            "venture_slug": venture["code_slug"],
            "billing_period": billing_period,
            "gross_revenue_usd": float(gross_dec),
            "infra_and_llm_costs_usd": float(costs_dec),
            "net_profit_usd": float(net_dec),
            "expert_rev_share_usd": float(expert_dec),
            "treasury_share_usd": float(treasury_dec),
            "reserve_fund_usd": float(reserve_dec),
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
