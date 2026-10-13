"""test_code_synthesizer_dallar.py — syntropion_core/code_synthesizer.py dal-kesen testleri

Spec-driven kod-sentez motoru + AST güvenlik-doğrulayıcı + 5 Dikey Pilot
yürütme motorunun TÜM dalları ( her-iddia-bir-çalıştırmayla-doğrulanır).

TÜM DALLAR:
  validate_python_code_ast / ASTSecurityValidator:
    1.  geçerli-kod → True
    2.  sözdizimi-hatası → SyntaxError ( ast.parse)
    3.  eval()/exec()/__import__() → ValueError ( 'Forbidden call: <ad>()')
    4.  os.system()/os.popen() → ValueError ( 'os.system/os.popen()')
    5.  başka-nesne.system() → RED-ALINMAZ ( yalnızca os.id=='os' dalı)
    6.  birden-çok ihlal birikir ( virgülle-birleşmiş mesaj)
    7.  iç-içe çağrılar generic_visit ile dolaşılır
    8.  boş-kod → True ( sınır)
    9.  FORBIDDEN_AST_NODES 'compile'/'subprocess.*' için DENETLENMEZ
        ( advisory-set gözü — sabit-kümede-ama-visit_Call'da-yok)
  CodeSynthesizer.generate_plugin_spec:
    10. mutlu-yol → openapi 3.1.0 + title + paths + operationId
    11. slug-normalizasyonu ( [^a-z0-9]+ → '-', strip, [:32])
    12. problem_statement[:100] kırpma + '...'
    13. idea-yok → ValueError('Idea not found')
    14. sorgu+parametreler ( idea_id,) ile gelir
  CodeSynthesizer.generate_python_code:
    15. geçerli FastAPI router üretir + ast.parse-geçerli
    16. prefix tireleri korur ( clean_name = replace('-','_') ATILDIR — dal-gözü)
  CodeSynthesizer.generate_test_suite:
    17. test-fonksiyon adı tire→alt-çizgi + pytest importu
  CodeSynthesizer.synthesize_venture:
    18. mutlu-yol: venture_id/slug/openapi/kod/test-suite/ast=True
    19. custom_slug kullanılır
    20. durum != APPROVED_FOR_SYNTHESIS → ValueError
    21. idea-yok → ValueError
    22. 2 execute ( INSERT ventures + UPDATE ideas SYNTHESIZED) + audit-event
    23. sabit 4250.00 MRR + ALPHA_TEST literalde
  VerticalPilotEngines.execute_radtrack_recist ( RECIST 1.1):
    24. baseline <= 0 → ValueError
    25. follow_up==0 → CR;  pct <= -30 → PR;  pct>=20 AND diff>=5 → PD;  else SD
    26. eşik-değerleri ( -30.0 tam, +20.0+5.0 tam PD-sınırı)
    27. fark/yüzde 2-basamak yuvarlanır
  VerticalPilotEngines.execute_lexnotice_ttb ( TTK 6102):
    28. 1 gün → LOW;  3 gün → MEDIUM ( açık-ayıp);  9 gün → HIGH ( gizli-ayıp)
    29. zamanaşımı > 730 gün ( 730→False, 731→True)
    30. faiz = amount * 0.48/365 * gün ( negatif-gün → 0)
    31. geçersiz-ISO-tarih → ValueError
    32. ihtarname-metni TTK-maddesini + tutarı içerir
  VerticalPilotEngines.execute_taxcross_reconciliation:
    33. diff < 1 → mutabık ( 0.99 True, 1.00 False)
    34. ceza = diff * kdv/100 * 1.5 + VUK 344 flag
    35. abs() negatif-toplamlar için
  VerticalPilotEngines.execute_tarifa_customs_gtip:
    36. polimer/plastik/reçine → 3901…;  çelik/sac/boru → 7208…;  ilaç → 3004…;
        else → 8471…
    37. tercihli-menşe ( DE/FR/IT/TR/EU/ALMANYA) → effective 0
  VerticalPilotEngines.execute_demurrage_calculation:
    38. serbest-süre-içinde → 0 ceza + dispute_ready True
    39. dwell > free → billable * rate;  negatif-dwell → max(0,…) ile 0
    40. geçersiz-ISO-tarih → ValueError
  Modül-tekil-nesneler:
    41. code_synthesizer / pilot_engines singleton'ları + FORBIDDEN_AST_NODES

Kural-1: SADECE-yeni-dosya. Kural-4: saf-in-memory — db çağrıları
monkeypatch'li-stub, /dev/shm ve syntropion.db'ye DOKUNULMAZ ( env-yönlendirme).
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile

import pytest

# --- Kural-4: import-anında gerçek syntropion.db'ye DOKUNMA -------------------
# code_synthesizer → database importu module-level `db = DatabaseManager()`
# üretir ( WAL+şema yazar → git M=1). Henüz-import-edilmemişse ( yalnız-bu-dosya
# koşusu) SYNTROPION_DB_PATH'i /tmp'ye yönlendir; zaten-import-edilmişse
# ( tam-suite) sys.modules'de olduğu için HİÇBİRŞEYE DOKUNMA.
if "syntropion_core.database" not in sys.modules:
    _TMPDIR = tempfile.mkdtemp(prefix="syntropion-dallar-cs-")
    os.environ.setdefault("SYNTROPION_DB_PATH", os.path.join(_TMPDIR, "db.db"))

from syntropion_core import code_synthesizer as cs
from syntropion_core.code_synthesizer import (
    ASTSecurityValidator,
    CodeSynthesizer,
    VerticalPilotEngines,
    validate_python_code_ast,
)

IDEA = {
    "idea_id": "idea-test-001",
    "title": "AI Legal Assistant",
    "problem_statement": "Hukuk büroları sözleşme risklerini elle takip ediyor." * 3,
    "status": "APPROVED_FOR_SYNTHESIS",
}


# ---------------------------------------------------------------------------
# Fixtures — in-memory db stub'ları ( Kural-4: gerçek-SQL YOK)
# ---------------------------------------------------------------------------
@pytest.fixture
def stub_db(monkeypatch):
    """code_synthesizer'in db bağımlılıklarını sahte-stub'la değiştirir."""
    store = {"one": None, "execs": [], "audits": [], "fetches": []}

    def _fetchone(query, params=()):
        store["fetches"].append((query, tuple(params)))
        return store["one"]

    def _execute(query, params=()):
        store["execs"].append((query, tuple(params)))
        return 1

    def _log_audit_event(**kwargs):
        store["audits"].append(kwargs)
        return "fake-sha256-for-test"

    monkeypatch.setattr(cs.db, "fetchone", _fetchone)
    monkeypatch.setattr(cs.db, "execute", _execute)
    monkeypatch.setattr(cs.db, "log_audit_event", _log_audit_event)
    return store


@pytest.fixture
def deterministic(monkeypatch):
    """uuid'yi ve zamanı deterministik yapar ( synthesize_venture için)."""
    monkeypatch.setattr(cs, "get_current_iso_time", lambda: "2026-01-01T00:00:00+00:00")

    class _FakeUUID:
        hex = "abcdef0123456789abcdef0123456789"

    monkeypatch.setattr(cs.uuid, "uuid4", lambda: _FakeUUID())


