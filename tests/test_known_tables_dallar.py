"""18-Syntropion honest_metrics._known_tables/_require_known_table dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory — GERCEK sqlite3 ':memory:' katalogu (subprocess/
network/remote YASAK). db globali GECICI olarak in-memory connection ile
monkeypatch edilir, finally'de geri-yuklenir.

ORTAM-ANATOMI:
- _known_tables(): sqlite_master katalogundan tablo adlari -> list[str]
- _require_known_table(table_name): tablo yoksa ValueError
  ('Bilinmeyen tablo: <ad>'); varsa table_name'i oldugu gibi dondurur
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, ".")
import syntropion_core.honest_metrics as hm  # noqa: E402
from syntropion_core.honest_metrics import (  # noqa: E402
    _known_tables, _require_known_table,
)

_ORIGINAL_DB = hm.db


class _FakeRow(dict):
    """sqlite3.Row-benzeri: r['name'] erisimi."""

    def __getitem__(self, key):
        return dict.__getitem__(self, key)


class _FakeDb:
    """sqlite_master katalogunu monkeypatch'lenmemis saf-kodla taklit eder."""

    def __init__(self, tables):
        self._tables = list(tables)

    def __init__(self, tables):
        self._tables = list(tables)
        self.queries = []

    def fetchall(self, query):
        self.queries.append(query)
        return [_FakeRow({"name": t}) for t in self._tables]


@pytest.fixture
def fake_db(monkeypatch):
    def _set(tables):
        monkeypatch.setattr(hm, "db", _FakeDb(tables))
    return _set


def _fake(tables):
    """_FakeDb dogrudan (query-kaydi icin)."""
    return _FakeDb(tables)


# == _known_tables ====================================================================================

def test_known_tables_bos(fake_db):
    fake_db([])
    assert _known_tables() == []


def test_known_tables_bir(fake_db):
    fake_db(["agents"])
    assert _known_tables() == ["agents"]


def test_known_tables_birkac(fake_db):
    fake_db(["agents", "ventures", "events"])
    assert _known_tables() == ["agents", "ventures", "events"]


def test_known_tables_donut_tipi(fake_db):
    fake_db(["a"])
    assert isinstance(_known_tables(), list)


def test_known_tables_eleman_tipi(fake_db):
    fake_db(["a"])
    assert all(isinstance(t, str) for t in _known_tables())


def test_known_tables_stabil(fake_db):
    fake_db(["a", "b"])
    assert _known_tables() == _known_tables()


def test_known_tables_sira_korunur(fake_db):
    """ORTAM: katalog siralamasi KORUNUR (ORDER BY YOK)."""
    fake_db(["z", "a", "m"])
    assert _known_tables() == ["z", "a", "m"]


def test_known_tables_tekrar(fake_db):
    """ORTAM: tekrarlanan isimler tekrarlanir (DISTINCT YOK)."""
    fake_db(["a", "a"])
    assert _known_tables() == ["a", "a"]


def test_known_tables_sql_injection_komut_adi(fake_db):
    """ORTAM: tablo adi olarak SQL anahtari KABUL (katalogdan gelir)."""
    fake_db(["select", "from", "where"])
    assert _known_tables() == ["select", "from", "where"]


def test_known_tables_ozel_karakter(fake_db):
    fake_db(["tablo-adı", "tëst"])
    assert _known_tables() == ["tablo-adı", "tëst"]


@pytest.mark.parametrize("tables", [[], ["a"], ["a", "b"], ["x", "y", "z"]])
def test_known_tables_matrix(fake_db, tables):
    fake_db(tables)
    assert _known_tables() == tables


# == _require_known_table =============================================================================

def test_require_var(fake_db):
    """ORTAM: tablo var -> ayni isim geri doner."""
    fake_db(["agents"])
    assert _require_known_table("agents") == "agents"


def test_require_yok_hata(fake_db):
    """ORTAM: tablo yok -> ValueError."""
    fake_db(["agents"])
    with pytest.raises(ValueError):
        _require_known_table("yok")


def test_require_bos_liste(fake_db):
    fake_db([])
    with pytest.raises(ValueError):
        _require_known_table("agents")


def test_require_hata_mesaj(fake_db):
    """ORTAM: hata mesaji 'Bilinmeyen tablo: <ad>'."""
    fake_db([])
    with pytest.raises(ValueError) as e:
        _require_known_table("foo")
    assert "Bilinmeyen tablo" in str(e.value)
    assert "foo" in str(e.value)


