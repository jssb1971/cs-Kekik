// ! Bu araç @keyiflerolsun tarafından | @KekikAkademi için yazılmıştır.
// ! Şablon » Her eklentinin bir *Plugin.kt dosyası olmak zorundadır, sınıf adı dosya adıyla aynı olmalı.

package __PAKET__

import android.content.Context
import com.lagradost.cloudstream3.plugins.CloudstreamPlugin
import com.lagradost.cloudstream3.plugins.Plugin

@CloudstreamPlugin
class __AD__Plugin : Plugin() {
    override fun load(context: Context) {
        registerMainAPI(__AD__())

        // ! Aynı eklentide birden fazla sağlayıcı varsa hepsini burada kaydet
        // registerMainAPI(__AD__Yedek())

        // ! Özel extractor (player) varsa burada kaydet
        // registerExtractorAPI(__AD__Extractor())
    }
}
