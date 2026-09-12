"""
SYNTROPION OS — Fair-Use Token Quota Governor
Manages the 5,000,000 free tokens/month allowance for lifetime enterprise license holders.
Tracks usage, alerts at 80% & 100%, and meters at-cost overflow at $0.0005 per 1k tokens.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Tuple
from datetime import datetime, timezone
from syntropion_core.database import db, get_current_iso_time


class QuotaGovernor:
    """Enforces fair-use token allocation to prevent abusive runaway LLM costs with Decimal precision."""

    FREE_MONTHLY_LIMIT = 5_000_000
    OVERFLOW_PRICE_PER_1K_TOKENS = Decimal("0.0005")  # $0.50 per 1M tokens at-cost pass-through

    def _get_or_create_quota_record(self, expert_id: str, venture_id: str) -> Dict[str, Any]:
        """Fetches or initializes the quota record for the current month."""
        now = get_current_iso_time()
        month = now[:7]  # YYYY-MM
        import hashlib
        key_hash = hashlib.md5(f"{expert_id}:{venture_id}:{month}".encode("utf-8")).hexdigest()[:16]
        quota_id = f"quota-{key_hash}"

        row = db.fetchone(
            "SELECT * FROM token_quotas WHERE expert_id = ? AND venture_id = ? AND billing_cycle_month = ?",
            (expert_id, venture_id, month)
        )

        if not row:
            db.execute(
                """
                INSERT INTO token_quotas (
                    quota_id, expert_id, venture_id, billing_cycle_month,
                    free_token_limit, used_tokens, overflow_tokens, overflow_billed_usd,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 0.0000, ?, ?)
                """,
                (quota_id, expert_id, venture_id, month, self.FREE_MONTHLY_LIMIT, now, now)
            )
            row = db.fetchone("SELECT * FROM token_quotas WHERE quota_id = ?", (quota_id,))

        return row

    def consume_tokens(self, expert_id: str, venture_id: str, token_count: int) -> Dict[str, Any]:
        """Consumes tokens from the free monthly pool or tallies overflow."""
        if token_count <= 0:
            raise ValueError("Token count to consume must be positive")

        record = self._get_or_create_quota_record(expert_id, venture_id)
        current_used = record["used_tokens"]
        limit = record["free_token_limit"]
        new_total = current_used + token_count

        now = get_current_iso_time()
        overflow_add = 0
        overflow_cost_dec = Decimal("0.0000")

        if new_total <= limit:
            # Entirely within free limit
            db.execute(
                "UPDATE token_quotas SET used_tokens = ?, updated_at = ? WHERE quota_id = ?",
                (new_total, now, record["quota_id"])
            )
        else:
            # Spilled into overflow
            overflow_add = new_total - max(limit, current_used)
            overflow_cost_dec = ((Decimal(str(overflow_add)) / Decimal("1000")) * self.OVERFLOW_PRICE_PER_1K_TOKENS).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            db.execute(
                """
                UPDATE token_quotas
                SET used_tokens = ?,
                    overflow_tokens = overflow_tokens + ?,
                    overflow_billed_usd = overflow_billed_usd + ?,
                    updated_at = ?
                WHERE quota_id = ?
                """,
                (new_total, overflow_add, float(overflow_cost_dec), now, record["quota_id"])
            )

        updated = db.fetchone("SELECT * FROM token_quotas WHERE quota_id = ?", (record["quota_id"],))
        return self._format_quota_status(updated)

    def get_status(self, expert_id: str, venture_id: str) -> Dict[str, Any]:
        """Returns the current quota status, usage ratio, and alert level."""
        record = self._get_or_create_quota_record(expert_id, venture_id)
        return self._format_quota_status(record)

    def _format_quota_status(self, row: Dict[str, Any]) -> Dict[str, Any]:
        limit = row["free_token_limit"]
        used = row["used_tokens"]
        remaining = max(0, limit - used)
        ratio = used / limit if limit > 0 else 1.0

        if ratio >= 1.0:
            alert = "DEPLETED_100_PCT"
        elif ratio >= 0.8:
            alert = "WARNING_80_PCT"
        else:
            alert = "NORMAL"

        return {
            "expert_id": row["expert_id"],
            "venture_id": row["venture_id"],
            "billing_month": row["billing_cycle_month"],
            "free_token_limit": limit,
            "used_tokens": used,
            "remaining_free_tokens": remaining,
            "overflow_tokens": row["overflow_tokens"],
            "overflow_billed_usd": round(row["overflow_billed_usd"], 4),
            "usage_ratio_pct": round(min(100.0, ratio * 100.0), 2),
            "is_throttled": False,  # Never throttled, continuous at-cost overflow
            "alert_level": alert
        }


quota_governor = QuotaGovernor()
