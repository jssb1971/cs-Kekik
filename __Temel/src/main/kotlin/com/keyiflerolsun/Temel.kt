// ! Bu araç @keyiflerolsun tarafından | @KekikAkademi için yazılmıştır.
// ! »---»---»  ŞABLON (__Temel)  «---«---«
// !
// ! Yeni eklenti üretmek için :
// !     python3 ARACLAR/eklenti.py yeni --ad EklentiAdi --site https://www.site.com --tip TvSeries
// !
// ! Elle kopyalayacaksan : klasörü çoğalt, ardından yer tutucuları değiştir →
// !     __AD__        » Sınıf / dosya adı        (ör. DiziBox)
// !     __SITE__      » mainUrl                  (ör. https://www.dizibox.live)
// !     __PAKET__     » package adı              (ör. com.keyiflerolsun)
// !     __ACIKLAMA__  » build.gradle.kts açıklaması
// !     __YAZARLAR__  » build.gradle.kts yazarları
// !     __TIPLER__    » supportedTypes  (ör. TvType.Movie, TvType.TvSeries)
// !     __TV_TIPLERI__ » tvTypes        (ör. "Movie", "TvSeries")
// !     __DIL__       » lang             (ör. tr)
// !     __IKON__      » iconUrl          (ör. https://www.google.com/s2/favicons?domain=www.site.com&sz=%size%)

package __PAKET__

import android.util.Log
import org.jsoup.nodes.Element
import com.lagradost.cloudstream3.*
import com.lagradost.cloudstream3.utils.*
import com.lagradost.cloudstream3.LoadResponse.Companion.addActors
import com.lagradost.cloudstream3.LoadResponse.Companion.addTrailer

class __AD__ : MainAPI() {
    /* ----------------------------------------------------------------------------------------------------------
     *  1) KİMLİK
     *  ?  mainUrl         » KONTROL.py bu satırı okuyup yönlendirmeleri takip eder, adresi tek yerde tut
     *  ?  supportedTypes  » Movie / TvSeries / Anime / Cartoon / Documentary / AsianDrama / Live
     * ------------------------------------------------------------------------------------------------------- */
    override var mainUrl        = "__SITE__"
    override var name           = "__AD__"
    override val hasMainPage    = true
    override var lang           = "__DIL__"
    override val hasQuickSearch = false
    override val supportedTypes = setOf(__TIPLER__)

    /* ----------------------------------------------------------------------------------------------------------
     *  2) ANA SAYFA
     *  ?  mainPageOf("kategori_adresi" to "Menüde görünecek isim")
     *  ?  Adresteki SAYFA ifadesi, sayfa numarası ile değiştirilir
     *  ?  Sadece tek kategori varsa mainPage + getMainPage yerine mainPageOf da kullanılabilir
     * ------------------------------------------------------------------------------------------------------- */
    override val mainPage = mainPageOf(
        "${mainUrl}/"                   to "Son Eklenenler",
        "${mainUrl}/tur/aksiyon/SAYFA/" to "Aksiyon",
        "${mainUrl}/tur/komedi/SAYFA/"  to "Komedi",
        "${mainUrl}/tur/dram/SAYFA/"    to "Dram"
    )

    override suspend fun getMainPage(page: Int, request: MainPageRequest): HomePageResponse {
        val url      = request.data.replace("SAYFA", "$page")
        val document = app.get(url).document
        val home     = document.select("div.item").mapNotNull { it.toMainPageResult() }

        return newHomePageResponse(request.name, home)
    }

    private fun Element.toMainPageResult(): SearchResponse? {
        val title = this.selectFirst("h3 a, div.title a, a.title")?.text()?.trim() ?: return null
        val href  = fixUrlNull(this.selectFirst("a")?.attr("href"))                ?: return null
        val posterUrl = fixUrlNull(
            this.selectFirst("img")?.let { it.attr("data-src").ifBlank { it.attr("src") } }
        )

        // ! Dizi sitesinde TvType.TvSeries, film sitesinde TvType.Movie olmalı
        return newTvSeriesSearchResponse(title, href, TvType.TvSeries) { this.posterUrl = posterUrl }
    }

    /* ----------------------------------------------------------------------------------------------------------
     *  3) ARAMA
     *  ?  quickSearch » tam arama sonucu gelene kadar gösterilen öneriler
     *  ?  hasQuickSearch = true ise quickSearch override edilmeli, aksi halde search çağrılır
     * ------------------------------------------------------------------------------------------------------- */
    override suspend fun search(query: String): List<SearchResponse> {
        val document = app.get("${mainUrl}/?s=${query}").document

        return document.select("div.item, div.result-item").mapNotNull { it.toSearchResult() }
    }

    private fun Element.toSearchResult(): SearchResponse? {
        val title = this.selectFirst("h3 a, div.title a, a.title")?.text()?.trim() ?: return null
        val href  = fixUrlNull(this.selectFirst("a")?.attr("href"))                ?: return null
        val posterUrl = fixUrlNull(
            this.selectFirst("img")?.let { it.attr("data-src").ifBlank { it.attr("src") } }
        )

        return newTvSeriesSearchResponse(title, href, TvType.TvSeries) { this.posterUrl = posterUrl }
    }

    override suspend fun quickSearch(query: String): List<SearchResponse> = search(query)

