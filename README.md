# cs-Kekik

Arşive alınmış projenin canlıya çekilmiş hali

## 💾 Kurulum

1. **[cloudstream/pre-release](https://github.com/recloudstream/cloudstream/releases/tag/pre-release)** _Adresinden güncel APK dosyasını indirip kurun._
2. **Uygulamanın yüklü olduğu cihazda** _[depoyu otomatik yüklemek için tıklayın](https://keyiflerolsun.me/http-protocol-redirector?r=cloudstreamrepo://raw.githubusercontent.com/maarrem/cs-Kekik/master/repo.json)_
   - **veya**
   - `Depo ekle` _butonuyla **manuel** ekleme yapmak isteyen arkadaşlar için_ `kekikdevam` _**kısa kod**u mevcuttur._ `Depo ismi` _kısmını boş bırakarak_ `Depo URL'si` _kısmına_ `kekikdevam` yazarak `Depo ekle` _demeniz yeterli.._
  
## 🛠️ Araçlar

Depo kökündeki `ARACLAR/` klasörü, eklenti yazımını ve bakımını kolaylaştıran **harici kütüphane gerektirmeyen** Python araçlarını barındırır.

```bash
# Eklentileri listele (sürüm / durum / tip / mainUrl)
python3 ARACLAR/eklenti.py liste

# Eklentileri denetle (eksik dosya, hatalı API, mainUrl tutarlılığı)
python3 ARACLAR/eklenti.py dogrula
python3 ARACLAR/eklenti.py dogrula --sadece DiziBox --kati

# Şablondan yeni eklenti üret
python3 ARACLAR/eklenti.py yeni --ad DiziOrnek --site https://www.diziornek.com --tip TvSeries
```

### ➕ Yeni eklenti eklemek

1. `python3 ARACLAR/eklenti.py yeni --ad <İsim> --site <https://site> --tip <TvSeries|Movie|Anime|Live|...>`
2. Üretilen Kotlin dosyasındaki HTML seçicilerini sitenin kaynak koduna göre uyarla
3. `./gradlew :<İsim>:make` ile derle (veya CI'ya gönder)

`settings.gradle.kts` yeni klasörü **otomatik** algılar; ek dosya değişikliği gerekmez.
Şablonun detayları için `__Temel/OKUBENI.md`.

### ♻️ CloudStream API göçü

CloudStream, 2026 Temmuz'undan itibaren `toRatingInt()`, `rating`, `ExtractorLink(...)` ve
`Episode(...)` gibi API'leri **`DeprecationLevel.ERROR`** seviyesine aldı. Bu seviyedeki kullanımlar
derlemeyi kırar. Depoyu yeni API'ye taşımak için:

```bash
python3 ARACLAR/goc.py            # nelerin değişeceğini gösterir (kuru çalıştırma)
python3 ARACLAR/goc.py --uygula   # değişiklikleri uygular
```

| Eski | Yeni |
|---|---|
| `X.toRatingInt()` | `Score.from10(X)` |
| `this.rating = ...` | `this.score = ...` |
| `ExtractorLink(source, name, url, referer, quality, isM3u8 = true)` | `newExtractorLink(source, name, url, type = ExtractorLinkType.M3U8) { this.referer = ...; this.quality = ... }` |
| `Episode(data = X, name = ...)` | `newEpisode(X) { this.name = ... }` |

## Faydalı Linkler

- [Tanıtım Videosu](https://www.youtube.com/watch?v=CiYK7zrP00c)
- [Cloudstream 3 Repositories](https://rentry.org/cs3-repos)
- [List of extensions](https://cloudstream.miraheze.org/wiki/List_of_extensions)
- [Open Subtitles FAQ](https://recloudstream.github.io/csdocs/integrations/opensubtitles/)
- [anicompat](https://youtu.be/0Gl48lL7e9Y)
- [Eklenti Kodlama](https://www.youtube.com/watch?v=gWECdddixyA)

---

via : https://forum.sinetech.tr/
