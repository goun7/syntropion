"""test_database_dallar.py — syntropion_core/database.py dal-kesen testleri

Thread-safe SQLite WAL kalıcılık-katmanı: bağlantı-üretimi, atomik
transaction, kilit-yeniden-deneme ( exponential-backoff), WAL-checkpoint,
şema-yönetimi, merkle-hash-chain audit-ledger ve 5-pilot tohumlama.

TÜM DALLAR:
  get_current_iso_time:
    1.  ISO-8601 UTC döner ( '+00:00' suffix, parse-edilebilir, şimdiki-zamana-yakın)
  DatabaseManager.__init__ / _ensure_schema:
    2.  şema oluşturur ( ventures/ideas/experts/audit_ledger tabloları)
    3.  db_path kaydedilir
    4.  idempotent — tekrar-çağrı tablo-sayısını-bozmaz
    5.  schema.sql yoksa ( os.path.exists False) sessizce-atlar
  get_connection:
    6.  row_factory = sqlite3.Row ( dict-erişim)
    7.  journal_mode = WAL
    8.  foreign_keys = ON ( 1)
    9.  synchronous = NORMAL ( 1)
    10. busy_timeout = 60000
    11. check_same_thread=False → başka-thread'den sorgu-çalışır
  transaction:
    12. başarı → commit kalıcı olur
    13. istisna → rollback + istisna-yayılır + veri-yazılmaz
    14. çıkışta bağlantı kapanır ( kapalı-db hatası)
  run_transaction:
    15. callback sonucu-döner + commit
    16. generic-exception → rollback + hemen-yükselir
    17. 'locked' OperationalError → exponential-backoff ile YENİDEN-DENER
        ( 0.05 → 0.1, deneme-bittiğinde yükselir)
    18. 'locked' OLMAYAN OperationalError → yeniden-deneme-YOK ( hemen)
    19. her-durumda bağlantı kapanır
  checkpoint_wal:
    20. None döner + WAL truncate edilir + veri-okunmaya-devam-eder
  execute / fetchone / fetchall:
    21. INSERT rowcount=1; UPDATE-yok rowcount=0
    22. fetchone → dict | None
    23. fetchall → dict-listesi | [] ( parametrelerle)
  log_audit_event ( merkle-zinciri):
    24. ilk-event previous_hash = GENESIS_HASH_000…
    25. zincir-bağlı: 2.event.prev = 1.event.current_hash
    26. sha256(prev:type:actor:ts:payload) == current_hash ( DOĞRULANABİLİR)
    27. payload_json sort_keys=True ile-serileşir
    28. dönüş-değeri = current_hash ( 64-hex)
  seed_deep_vertical_pilots:
    29. 5 expert + 5 idea + 5 venture + 5 milestone + 5 quota ekler
    30. özgür-değerler ( radtrack-ai/PRODUCTION_LIVE/8358.00 MRR)
    31. idempotent ( 2.çağrı yine-5)
    32. milestone: 20% rev-share + unlocked + SYNTROPION-LIFETIME license
    33. token_quotas: 5_000_000 limit / 1_420_500 used

Kural-1: SADECE-yeni-dosya ( modül/conftest-DOKUNULMAZ). Kural-4: tmp_path
SQLite ( repo-dışı), gerçek-syntropion.db'ye DOKUNULMAZ; time.sleep monkeypatch.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

import pytest

# --- Kural-4: import-anında gerçek syntropion.db'ye DOKUNMA -------------------
# database.py module-level `db = DatabaseManager()` üretir → WAL+şema yazar.
# Henüz-import-edilmemişse SYNTROPION_DB_PATH'i /tmp'ye yönlendir ( tam-suite
# koşusunda zaten-import-edilmiştir → DOKUNMA).
if "syntropion_core.database" not in sys.modules:
    _TMPDIR = tempfile.mkdtemp(prefix="syntropion-dallar-db-")
    os.environ.setdefault("SYNTROPION_DB_PATH", os.path.join(_TMPDIR, "db.db"))

from syntropion_core import database as dbmod
from syntropion_core.database import DatabaseManager, get_current_iso_time

EXPERT_INSERT = """
    INSERT INTO domain_experts (
        expert_id, email, full_name, industry_domain, years_of_experience,
        ip_assignment_signed, ip_assignment_signed_at, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
"""


@pytest.fixture
def mgr(tmp_path):
    """Taze tmp SQLite dosyalı-yönetici ( repo-dışı — Kural-4)."""
    return DatabaseManager(str(tmp_path / "dallar.db"))


@pytest.fixture
def expert(mgr):
    """Bir-satır expert ekler ve rowcount döner."""
    now = get_current_iso_time()
    return mgr.execute(
        EXPERT_INSERT,
        ("exp-1", "a@b.com", "Test Uzmanı", "general", 10, now, now, now),
    )


# ---------------------------------------------------------------------------
# get_current_iso_time
# ---------------------------------------------------------------------------
class TestGetCurrentIsoTime:
    def test_iso8601_utc_donuyor(self):
        ts = get_current_iso_time()
        assert isinstance(ts, str)
        assert ts.endswith("+00:00")
        # parse-edilebilir + UTC-zamandiliminde
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == 0

    def test_simdiki_zamana_yakin(self):
        ts = get_current_iso_time()
        dt = datetime.fromisoformat(ts)
        fark = abs((datetime.now(timezone.utc) - dt).total_seconds())
        assert fark < 5.0

    def test_format_genisligi(self):
        ts = get_current_iso_time()
        assert ts[4] == "-" and ts[7] == "-" and ts[10] == "T"
        assert ts[13] == ":" and ts[16] == ":"  # ss:dd:ss
        assert ts.endswith("+00:00") and ts.index("+") > ts.index("T")


# ---------------------------------------------------------------------------
# __init__ / _ensure_schema
# ---------------------------------------------------------------------------
class TestEnsureSchema:
    def test_tablolari_olusturur(self, mgr):
        tablolar = {
            r["name"]
            for r in mgr.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "ventures" in tablolar
        assert "domain_ideas" in tablolar
        assert "domain_experts" in tablolar
        assert "audit_ledger" in tablolar
        assert "milestone_vestings" in tablolar
        assert "token_quotas" in tablolar

    def test_db_path_kaydedilir(self, tmp_path):
        yol = str(tmp_path / "diger.db")
        assert DatabaseManager(yol).db_path == yol

    def test_idempotent_tablo_sayisi_korunur(self, mgr):
        once = mgr.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        mgr._ensure_schema()
        mgr._ensure_schema()
        sonra = mgr.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        assert once == sonra

    def test_schema_yoksa_sessizce_atlar(self, tmp_path, monkeypatch):
        """os.path.exists False → executescript ÇALIŞMAZ → tablo-yok."""
        monkeypatch.setattr(dbmod.os.path, "exists", lambda yol: False)
        bos = DatabaseManager(str(tmp_path / "bosluk.db"))
        tablolar = bos.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        # sqlite_* iç-tabloları hariç-tut
        assert not any(not t["name"].startswith("sqlite_") for t in tablolar)


# ---------------------------------------------------------------------------
# get_connection
# ---------------------------------------------------------------------------
class TestGetConnection:
    def test_row_factory_row(self, mgr):
        conn = mgr.get_connection()
        try:
            assert conn.row_factory is sqlite3.Row
            satir = conn.execute("SELECT 42 as cevap").fetchone()
            assert satir["cevap"] == 42
        finally:
            conn.close()

    def test_journal_mode_wal(self, mgr):
        conn = mgr.get_connection()
        try:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        finally:
            conn.close()

    def test_foreign_keys_acik(self, mgr):
        conn = mgr.get_connection()
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()

    def test_synchronous_normal(self, mgr):
        conn = mgr.get_connection()
        try:
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
        finally:
            conn.close()

    def test_busy_timeout_60s(self, mgr):
        conn = mgr.get_connection()
        try:
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 60000
        finally:
            conn.close()

    def test_baska_threadden_calisir(self, mgr):
        """check_same_thread=False → bağlantı başka-thread'de-kullanılabilir."""
        import threading

        sonuc = {}
        conn = mgr.get_connection()

        def _calis():
            try:
                sonuc["deger"] = conn.execute("SELECT 7 as x").fetchone()["x"]
            except Exception as hata:  # noqa: BLE001
                sonuc["hata"] = repr(hata)

        thread = threading.Thread(target=_calis)
        thread.start()
        thread.join()
        conn.close()
        assert sonuc.get("deger") == 7
        assert "hata" not in sonuc


# ---------------------------------------------------------------------------
# transaction
# ---------------------------------------------------------------------------
class TestTransaction:
    def test_basari_commit_kalici(self, mgr):
        with mgr.transaction() as conn:
            conn.execute("CREATE TABLE gecici_t (x INTEGER)")
            conn.execute("INSERT INTO gecici_t VALUES (99)")
        assert mgr.fetchone("SELECT x FROM gecici_t")["x"] == 99

    def test_istisna_rollback_ve_yayilir(self, mgr):
        """DML ( INSERT) rollback ile tamamen-geri-alınır."""
        now = get_current_iso_time()
        with pytest.raises(RuntimeError, match="bilinçli-hata"):
            with mgr.transaction() as conn:
                conn.execute(
                    EXPERT_INSERT, ("exp-rb", "rb@b.com", "U", "g", 1, now, now, now)
                )
                raise RuntimeError("bilinçli-hata")
        assert mgr.fetchone("SELECT expert_id FROM domain_experts WHERE expert_id='exp-rb'") is None

    def test_ddl_rollback_disinda_kalir(self, mgr):
        """DAL-GÖZÜ: transaction() DDL'i ( CREATE TABLE) geri-ALAMAZ.

        Python-3.12+ sqlite3 modülü DDL'leri otomatik-commit'ler ( implicit
        transaction yalnızca DML için-açılır); bu-yüzden raise sonrası
        rollback() tablo-yaratımını-GERİ-ALMAZ. DML ( yukarıdaki-test) ise
        tamamen geri-alınır. Bu-test o-sınırı-belgeler.
        """
        with pytest.raises(RuntimeError, match="bilinçli-hata"):
            with mgr.transaction() as conn:
                conn.execute("CREATE TABLE ddl_disarida (x INTEGER)")
                raise RuntimeError("bilinçli-hata")
        kalan = mgr.fetchone("SELECT name FROM sqlite_master WHERE name='ddl_disarida'")
        assert kalan is not None
        assert kalan["name"] == "ddl_disarida"

    def test_cikista_baglanti_kapanir(self, mgr):
        with mgr.transaction() as conn:
            conn.execute("SELECT 1")
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# run_transaction
# ---------------------------------------------------------------------------
class _FakeConn:
    """run_transaction davranışını-kaydeden sahte-bağlantı ( gerçek-SQL YOK)."""

    def __init__(self, kayit, hata=None, basarisiz_deneme=0):
        self.kayit = kayit
        self.hata = hata
        self.basarisiz_deneme = basarisiz_deneme
        self.deneme = 0

    def execute(self, query, params=()):
        self.deneme += 1
        if self.deneme <= self.basarisiz_deneme and self.hata is not None:
            raise self.hata
        return iter([])

    def commit(self):
        self.kayit["commit"] += 1

    def rollback(self):
        self.kayit["rollback"] += 1

    def close(self):
        self.kayit["close"] += 1


class TestRunTransaction:
    def test_sonuc_ve_commit(self, mgr):
        sonuc = mgr.run_transaction(lambda conn: "tamam")
        assert sonuc == "tamam"

    def test_callback_calismasi_kalici(self, mgr):
        mgr.run_transaction(
            lambda conn: conn.execute("CREATE TABLE run_t (x INTEGER)")
        )
        assert mgr.fetchone("SELECT name FROM sqlite_master WHERE name='run_t'") is not None

    def test_generic_exception_rollback(self, mgr):
        def _patlat(conn):
            raise ValueError("kasitli")

        with pytest.raises(ValueError, match="kasitli"):
            mgr.run_transaction(_patlat)
        # hata sonrası tablo-yok ( rollback + bağlantı-kapandı)

    def test_basarisizda_baglanti_kapanir(self, mgr):
        kayit = {"commit": 0, "rollback": 0, "close": 0}

        def _factory():
            return _FakeConn(kayit, hata=RuntimeError("patla"), basarisiz_deneme=1)

        mgr.get_connection = _factory

        def _calistir(conn):
            conn.execute("SELECT 1")  # _FakeConn burada-hata-fırlatır

        with pytest.raises(RuntimeError, match="patla"):
            mgr.run_transaction(_calistir)
        assert kayit == {"commit": 0, "rollback": 1, "close": 1}

    def test_locked_exponential_backoff_ile_yeniden_dener(self, mgr, monkeypatch):
        """'locked' hatası 2-kez-then-başarı → 0.05 + 0.1 uyku ile 3-deneme."""
        uyuklar = []
        monkeypatch.setattr("time.sleep", lambda s: uyuklar.append(s))
        kayit = {"commit": 0, "rollback": 0, "close": 0}
        cagrilar = []

        def _factory():
            n = len(cagrilar) + 1
            cagrilar.append(n)
            # 1. ve 2. bağlantı locked-hata-verir, 3. başarılı
            return _FakeConn(
                kayit,
                hata=sqlite3.OperationalError("database is locked"),
                basarisiz_deneme=3 if n <= 2 else 0,
            )

        mgr.get_connection = _factory

        def _calistir(conn):
            conn.execute("SELECT 1")
            return "3-denemede-tamam"

        sonuc = mgr.run_transaction(_calistir, max_retries=3)
        assert sonuc == "3-denemede-tamam"
        assert uyuklar == [0.05, 0.1]  # exponential: 0.05 → 0.1
        assert cagrilar == [1, 2, 3]
        # 2-başarısız ( rollback+close) + 1-başarılı ( commit+close)
        assert kayit == {"commit": 1, "rollback": 2, "close": 3}

    def test_locked_deneme_bitince_yukselir(self, mgr, monkeypatch):
        uyuklar = []
        monkeypatch.setattr("time.sleep", lambda s: uyuklar.append(s))
        kayit = {"commit": 0, "rollback": 0, "close": 0}

        def _factory():
            return _FakeConn(
                kayit,
                hata=sqlite3.OperationalError("database is locked"),
                basarisiz_deneme=99,
            )

        mgr.get_connection = _factory

        def _calistir(conn):
            conn.execute("SELECT 1")

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            mgr.run_transaction(_calistir, max_retries=2)
        assert uyuklar == [0.05]  # yalnızca 1. deneme-sırasında uyku ( 2 < 2 false)
        assert kayit == {"commit": 0, "rollback": 2, "close": 2}

    def test_locked_olmayan_operational_hemen_yukselir(self, mgr, monkeypatch):
        uyuklar = []
        monkeypatch.setattr("time.sleep", lambda s: uyuklar.append(s))
        kayit = {"commit": 0, "rollback": 0, "close": 0}

        def _factory():
            return _FakeConn(
                kayit,
                hata=sqlite3.OperationalError("no such table: yok"),
                basarisiz_deneme=1,
            )

        mgr.get_connection = _factory

        def _calistir(conn):
            conn.execute("SELECT 1")

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            mgr.run_transaction(_calistir, max_retries=5)
        assert uyuklar == []  # yeniden-deneme-YOK
        assert kayit == {"commit": 0, "rollback": 1, "close": 1}

    def test_baslangic_backoff_degistirilebilir(self, mgr, monkeypatch):
        """initial_backoff parametresi uykunun-başlangıç-değerini-belirler."""
        uyuklar = []
        monkeypatch.setattr("time.sleep", lambda s: uyuklar.append(s))
        kayit = {"commit": 0, "rollback": 0, "close": 0}
        cagrilar = []

        def _factory():
            n = len(cagrilar) + 1
            cagrilar.append(n)
            return _FakeConn(
                kayit,
                hata=sqlite3.OperationalError("database is locked"),
                basarisiz_deneme=3 if n == 1 else 0,
            )

        mgr.get_connection = _factory

        def _calistir(conn):
            conn.execute("SELECT 1")

        assert mgr.run_transaction(_calistir, max_retries=3, initial_backoff=0.2) is None
        assert uyuklar == [0.2]  # 0.2'den-başladı ( 2.deneme-olmadı)


# ---------------------------------------------------------------------------
# checkpoint_wal
# ---------------------------------------------------------------------------
class TestCheckpointWal:
    def test_none_doner_veri_korunur(self, mgr, expert):
        assert mgr.checkpoint_wal() is None
        assert mgr.fetchone("SELECT expert_id FROM domain_experts WHERE expert_id='exp-1'") is not None

    def test_insert_sonrasi_checkpoint_yine_calisir(self, mgr):
        for i in range(5):
            now = get_current_iso_time()
            mgr.execute(
                EXPERT_INSERT,
                (f"exp-{i}", f"x{i}@b.com", "U", "g", 1, now, now, now),
            )
        mgr.checkpoint_wal()
        assert len(mgr.fetchall("SELECT expert_id FROM domain_experts")) == 5


# ---------------------------------------------------------------------------
# execute / fetchone / fetchall
# ---------------------------------------------------------------------------
class TestSorguMetodlari:
    def test_execute_insert_rowcount_bir(self, expert):
        assert expert == 1

    def test_execute_update_rowcount_sifir(self, mgr):
        assert mgr.execute("UPDATE domain_experts SET full_name=? WHERE expert_id=?",
                           ("Yok", "exp-yok-999")) == 0

    def test_fetchone_dict_donuyor(self, mgr, expert):
        satir = mgr.fetchone("SELECT expert_id, email FROM domain_experts WHERE expert_id=?",
                             ("exp-1",))
        assert satir["expert_id"] == "exp-1"
        assert satir["email"] == "a@b.com"

    def test_fetchone_satir_yok_none(self, mgr):
        assert mgr.fetchone("SELECT * FROM domain_experts WHERE expert_id=?", ("yok",)) is None

    def test_fetchall_dict_listesi(self, mgr):
        for i in range(3):
            now = get_current_iso_time()
            mgr.execute(EXPERT_INSERT, (f"e{i}", f"e{i}@b.com", "U", "g", 1, now, now, now))
        satirlar = mgr.fetchall("SELECT expert_id FROM domain_experts ORDER BY expert_id")
        assert [r["expert_id"] for r in satirlar] == ["e0", "e1", "e2"]

    def test_fetchall_bos_liste(self, mgr):
        assert mgr.fetchall("SELECT * FROM domain_experts") == []

    def test_fetchall_parametre_gecirilir(self, mgr):
        now = get_current_iso_time()
        mgr.execute(EXPERT_INSERT, ("a", "a@b.com", "U", "g", 1, now, now, now))
        mgr.execute(EXPERT_INSERT, ("b", "b@b.com", "U", "g", 1, now, now, now))
        sonuc = mgr.fetchall("SELECT expert_id FROM domain_experts WHERE email=?",
                            ("b@b.com",))
        assert sonuc == [{"expert_id": "b"}]


# ---------------------------------------------------------------------------
# log_audit_event ( merkle hash-chain)
# ---------------------------------------------------------------------------
class TestLogAuditEvent:
    def test_ilk_event_genesis_prev(self, mgr):
        h1 = mgr.log_audit_event("TEST_EVENT", "TEST_ACTOR", {"x": 1})
        satir = mgr.fetchone("SELECT * FROM audit_ledger WHERE id=1")
        assert len(h1) == 64
        assert int(h1, 16) >= 0  # geçerli-hex
        assert satir["previous_hash"].startswith("GENESIS_HASH_000")
        assert satir["current_hash"] == h1

    def test_zincir_bagli(self, mgr):
        h1 = mgr.log_audit_event("A", "ACTOR", {"i": 1})
        h2 = mgr.log_audit_event("B", "ACTOR", {"i": 2})
        satirlar = mgr.fetchall("SELECT previous_hash, current_hash FROM audit_ledger ORDER BY id")
        assert satirlar[1]["previous_hash"] == h1
        assert satirlar[0]["current_hash"] == h1
        assert satirlar[1]["current_hash"] == h2
        assert h1 != h2

    def test_hash_dogrulanabilir(self, mgr):
        donus = mgr.log_audit_event("EVENT", "AKTOR", {"b": 1, "a": 2})
        satir = mgr.fetchone(
            "SELECT event_type, actor, payload_json, timestamp, previous_hash, current_hash "
            "FROM audit_ledger WHERE id=1"
        )
        beklenen = hashlib.sha256(
            f"{satir['previous_hash']}:{satir['event_type']}:{satir['actor']}:"
            f"{satir['timestamp']}:{satir['payload_json']}".encode("utf-8")
        ).hexdigest()
        assert beklenen == satir["current_hash"]
        assert beklenen == donus

    def test_payload_json_sort_keys(self, mgr):
        mgr.log_audit_event("E", "A", {"b": 1, "a": 2, "c": 3})
        satir = mgr.fetchone("SELECT payload_json FROM audit_ledger")
        assert satir["payload_json"] == '{"a": 2, "b": 1, "c": 3}'

    def test_payload_dict_degilse_de_calisir(self, mgr):
        """json.dumps herhangi bir JSON-değerini-kabul-eder ( liste/sayı)."""
        mgr.log_audit_event("E", "A", [1, 2, 3])
        satir = mgr.fetchone("SELECT payload_json FROM audit_ledger")
        assert satir["payload_json"] == "[1, 2, 3]"


# ---------------------------------------------------------------------------
# seed_deep_vertical_pilots
# ---------------------------------------------------------------------------
class TestSeedDeepVerticalPilots:
    def test_bes_pilot_ekler(self, mgr):
        mgr.seed_deep_vertical_pilots()
        assert len(mgr.fetchall("SELECT * FROM domain_experts")) == 5
        assert len(mgr.fetchall("SELECT * FROM domain_ideas")) == 5
        assert len(mgr.fetchall("SELECT * FROM ventures")) == 5
        assert len(mgr.fetchall("SELECT * FROM milestone_vestings")) == 5
        assert len(mgr.fetchall("SELECT * FROM token_quotas")) == 5

    def test_ozgur_pilot_degerleri(self, mgr):
        mgr.seed_deep_vertical_pilots()
        sluglar = {
            r["code_slug"]: r
            for r in mgr.fetchall("SELECT code_slug, status, current_monthly_mrr_usd "
                                  "FROM ventures")
        }
        assert set(sluglar) == {
            "radtrack-ai", "lexnotice-ai", "taxcross-audit",
            "tarifacustoms-ai", "demurrage-shield",
        }
        assert sluglar["radtrack-ai"]["status"] == "PRODUCTION_LIVE"
        assert sluglar["radtrack-ai"]["current_monthly_mrr_usd"] == 8358.00
        assert sluglar["demurrage-shield"]["current_monthly_mrr_usd"] == 8715.00

    def test_idea_status_sentezlendi(self, mgr):
        mgr.seed_deep_vertical_pilots()
        durumlar = {
            r["status"] for r in mgr.fetchall("SELECT status FROM domain_ideas")
        }
        assert durumlar == {"SYNTHESIZED"}

    def test_idempotent_bes_kalir(self, mgr):
        mgr.seed_deep_vertical_pilots()
        mgr.seed_deep_vertical_pilots()
        assert len(mgr.fetchall("SELECT * FROM ventures")) == 5
        assert len(mgr.fetchall("SELECT * FROM domain_experts")) == 5

    def test_milestone_vesting_degerleri(self, mgr):
        mgr.seed_deep_vertical_pilots()
        ms = mgr.fetchone(
            "SELECT rev_share_percentage, is_unlocked, license_key, milestone_tier "
            "FROM milestone_vestings WHERE venture_id LIKE '%radtrack%'"
        )
        assert ms["rev_share_percentage"] == 20.00
        assert ms["is_unlocked"] == 1
        assert ms["milestone_tier"] == 1
        assert ms["license_key"].startswith("SYNTROPION-LIFETIME-")
        assert "RADTRACK-AI" in ms["license_key"]

    def test_token_quota_degerleri(self, mgr):
        mgr.seed_deep_vertical_pilots()
        q = mgr.fetchone(
            "SELECT free_token_limit, used_tokens, overflow_tokens, billing_cycle_month "
            "FROM token_quotas LIMIT 1"
        )
        assert q["free_token_limit"] == 5_000_000
        assert q["used_tokens"] == 1_420_500
        assert q["overflow_tokens"] == 0
        assert len(q["billing_cycle_month"]) == 7  # YYYY-MM

    def test_audit_zinciri_dolu_degil(self, mgr):
        """seedDeepVerticalPilots audit-ledger'a YAZMAZ ( yalnızca tablolar)."""
        mgr.seed_deep_vertical_pilots()
        assert mgr.fetchall("SELECT * FROM audit_ledger") == []
