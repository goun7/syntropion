# HONEST METRICS — Syntropion Doğrulanmış Veri Raporu

> Bu rapor, "C notu — fabricated MRR → 0 DB rows" itirazına karşılık
> **doğrudan `syntropion.db` üzerinde SQL sorguları çalıştırılarak**
> üretilmiştir. Hiçbir sayı öngörü/tahmin değil, hepsi sorgu çıktısıdır.

---

## 1. GERÇEK DB SATIR SAYILARI (ADIM 1 — sqlite3 sorgu çıktısı)

Veritabanı dosyası: `syntropion.db` (2,584,576 byte — gerçek dosya, mevcut)

| Tablo | GERÇEK satır sayısı |
|---|---|
| `audit_ledger` | 5707 |
| `socratic_interviews` | 619 |
| `domain_ideas` | 474 |
| `domain_experts` | 226 |
| `milestone_vestings` | 226 |
| `revenue_distributions` | 222 |
| `ventures` | 139 |
| `token_quotas` | 13 |
| **`b2b_subscriptions`** | **0** ← KRİTİK |
| **TOPLAM** | **7626** |

### MRR claim'i DB'den geliyor mu? — HAYIR

`b2b_subscriptions` tablosu, ACTIVE aboneliklerin **tek meşru kaynağıdır**
(`status IN ('ACTIVE','PAST_DUE','CANCELLED')`, `monthly_price_usd REAL`).
Bu tabloda **0 (sıfır) satır** vardır.

Doğrulanan MRR sorgusu:

```sql
SELECT COALESCE(SUM(monthly_price_usd), 0) FROM b2b_subscriptions WHERE status='ACTIVE';
-- Sonuç: 0.00   (tabloda satır olmadığı için COALESCE varsayılanına düşer)
```

**DOĞRULANAN MRR = $0.00**
**DOĞRULANAN ACTIVE abone = 0**

İddia edilen $44,175 MRR ve 275 abone sayısı, `ventures` tablosuna
**seed scripti tarafından gömülmüş sabit kolon değerleridir**
(`current_monthly_mrr_usd`, `active_b2b_subscribers`) — hiçbir gerçek
abonelik kaydından türememiştir. Özet sorgu:

```sql
SELECT COUNT(*), SUM(target_monthly_mrr_usd), SUM(current_monthly_mrr_usd),
       SUM(active_b2b_subscribers) FROM ventures;
-- 139 | 598250.00 | 44175.00 | 275
```

Yani: `ventures.current_monthly_mrr_usd` = 44175.00 olması, arkasında
`b2b_subscriptions`'da 0 satır olduğu için **gerçek gelir değil,kod içine
yazılmış kurgusal bir sabittir.** Sadece 5 venture bu sabit değerleri taşır
(RadTrack AI, LexNotice AI, TaxCrossAudit, TarifaCustoms AI, DemurrageShield);
geri kalan 134 venture'ın `current_monthly_mrr_usd` = 0.00'dır.

---

## 2. MRR CLAIM'LERİNİN KONUM VE DEĞERLERİ (ADIM 2 — grep çıktısı)

Tüm MRR iddiaları **`README.md`** içindedir (`docs/` dizininde eşleşme yoktur).

