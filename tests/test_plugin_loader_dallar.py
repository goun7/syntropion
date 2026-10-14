"""test_plugin_loader_dallar.py — syntropion_core/plugin_loader.py dal-kesen testleri

Dinamik micro-SaaS plugin-motoru: AST-doğrulama + exec + APIRouter çıkarma,
FastAPI'ye hot-mount, venture-ID ile-mount, doğrudan-yürütme ( kota-sayımı).

TÜM DALLAR:
  load_plugin_from_code:
    1.  APIRouter döner + modül sys.modules'e-konur ( tire→alt-çizgi)
    2.  loaded_plugins'a kaydedilir
    3.  'router' yoksa → ValueError ( ama loaded_plugins'a-eklenmiş-kalır)
    4.  güvensiz-kod ( eval) → AST doğrulamasında-reddedilir
    5.  app varsa → include_router; yoksa → monte-etme-YOK
    6.  set_app sonrası mount çalışır
  mount_venture_by_id:
    7.  mutlu-yol: MOUNTED + routes_count + audit PLUGIN_HOT_MOUNTED
    8.  venture-yok → ValueError('not found in database')
    9.  sorgu hem venture_id hem code_slug ile-aranır
    10. app varsa router gerçek-route'larla monte-edilir
  execute_plugin_direct:
    11. dict-payload → processed_fields = anahtar-sayısı
    12. dict-olmayan-payload → processed_fields = 1
    13. venture-yok → ValueError
    14. yüklü-değilse → otomatik-yükleme ( generate_python_code)
    15. zaten-yüklüyse → generate_python_code ÇAĞRILMAZ
  get_loaded_plugins:
    16. başlangıçta-boş; yükleme-sonrası slug listesi
  singleton:
    17. plugin_manager örneği-hazır ( app=None)

Kural-1: SADECE-yeni-dosya. Kural-4: db fetchone/audit monkeypatch'li-stub,
gerçek-syntropion.db'ye DOKUNULMAZ ( env-yönlendirme).
"""
from __future__ import annotations

import os
import sys
import tempfile
from types import ModuleType

import pytest
from fastapi import APIRouter, FastAPI

# --- Kural-4: import-anında gerçek syntropion.db'ye DOKUNMA ------------------
# plugin_loader → database.db singleton import-anı şema yazar.
if "syntropion_core.database" not in sys.modules:
    _TMPDIR = tempfile.mkdtemp(prefix="syntropion-dallar-pl-")
    os.environ.setdefault("SYNTROPION_DB_PATH", os.path.join(_TMPDIR, "db.db"))

from syntropion_core import plugin_loader as pl
from syntropion_core.plugin_loader import DynamicPluginManager

MINI_KOD = """
from fastapi import APIRouter

router = APIRouter()

@router.get("/ping")
def ping():
    return {"ok": True}
"""

ROUTER_YOK_KOD = "x = 1\ny = 2\n"

GUVENLIKSIZ_KOD = "eval('1')\nrouter = APIRouter()\n"


def _yollar(app):
    """FastAPI ≥0.141 include_router → _IncludedRouter ( original_router içinde).

    Üretilen-route-yollarını-döndürür ( varsayılan /docs vb. hariç).
    """
    yollar = set()
    for r in app.routes:
        alt = getattr(r, "original_router", None)
        if alt is not None:
            yollar.update(x.path for x in alt.routes)
    return yollar

VENTURE = {
    "venture_id": "ven-test-001",
    "idea_id": "idea-test-001",
    "code_slug": "demo-plugin",
    "display_name": "Demo Plugin",
    "api_prefix_path": "/api/v1/plugins/demo-plugin",
    "status": "ALPHA_TEST",
}


@pytest.fixture(autouse=True)
def eklentileri_temizle():
    """Test'lerin sys.modules'e-eklediği syntropion_plugins.* modüllerini-temizler."""
    once = {k for k in sys.modules if k.startswith("syntropion_plugins.")}
    yield
    for k in list(sys.modules):
        if k.startswith("syntropion_plugins.") and k not in once:
            del sys.modules[k]


@pytest.fixture
def yonetici():
    return DynamicPluginManager()


@pytest.fixture
def stub_db(monkeypatch):
    store = {"one": None, "audits": [], "fetches": []}

    def _fetchone(query, params=()):
        store["fetches"].append((query, tuple(params)))
        return store["one"]

    def _log_audit_event(**kwargs):
        store["audits"].append(kwargs)
        return "fake-sha256"

    monkeypatch.setattr(pl.db, "fetchone", _fetchone)
    monkeypatch.setattr(pl.db, "log_audit_event", _log_audit_event)
    return store


@pytest.fixture
def mini_kod(monkeypatch):
    """generate_python_code'i sabit-mini-router dönecek-şekilde-patch'ler."""
    monkeypatch.setattr(pl.code_synthesizer, "generate_python_code",
                        lambda idea_id, slug: MINI_KOD)


