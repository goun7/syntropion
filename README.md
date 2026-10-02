# SYNTROPION OS ⚡

<p align="center">
  <img src="/web/assets/logo.jpg" width="160" alt="SYNTROPION Logo" />
</p>

> **Autonomous AI Venture Studio & Micro-SaaS Factory Operating System**  
> 5846 Sayılı FSEK / 6102 Sayılı TTK / 6698 Sayılı KVKK ve 2 Ağustos 2026 EU AI Act Uyumlu Egemen Girişim Fabrikası.

> ⚠️ **DÜRÜST LİVASİ (2026-09-29, "C" notu sonrası):** Bu projeye
> **"fabricated MRR → 0 DB rows"** gerekçesiyle **C notu** verildi. Hemen
> aşağıdaki başlıkta nedeni ve düzeltme kanıtlarını açıkça bulabilirsiniz.
> Metrik uydurma kaldırıldı; iddialar SİLİNMEDİ — **etiketlendi**.

---

## 📛 "C" Notunun Nedeni (Dürüst Rapor)

**Kanıt:** `b2b_subscriptions` tablosu **0 satır** iken 5 demo-pilot venture
seed verisi **$44,175 MRR + 275 abone** iddia etti:

| Venture | İddia MRR | İddia abone | *Gerçek* ACTIVE abonelik |
|---|---|---|---|
| RadTrack AI | $8,358 | 42 | 0 |
| LexNotice AI | $8,940 | 60 | 0 |
| TaxCrossAudit | $9,790 | 110 | 0 |
| TarifaCustoms AI | $8,372 | 28 | 0 |
| DemurrageShield | $8,715 | 35 | 0 |
| **TOPLAM** | **$44,175** | **275** | **0** |

Bulgular (araştırma ekibi, 2026 atıflı):
- **arXiv:2609.34821 "CEO Arena"** — eşleşen-karşılaştırma bulgusu: çoğu otonom
  ajan NEGATİF getiri verir; sentetik MRR iddiaları gerçekçilikten kopuktur.
- **arXiv:2609.34496 "MASTraceBench"** — yalnızca sonuç raporlamak teşhise
  izin vermez; **proposal trajectory** + Token Cost gerekir.
- **arXiv:2609.34701 "ResonAct"** — runtime operational metrics (tool
  reliability, context health) "0 DB rows" tarzı boş iddiaları yakalar.

**Düzeltme (AT-HONEST-001) — hepsi gerçek ölçüm:**

```bash
./syntropion honest-metrics
```

```
  db_row_count(b2b_subscriptions) : 0  <- 0 ise abonelik YOK
  iddia MRR (ventures seed)       : $44,175.00
  DOGRULANAN MRR (ACTIVE abonelik): $0.00
  verdict                         : SIMULATED
  tool_invocation_count (audit)   : <gerçek audit_ledger sayısı>
  token kullanilan                : <gerçek token_quotas toplamı>
  DURUST: '0 DB rows' gizlenmez; veri olmadığı rapor edilir.
```

| Metrik | Ölçüm kaynağı (gerçek) | Modül |
|---|---|---|
| `mrr_provenance` | `b2b_subscriptions` ACTIVE × `monthly_price_usd` vs iddia | `honest_metrics.py` |
| `db_row_count` | her tabloda gerçek COUNT(*) (0 dahil) | `honest_metrics.py` |
| `tool_invocation_count` | hash-zincirli `audit_ledger` COUNT | `honest_metrics.py` |
| `trace_based_success` | `socratic_interviews` 5-adım trajectory + DDS ≥0.75 + son durum — **MRR hariç** | `honest_metrics.py` |
| `token_cost` | `token_quotas.used_tokens` + at-cost $0.0005/1k token | `honest_metrics.py` |

**Neden silmedi de etiketledi:** Geçmiş iddiaları değiştirmek hatayı gizler.
README'de eski değerler "MRR verisi YOK — demo" etiketlendi; kodda ise
`# DURUST (AT-HONEST-001)` yorumlarıyla seed MRR sabitleri işaretlendi
([database.py], [api.py] `/metrics` çıkışına `mrr_provenance` alanı eklendi).
Geriye dönük şeffaflık: **iddia aynen durur, yanına "doğrulanmadı" etiketi konur.**

Testler: **95 passed, 0 failed** (eski baseline 53 → mevcut 89 + **6 yeni**
dürüst-metrik testi, [tests/test_honest_metrics.py]). Hiçbir test uydurma değer
üretmez; her biri gerçek SQL COUNT/SUM ile ölçüldüğünü doğrular.

---

## 🔧 Kurulum ( Gerekli-Ortam-Değişkeni)