# ---------------------------------------------------------------------------
# validate_python_code_ast / ASTSecurityValidator
# ---------------------------------------------------------------------------
class TestValidatePythonCodeAst:
    """AST güvenlik-doğrulayıcı — başarı/başarısızlık/sınır dalları."""

    def test_gecerli_kod_true(self):
        assert validate_python_code_ast("x = 1\ny = x + 2\nprint(y)\n") is True

    def test_bos_kod_true(self):
        """Sınır: boş-kod parse-edilir ve ihlalsızdır."""
        assert validate_python_code_ast("") is True

    def test_sozdizimi_hatasi_syntax_error(self):
        with pytest.raises(SyntaxError):
            validate_python_code_ast("def (:\n  pass\n")

    @pytest.mark.parametrize("name", ["eval", "exec", "__import__"])
    def test_yasakli_cagri_value_error(self, name):
        with pytest.raises(ValueError, match="AST Security Violations"):
            validate_python_code_ast(f"{name}('test')")

    @pytest.mark.parametrize("yasakli", ["os.system('rm -rf /')", "os.popen('ls')"])
    def test_os_system_popen_value_error(self, yasakli):
        with pytest.raises(ValueError, match="os.system/os.popen"):
            validate_python_code_ast(yasakli)

    def test_baska_nesne_system_red_alinmaz(self):
        """Dal: yalnızca func.value.id == 'os' ise RED-edilir."""
        code = "class T:\n    def system(self, x):\n        return x\n\n"
        code += "T().system('neden-siz')\n"
        assert validate_python_code_ast(code) is True

    def test_ihlaller_birikir(self):
        with pytest.raises(ValueError) as exc_info:
            validate_python_code_ast("import os\neval('1')\nos.system('x')\n")
        mesaj = str(exc_info.value)
        assert "Forbidden call: eval()" in mesaj
        assert "os.system/os.popen()" in mesaj

    def test_ice_ice_cagrilar_dolasilir(self):
        """generic_visit iç-içe çağrıları da yakalar ( fonksiyon-gövdesi)."""
        with pytest.raises(ValueError, match="Forbidden call: exec"):
            validate_python_code_ast("def f():\n    return exec('1')\n")

    def test_guvenli_cagrilar_serbest(self):
        code = "def foo(x):\n    return len([i for i in range(x)])\n\nfoo(bar(1))\n"
        assert validate_python_code_ast(code) is True

    @pytest.mark.parametrize(
        "kod, aciklama",
        [
            ("compile('1', '<s>', 'exec')", "compile"),
            ("import subprocess\nsubprocess.run(['ls'])\n", "subprocess.run"),
            ("import subprocess\nsubprocess.Popen(['ls'])\n", "subprocess.Popen"),
        ],
    )
    def test_engellenmeyen_advisor_set_gozu(self, kod, aciklama):
        """DAL-GÖZÜ: FORBIDDEN_AST_NODES kümesinde-ama-visit_Call'da-denetlenmez.

        Sabit-küme {'compile','subprocess.Popen','subprocess.run',...} advisory
        ( danışma) amaçlıdır; ASTSecurityValidator.visit_Call yalnızca
        eval/exec/__import__ ve os.system/os.popen yakalar. Bu-test o-gerçeği
        belgeler ( davranış-değişikliği-DEĞİL).
        """
        assert aciklama in cs.FORBIDDEN_AST_NODES
        assert validate_python_code_ast(kod) is True

    def test_validator_dogrudan_kullanim(self):
        """ASTSecurityValidator tekil-başına: ihlal listesini biriktirir."""
        validator = ASTSecurityValidator()
        validator.visit(ast.parse("eval('x')\n"))
        assert validator.violations == ["Forbidden call: eval()"]

    def test_validator_temiz_kod_ihlalsiz(self):
        validator = ASTSecurityValidator()
        validator.visit(ast.parse("print(1)\nx = 2\n"))
        assert validator.violations == []


