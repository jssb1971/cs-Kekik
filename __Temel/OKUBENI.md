# 🧩 Şablon » __Temel

Bu klasör, **yeni eklenti yazarken kopyalanacak iskelettir**. `settings.gradle.kts` içindeki
`disabled` listesinde olduğu için derlemeye girmez, dolayısıyla depoya sahte bir eklenti olarak düşmez.

## İçindekiler

| Dosya | Görevi |
|---|---|
| `build.gradle.kts` | Sürüm, yazar, açıklama, `tvTypes`, `iconUrl` |
| `src/main/AndroidManifest.xml` | CloudStream eklentisi için boş manifest |
| `src/main/kotlin/com/keyiflerolsun/Temel.kt` | Ana API: ana sayfa, arama, detay, kaynaklar |
| `src/main/kotlin/com/keyiflerolsun/TemelPlugin.kt` | `@CloudstreamPlugin` giriş noktası |
| `src/main/kotlin/com/keyiflerolsun/TemelUtils.kt` | Puan/süre/görsel ayıklama yardımcıları |

## Otomatik üretim (önerilen)

```bash
python3 ARACLAR/eklenti.py yeni --ad DiziOrnek --site https://www.diziornek.com --tip TvSeries
```

Script; klasörü, Kotlin dosyalarını, manifesti ve `build.gradle.kts`'i yer tutucuları doldurarak oluşturur.
Ardından `ARACLAR/eklenti.py dogrula --sadece DiziOrnek` ile kontrol edebilirsin.

## Elle üretim

1. Klasörü çoğalt: `cp -r __Temel YeniEklenti`
2. Dosya adlarını değiştir: `Temel.kt` → `YeniEklenti.kt`, `TemelPlugin.kt` → `YeniEklentiPlugin.kt`
3. Yer tutucuları değiştir: `__AD__`, `__SITE__`, `__PAKET__`, `__ACIKLAMA__`, `__YAZARLAR__`,
   `__TIPLER__`, `__TV_TIPLERI__`, `__DIL__`, `__IKON__`
4. `version = 1` yapıp commit'le — `settings.gradle.kts` yeni klasörü **otomatik** algılar.

## Notlar

- `KONTROL.py` her çalıştığında `override var mainUrl` satırını okuyup yönlendirmeleri takip eder.
  Bu yüzden `mainUrl` **tek yerde** ve **sonunda `/` olmadan** tutulur.
- Altyazı için `SubtitleFile(lang = "...", url = "...")`, video için `loadExtractor(...)` veya
  `ExtractorLink(...)` kullanılır.
- Özel player (extractor) yazacaksan `dogrula` komutu, `loadExtractor` yerine kendi extractor'ını
  kaydetmen gerektiğini hatırlatır: `registerExtractorAPI(...)`
