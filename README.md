# SYNTROPION OS ⚡

<p align="center">
  <img src="/web/assets/logo.jpg" width="160" alt="SYNTROPION Logo" />
</p>

> **Autonomous AI Venture Studio & Micro-SaaS Factory Operating System**  
> 5846 Sayılı FSEK / 6102 Sayılı TTK / 6698 Sayılı KVKK ve 2 Ağustos 2026 EU AI Act Uyumlu Egemen Girişim Fabrikası.

---

## 🔧 Kurulum ( Gerekli-Ortam-Değişkeni)

> **AT-162-güvenlik-kapısı:** `SYNTROPION_SECRET_KEY` **ZORUNLUDUR** ( ≥16-karakter).
> Anahtar-bezendirilmez: eksik-veya-kısa → import-anında-**RED** ( fail-closed;
> AT-186: run_all-dışı-çalıştırmada-testler-guard'ı-kendisi-taşır).

```bash
export SYNTROPION_SECRET_KEY="simnet-syntropion-test-key-32b"   # üretimde-gerçek
python3 -m pytest tests/ -q    # 89-passed
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
# Aktif mikro-SaaS girişimlerini ve ciroları listeleyin
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