# ---------------------------------------------------------------------------
# CodeSynthesizer.generate_plugin_spec
# ---------------------------------------------------------------------------
class TestGeneratePluginSpec:
    def test_mutlu_yol(self, stub_db):
        stub_db["one"] = dict(IDEA)
        spec = CodeSynthesizer().generate_plugin_spec("idea-test-001")

        assert spec["openapi"] == "3.1.0"
        assert spec["info"]["title"] == "AI Legal Assistant Plugin API"
        assert spec["info"]["version"] == "1.0.0"
        assert spec["info"]["description"].startswith(
            "Autonomous micro-SaaS plugin derived from domain proposal: "
        )
        yol = "/api/v1/plugins/ai-legal-assistant/process"
        assert yol in spec["paths"]
        assert spec["paths"][yol]["post"]["operationId"] == "process_ai_legal_assistant"
        assert spec["paths"][yol]["post"]["summary"] == "Execute domain automation algorithm"
        assert "200" in spec["paths"][yol]["post"]["responses"]

    @pytest.mark.parametrize(
        "baslik, beklenen_slug",
        [
            ("AI Legal Assistant", "ai-legal-assistant"),
            ("abc123", "abc123"),
            ("---Başlık---", "ba-l-k"),
        ],
    )
    def test_slug_normalizasyonu(self, stub_db, baslik, beklenen_slug):
        stub_db["one"] = dict(IDEA, title=baslik)
        spec = CodeSynthesizer().generate_plugin_spec("idea-test-001")
        yol = list(spec["paths"].keys())[0]
        assert yol == f"/api/v1/plugins/{beklenen_slug}/process"

    def test_slug_turkce_karakterleri_atar(self, stub_db):
        """DAL-GÖZÜ: [^a-z0-9] regex'i Türkçe-harfleri de-ayırır.

        ' Başlık' → 'ş','ı' dahil tüm UTF-8 harfler [a-z0-9] dışındadır;
        her-biri '-' olur: 'başlık' → 'ba-l-k'. lower() Türkçe'yi-eksik-
        dönüştürür ( 'İ'.lower() → 'i̇' U+0307), bu-yüzden 'Çift' → '-ift'.
        """
        stub_db["one"] = dict(IDEA, title="  !!!Çift++Boşluk---Başlık  ")
        spec = CodeSynthesizer().generate_plugin_spec("i")
        slug = list(spec["paths"].keys())[0].split("/")[-2]
        assert slug == "ift-bo-luk-ba-l-k"

    def test_slug_32_karakten_kirpilir(self, stub_db):
        stub_db["one"] = dict(IDEA, title="k" * 50)
        spec = CodeSynthesizer().generate_plugin_spec("i")
        slug = list(spec["paths"].keys())[0].split("/")[-2]
        assert len(slug) == 32
        assert slug == "k" * 32

    def test_problem_statement_100_kirpilir(self, stub_db):
        problem = "p" * 200
        stub_db["one"] = dict(IDEA, problem_statement=problem)
        aciklama = CodeSynthesizer().generate_plugin_spec("i")["info"]["description"]
        # tam-100 karakter + '...' ( 101+ olsaydı kırpılmamış-demek)
        assert aciklama.endswith("p" * 100 + "...")
        assert aciklama.count("p" * 101) == 0

    def test_idea_yok_value_error(self, stub_db):
        stub_db["one"] = None
        with pytest.raises(ValueError, match="Idea not found: idea-yok-999"):
            CodeSynthesizer().generate_plugin_spec("idea-yok-999")

    def test_sorgu_ve_parametreler(self, stub_db):
        stub_db["one"] = dict(IDEA)
        CodeSynthesizer().generate_plugin_spec("idea-test-001")
        sorgu, param = stub_db["fetches"][-1]
        assert "domain_ideas" in sorgu
        assert "idea_id = ?" in sorgu
        assert param == ("idea-test-001",)


