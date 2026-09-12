"""
SYNTROPION OS — Database Persistence Layer
Thread-safe SQLite WAL persistence engine with schema management and seed data.
"""

import os
import sqlite3
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional, List, Dict, Any

DEFAULT_DB_PATH = os.environ.get("SYNTROPION_DB_PATH", "syntropion.db")
SCHEMA_SQL_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_current_iso_time() -> str:
    """Returns current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class DatabaseManager:
    """Thread-safe connection and query manager for Syntropion OS."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a connection with WAL, 60s busy timeout, and Row factory."""
        conn = sqlite3.connect(self.db_path, timeout=60.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 60000;")  # 60s busy timeout (Mergen #3990)
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for atomic transactions with exponential backoff retry on lock."""
        import time
        max_retries = 3
        backoff = 0.05

        for attempt in range(1, max_retries + 1):
            conn = self.get_connection()
            try:
                yield conn
                conn.commit()
                conn.close()
                return
            except sqlite3.OperationalError as e:
                conn.rollback()
                conn.close()
                if "locked" in str(e).lower() and attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise
            except Exception:
                conn.rollback()
                conn.close()
                raise

    def checkpoint_wal(self) -> None:
        """Truncates WAL journal file to prevent unbounded growth."""
        with self.transaction() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

    def _ensure_schema(self) -> None:
        """Executes schema.sql if database is not initialized."""
        if os.path.exists(SCHEMA_SQL_PATH):
            with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
                schema_ddl = f.read()
            with self.transaction() as conn:
                conn.executescript(schema_ddl)

    def execute(self, query: str, params: tuple = ()) -> int:
        """Executes an INSERT/UPDATE/DELETE query and returns rowcount."""
        with self.transaction() as conn:
            cur = conn.execute(query, params)
            return cur.rowcount

    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Executes a SELECT query and returns a single row as dict."""
        with self.transaction() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Executes a SELECT query and returns all matching rows as dicts."""
        with self.transaction() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def log_audit_event(self, event_type: str, actor: str, payload: dict) -> str:
        """Appends an event to the immutable Merkle hash chain audit ledger."""
        with self.transaction() as conn:
            last_row = conn.execute(
                "SELECT current_hash FROM audit_ledger ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = last_row["current_hash"] if last_row else "GENESIS_HASH_0000000000000000000000000000000000000000000000000000000000000000"
            
            ts = get_current_iso_time()
            payload_str = json.dumps(payload, sort_keys=True)
            to_hash = f"{prev_hash}:{event_type}:{actor}:{ts}:{payload_str}"
            curr_hash = hashlib.sha256(to_hash.encode("utf-8")).hexdigest()

            conn.execute(
                """
                INSERT INTO audit_ledger (event_type, actor, payload_json, timestamp, previous_hash, current_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_type, actor, payload_str, ts, prev_hash, curr_hash)
            )
            return curr_hash

    def seed_deep_vertical_pilots(self) -> None:
        """Seeds the 5 deep vertical pilots defined in Chapter 23 of Fikir.md."""
        pilots = [
            {
                "expert_id": "exp-pilot-001-radiologist",
                "email": "dr.ahmet.yilmaz@hastane.com.tr",
                "full_name": "Dr. M. K. (Radyoloji Uzmanı)",
                "phone": "+905321112233",
                "domain": "healthcare",
                "exp": 16,
                "idea_id": "idea-pilot-001-radtrack",
                "title": "RadTrack AI (Radyoloji Lezyon Kıyaslama & RECIST 1.1 Takip Ajanı)",
                "problem": "Onkoloji hastalarının önceki BT/MR raporları ile yenilerini kıyaslamak radyoloğun günde 2.5 saatini alıyor.",
                "audience": "Özel ve kamu hastaneleri onkoloji/radyoloji klinikleri",
                "workaround": "İki PDF raporu yan yana açıp elle milimetrik kıyaslama yapmak",
                "venture_id": "ven-pilot-001-radtrack",
                "code_slug": "radtrack-ai",
                "display_name": "RadTrack AI",
                "tagline": "Radyoloji Lezyon Kıyaslama & RECIST 1.1 Takip Ajanı",
                "api_path": "/api/v1/plugins/radtrack",
                "mrr": 8358.00,
                "subscribers": 42
            },
            {
                "expert_id": "exp-pilot-002-lawyer",
                "email": "av.selin.baro@hukuk.av.tr",
                "full_name": "Av. S. B. (Ticaret Hukuku)",
                "phone": "+905332223344",
                "domain": "legal",
                "exp": 19,
                "idea_id": "idea-pilot-002-lexnotice",
                "title": "LexNotice AI (Ticari İhtarname, Sözleşme Riski & Dava Zaman Aşımı Ajanı)",
                "problem": "6102 Sayılı TTK ve TBK uyarınca 2 ve 8 günlük ayıplı mal bildirim ve ihtarname süreleri kaçırıldığında hak kaybı doğuyor.",
                "audience": "Kurumsal hukuk büroları ve şirket içi hukuk müşavirlikleri",
                "workaround": "Excel takvimleri ve elle dilekçe yazımı",
                "venture_id": "ven-pilot-002-lexnotice",
                "code_slug": "lexnotice-ai",
                "display_name": "LexNotice AI",
                "tagline": "Ticari İhtarname ve TTK Zaman Aşımı Erken Uyarı Ajanı",
                "api_path": "/api/v1/plugins/lexnotice",
                "mrr": 8940.00,
                "subscribers": 60
            },
            {
                "expert_id": "exp-pilot-003-accountant",
                "email": "ymm.cemal@vergidenetim.com.tr",
                "full_name": "YMM / SMMM C. D.",
                "phone": "+905353334455",
                "domain": "accounting_tax",
                "exp": 22,
                "idea_id": "idea-pilot-003-taxcross",
                "title": "TaxCrossAudit (KDV Beyanname & Ba-Bs Çapraz Denetim Motoru)",
                "problem": "KDV2 ve 1 No'lu KDV beyannamelerindeki fatura matrah uyumsuzlukları vergi dairesinden ceza ve izaha davet aldırıyor.",
                "audience": "Mali müşavirler, YMM büroları ve kurumsal finans ekipleri",
                "workaround": "GİB portalından e-fatura XML indirip Excel VLOOKUP ile tek tek eşlemek",
                "venture_id": "ven-pilot-003-taxcross",
                "code_slug": "taxcross-audit",
                "display_name": "TaxCrossAudit",
                "tagline": "KDV2 ve Ba-Bs e-Fatura Çapraz Denetim ve İzaha Davet Kalkanı",
                "api_path": "/api/v1/plugins/taxcross",
                "mrr": 9790.00,
                "subscribers": 110
            },
            {
                "expert_id": "exp-pilot-004-customs",
                "email": "gumruk.hasan@gumrukmusavirlik.com",
                "full_name": "H. E. (Gümrük Müşaviri)",
                "phone": "+905364445566",
                "domain": "customs_trade",
                "exp": 18,
                "idea_id": "idea-pilot-004-tarifa",
                "title": "TarifaCustoms AI (12 Haneli GTİP & Menşe Güvencesi Ajanı)",
                "problem": "Hatalı GTİP beyanı 4458 sayılı Kanun uyarınca 3 kat vergi cezası ve kaçakçılık soruşturması açtırıyor.",
                "audience": "Gümrük müşavirlikleri, ithalat/ihracat devleri",
                "workaround": "Bakanlık ciltli tarife cetvellerini ve emsal kararları elle taramak",
                "venture_id": "ven-pilot-004-tarifa",
                "code_slug": "tarifacustoms-ai",
                "display_name": "TarifaCustoms AI",
                "tagline": "12 Haneli GTİP Tespiti ve Menşe Risk Analiz Motoru",
                "api_path": "/api/v1/plugins/tarifa",
                "mrr": 8372.00,
                "subscribers": 28
            },
            {
                "expert_id": "exp-pilot-005-freight",
                "email": "onur.lojistik@freightforwarding.com",
                "full_name": "O. T. (Freight Forwarder Operasyon Direktörü)",
                "phone": "+905375556677",
                "domain": "maritime_logistics",
                "exp": 15,
                "idea_id": "idea-pilot-005-demurrage",
                "title": "DemurrageShield (Konteyner Ardiye, Demuraj ve Serbest Süre Erken Uyarı Ajanı)",
                "problem": "Limanlarda serbest süresi dolan konteynerler için günlük $150-$300 ceza kesiliyor; armatör faturalarının %35'i hatalı.",
                "audience": "Uluslararası freight forwarder ve lojistik firmaları",
                "workaround": "Armatör takip sitelerine tek tek konteyner no girip serbest gün saymak",
                "venture_id": "ven-pilot-005-demurrage",
                "code_slug": "demurrage-shield",
                "display_name": "DemurrageShield",
                "tagline": "Konteyner Serbest Süre ve Haksız Demuraj Fatura İtiraz Motoru",
                "api_path": "/api/v1/plugins/demurrage",
                "mrr": 8715.00,
                "subscribers": 35
            }
        ]

        now = get_current_iso_time()
        for p in pilots:
            # 1. Expert
            self.execute(
                """
                INSERT OR IGNORE INTO domain_experts (
                    expert_id, email, full_name, phone_number, industry_domain,
                    years_of_experience, ip_assignment_signed, ip_assignment_signed_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (p["expert_id"], p["email"], p["full_name"], p["phone"], p["domain"], p["exp"], now, now, now)
            )

            # 2. Idea
            self.execute(
                """
                INSERT OR IGNORE INTO domain_ideas (
                    idea_id, expert_id, title, problem_statement, target_audience,
                    current_workaround, stake_amount_usd, stake_payment_status, status,
                    domain_depth_score, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 10.00, 'CAPTURED_TO_EQUITY', 'SYNTHESIZED', 0.94, ?, ?)
                """,
                (p["idea_id"], p["expert_id"], p["title"], p["problem"], p["audience"], p["workaround"], now, now)
            )

            # 3. Venture
            self.execute(
                """
                INSERT OR IGNORE INTO ventures (
                    venture_id, idea_id, code_slug, display_name, tagline,
                    docker_container_name, git_commit_sha, api_prefix_path, status,
                    target_monthly_mrr_usd, current_monthly_mrr_usd, active_b2b_subscribers,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'git-prod-c0ffee2026', ?, 'PRODUCTION_LIVE', 10000.00, ?, ?, ?, ?)
                """,
                (p["venture_id"], p["idea_id"], p["code_slug"], p["display_name"], p["tagline"],
                 f"syntropion-{p['code_slug']}", p["api_path"], p["mrr"], p["subscribers"], now, now)
            )

            # 4. Milestone Vesting (Tier 1 Unlocked)
            self.execute(
                """
                INSERT OR IGNORE INTO milestone_vestings (
                    vesting_id, venture_id, expert_id, milestone_tier, description,
                    rev_share_percentage, is_unlocked, unlocked_at, license_key, created_at
                ) VALUES (?, ?, ?, 1, 'Alpha Testi ve 10 Doğrulama Veri Seti Onayı', 20.00, 1, ?, ?, ?)
                """,
                (f"vest-{p['venture_id']}-1", p["venture_id"], p["expert_id"], now,
                 f"SYNTROPION-LIFETIME-{p['code_slug'].upper()}-VALID-2026", now)
            )

            # 5. Token Quota
            billing_month = now[:7]
            self.execute(
                """
                INSERT OR IGNORE INTO token_quotas (
                    quota_id, expert_id, venture_id, billing_cycle_month,
                    free_token_limit, used_tokens, overflow_tokens, overflow_billed_usd,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 5000000, 1420500, 0, 0.0, ?, ?)
                """,
                (f"quota-{p['expert_id']}-{billing_month}", p["expert_id"], p["venture_id"], billing_month, now, now)
            )


# Default Singleton
db = DatabaseManager()