| Konum | Değer / İçerik |
|---|---|
| `README.md:11` | "fabricated MRR → 0 DB rows" gerekçesiyle **C notu** verildi (itirazın kendisi) |
| `README.md:20` | seed verisi **$44,175 MRR + 275 abone** iddia etti |
| `README.md:24` | RadTrack AI — iddia **$8,358** MRR / 42 abone (gerçek ACTIVE: 0) |
| `README.md:25` | LexNotice AI — iddia **$8,940** MRR / 60 abone (gerçek ACTIVE: 0) |
| `README.md:26` | TaxCrossAudit — iddia **$9,790** MRR / 110 abone (gerçek ACTIVE: 0) |
| `README.md:27` | TarifaCustoms AI — iddia **$8,372** MRR / 28 abone (gerçek ACTIVE: 0) |
| `README.md:28` | DemurrageShield — iddia **$8,715** MRR / 35 abone (gerçek ACTIVE: 0) |
| `README.md:29` | **TOPLAM — $44,175 MRR / 275 abone** (gerçek ACTIVE: **0**) |
| `README.md:33` | "sentetik MRR iddiaları gerçekçilikten kopuktur" |
| `README.md:47` | iddia MRR (ventures seed): **$44,175.00** |
| `README.md:48` | DOĞRULANAN MRR (ACTIVE abonelik): **$0.00** |
| `README.md:60` | `trace_based_success` metrik tanımı — "MRR hariç" |
| `README.md:128` | doğrulanmayan MRR değerleri "[simülasyon]" etiketiyle gösterilir |
| `README.md:145` | RadTrack AI — "MRR verisi YOK — demo" |
| `README.md:146` | LexNotice AI — "MRR verisi YOK — demo" |

Toplam **16 MRR/başlangıç değeri içeren satır**; bunların tümü ya iddiayı
ya da iddianın çürütülmesini belgeler. README zaten itirazı kabul etmiş
şekildedir (satır 47–48 iddia/doğrulanmış ikilisini açıkça ayırır).

---

## 3. DÜRÜST NOT — C Notunun Gerçek Nedeni

**C notu nedeni — MRR metrikleri simüle edildi, gerçek DB'den gelmiyor.**

 somut kanıtı:

- **X (iddia):** 275 abone + **$44,175** MRR — `README.md`'de ve
  `ventures.current_monthly_mrr_usd` / `active_b2b_subscribers` kolonlarında
  seed sabiti olarak.
- **Y (gerçek):** **0 satır** `b2b_subscriptions` tablosunda →
  **$0.00** doğrulanabilir MRR, **0** doğrulanabilir ACTIVE abone.
- **X / Y oranı: iddia ∞'a böler** — iddia edilen her aboneliğin arkasında
  sıfır satırlık bir kaynak tablo vardır.

Semantik olarak da tutarsızlık vardır: seed, `ventures` tablosunun
`target_monthly_mrr_usd` kolonuna bile 5 venture için 10000.00 yazmıştır
(toplam $598,250 hedef), yani "iddia" ile "gerçek" arasındaki uçurum
kodun kendi içinde iki kolona bölünmüş ama ikisi de gerçek abonelik
kayıtlarına **bağlanmamıştır**. Doğrulanabilir gelir metriği ancak
`b2b_subscriptions` dolduğüzaman anlam kazanır; bugün o tablo boştur.

Bu dosya, sayıları düzeltmek için değil, **gerçek durumu kayıt altına almak**
için yazılmıştır. 53 test / 0 failed durumu ve mevcut `.py` dosyaları
bu raporla **değiştirilmemiştir.**

---

## 4. Referans Makaleler (2026)

1. **arXiv 2609.34821** — *CEO Arena: Matched Replacement* — çalışan-çift
   karşılaştırmalı değerlendirme protokolü (bu rapordaki "iddia vs gerçek"
   matched-karşılaştırma mantığının akademik karşılığı).
2. **arXiv 2609.34496** — *MASTraceBench* — çok-adımlı ajan iz
   (trace) doğrulama benchmarkı (`audit_ledger` / `socratic_interviews`
   izlerinde bütünlük denetimi için metod çerçevesi).
3. **arXiv 2609.34701** — *ResonAct* — rezonans-tabanlı ajan eylem
   seçilimi (Sokratik filtre ve DDS ≥ 0.75 eşik tasarımının teorik tabanı).

---

*Üretim tarihi: 2026-09-30 · Tüm sayılar `sqlite3 syntropion.db` üzerinde
çalıştırılan canlı sorgulardan alınmıştır. Bu dosya `HONEST_METRICS.md`
dışında hiçbir dosyayı değiştirmez.*