# ---------------------------------------------------------------------------
# CodeSynthesizer.generate_python_code
# ---------------------------------------------------------------------------
class TestGeneratePythonCode:
    def test_gecerli_router_uretilir(self):
        kod = CodeSynthesizer().generate_python_code("i", "ai-legal")
        assert 'router = APIRouter(prefix="/api/v1/plugins/ai-legal"' in kod
        assert 'tags=["ai-legal"]' in kod
        assert "class PluginRequest(BaseModel):" in kod
        assert "class PluginResponse(BaseModel):" in kod
        assert 'engine="ai-legal"' in kod
        assert "@router.post(\"/process\", response_model=PluginResponse)" in kod
        assert "from fastapi import APIRouter, HTTPException" in kod
        # Üretilen-kod geçerli-Python ( derle — çalıştırma)
        ast.parse(kod)
        compile(kod, "<uretilen>", "exec")

    def test_ast_dogrulamadan_gecer(self):
        kod = CodeSynthesizer().generate_python_code("i", "demo")
        assert validate_python_code_ast(kod) is True

    def test_prefix_tireleri_korur_clean_name_atildir(self):
        """DAL-GÖZÜ: clean_name = slug.replace('-','_') HİÇ-KULLANILMAZ.

        generate_python_code'in içinde-türetilip f-string'lerde yer-almaz;
        prefix/tagName/engine olduğu-gibi slug'i ( tireli) kullanır.
        """
        kod = CodeSynthesizer().generate_python_code("i", "demo-plugin-x")
        assert 'prefix="/api/v1/plugins/demo-plugin-x"' in kod
        assert 'engine="demo-plugin-x"' in kod


# ---------------------------------------------------------------------------
# CodeSynthesizer.generate_test_suite
# ---------------------------------------------------------------------------
class TestGenerateTestSuite:
    def test_test_suite_icerigi(self):
        kod = CodeSynthesizer().generate_test_suite("demo-plugin")
        assert '"""Unit tests for synthesized demo-plugin plugin."""' in kod
        assert "import pytest" in kod
        assert "from syntropion_core.code_synthesizer import CodeSynthesizer" in kod
        assert "def test_demo_plugin_processing():" in kod
        ast.parse(kod)

    def test_tire_alt_cizgi_donusumu(self):
        kod = CodeSynthesizer().generate_test_suite("a-b-c")
        assert "def test_a_b_c_processing():" in kod


# ---------------------------------------------------------------------------
# CodeSynthesizer.synthesize_venture
# ---------------------------------------------------------------------------
class TestSynthesizeVenture:
    def test_mutlu_yol(self, stub_db, deterministic):
        stub_db["one"] = dict(IDEA)
        sonuc = CodeSynthesizer().synthesize_venture("idea-test-001")

        assert sonuc["venture_id"] == "ven-abcdef0123"
        assert sonuc["code_slug"] == "ai-legal-assistant-abcdef"
        assert sonuc["idea_id"] == "idea-test-001"
        assert sonuc["api_prefix_path"] == "/api/v1/plugins/ai-legal-assistant-abcdef"
        assert sonuc["ast_validation_passed"] is True
        assert sonuc["openapi_spec"]["openapi"] == "3.1.0"
        assert 'router = APIRouter(' in sonuc["fastapi_router_code"]
        assert "def test_" in sonuc["test_suite_code"]

    def test_custom_slug_kullanilir(self, stub_db, deterministic):
        stub_db["one"] = dict(IDEA)
        sonuc = CodeSynthesizer().synthesize_venture("i", custom_slug="ozel-slug")
        assert sonuc["code_slug"].startswith("ozel-slug-")
        assert sonuc["api_prefix_path"].startswith("/api/v1/plugins/ozel-slug-")

    def test_custom_slug_kirpilma_yoktur(self, stub_db, deterministic):
        """DAL-GÖZÜ: custom_slug [:24] KIRPILMASINDAN-geçer — olduğu-gibi-kullanılır.

        `custom_slug or re.sub(...)[:24]` — Python önceliği nedeniyle [:24]
        yalnızca re.sub() sonucuna uygulanır; custom_slug verildiğinde uzunluk
        SINIRSIZDır. Ototematik ( title-türetimli) yol 24 ile sınırlıdır.
        """
        stub_db["one"] = dict(IDEA)
        sonuc = CodeSynthesizer().synthesize_venture("i", custom_slug="z" * 30)
        assert sonuc["code_slug"] == "z" * 30 + "-abcdef"
        assert len(sonuc["code_slug"]) == 37

    def test_title_turevimli_slug_24_karakterle_sinirlidir(self, stub_db, deterministic):
        """Otomatik yol: re.sub(...).strip('-')[:24] → en-fazla 24 karakter."""
        stub_db["one"] = dict(IDEA, title="k" * 40)
        sonuc = CodeSynthesizer().synthesize_venture("i")
        assert sonuc["code_slug"] == "k" * 24 + "-abcdef"

    def test_durum_onayli_degil_value_error(self, stub_db):
        stub_db["one"] = dict(IDEA, status="DRAFT")
        with pytest.raises(ValueError, match="not approved for synthesis"):
            CodeSynthesizer().synthesize_venture("i")
        with pytest.raises(ValueError) as exc_info:
            CodeSynthesizer().synthesize_venture("i")
        assert "Current status: DRAFT" in str(exc_info.value)

    def test_idea_yok_value_error(self, stub_db):
        stub_db["one"] = None
        with pytest.raises(ValueError, match="Idea not found"):
            CodeSynthesizer().synthesize_venture("i")

    def test_iki_execute_ve_audit_event(self, stub_db, deterministic):
        stub_db["one"] = dict(IDEA)
        CodeSynthesizer().synthesize_venture("idea-test-001")

        assert len(stub_db["execs"]) == 2
        insert_sorgu = stub_db["execs"][0][0]
        update_sorgu = stub_db["execs"][1][0]
        assert "INSERT INTO ventures" in insert_sorgu
        assert "'ALPHA_TEST'" in insert_sorgu
        assert "4250.00" in insert_sorgu
        assert "UPDATE domain_ideas" in update_sorgu
        assert "SYNTHESIZED" in update_sorgu

        assert len(stub_db["audits"]) == 1
        audit = stub_db["audits"][0]
        assert audit["event_type"] == "VENTURE_SYNTHESIZED"
        assert audit["actor"] == "SYSTEM_SYNTHESIZER"
        assert audit["payload"]["idea_id"] == "idea-test-001"
        assert "slug" in audit["payload"]
        assert "venture_id" in audit["payload"]

    def test_insert_parametreleri(self, stub_db, deterministic):
        stub_db["one"] = dict(IDEA)
        CodeSynthesizer().synthesize_venture("idea-test-001")
        parametre = stub_db["execs"][0][1]
        assert parametre[0] == "ven-abcdef0123"          # venture_id
        assert parametre[1] == "idea-test-001"           # idea_id
        assert parametre[2] == "ai-legal-assistant-abcdef"  # code_slug
        assert parametre[3] == "AI Legal Assistant"      # display_name ( title)
        assert parametre[-1] == "2026-01-01T00:00:00+00:00"  # updated_at
        assert "syntropion-ai-legal-assistant-abcdef" in parametre