    /* ----------------------------------------------------------------------------------------------------------
     *  4) DETAY
     *  ?  Film     » newMovieLoadResponse(dizin_adı, url, TvType.Movie, veri) { ... }
     *  ?  Dizi     » newTvSeriesLoadResponse(dizin_adı, url, TvType.TvSeries, bölümler) { ... }
     *  ?  Live/TV  » newLiveStreamLoadResponse(dizin_adı, url, veri) { ... }
     * ------------------------------------------------------------------------------------------------------- */
    override suspend fun load(url: String): LoadResponse? {
        val document = app.get(url).document

        val title       = document.selectFirst("h1, div.entry-title")?.text()?.trim() ?: return null
        val poster      = fixUrlNull(document.selectFirst("div.poster img, meta[property=og:image]")?.let {
            it.attr("content").ifBlank { it.attr("src") }
        })
        val description = document.selectFirst("div.description, div.wp-content p")?.text()?.trim()
        val year        = document.selectFirst("span.year, a.year")?.text()?.trim()?.toIntOrNull()
        val tags        = document.select("div.genres a, div.tags a").map { it.text() }
        val score       = document.selectFirst("span.rating, span.imdb")?.text()?.trim()?.toPuan()
        val actors      = document.select("div.cast a, span.actors a").map { Actor(it.text()) }
        val trailer     = document.selectFirst("iframe[src*=youtube], iframe[src*=trailer]")?.attr("src")
        val recommendations = document.select("div.related div.item").mapNotNull { it.toRecommendationResult() }

        // * Bölümler yoksa film gibi davran
        val episodes = document.select("div.episodes div.episode, div.bolumust").mapNotNull {
            val epName = it.selectFirst("a, div.baslik")?.text()?.trim() ?: return@mapNotNull null
            val epHref = fixUrlNull(it.selectFirst("a")?.attr("href")) ?: return@mapNotNull null

            newEpisode(epHref) {
                this.name    = epName
                this.season  = Regex("""(\d+)\.\s*Sezon""").find(epName)?.groupValues?.get(1)?.toIntOrNull() ?: 1
                this.episode = Regex("""(\d+)\.\s*Bölüm""").find(epName)?.groupValues?.get(1)?.toIntOrNull()
            }
        }

        if (episodes.isEmpty()) {
            return newMovieLoadResponse(title, url, TvType.Movie, url) {
                this.posterUrl       = poster
                this.plot            = description
                this.year            = year
                this.tags            = tags
                this.score           = score
                this.recommendations = recommendations
                addActors(actors)
                addTrailer(trailer)
            }
        }

        return newTvSeriesLoadResponse(title, url, TvType.TvSeries, episodes) {
            this.posterUrl       = poster
            this.plot            = description
            this.year            = year
            this.tags            = tags
            this.score           = score
            this.recommendations = recommendations
            addActors(actors)
            addTrailer(trailer)
        }
    }

    private fun Element.toRecommendationResult(): SearchResponse? {
        val title     = this.selectFirst("a")?.attr("title").ifBlank { this.selectFirst("h3, a")?.text() } ?: return null
        val href      = fixUrlNull(this.selectFirst("a")?.attr("href")) ?: return null
        val posterUrl = fixUrlNull(
            this.selectFirst("img")?.let { it.attr("data-src").ifBlank { it.attr("src") } }
        )

        return newTvSeriesSearchResponse(title, href, TvType.TvSeries) { this.posterUrl = posterUrl }
    }

    /* ----------------------------------------------------------------------------------------------------------
     *  5) KAYNAKLAR
     *  ?  Altyazı   » subtitleCallback.invoke(SubtitleFile(lang = "...", url = "..."))
     *  ?  Video     » loadExtractor(iframe, "${mainUrl}/", subtitleCallback, callback)
     *  ?  M3U8/MP4  » callback.invoke(newExtractorLink(source, name, url) { referer = ...; quality = ...; type = ExtractorLinkType.M3U8 })
     *  ?  Özel player varsa » ExtractorApi sınıfı yaz ve Plugin.kt içinde registerExtractorAPI(...) ile kaydet
     * ------------------------------------------------------------------------------------------------------- */
    override suspend fun loadLinks(data: String, isCasting: Boolean, subtitleCallback: (SubtitleFile) -> Unit, callback: (ExtractorLink) -> Unit): Boolean {
        Log.d("__AD__", "data » $data")
        val document = app.get(data).document

        val iframes = document.select("iframe[src], div#player iframe").map { it.attr("src") }
        if (iframes.isEmpty()) return false

        for (iframe in iframes) {
            val videoUrl = fixUrl(iframe)
            loadExtractor(videoUrl, "${mainUrl}/", subtitleCallback, callback)
        }

        return true
    }

    /* ----------------------------------------------------------------------------------------------------------
     *  * CloudFlare koruması olan siteler için (DiziBox.kt'deki kullanımın aynısı)
     * ----------------------------------------------------------------------------------------------------------
     *  private val cloudflareKiller by lazy { CloudflareKiller() }
     *  private val interceptor      by lazy { CloudflareInterceptor(cloudflareKiller) }
     *
     *  class CloudflareInterceptor(private val cloudflareKiller: CloudflareKiller): Interceptor {
     *      override fun intercept(chain: Interceptor.Chain): Response {
     *          val request  = chain.request()
     *          val response = chain.proceed(request)
     *          val doc      = Jsoup.parse(response.peekBody(1024 * 1024).string())
     *
     *          if (doc.text().contains("Güvenlik taramasından geçiriliyorsunuz. Lütfen bekleyiniz..")) {
     *              return cloudflareKiller.intercept(chain)
     *          }
     *
     *          return response
     *      }
     *  }
     *
     *  » Çağırırken : app.get(url, interceptor = interceptor)
     *  » Gerekli import'lar : com.lagradost.cloudstream3.network.CloudflareKiller, okhttp3.Interceptor, okhttp3.Response, org.jsoup.Jsoup
     *  » Yavaş sitelerde sıralı yükleme : override var sequentialMainPage = true
     * ------------------------------------------------------------------------------------------------------- */
}
