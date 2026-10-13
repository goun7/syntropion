"""test_cli_dallar.py — syntropion_core/cli.py dal-kesen testleri

Argparse tabanlı CLI: 8 komutun ( init-db, seed-pilots, list-ventures,
honest-metrics, submit-idea, interview, dist-revenue, run-server) her-biri
stub'lanmış-bağımlılıklarla çalışır; argparse çözümlemesi + varsayılan-değerler
+ gerekli-argüman-hataları dahil tüm-dallar.

TÜM DALLAR:
  cmd_init_db:
    1.  _ensure_schema() çağrılır + başlangıç/başarı-mesajları + db_path yazılır
  cmd_seed_pilots:
    2.  seed_deep_vertical_pilots() + her-venture satırı "$X,XXX.XX MRR"
  cmd_list_ventures:
    3.  MRR>0 & abonelik-sayısı=0 → "[simülasyon — b2b_subscriptions=0]" etiketi
    4.  abonelik varsa etiket-YOK
    5.  MRR=0 ise etiket-YOK ( sıfır-iddia)
    6.  DOĞRULANAN/iddia/verdict satırı yazılır
  cmd_honest_metrics:
    7.  render_honest_report() çıktısı basılır
  cmd_submit_idea:
    8.  yeni-uzman: 2 INSERT ( expert + idea) + scrubbed problem + $10 escrow
    9.  mevcut-uzman: expert-INSERT-YOK ( mevcut expert_id kullanılır)
    10. scrub_pii_presidio_grade problem-metnini-alır
    11. id formatları exp-cli-<8hex> / idea-cli-<8hex>
  cmd_run_interview:
    12. süreç-sonuçları yazılır + sonraki-soru ( step+1)
    13. next_question=None → sonraki-soru basılmaz
  cmd_dist_revenue:
    14. kwargs iletilir + JSON çıktısı basılır
  cmd_run_server:
    15. uvicorn.run'a doğru host/port/reload iletilir
  main ( argparse):
    16. komut-yok → print_help + SystemExit(0)
    17. her-komut func'a yönlendirir
    18. --reload store_true; host/port varsayılanları
    19. gerekli-argüman-eksik → SystemExit(2)
    20. interview --step 6 → invalid-choice ( SystemExit 2)

Kural-1: SADECE-yeni-dosya. Kural-4: db/uvicorn/honest-metrics/socratic-engine
hepsi monkeypatch'li-stub; gerçek-ağ/SUNUCU-YOK. Import-anı /dev/shm ve
syntropion.db dokunmasın → SYNTROPION_DB_PATH + SHM_IPC_PATH /tmp'ye.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

import pytest

# --- Kural-4: import-anında gerçek syntropion.db ve /dev/shm'ye DOKUNMA ------
# cli → database.db singleton ve revenue_router → shared_memory_ipc singleton
# import-anı yan-etki yapar ( WAL-şema + mmap-dosya). Henüz-import-edilmemişse
# /tmp'ye yönlendir; tam-suite'te zaten-import-edildiği-için DOKUNMA.
_TMPDIR = tempfile.mkdtemp(prefix="syntropion-dallar-cli-")
if "syntropion_core.database" not in sys.modules:
    os.environ.setdefault("SYNTROPION_DB_PATH", os.path.join(_TMPDIR, "db.db"))
if "syntropion_core.shared_memory_ipc" not in sys.modules:
    os.environ.setdefault("SHM_IPC_PATH", os.path.join(_TMPDIR, "shm.bin"))

from syntropion_core import cli


@pytest.fixture
def argv(monkeypatch):
    """main()'in sys.argv'sini-ayarlar ( argparse doğrudan sys.argv okur)."""
    def _set(degerler):
        monkeypatch.setattr(sys, "argv", degerler)
    return _set


# ---------------------------------------------------------------------------
# cmd_init_db
# ---------------------------------------------------------------------------
class TestCmdInitDb:
    def test_schema_baslatir_ve_mesaj(self, monkeypatch, capsys):
        cagrilan = []
        monkeypatch.setattr(cli.db, "_ensure_schema", lambda: cagrilan.append(1))
        monkeypatch.setattr(cli.db, "db_path", "/tmp/dallar/cli.db")
        cli.cmd_init_db(argparse.Namespace())

        out = capsys.readouterr().out
        assert cagrilan == [1]
        assert "Initializing SYNTROPION OS database schema..." in out
        assert "Schema initialized successfully at: /tmp/dallar/cli.db" in out


# ---------------------------------------------------------------------------
# cmd_seed_pilots
# ---------------------------------------------------------------------------
class TestCmdSeedPilots:
    PILOTS = [
        {"code_slug": "radtrack-ai", "display_name": "RadTrack AI",
         "current_monthly_mrr_usd": 8358.0},
        {"code_slug": "demurrage-shield", "display_name": "Demurrage Shield",
         "current_monthly_mrr_usd": 0.0},
    ]

    def test_pilotlari_seeder_ve_listeler(self, monkeypatch, capsys):
        cagrilan = []
        monkeypatch.setattr(cli.db, "seed_deep_vertical_pilots",
                            lambda: cagrilan.append(1))
        monkeypatch.setattr(cli.db, "fetchall", lambda q, p=(): self.PILOTS)
        cli.cmd_seed_pilots(argparse.Namespace())

        out = capsys.readouterr().out
        assert cagrilan == [1]
        assert "Seeding 5 Deep Vertical Pilots" in out
        assert "Successfully seeded 2 ventures:" in out
        assert "[radtrack-ai]" in out
        assert "$8,358.00 MRR" in out
        assert "$0.00 MRR" in out
        assert "RadTrack AI -> $8,358.00 MRR" in out


# ---------------------------------------------------------------------------
# cmd_list_ventures
# ---------------------------------------------------------------------------
class TestCmdListVentures:
    VENTURES = [
        {"venture_id": "v1", "code_slug": "radtrack-ai", "display_name": "RadTrack AI",
         "status": "PRODUCTION_LIVE", "current_monthly_mrr_usd": 8358.0,
         "active_b2b_subscribers": 0},
        {"venture_id": "v2", "code_slug": "lexnotice-ai", "display_name": "LexNotice AI",
         "status": "PRODUCTION_LIVE", "current_monthly_mrr_usd": 5295.0,
         "active_b2b_subscribers": 0},
        {"venture_id": "v3", "code_slug": "sifir-mrr", "display_name": "Sıfır MRR",
         "status": "ALPHA_TEST", "current_monthly_mrr_usd": 0.0,
         "active_b2b_subscribers": 0},
    ]

    def _provenance(self, monkeypatch, aktif_abonelik=0):
        from syntropion_core import honest_metrics

        monkeypatch.setattr(honest_metrics, "mrr_provenance", lambda: {
            "verified_mrr_usd": 1000.0,
            "claimed_mrr_usd": 13653.0,
            "active_subscription_rows": aktif_abonelik,
            "verdict": "SIMULASYON-MRR",
        })

    def test_simulasyon_etiketi_yazilir(self, monkeypatch, capsys):
        self._provenance(monkeypatch, aktif_abonelik=0)
        monkeypatch.setattr(cli.db, "fetchall", lambda q, p=(): self.VENTURES)
        cli.cmd_list_ventures(argparse.Namespace())

        out = capsys.readouterr().out
        assert "[simülasyon — b2b_subscriptions=0]" in out
        assert "radtrack-ai" in out and "lexnotice-ai" in out
        assert "DOĞRULANAN MRR (ACTIVE b2b_subscriptions): $1,000.00" in out
        assert "iddia: $13,653.00" in out
        assert "verdict: SIMULASYON-MRR" in out

    def test_abonelik_varsa_etiket_yok(self, monkeypatch, capsys):
        self._provenance(monkeypatch, aktif_abonelik=2)
        monkeypatch.setattr(cli.db, "fetchall", lambda q, p=(): self.VENTURES)
        cli.cmd_list_ventures(argparse.Namespace())
        assert "[simülasyon" not in capsys.readouterr().out

    def test_sifir_mrr_icin_etiket_yok(self, monkeypatch, capsys):
        self._provenance(monkeypatch, aktif_abonelik=0)
        sifir = [dict(self.VENTURES[2])]
        monkeypatch.setattr(cli.db, "fetchall", lambda q, p=(): sifir)
        cli.cmd_list_ventures(argparse.Namespace())
        out = capsys.readouterr().out  # bir-kez-tüket ( ikinci-okuma boş-döner)
        assert "[simülasyon" not in out
        assert "sifir-mrr" in out
        assert "Sıfır MRR" in out


# ---------------------------------------------------------------------------
# cmd_honest_metrics
# ---------------------------------------------------------------------------
class TestCmdHonestMetrics:
    def test_rapor_basilir(self, monkeypatch, capsys):
        from syntropion_core import honest_metrics

        monkeypatch.setattr(honest_metrics, "render_honest_report",
                            lambda: "DÜRÜST-TEST-RAPORU")
        cli.cmd_honest_metrics(argparse.Namespace())
        assert "DÜRÜST-TEST-RAPORU" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# cmd_submit_idea
# ---------------------------------------------------------------------------
class TestCmdSubmitIdea:
    ARGS = argparse.Namespace(
        title="Test Fikri", problem="Banka müşterileri zarar-görüyor.",
        audience="Bankalar", expert_email="uzman@banka.com",
        expert_name="Test Uzmanı", domain="fintech", exp=12,
    )

    @pytest.fixture
    def security_stub(self, monkeypatch):
        from syntropion_core import security

        gelen = {}
        monkeypatch.setattr(security, "scrub_pii_presidio_grade",
                            lambda metin: gelen.update(metin=metin) or ("temizlenmiş", None))
        return gelen

    @pytest.fixture
    def db_stub(self, monkeypatch):
        store = {"one": None, "execs": []}
        monkeypatch.setattr(cli.db, "fetchone", lambda q, p=(): store["one"])
        monkeypatch.setattr(
            cli.db, "execute", lambda q, p=(): store["execs"].append((q, tuple(p))) or 1
        )
        return store

    def test_yeni_uzman_iki_insert(self, monkeypatch, db_stub, security_stub, capsys):
        db_stub["one"] = None
        cli.cmd_submit_idea(self.ARGS)

        assert len(db_stub["execs"]) == 2
        expert_sql, expert_params = db_stub["execs"][0]
        idea_sql, idea_params = db_stub["execs"][1]
        assert "INSERT INTO domain_experts" in expert_sql
        assert expert_params[1] == "uzman@banka.com"      # email
        assert expert_params[2] == "Test Uzmanı"          # full_name
        assert expert_params[3] == "fintech"              # industry_domain
        assert expert_params[4] == 12                     # years_of_experience
        assert "INSERT INTO domain_ideas" in idea_sql
        assert "'HELD_IN_ESCROW'" in idea_sql
        assert "10.00" in idea_sql
        assert idea_params[3] == "temizlenmiş"            # scrubbed problem
        assert idea_params[4] == "Bankalar"               # audience

        out = capsys.readouterr().out
        assert "Submitting domain idea: 'Test Fikri' by uzman@banka.com..." in out
        assert "(Stake: $10 HELD_IN_ESCROW)" in out
        import re
        eslesme = re.search(r"Idea created successfully: (idea-cli-[0-9a-f]{8})", out)
        assert eslesme is not None
        assert f"interview --idea-id {eslesme.group(1)} --step 1" in out

    def test_yeni_uzman_id_formati(self, db_stub, security_stub, capsys):
        db_stub["one"] = None
        cli.cmd_submit_idea(self.ARGS)
        import re
        assert re.fullmatch(r"exp-cli-[0-9a-f]{8}", db_stub["execs"][0][1][0])

    def test_mevcut_uzman_expert_insert_yok(self, db_stub, security_stub, capsys):
        db_stub["one"] = {"expert_id": "exp-mevcut-001"}
        cli.cmd_submit_idea(self.ARGS)

        assert len(db_stub["execs"]) == 1
        assert db_stub["execs"][0][1][1] == "exp-mevcut-001"  # idea → expert_id

    def test_scrubber_problem_metnini_alir(self, db_stub, security_stub):
        db_stub["one"] = None
        cli.cmd_submit_idea(self.ARGS)
        assert security_stub["metin"] == "Banka müşterileri zarar-görüyor."


# ---------------------------------------------------------------------------
# cmd_run_interview
# ---------------------------------------------------------------------------
class TestCmdRunInterview:
    @staticmethod
    def _patch_engine(monkeypatch, sonraki_soru):
        sonuc = {
            "score": 0.85,
            "domain_depth_score_running": 2.40,
            "status": "IN_PROGRESS",
            "feedback": "İyi-derinlik",
            "next_question": sonraki_soru,
        }
        cagrilan = []
        monkeypatch.setattr(cli.socratic_engine, "process_step",
                            lambda iid, adim, yanit: cagrilan.append((iid, adim, yanit)) or sonuc)
        return cagrilan

    def test_sonuc_ve_sonraki_soru(self, monkeypatch, capsys):
        cagrilan = self._patch_engine(monkeypatch, "Sırada hangi-metrik?")
        args = argparse.Namespace(idea_id="idea-1", step=1, response="yanıtım")
        cli.cmd_run_interview(args)

        assert cagrilan == [("idea-1", 1, "yanıtım")]
        out = capsys.readouterr().out
        assert "Evaluating Socratic Step 1 for Idea idea-1..." in out
        assert "Step Score: 0.85" in out
        assert "Running DDS: 2.40" in out
        assert "Status: IN_PROGRESS" in out
        assert "Feedback: İyi-derinlik" in out
        assert "Next Question (Step 2):\nSırada hangi-metrik?" in out

    def test_sonraki_soru_yoksa_basilma(self, monkeypatch, capsys):
        self._patch_engine(monkeypatch, None)
        cli.cmd_run_interview(argparse.Namespace(idea_id="i", step=5, response="y"))
        out = capsys.readouterr().out
        assert "Next Question" not in out
        assert "Step 5 for Idea i" in out


# ---------------------------------------------------------------------------
# cmd_dist_revenue
# ---------------------------------------------------------------------------
class TestCmdDistRevenue:
    def test_kwargs_ve_json_cikti(self, monkeypatch, capsys):
        giden = {}
        sonuc = {"treasury_usd": 100.0, "expert_payout_usd": 40.0}

        def _kayit(**kwargs):
            giden.update(kwargs)
            return sonuc

        monkeypatch.setattr(cli.revenue_router, "calculate_and_record_split", _kayit)
        args = argparse.Namespace(venture_id="ven-1", period="2026-09",
                                  gross=500.0, costs=50.0)
        cli.cmd_dist_revenue(args)

        assert giden == {"venture_id": "ven-1", "billing_period": "2026-09",
                         "gross_revenue_usd": 500.0, "infra_costs_usd": 50.0}
        out = capsys.readouterr().out
        assert "Processing revenue split for venture ven-1 (Period: 2026-09)..." in out
        assert '"treasury_usd": 100.0' in out
        assert '"expert_payout_usd": 40.0' in out


# ---------------------------------------------------------------------------
# cmd_run_server
# ---------------------------------------------------------------------------
class TestCmdRunServer:
    def test_uvicorn_cagrilir(self, monkeypatch, capsys):
        cagrilan = {}
        monkeypatch.setattr("uvicorn.run", lambda *a, **kw: cagrilan.update(args=a, kwargs=kw))
        args = argparse.Namespace(host="127.0.0.1", port=9999, reload=True)
        cli.cmd_run_server(args)

        assert cagrilan["args"] == ("syntropion_core.api:app",)
        assert cagrilan["kwargs"] == {"host": "127.0.0.1", "port": 9999, "reload": True}
        out = capsys.readouterr().out
        assert "Starting SYNTROPION OS Server on 127.0.0.1:9999..." in out

    def test_reload_false(self, monkeypatch):
        cagrilan = {}
        monkeypatch.setattr("uvicorn.run", lambda *a, **kw: cagrilan.update(kwargs=kw))
        cli.cmd_run_server(argparse.Namespace(host="0.0.0.0", port=8000, reload=False))
        assert cagrilan["kwargs"]["reload"] is False


# ---------------------------------------------------------------------------
# main() — argparse çözümleme ve yönlendirme
# ---------------------------------------------------------------------------
class TestMainArgparse:
    @pytest.mark.parametrize(
        "komut, beklenen_fonk",
        [
            ("init-db", "cmd_init_db"),
            ("seed-pilots", "cmd_seed_pilots"),
            ("list-ventures", "cmd_list_ventures"),
            ("honest-metrics", "cmd_honest_metrics"),
        ],
    )
    def test_komutlar_yonlendirir(self, argv, monkeypatch, komut, beklenen_fonk):
        argv(["syntropion", komut])
        cagrilan = []
        fake = lambda a: cagrilan.append(a)  # noqa: E731
        monkeypatch.setattr(cli, beklenen_fonk, fake)
        cli.main()
        assert len(cagrilan) == 1
        # Namespace'e subparser tarafından command + func eklenir
        assert cagrilan[0].command == komut
        assert cagrilan[0].func is fake

    def test_komut_yok_help_ve_exit0(self, argv, capsys):
        argv(["syntropion"])
        with pytest.raises(SystemExit) as hata:
            cli.main()
        assert hata.value.code == 0
        assert "usage: syntropion" in capsys.readouterr().out

    def test_submit_idea_argumanlar(self, argv, monkeypatch):
        argv(["syntropion", "submit-idea", "--title", "T", "--problem", "P",
              "--audience", "A", "--expert-email", "e@x.com"])
        gelen = {}
        monkeypatch.setattr(cli, "cmd_submit_idea", lambda a: gelen.update(vars(a)))
        cli.main()
        assert gelen["title"] == "T"
        assert gelen["problem"] == "P"
        assert gelen["audience"] == "A"
        assert gelen["expert_email"] == "e@x.com"
        # varsayılan-değerler
        assert gelen["expert_name"] == "Saha Uzmanı"
        assert gelen["domain"] == "general"
        assert gelen["exp"] == 10

    def test_submit_idea_gerekli_eksik_exit2(self, argv, capsys):
        argv(["syntropion", "submit-idea", "--title", "T"])
        with pytest.raises(SystemExit) as hata:
            cli.main()
        assert hata.value.code == 2
        assert "the following arguments are required" in capsys.readouterr().err

    def test_interview_gecerli_adimlar(self, argv, monkeypatch):
        argv(["syntropion", "interview", "--idea-id", "i1", "--step", "3",
              "--response", "r"])
        gelen = {}
        monkeypatch.setattr(cli, "cmd_run_interview", lambda a: gelen.update(vars(a)))
        cli.main()
        assert gelen["step"] == 3 and gelen["idea_id"] == "i1"

    @pytest.mark.parametrize("adim", ["0", "6", "99", "-1"])
    def test_interview_gecersiz_adim_exit2(self, argv, capsys, adim):
        argv(["syntropion", "interview", "--idea-id", "i1", "--step", adim,
              "--response", "r"])
        with pytest.raises(SystemExit) as hata:
            cli.main()
        assert hata.value.code == 2
        assert "invalid choice" in capsys.readouterr().err

    def test_dist_revenue_argumanlar(self, argv, monkeypatch):
        argv(["syntropion", "dist-revenue", "--venture-id", "v1", "--period", "2026-09",
              "--gross", "1000"])
        gelen = {}
        monkeypatch.setattr(cli, "cmd_dist_revenue", lambda a: gelen.update(vars(a)))
        cli.main()
        assert gelen["venture_id"] == "v1"
        assert gelen["period"] == "2026-09"
        assert gelen["gross"] == 1000.0
        assert gelen["costs"] == 0.0  # varsayılan

    def test_run_server_varsayilanlari(self, argv, monkeypatch):
        argv(["syntropion", "run-server"])
        gelen = {}
        monkeypatch.setattr(cli, "cmd_run_server", lambda a: gelen.update(vars(a)))
        cli.main()
        assert gelen["host"] == "0.0.0.0"
        assert gelen["port"] == 8000
        assert gelen["reload"] is False

    def test_run_server_reload_flag(self, argv, monkeypatch):
        argv(["syntropion", "run-server", "--reload", "--port", "9000"])
        gelen = {}
        monkeypatch.setattr(cli, "cmd_run_server", lambda a: gelen.update(vars(a)))
        cli.main()
        assert gelen["reload"] is True
        assert gelen["port"] == 9000

    def test_bilinmeyen_komut_exit2(self, argv, capsys):
        argv(["syntropion", "olmayan-komut"])
        with pytest.raises(SystemExit) as hata:
            cli.main()
        assert hata.value.code == 2