# ---------------------------------------------------------------------------
# VerticalPilotEngines.execute_radtrack_recist ( RECIST 1.1)
# ---------------------------------------------------------------------------
class TestRadTrackRecist:
    @pytest.mark.parametrize("baseline", [0, -0.01, -100])
    def test_baseline_sifir_alti_value_error(self, baseline):
        with pytest.raises(ValueError, match="greater than 0 mm"):
            VerticalPilotEngines.execute_radtrack_recist(baseline, 10)

    def test_tam_yanit_cr(self):
        r = VerticalPilotEngines.execute_radtrack_recist(20, 0)
        assert "CR (Tam Yanıt" in r["recist_classification"]
        assert r["difference_mm"] == -20.0
        assert r["percentage_change"] == -100.0

    def test_kismi_yanit_pr_esigini_tam_vurur(self):
        r = VerticalPilotEngines.execute_radtrack_recist(20, 14)
        assert r["percentage_change"] == -30.0
        assert "PR (Kısmi Yanıt" in r["recist_classification"]

    def test_pr_esigini_kacirir_sd(self):
        """-29.95% <= -30.0 değil → SD."""
        r = VerticalPilotEngines.execute_radtrack_recist(20, 14.01)
        assert r["percentage_change"] == pytest.approx(-29.95, abs=0.01)
        assert "SD (Stabil Hastalık" in r["recist_classification"]

    def test_ilerleyen_hastalık_pd(self):
        r = VerticalPilotEngines.execute_radtrack_recist(10, 15)
        assert r["percentage_change"] == 50.0
        assert r["difference_mm"] == 5.0
        assert "PD (İlerleyen Hastalık" in r["recist_classification"]

    @pytest.mark.parametrize(
        "baseline, follow_up, beklenen",
        [
            (100, 105, "SD"),   # diff 5 ama pct %5 < 20
            (10, 12.4, "SD"),   # pct %24 ama diff 2.4 < 5
            (10, 12, "SD"),     # pct tam %20 ama diff 2 < 5
            (25, 30, "PD"),     # pct tam %20 VE diff tam 5.0 → PD-eşiği
        ],
    )
    def test_pd_icin_hem_yuzde_hem_fark_gerekli(self, baseline, follow_up, beklenen):
        r = VerticalPilotEngines.execute_radtrack_recist(baseline, follow_up)
        assert r["recist_classification"].startswith(beklenen + " (")

    def test_stabil_hastalık_sd(self):
        r = VerticalPilotEngines.execute_radtrack_recist(10, 11)
        assert r["percentage_change"] == 10.0
        assert "SD (Stabil Hastalık" in r["recist_classification"]

    def test_rapor_metni_degerleri_icerir(self):
        r = VerticalPilotEngines.execute_radtrack_recist(20, 11)
        paragraf = r["report_paragraph"]
        assert "20.0 mm" in paragraf
        assert "11.0 mm" in paragraf
        assert "%-45.0" in paragraf
        # -45% <= -30 olduğu-için PR ( SD-değil)
        assert "PR (Kısmi Yanıt" in paragraf
        assert "RECIST 1.1 Kriterlerine Göre Kıyaslama" in paragraf

    def test_yuvarlama_iki_basamak(self):
        r = VerticalPilotEngines.execute_radtrack_recist(10, 10.126)
        assert r["difference_mm"] == 0.13
        assert r["percentage_change"] == 1.26

    def test_sayilar_oldugu_gibi_geri_doner(self):
        r = VerticalPilotEngines.execute_radtrack_recist(33.5, 40.25)
        assert r["baseline_mm"] == 33.5
        assert r["follow_up_mm"] == 40.25

    def test_singleton_uzerinden_de_calisir(self):
        """pilot_engines singleton'ı aynı-davranışı-verir ( statik-metod)."""
        r = cs.pilot_engines.execute_radtrack_recist(10, 0)
        assert "CR (Tam Yanıt" in r["recist_classification"]


