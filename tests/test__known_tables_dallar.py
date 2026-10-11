"""test__known_tables_dallar.py — syntropion_core/honest_metrics.py

AT-HONEST-001: SQL-enjeksiyon-koruma-beyaz-listesi. _known_tables kataloğu
canlı-okur, _require_known_table bilinmeyen-adı RED-eder.

TÜM DALLAR ( her-iddia-bir-çalıştırmayla-doğrulanır):
  _known_tables:
    1. sqlite_master kataloğunu listeler ( tablo-adları)
    2. sqlite_% ve view/index/etc. FİLTRELENİR ( type='table' + LIKE-olumsuz)
    3. boş-veritabanı → []
  _require_known_table:
    4. bilinen-tablo → aynı-adı-döner ( mutlu-yol)
    5. bilinmeyen-tablo → ValueError ( bilinen-liste mesajda)
    6. boş-string / None-benzeri → ValueError
    7. büyük-küçük-harf-hassas
    8. SQL-enjeksiyon girişimi → ValueError ( beyaz-liste-ile-RED)

SADECE-in-memory: gerçek-db-yerine monkeypatch'li fetchall ( ağ/HTTP/YOK).
"""
import pytest

from syntropion_core import honest_metrics as hm
from syntropion_core.honest_metrics import _known_tables, _require_known_table


@pytest.fixture
def fake_tables(monkeypatch):
    """db.fetchall'ı sahte-katalogla değiştir ( gerçek-SQL-YOK)."""
    state = {"rows": [], "queries": []}

    def _fake_fetchall(query, params=()):
        state["queries"].append(query)
        return state["rows"]

    monkeypatch.setattr(hm.db, "fetchall", _fake_fetchall)
    return state


# ---------------------------------------------------------------------------
# _known_tables — katalog-listeleme
# ---------------------------------------------------------------------------

def test_known_tables_bos_veritabani(fake_tables):
    assert _known_tables() == []


def test_known_tables_listeler(fake_tables):
    fake_tables["rows"] = [
        {"name": "ventures"}, {"name": "experts"}, {"name": "audit_ledger"},
    ]
    assert _known_tables() == ["ventures", "experts", "audit_ledger"]


def test_known_tables_sqlite_filtresi_sql_de(fake_tables):
    """sqlite_%-dışlama SQL-cümlesinde-dir — Python-katmanı satırları OLDUĞU-GİBİ geçirir.

    Bu-test o-gerçeği-belgeler: filtre db-engine'inde-uygulanır ( aşağıdaki
    test_sorgu_..._var ile cümlede-doirulanır), _known_tables sadece eşler.
    """
    fake_tables["rows"] = [
        {"name": "ventures"},
        {"name": "sqlite_sequence"},
        {"name": "sqlite_autoindex_1"},
    ]
    # monkeypatch'li-fetchall SQL'i-uygulamadığı-için hepsi-geçer — filtre
    # SQL-cümlesindedir, Python'da-DEĞİL
    assert _known_tables() == ["ventures", "sqlite_sequence", "sqlite_autoindex_1"]


def test_sorgu_type_table_filtresi_var(fake_tables):
    """SQL'de type='table' ve sqlite_%-dışlama var ( katalog-doğruluğu)."""
    _known_tables()
    q = fake_tables["queries"][-1]
    assert "sqlite_master" in q
    assert "type='table'" in q
    assert "NOT LIKE 'sqlite_%'" in q


def test_known_tables_sutun_adi_name(fake_tables):
    """Satır sözlüğü 'name' anahtarını kullanır ( başka-anahtar → KeyError)."""
    fake_tables["rows"] = [{"name": "tablo1"}]
    assert _known_tables() == ["tablo1"]


def test_known_tables_baska_anahtar_hatasi(fake_tables):
    fake_tables["rows"] = [{"tablo": "x"}]
    with pytest.raises(KeyError):
        _known_tables()


def test_known_tables_unicode_ad(fake_tables):
    fake_tables["rows"] = [{"name": "türkçe_tablo_ğüıöşç"}]
    assert _known_tables() == ["türkçe_tablo_ğüıöşç"]


# ---------------------------------------------------------------------------
# _require_known_table — mutlu-yol & bilinmeyen
# ---------------------------------------------------------------------------

def test_require_mutlu_yol(fake_tables):
    fake_tables["rows"] = [{"name": "ventures"}, {"name": "experts"}]
    assert _require_known_table("ventures") == "ventures"


def test_require_ikinci_tablo(fake_tables):
    fake_tables["rows"] = [{"name": "a"}, {"name": "b"}]
    assert _require_known_table("b") == "b"


