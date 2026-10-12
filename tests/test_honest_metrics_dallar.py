r"""18-Syntropion foundry_core.honest_metrics._known_tables/_require_known_table dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (monkeypatch ile sahte db.fetchall; network/DB YOK).

ORTAM-ANATOMI:
- _known_tables(): db.fetchall("SELECT name FROM sqlite_master ...")
  -> [r["name"] for r in rows] (sqlite_% tablolari HARIC)
- _require_known_table(table_name): tablo katalogda YOKSA ValueError
  (mesaj: bilinen tablolar sorted); varsa table_name doner
"""
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "foundry_core")
import foundry_core.honest_metrics as hm  # noqa: E402
from foundry_core.honest_metrics import _known_tables, _require_known_table  # noqa: E402


class _FakeDB:
    """sqlite_master katalogunu sahteleyen in-memory db.fetchall."""

    def __init__(self, names):
        self._names = names
        self.calls = []

    def fetchall(self, sql):
        self.calls.append(sql)
        # SQLite'in "NOT LIKE sqlite_%" filtresini safteliyoruz (sorgu
        # tarafinda filtrelenir — Python'da DEGIL)
        names = [n for n in self._names if not n.startswith("sqlite_")]
        return [{"name": n} for n in names]


@pytest.fixture
def fake_db(monkeypatch):
    def _install(names):
        db = _FakeDB(names)
        monkeypatch.setattr(hm, "db", db)
        return db
    return _install


@pytest.fixture
def katalog(monkeypatch):
    db = _FakeDB(["users", "socratic_interviews", "mrr_provenance", "events"])
    monkeypatch.setattr(hm, "db", db)
    return db


# == _known_tables =====================================================================================

def test_known_tables_basit(katalog):
    """ORTAM: [r['name'] for r in rows]."""
    assert _known_tables() == ["users", "socratic_interviews",
                               "mrr_provenance", "events"]


def test_known_tables_sql(katalog):
    """ORTAM: sqlite_master sorgusu — type='table' + sqlite_% HARIC."""
    _known_tables()
    sql = katalog.calls[0]
    assert "sqlite_master" in sql
    assert "type='table'" in sql
    assert "sqlite_%" in sql


def test_known_tables_sqlite_haric(monkeypatch):
    """ORTAM-OGRENDI: sqlite_% tablolari HARIC tutulur (sorgu filtresi —
    _known_tables degil; internal tablolar gizlenir)."""
    db = _FakeDB(["users", "sqlite_sequence", "sqlite_stat1"])
    monkeypatch.setattr(hm, "db", db)
    assert _known_tables() == ["users"]


def test_known_tables_bos(monkeypatch):
    monkeypatch.setattr(hm, "db", _FakeDB([]))
    assert _known_tables() == []


def test_known_tables_donut_liste(katalog):
    assert isinstance(_known_tables(), list)


def test_known_tables_string_elemanlar(katalog):
    assert all(isinstance(t, str) for t in _known_tables())


def test_known_tables_sorgu_dogru(monkeypatch):
    """ORTAM: fetchall'a giden SQL tam metni."""
    db = _FakeDB(["a"])
    monkeypatch.setattr(hm, "db", db)
    _known_tables()
    assert db.calls == ["SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%'"]


def test_known_tables_stabil(katalog):
    assert _known_tables() == _known_tables()


# == _require_known_table ==============================================================================

def test_require_bilinen(katalog):
    """ORTAM: bilinen tablo -> table_name doner."""
    assert _require_known_table("users") == "users"


def test_require_bilinen_listeden(katalog):
    assert _require_known_table("mrr_provenance") == "mrr_provenance"


def test_require_bilinmeyen_hata(katalog):
    """ORTAM-OGRENDI: bilinmeyen tablo -> ValueError ('Bilinmeyen tablo:
    ...'; SQL enjeksiyon korumasi — asla sabit-kodlanmis liste DEGIL,
    canli katalog)."""
    with pytest.raises(ValueError, match="Bilinmeyen tablo"):
        _require_known_table("yok")


def test_require_hata_mesaji_bilinenler(katalog):
    """ORTAM: hata mesajinda sorted(tables) listesi."""
    with pytest.raises(ValueError) as exc:
        _require_known_table("yok")
    assert "events" in str(exc.value)
    assert "mrr_provenance" in str(exc.value)


def test_require_hata_mesaji_sorted(monkeypatch):
    """ORTAM-OGRENDI: sorted(tables) — bilinenler mesajda ALFABETIK
    (kullanici icin okunabilirlik)."""
    monkeypatch.setattr(hm, "db", _FakeDB(["zeta", "alpha", "mid"]))
    with pytest.raises(ValueError) as exc:
        _require_known_table("yok")
    assert str(exc.value).index("alpha") < str(exc.value).index("zeta")


def test_require_bos_katalog(monkeypatch):
    """ORTAM: bos katalog -> her ad RED."""
    monkeypatch.setattr(hm, "db", _FakeDB([]))
    with pytest.raises(ValueError):
        _require_known_table("users")


def test_require_sqlite_tablo_red(monkeypatch):
    """ORTAM-OGRENDI: 'sqlite_sequence' katalogda GORUNMEDIGI icin RED
    (sqlite_% filtresi — internal tabloya disaridan erisim YOK)."""
    monkeypatch.setattr(hm, "db", _FakeDB(["users"]))
    with pytest.raises(ValueError):
        _require_known_table("sqlite_sequence")


def test_require_case_sensitive(katalog):
    """ORTAM: case-sensitive — 'Users' != 'users'."""
    with pytest.raises(ValueError):
        _require_known_table("Users")
    with pytest.raises(ValueError):
        _require_known_table("USERS")


def test_require_bos_ad(katalog):
    """ORTAM: '' katalogda yok -> ValueError."""
    with pytest.raises(ValueError):
        _require_known_table("")


def test_require_none_ad(katalog):
    """ORTAM: None not in tables -> ValueError."""
    with pytest.raises(ValueError):
        _require_known_table(None)


def test_require_int_ad(katalog):
    with pytest.raises(ValueError):
        _require_known_table(42)


def test_require_katalog_sorgulanir(katalog):
    """ORTAM: her cagrida katalog CANLI okunur (sabit liste DEGIL)."""
    _require_known_table("users")
    assert len(katalog.calls) == 1
    _require_known_table("events")
    assert len(katalog.calls) == 2


def test_require_donut_str(katalog):
    assert isinstance(_require_known_table("users"), str)


def test_require_stabil(katalog):
    assert _require_known_table("users") == _require_known_table("users")


# == karakterizasyon ===================================================================================

def test_known_tables_amaci():
    r"""ORTAM-OGRENDI (DOCSTACK): sqlite_master katalogundan GUNCEL tablo
    listesi (canli sorgu; asla sabit kodlanmaz — AT-HONEST-001 dürüst-
    metrik sözleşmesi: butun sayilar GERCEK SQL COGULLARINDAN gelir);
    sqlite_% internal tablolari HARIC (sorgu-filtesi)."""
    assert "sqlite_%" in "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"


def test_require_amaci():
    """ORTAM-OGRENDI (DOCSTACK): tablo adini kataloga karsi dogrular —
    bilinmeyen ad kabul EDILMEZ (SQL enjeksiyon korumasi: beyaz-liste
    katalogdan canli okunur, sabit DEGIL); hata mesaji sorted listesi
    ile (operator icin hangi tablolar var); Dürüst-Metrik sözleşmesi
    uyarica butun sorgular bilinen tablolardadir."""
    with pytest.raises(ValueError, match="Bilinmeyen tablo"):
        _require_known_table("yok")