# ---------------------------------------------------------------------------
# VerticalPilotEngines.execute_lexnotice_ttb ( TTK 6102 / TBK)
# ---------------------------------------------------------------------------
class TestLexNoticeTTB:
    @staticmethod
    def _cagir(gun_sayisi, tutar=100_000.0):
        """delivery_date=2026-01-01'den gun_sayisi gün-sonrasını ISO olarak üretir."""
        from datetime import date, timedelta

        current = (date(2026, 1, 1) + timedelta(days=gun_sayisi)).isoformat()
        return VerticalPilotEngines.execute_lexnotice_ttb("2026-01-01", current, tutar)

    def test_dusuk_risk_1_gun(self):
        r = VerticalPilotEngines.execute_lexnotice_ttb("2026-01-01", "2026-01-02", 100_000)
        assert r["days_passed"] == 1
        assert r["is_obvious_notice_expired"] is False
        assert r["is_hidden_notice_expired"] is False
        assert r["is_statute_of_limitations_expired"] is False
        assert r["risk_level"] == "LOW"

    @pytest.mark.parametrize(
        "gun, beklenen_risk",
        [
            (1, "LOW"),
            (2, "LOW"),                       # > 2 değil ( eşik-hassas)
            (3, "MEDIUM_RISK_HIDDEN_DEFECT_ONLY"),
            (8, "MEDIUM_RISK_HIDDEN_DEFECT_ONLY"),  # > 8 değil
            (9, "HIGH_RISK_DEFECT_NOTICE_FORFEITED"),
            (100, "HIGH_RISK_DEFECT_NOTICE_FORFEITED"),
        ],
    )
    def test_risk_seviyesi_gun_sayisina_gore(self, gun, beklenen_risk):
        r = self._cagir(gun)
        assert r["risk_level"] == beklenen_risk

    @pytest.mark.parametrize(
        "gun, beklenen",
        [(730, False), (731, True), (800, True)],
    )
    def test_zamanasimi_730_gun_esigi(self, gun, beklenen):
        r = self._cagir(gun)
        assert r["is_statute_of_limitations_expired"] is beklenen

    def test_faiz_hesabi_yillik_yuzde_48(self):
        """0.48/365 günlük-faiz → 365 günde %48."""
        r = VerticalPilotEngines.execute_lexnotice_ttb("2026-01-01", "2027-01-01", 100_000)
        assert r["accrued_interest_try"] == pytest.approx(48_000.0, abs=0.01)
        assert r["total_claim_try"] == pytest.approx(148_000.0, abs=0.01)

    def test_faiz_yuvarlama_iki_basamak(self):
        r = self._cagir(30)
        # 100000 * 0.48/365 * 30 = 3945.2054...
        assert r["accrued_interest_try"] == pytest.approx(3945.21, abs=0.01)

    def test_negatif_gun_sifir_faiz(self):
        """current_date < delivery_date → gün-negatif → faiz max(0, gün) ile 0."""
        r = VerticalPilotEngines.execute_lexnotice_ttb("2026-01-10", "2026-01-05", 100_000)
        assert r["days_passed"] == -5
        assert r["accrued_interest_try"] == 0.0
        assert r["total_claim_try"] == 100_000.0
        assert r["risk_level"] == "LOW"

    @pytest.mark.parametrize("tarih", ["2026/01/01", "01-01-2026", "bugün", ""])
    def test_gecersiz_tarih_value_error(self, tarih):
        with pytest.raises(ValueError):
            VerticalPilotEngines.execute_lexnotice_ttb(tarih, "2026-01-02", 100)

    def test_ihtarname_metni(self):
        r = VerticalPilotEngines.execute_lexnotice_ttb("2026-01-01", "2026-01-10", 1_000_000)
        metin = r["draft_legal_notice"]
        assert "İHTARNAME TASLAĞI" in metin
        assert "6102 Sayılı TTK Md. 23/1-c" in metin
        assert "3 iş günü" in metin
        assert "1,000,000.00 TL" in metin
        assert "9 gün" in metin

    def test_anahtarlar_tam_dir(self):
        r = self._cagir(5)
        assert set(r.keys()) == {
            "days_passed", "is_obvious_notice_expired", "is_hidden_notice_expired",
            "is_statute_of_limitations_expired", "accrued_interest_try",
            "total_claim_try", "risk_level", "draft_legal_notice",
        }