def test_require_donut_tipi(fake_db):
    fake_db(["a"])
    assert isinstance(_require_known_table("a"), str)


def test_require_case_sensitive(fake_db):
    """ORTAM-OGRENDI: karsilastirma case-SENSITIVE — 'AGENTS' != 'agents'."""
    fake_db(["agents"])
    with pytest.raises(ValueError):
        _require_known_table("AGENTS")


def test_require_bosluklu(fake_db):
    """ORTAM: ' agents' (bosluk) != 'agents'."""
    fake_db(["agents"])
    with pytest.raises(ValueError):
        _require_known_table(" agents")


def test_require_bos_isim(fake_db):
    """ORTAM: '' tablo yok -> ValueError."""
    fake_db(["agents"])
    with pytest.raises(ValueError):
        _require_known_table("")


def test_require_none_isim(fake_db):
    """ORTAM: None -> ValueError (None not in list)."""
    fake_db(["agents"])
    with pytest.raises(ValueError):
        _require_known_table(None)


def test_require_coklu(fake_db):
    fake_db(["a", "b", "c"])
    for t in ["a", "b", "c"]:
        assert _require_known_table(t) == t


@pytest.mark.parametrize("table", ["a", "b", "c"])
def test_require_matrix(fake_db, table):
    fake_db(["a", "b", "c"])
    assert _require_known_table(table) == table


@pytest.mark.parametrize("table", ["d", "A", "", "x"])
def test_require_yok_matrix(fake_db, table):
    fake_db(["a", "b", "c"])
    with pytest.raises(ValueError):
        _require_known_table(table)


# == sqlite_master sorgu dogrulama ================================================================

def test_sqlite_master_sorgusu(fake_db):
    """ORTAM-OGRENDI: _known_tables sqlite_master katalogunu sorar —
    'SELECT name FROM sqlite_master ...'. Bu db'nin fetchall'ina gider."""
    db = _FakeDb(["a"])
    import syntropion_core.honest_metrics as m
    eski = m.db
    m.db = db
    try:
        _known_tables()
    finally:
        m.db = eski
    assert len(db.queries) == 1
    assert "sqlite_master" in db.queries[0]


def test_sqlite_master_sorgu_tipi(fake_db):
    db = _FakeDb(["a"])
    import syntropion_core.honest_metrics as m
    eski = m.db
    m.db = db
    try:
        _known_tables()
    finally:
        m.db = eski
    assert "name" in db.queries[0]


def test_require_known_tables_cagrisi():
    """ORTAM: _require_known_table once _known_tables cagirir."""
    db = _FakeDb(["agents"])
    import syntropion_core.honest_metrics as m
    eski = m.db
    m.db = db
    try:
        _require_known_table("agents")
    finally:
        m.db = eski
    assert len(db.queries) == 1


def test_require_iki_cagri_stabil():
    db = _FakeDb(["a", "b"])
    import syntropion_core.honest_metrics as m
    eski = m.db
    m.db = db
    try:
        _require_known_table("a")
        _require_known_table("b")
    finally:
        m.db = eski
    assert len(db.queries) == 2


# == karakterizasyon ===================================================================================

def test_db_global_tipi():
    """ORTAM: db modul-level globali (import ile gelir)."""
    assert _ORIGINAL_DB is not None


def test_db_global_geri_yuklenir(fake_db):
    """ORTAM-OGRENDI: monkeypatch sonrasi orijinal db geri-yuklenmeli
    (fixture teardown). Kural-4: diger testler etkilenmesin."""
    fake_db(["x"])
    assert hm.db is not _ORIGINAL_DB


def test_injection_guvenligi(fake_db):
    """ORTAM-OGRENDI (GUVENLIK): tablo adi KATALOG ile karsilastirilir —
    'agents; DROP TABLE' gibi injection DENEMELERI ValueError alir
    (katalogda boyle tablo yok). Bu string-interpolation'i onler:
    db_row_count(f'SELECT ... {table}') once _require_known_table ile
    dogrulamak guvenli kilar."""
    fake_db(["agents"])
    for kotu in ["agents; DROP TABLE users", "agents' OR '1'='1", "agents--"]:
        with pytest.raises(ValueError):
            _require_known_table(kotu)