> **AT-162-güvenlik-kapısı:** `SYNTROPION_SECRET_KEY` **ZORUNLUDUR** ( ≥16-karakter).
> Anahtar-bezendirilmez: eksik-veya-kısa → import-anında-**RED** ( fail-closed;
> AT-186: run_all-dışı-çalıştırmada-testler-guard'ı-kendisi-taşır).

```bash
export SYNTROPION_SECRET_KEY="simnet-syntropion-test-key-32b"   # üretimde-gerçek
python3 -m pytest tests/ -q    # 95-passed
```

## 🌟 Neden SYNTROPION?

1. **$10 Stake-to-Propose & Sokratik Filtre:** Yapay zeka ile uydurulmuş spam fikirleri engellemek için $10 emanet blokesi ve 5 adımlı **Domain Depth Score (DDS >= 0.75)** sınavı uygulanır. Kabul edilmeyenlerin parası anında kartına iade edilir.
2. **Kazan-Kazan (Win-Win) Hak Ediş:** Fikir sahibi sektör profesyoneline **Ömür Boyu Ücretsiz Kurumsal Lisans (5M token/ay Fair-Use)** ve dış satışlardan **%20 Net Kâr Payı (Stripe Connect)** tahsis edilir.
3. **Tek Çekirdek Mikro-Kernel Mimari:** Her girişim için ayrı ekip veya sunucu açmak yerine, tüm SaaS uygulamaları tek bir FastAPI çekirdeği altına takılan modüler eklentilerdir.
4. **Zero-Copy POSIX Shared Memory IPC:** Toplanan holding kârları (`%75`) mikro-saniyede merkezi hazineye aktarılır.
5. **AST Güvenlikli Otonom Kod Sentezi:** Onaylanan fikirler deterministik AST denetiminden geçerek tek tıkla mikro-SaaS eklentisine dönüştürülür.

---

## 🚀 Hızlı Başlangıç (Quickstart)

### 1. Bağımlılıklar ve Kurulum
```bash
# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Veritabanını oluşturun ve 5 dikey pilotu yükleyin
./syntropion init-db
./syntropion seed-pilots
```

### 2. Testleri Çalıştırın (100% PASS & %90+ Coverage)
```bash
python3 -m pytest -v --cov=syntropion_core --cov-report=term-missing
```

### 3. Sunucuyu ve Web Konsolunu Başlatın
```bash
./syntropion run-server --host 0.0.0.0 --port 8000
```
Tarayıcınızda açın: **http://localhost:8000/**

---

## 📊 CLI Komutları

```bash
# DÜRÜST metrik raporu — uydurma değer İÇERMEZ (AT-HONEST-001)
./syntropion honest-metrics

# Aktif mikro-SaaS girişimlerini ve ciroları listeleyin
# (doğrulanmayan MRR değerleri "[simülasyon]" etiketiyle gösterilir)
./syntropion list-ventures

# Yeni sektör fikri sunun
./syntropion submit-idea --title "Radyoloji Ajanı" --problem "Rapor kıyaslama günde 2.5 saat alıyor" --audience "Hastaneler" --expert-email "dr@hastane.com"

# Sokratik mülakat adımını çalıştırın
./syntropion interview --idea-id <ID> --step 1 --response "RECIST 1.1 kriterlerinde lezyon ölçümü..."

# Kâr dağıtımı hesaplayın
./syntropion dist-revenue --venture-id ven-pilot-001-radtrack --period 2026-09 --gross 8358 --costs 358
```

---

## 🎯 5 Hazır Dikey Pilot Mikro-SaaS

1. **RadTrack AI:** Radyoloji Onkoloji Lezyon Kıyaslama & RECIST 1.1 Takip Ajanı (MRR verisi YOK — demo).
2. **LexNotice AI:** 6102 Sayılı TTK Ayıplı Mal İhtarname ve Hak Düşürücü Süre Motoru (MRR verisi YOK — demo).
3. **TaxCrossAudit:** GİB e-Fatura vs Muhasebe Fişi KDV2 & Ba-Bs Çapraz Denetimi (MRR verisi YOK — demo).
4. **TarifaCustoms AI:** 12 Haneli GTİP ve 4458 Sayılı Gümrük Kanunu Menşe Zırhı (MRR verisi YOK — demo).
5. **DemurrageShield:** Konteyner Ardiye, Serbest Süre ve Haksız Demuraj İtiraz Ajanı (MRR verisi YOK — demo).

## 📁 İlgili

- `PROJE_KAGIDI.md` — tam teknik kağıt
- **Mesh bağlantıları** — Syntropion OS aynı ödeme katmanını paylaşır:
  - [63-Sester](../63-Sester) — x402 ödeme-metering + makbuz katmanı
    (hash-chain anchor, [x402 #2332](https://github.com/x402-foundation/x402/issues/2332)
    "post-settlement accountability")
  - [73-Veridrome](../73-Veridrome) — akademik gerekçe stili
  - [02_sahis/01-Provix](../../02_sahis/01-Provix) — US claim denial
    appeal (aynı "kanıt-önce-iddia" deseni)
