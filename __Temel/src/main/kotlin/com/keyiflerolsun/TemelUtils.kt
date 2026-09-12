// ! Bu araç @keyiflerolsun tarafından | @KekikAkademi için yazılmıştır.
// ! Şablon yardımcıları » İhtiyacın olmayanları sil, kalanları kendi eklentinde kullan.

package __PAKET__

import org.jsoup.nodes.Element
import com.lagradost.cloudstream3.*
import com.lagradost.cloudstream3.utils.*

/**
 * "7.8/10", "7,8" gibi metinleri CloudStream puanına (Score) çevirir.
 * ?  Kullanım : element.text().toPuan()
 * !  Eski `toRatingInt()` ERROR seviyesinde deprecated, `Score.from10(...)` kullanılır.
 */
fun String?.toPuan(): Score? = this?.let { metin ->
    val sayi = Regex("""(\d+[.,]?\d*)""").find(metin)?.groupValues?.get(1)?.replace(",", ".")

    // ? 10 üzerinden puanlanan siteler için » Score.from10("8.5")
    Score.from10(sayi)
}

/**
 * "1s 45dk", "105 dk", "2 saat" gibi süreleri dakikaya çevirir.
 * ?  Kullanım : element.text().toSure()
 */
fun String?.toSure(): Int? = this?.let { metin ->
    val saat = Regex("""(\d+)\s*(s|sa|saat)""").find(metin)?.groupValues?.get(1)?.toIntOrNull() ?: 0
    val dk   = Regex("""(\d+)\s*(d|dk|dakika)""").find(metin)?.groupValues?.get(1)?.toIntOrNull() ?: 0

    (saat * 60 + dk).takeIf { it > 0 }
}

/**
 * Görsel adresini bulur » lazy-load kullanan sitelerde data-src, yoksa src.
 * ?  Kullanım : fixUrlNull(element.toGorsel())   // ! göreli adresi eklenti içinde tamamla
 */
fun Element.toGorsel(): String? {
    val img = this.selectFirst("img") ?: return null

    return img.attr("data-src").ifBlank { img.attr("src") }.trim().ifBlank { null }
}

/**
 * Boş bırakılabilecek SEÇİCİLER için kısa yol.
 * ?  Kullanım : document.toMetin("div.description, div.plot")
 */
fun Element.toMetin(secici: String): String? = this.selectFirst(secici)?.text()?.trim()?.ifBlank { null }

/**
 * Sayısal alan için kısa yol.
 * ?  Kullanım : document.toSayi("span.year")
 */
fun Element.toSayi(secici: String): Int? = this.selectFirst(secici)?.text()?.filter { it.isDigit() }?.toIntOrNull()