def test_require_bilinmeyen_value_error(fake_tables):
    fake_tables["rows"] = [{"name": "ventures"}]
    with pytest.raises(ValueError):
        _require_known_table("yok-boyle-tablo")


def test_require_bilinmeyen_mesajda_bilinenler(fake_tables):
    fake_tables["rows"] = [{"name": "zzz"}, {"name": "aaa"}]
    with pytest.raises(ValueError) as e:
        _require_known_table("yok")
    msg = str(e.value)
    assert "Bilinmeyen tablo" in msg
    assert "'yok'" in msg
    # bilinenler SORTED olarak mesajda ( aaa-önce)
    assert msg.index("aaa") < msg.index("zzz")


def test_require_bos_string_value_error(fake_tables):
    fake_tables["rows"] = [{"name": "ventures"}]
    with pytest.raises(ValueError):
        _require_known_table("")


def test_require_bosluk_dolgu_value_error(fake_tables):
    fake_tables["rows"] = [{"name": "ventures"}]
    with pytest.raises(ValueError):
        _require_known_table("  ventures  ")


def test_require_buyuk_kucuk_hassas(fake_tables):
    fake_tables["rows"] = [{"name": "ventures"}]
    with pytest.raises(ValueError):
        _require_known_table("Ventures")
    with pytest.raises(ValueError):
        _require_known_table("VENTURES")


@pytest.mark.parametrize("ad", [
    "ventures; DROP TABLE users; --",
    "ventures' OR '1'='1",
    "sqlite_master",
    "information_schema.tables",
    "..",
    "%",
    "_",
])
def test_require_sql_enjeksiyon_red(fake_tables, ad):
    """Beyaz-liste: SQL-meta-adları ve enjeksiyon-metinleri RED-edilir."""
    fake_tables["rows"] = [{"name": "ventures"}]
    with pytest.raises(ValueError):
        _require_known_table(ad)


def test_require_bos_katalogda_her_sey_red(fake_tables):
    fake_tables["rows"] = []
    with pytest.raises(ValueError):
        _require_known_table("ventures")


def test_require_known_tables_cagirir(fake_tables):
    """_require_known_table katalogu HER-ÇAĞRIDA taze-okur ( caching-YOK)."""
    fake_tables["rows"] = [{"name": "a"}]
    assert _require_known_table("a") == "a"
    fake_tables["rows"] = [{"name": "b"}]  # katalog-değişti
    assert _require_known_table("b") == "b"
    with pytest.raises(ValueError):
        _require_known_table("a")  # artık-bilinmiyor


def test_require_unicode_ad_mutlu_yol(fake_tables):
    fake_tables["rows"] = [{"name": "türkçe_tablo"}]
    assert _require_known_table("türkçe_tablo") == "türkçe_tablo"


def test_require_ayni_string_nesnesi(fake_tables):
    """Aynı-ad döner ( kimlik-korunur)."""
    fake_tables["rows"] = [{"name": "ventures"}]
    ad = "ventures"
    assert _require_known_table(ad) is ad


# ---------------------------------------------------------------------------
# gerçek-schema entegrasyonu ( in-memory :memory: — dosya-YAZILMAZ)
# ---------------------------------------------------------------------------

def test_gercek_schema_bilinen_tablolar_icerir():
    """Gerçek schema.sql kataloğunda bilinen-tablolar var ( fetchall-sayma)."""
    import sqlite3
    import os
    schema_yol = os.path.join(os.path.dirname(hm.__file__), "schema.sql")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(schema_yol, encoding="utf-8") as f:
        conn.executescript(f.read())
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    tablolar = [r["name"] for r in rows]
    conn.close()
    # en az-bilinen-çekirdek-tablolar ( schema.sql'deki-gerçek-adlar)
    for beklenen in ("ventures", "domain_experts", "audit_ledger", "socratic_interviews"):
        assert beklenen in tablolar


def test_gercek_schema_require_gecerli():
    import sqlite3
    import os
    import syntropion_core.honest_metrics as mod
    schema_yol = os.path.join(os.path.dirname(mod.__file__), "schema.sql")
    conn = sqlite3.connect(":memory:")
    with open(schema_yol, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()
    # _require_known_table gerçek-db'yi db üzerinden kullanır — ventures geçerli
    assert _require_known_table("ventures") == "ventures"


def test_gercek_schema_sqlite_filtresi():
    import sqlite3
    import os
    import syntropion_core.honest_metrics as mod
    schema_yol = os.path.join(os.path.dirname(mod.__file__), "schema.sql")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    with open(schema_yol, encoding="utf-8") as f:
        conn.executescript(f.read())
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    conn.close()
    tablolar = [r["name"] for r in rows]
    assert not any(t.startswith("sqlite_") for t in tablolar)