# ---------------------------------------------------------------------------
# VerticalPilotEngines.execute_taxcross_reconciliation
# ---------------------------------------------------------------------------
class TestTaxCrossReconciliation:
    def test_tam_mutabik(self):
        r = VerticalPilotEngines.execute_taxcross_reconciliation(1000, 1000)
        assert r["is_fully_reconciled"] is True
        assert r["discrepancy_try"] == 0.0
        assert r["potential_penalty_risk_try"] == 0.0
        assert r["audit_flags"] == ["Tüm e-Fatura ve Muhasebe Kayıtları %100 Mutabık"]

    @pytest.mark.parametrize(
        "gib, ledger, mutabik",
        [(1000, 1000.5, True), (1000, 1000.99, True), (1000, 1001.0, False), (1000, 999.0, False)],
    )
    def test_bir_tl_tolerans_esigi(self, gib, ledger, mutabik):
        r = VerticalPilotEngines.execute_taxcross_reconciliation(gib, ledger)
        assert r["is_fully_reconciled"] is mutabik

    def test_buyuk_fark_ceza_ve_flagler(self):
        r = VerticalPilotEngines.execute_taxcross_reconciliation(10000, 9000)
        assert r["discrepancy_try"] == 1000.0
        assert r["potential_penalty_risk_try"] == 300.0  # 1000 * 0.20 * 1.5
        assert any("VUK Md. 344" in f for f in r["audit_flags"])
        assert "Matrah Uyumsuzluğu: 1,000.00 TL" in r["audit_flags"]

    def test_ozel_kdv_orani(self):
        r = VerticalPilotEngines.execute_taxcross_reconciliation(2000, 1000, vat_rate_pct=10.0)
        assert r["potential_penalty_risk_try"] == 150.0  # 1000 * 0.10 * 1.5

    def test_negatif_toplamlar_abs_alir(self):
        r = VerticalPilotEngines.execute_taxcross_reconciliation(-500, 500)
        assert r["discrepancy_try"] == 1000.0
        assert r["is_fully_reconciled"] is False

    def test_fark_yuvarlama(self):
        r = VerticalPilotEngines.execute_taxcross_reconciliation(1000.1, 1000)
        assert r["discrepancy_try"] == 0.1

    def test_anahtarlar_tam_dir(self):
        r = VerticalPilotEngines.execute_taxcross_reconciliation(1, 1)
        assert set(r.keys()) == {
            "gib_invoices_total_try", "accounting_ledger_total_try", "discrepancy_try",
            "is_fully_reconciled", "potential_penalty_risk_try", "audit_flags",
        }


# ---------------------------------------------------------------------------
# VerticalPilotEngines.execute_tarifa_customs_gtip
# ---------------------------------------------------------------------------
class TestTarifaCustomsGTIP:
    @pytest.mark.parametrize(
        "urun, gtip, vergi, risk",
        [
            ("Polimer granüller", "3901.10.10.00.11", 6.5, True),
            ("plastik şişe", "3901.10.10.00.11", 6.5, True),
            ("Reçine karışımı", "3901.10.10.00.11", 6.5, True),
            ("Çelik sac", "7208.39.00.00.00", 12.0, True),
            ("boru çekirdeği", "7208.39.00.00.00", 12.0, True),
            ("antibiyotik ilaç", "3004.20.00.00.00", 0.0, False),
            ("ilaç tableti", "3004.20.00.00.00", 0.0, False),
        ],
    )
    def test_gtip_siniflandirma(self, urun, gtip, vergi, risk):
        r = VerticalPilotEngines.execute_tarifa_customs_gtip(urun, "US")
        assert r["determined_gtip_12_digit"] == gtip
        assert r["standard_duty_pct"] == vergi
        assert r["surveillance_measure_active"] is risk

    def test_buyuk_harfli_turkce_ilac_tespit_edilemez(self):
        """DAL-GÖZÜ: 'İLAÇ'.lower() → 'i̇laç' ( i + U+0307) — 'ilaç' ile-EŞLEŞMEZ.

        Python str.lower() Türkçe-'İ'yi iki-karakrelik 'i̇' yapar; eşleştirme
        küçük-harflerle-yapıldığı-için 'İLAÇ tableti' GTIP-3004'e DEĞIL,
        varsayılan 8471'e düşer. Bu-test o-gerçeği-belgeler.
        """
        r = VerticalPilotEngines.execute_tarifa_customs_gtip("İLAÇ tableti", "US")
        assert r["determined_gtip_12_digit"] == "8471.30.00.00.00"
        assert "İLAÇ".lower() == "i̇laç"  # U+0307 birleştiren-nokta

    def test_genel_urun_varsayilan(self):
        r = VerticalPilotEngines.execute_tarifa_customs_gtip("Laptop bilgisayar", "US")
        assert r["determined_gtip_12_digit"] == "8471.30.00.00.00"
        assert r["standard_duty_pct"] == 0.0
        assert r["surveillance_measure_active"] is False

    @pytest.mark.parametrize("mense", ["DE", "FR", "IT", "TR", "EU", "ALMANYA", "de", "almanya"])
    def test_tercihli_mense_vergi_sifir(self, mense):
        r = VerticalPilotEngines.execute_tarifa_customs_gtip("Çelik sac", mense)
        assert r["preferential_origin_applied"] is True
        assert r["effective_duty_pct"] == 0.0
        # standart-vergi yine-de 12.0 olarak-hatırlanır
        assert r["standard_duty_pct"] == 12.0

    @pytest.mark.parametrize("mense", ["US", "CN", "IN"])
    def test_tercihli_olmayan_mense_tam_vergi(self, mense):
        r = VerticalPilotEngines.execute_tarifa_customs_gtip("Çelik sac", mense)
        assert r["preferential_origin_applied"] is False
        assert r["effective_duty_pct"] == 12.0

    def test_compliance_metni_sabit(self):
        r = VerticalPilotEngines.execute_tarifa_customs_gtip("x", "US")
        assert r["customs_law_compliance"] == (
            "4458 Sayılı Kanun Md. 234 Ceza Riski: SIFIR (Tam Eşleşme)"
        )

    def test_anahtarlar_tam_dir(self):
        r = VerticalPilotEngines.execute_tarifa_customs_gtip("x", "US")
        assert set(r.keys()) == {
            "determined_gtip_12_digit", "standard_duty_pct", "effective_duty_pct",
            "surveillance_measure_active", "preferential_origin_applied",
            "customs_law_compliance",
        }