# ---------------------------------------------------------------------------
# load_plugin_from_code
# ---------------------------------------------------------------------------
class TestLoadPluginFromCode:
    def test_router_doner_ve_modul_kaydedilir(self, yonetici):
        router = yonetici.load_plugin_from_code("demo-plugin", MINI_KOD)
        assert isinstance(router, APIRouter)
        assert "demo-plugin" in yonetici.loaded_plugins
        mod = yonetici.loaded_plugins["demo-plugin"]
        assert isinstance(mod, ModuleType)
        # DAL: tireler alt-çizgiye-dönüşür
        assert "syntropion_plugins.demo_plugin" in sys.modules
        assert sys.modules["syntropion_plugins.demo_plugin"] is mod

    def test_router_yoksa_value_error(self, yonetici):
        with pytest.raises(ValueError, match="does not export an APIRouter named 'router'"):
            yonetici.load_plugin_from_code("router-yok", ROUTER_YOK_KOD)
        # DAL-GÖZÜ: modül loaded_plugins'a-EKLENMİŞ-kalır ( kontrol-öncesi-kayıt)
        assert "router-yok" in yonetici.loaded_plugins

    def test_guvensiz_kod_reddedilir(self, yonetici):
        """AST doğrulaması exec-öncesi-yapılır → modül-üretilmez."""
        with pytest.raises(ValueError, match="AST Security Violations"):
            yonetici.load_plugin_from_code("kotu", GUVENLIKSIZ_KOD)
        assert "kotu" not in yonetici.loaded_plugins
        assert "syntropion_plugins.kotu" not in sys.modules

    def test_app_varsa_include_router(self):
        app = FastAPI()
        yonetici = DynamicPluginManager(app)
        yonetici.load_plugin_from_code("demo-plugin", MINI_KOD)
        # FastAPI _IncludedRouter olarak-sarlar → original_router'dan-okunur
        assert "/ping" in _yollar(app)

    def test_app_yoksa_monte_etme_yok(self, yonetici):
        assert yonetici.app is None
        router = yonetici.load_plugin_from_code("demo-plugin", MINI_KOD)
        assert isinstance(router, APIRouter)

    def test_set_app_sonrasi_mount(self, yonetici):
        app = FastAPI()
        yonetici.set_app(app)
        yonetici.load_plugin_from_code("demo-plugin", MINI_KOD)
        assert "/ping" in _yollar(app)

    def test_iki_ayni_slug_tek_modul(self, yonetici):
        yonetici.load_plugin_from_code("demo-plugin", MINI_KOD)
        yonetici.load_plugin_from_code("demo-plugin", MINI_KOD)
        assert list(yonetici.loaded_plugins) == ["demo-plugin"]
        assert len(yonetici.get_loaded_plugins()) == 1