# ---------------------------------------------------------------------------
# VerticalPilotEngines.execute_demurrage_calculation
# ---------------------------------------------------------------------------
class TestDemurrageCalculation:
    def test_serbest_sure_icinde_ceza_yok(self):
        r = VerticalPilotEngines.execute_demurrage_calculation("2026-01-01", "2026-01-03")
        assert r["total_dwell_days"] == 2
        assert r["free_time_allowed_days"] == 7
        assert r["billable_demurrage_days"] == 0
        assert r["total_demurrage_usd"] == 0.0
        assert r["has_demurrage_penalty"] is False
        assert r["dispute_ready"] is True

    @pytest.mark.parametrize(
        "cikis, gelis, beklenen_billable",
        [("2026-01-01", "2026-01-08", 0), ("2026-01-01", "2026-01-09", 1)],
    )
    def test_serbest_sure_esigi_hassas(self, cikis, gelis, beklenen_billable):
        r = VerticalPilotEngines.execute_demurrage_calculation(cikis, gelis)
        assert r["billable_demurrage_days"] == beklenen_billable

    def test_demurrage_uygulanir(self):
        r = VerticalPilotEngines.execute_demurrage_calculation("2026-01-01", "2026-01-11")
        assert r["total_dwell_days"] == 10
        assert r["billable_demurrage_days"] == 3
        assert r["daily_rate_usd"] == 180.0
        assert r["total_demurrage_usd"] == 540.0
        assert r["has_demurrage_penalty"] is True
        assert r["dispute_ready"] is False

    def test_ozel_oran_ve_serbest_sure(self):
        r = VerticalPilotEngines.execute_demurrage_calculation(
            "2026-01-01", "2026-01-06", free_time_days=3, daily_rate_usd=200.0
        )
        assert r["free_time_allowed_days"] == 3
        assert r["billable_demurrage_days"] == 2
        assert r["total_demurrage_usd"] == 400.0

    def test_negatif_dwell_sifira_cekilir(self):
        """gate_out < discharge → negatif-dwell → max(0, negatif-free) = 0."""
        r = VerticalPilotEngines.execute_demurrage_calculation("2026-01-10", "2026-01-05")
        assert r["total_dwell_days"] == -5
        assert r["billable_demurrage_days"] == 0
        assert r["total_demurrage_usd"] == 0.0
        assert r["has_demurrage_penalty"] is False

    def test_tutar_yuvarlama_iki_basamak(self):
        r = VerticalPilotEngines.execute_demurrage_calculation(
            "2026-01-01", "2026-01-10", daily_rate_usd=180.5
        )
        assert r["billable_demurrage_days"] == 2
        assert r["total_demurrage_usd"] == 361.0

    @pytest.mark.parametrize("tarih", ["2026/01/01", "01.01.2026", ""])
    def test_gecersiz_tarih_value_error(self, tarih):
        with pytest.raises(ValueError):
            VerticalPilotEngines.execute_demurrage_calculation(tarih, "2026-01-02")

    def test_anahtarlar_tam_dir(self):
        r = VerticalPilotEngines.execute_demurrage_calculation("2026-01-01", "2026-01-02")
        assert set(r.keys()) == {
            "total_dwell_days", "free_time_allowed_days", "billable_demurrage_days",
            "daily_rate_usd", "total_demurrage_usd", "has_demurrage_penalty",
            "dispute_ready",
        }


# ---------------------------------------------------------------------------
# Modül-tekil-nesneler
# ---------------------------------------------------------------------------
class TestModuleSingletonlar:
    def test_singletonlar_hazir(self):
        assert isinstance(cs.code_synthesizer, CodeSynthesizer)
        assert isinstance(cs.pilot_engines, VerticalPilotEngines)

    def test_forbidden_ast_nodes_icerigi(self):
        assert "eval" in cs.FORBIDDEN_AST_NODES
        assert "exec" in cs.FORBIDDEN_AST_NODES
        assert "compile" in cs.FORBIDDEN_AST_NODES
        assert "__import__" in cs.FORBIDDEN_AST_NODES
        assert "os.system" in cs.FORBIDDEN_AST_NODES
        assert "subprocess.Popen" in cs.FORBIDDEN_AST_NODES
        assert "subprocess.run" in cs.FORBIDDEN_AST_NODES
        assert len(cs.FORBIDDEN_AST_NODES) == 7