# ---------------------------------------------------------------------------
# mount_venture_by_id
# ---------------------------------------------------------------------------
class TestMountVentureById:
    def test_mutlu_yol_ve_audit(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = dict(VENTURE)
        sonuc = yonetici.mount_venture_by_id("ven-test-001")

        assert sonuc["status"] == "MOUNTED"
        assert sonuc["venture_id"] == "ven-test-001"
        assert sonuc["code_slug"] == "demo-plugin"
        assert sonuc["api_prefix_path"] == "/api/v1/plugins/demo-plugin"
        assert sonuc["routes_count"] >= 1
        assert "demo-plugin" in yonetici.loaded_plugins

        assert len(stub_db["audits"]) == 1
        audit = stub_db["audits"][0]
        assert audit["event_type"] == "PLUGIN_HOT_MOUNTED"
        assert audit["actor"] == "DYNAMIC_PLUGIN_MANAGER"
        assert audit["payload"]["venture_id"] == "ven-test-001"
        assert audit["payload"]["code_slug"] == "demo-plugin"
        assert "timestamp" in audit["payload"]

    def test_venture_yok_value_error(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = None
        with pytest.raises(ValueError, match="Venture 'yok-999' not found in database"):
            yonetici.mount_venture_by_id("yok-999")

    def test_sorgu_id_ve_slug_ile_aranir(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = dict(VENTURE)
        yonetici.mount_venture_by_id("demo-plugin")  # slug ile-ara
        sorgu, param = stub_db["fetches"][-1]
        assert "venture_id = ?" in sorgu
        assert "code_slug = ?" in sorgu
        assert param == ("demo-plugin", "demo-plugin")

    def test_app_ile_gercek_route_monte_edilir(self, stub_db, mini_kod):
        """Gerçek generate_python_code çıktısı prefix'yle birlikte-monte olur."""
        app = FastAPI()
        yonetici = DynamicPluginManager(app)
        gercek_venture = dict(VENTURE, code_slug="radtrack-ai",
                              api_prefix_path="/api/v1/plugins/radtrack-ai")
        stub_db["one"] = gercek_venture
        # mini_kod örneği-patch'ledi; sınıf-metoduna-bağlan ( örnek-niteliği-olarak
        # atanan-fonksiyon self-ALMAZ → 2-parametreli-olmalı)
        sinif_metodu = type(pl.code_synthesizer).generate_python_code
        pl.code_synthesizer.generate_python_code = (
            lambda idea_id, slug: sinif_metodu(pl.code_synthesizer, idea_id, slug)
        )
        try:
            sonuc = yonetici.mount_venture_by_id("radtrack-ai")
            assert sonuc["status"] == "MOUNTED"
            assert "/api/v1/plugins/radtrack-ai/process" in _yollar(app)
        finally:
            del pl.code_synthesizer.generate_python_code

    def test_yuklu_plugin_tekrar_monte_edilir(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = dict(VENTURE)
        yonetici.mount_venture_by_id("ven-test-001")
        sonuc = yonetici.mount_venture_by_id("ven-test-001")
        assert sonuc["status"] == "MOUNTED"
        assert len(stub_db["audits"]) == 2


# ---------------------------------------------------------------------------
# execute_plugin_direct
# ---------------------------------------------------------------------------
class TestExecutePluginDirect:
    def test_dict_payload_alan_sayisi(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = dict(VENTURE)
        sonuc = yonetici.execute_plugin_direct("demo-plugin", {"a": 1, "b": 2, "c": 3})

        assert sonuc["status"] == "COMPLETED"
        assert sonuc["venture_slug"] == "demo-plugin"
        assert sonuc["venture_id"] == "ven-test-001"
        assert sonuc["venture_name"] == "Demo Plugin"
        assert sonuc["processed_payload"] == {"a": 1, "b": 2, "c": 3}
        assert sonuc["processed_fields"] == 3
        assert sonuc["tenant_execution"] == "OK"
        assert sonuc["timestamp"] is not None

    @pytest.mark.parametrize("payload, beklenen", [
        ("düz-metin", 1),
        (42, 1),
        ([1, 2, 3], 1),
        ({}, 0),
    ])
    def test_dict_degilse_bir_alan(self, yonetici, stub_db, mini_kod, payload, beklenen):
        stub_db["one"] = dict(VENTURE)
        sonuc = yonetici.execute_plugin_direct("demo-plugin", payload)
        assert sonuc["processed_fields"] == beklenen

    def test_venture_yok_value_error(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = None
        with pytest.raises(ValueError, match="Venture slug 'yok' not found in database"):
            yonetici.execute_plugin_direct("yok", {"a": 1})

    def test_yuklu_degilse_otomatik_yuklenir(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = dict(VENTURE)
        assert "demo-plugin" not in yonetici.loaded_plugins
        yonetici.execute_plugin_direct("demo-plugin", {"x": 1})
        assert "demo-plugin" in yonetici.loaded_plugins

    def test_zaten_yuklu_ise_generate_cagrilmaz(self, yonetici, stub_db, monkeypatch):
        """Yüklü-plugin için generate_python_code tekrar-çağrılmaz."""
        stub_db["one"] = dict(VENTURE)
        yonetici.loaded_plugins["demo-plugin"] = ModuleType("syntropion_plugins.demo_plugin")

        def _patlat(self, idea_id, slug):
            raise AssertionError("generate_python_code çağrılmamalıydı")

        monkeypatch.setattr(pl.code_synthesizer, "generate_python_code", _patlat)
        sonuc = yonetici.execute_plugin_direct("demo-plugin", {"x": 1})
        assert sonuc["status"] == "COMPLETED"

    def test_sorgu_slug_ve_id_ile_aranir(self, yonetici, stub_db, mini_kod):
        stub_db["one"] = dict(VENTURE)
        yonetici.execute_plugin_direct("ven-test-001", {"x": 1})
        sorgu, param = stub_db["fetches"][-1]
        assert "code_slug = ? OR venture_id = ?" in sorgu
        assert param == ("ven-test-001", "ven-test-001")


# ---------------------------------------------------------------------------
# get_loaded_plugins
# ---------------------------------------------------------------------------
class TestGetLoadedPlugins:
    def test_baslangicta_bos(self, yonetici):
        assert yonetici.get_loaded_plugins() == []

    def test_yukleme_sonrasi_liste(self, yonetici):
        yonetici.load_plugin_from_code("plugin-a", MINI_KOD)
        yonetici.load_plugin_from_code("plugin-b", MINI_KOD)
        assert sorted(yonetici.get_loaded_plugins()) == ["plugin-a", "plugin-b"]

    def test_liste_kopyasi_donuyor(self, yonetici):
        yonetici.load_plugin_from_code("plugin-a", MINI_KOD)
        donen = yonetici.get_loaded_plugins()
        donen.append("sahte")
        assert "sahte" not in yonetici.get_loaded_plugins()


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_plugin_manager_hazir(self):
        assert isinstance(pl.plugin_manager, DynamicPluginManager)
        # DAL-GÖZÜ: tam-suite'te önceki-testler singleton'app'ini-ayarlamış-olabilir
        # ( sıra-bağımlı-None/boş-varsayımı-YANLIŞ) → türlerini-doğrula
        assert pl.plugin_manager.app is None or isinstance(
            pl.plugin_manager.app, FastAPI
        )
        assert isinstance(pl.plugin_manager.loaded_plugins, dict)
        for mod in pl.plugin_manager.loaded_plugins.values():
            assert isinstance(mod, ModuleType)

    def test_logger_tanimli(self):
        assert pl.logger.name == "syntropion.plugin_loader"
