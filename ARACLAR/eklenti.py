#!/usr/bin/env python3
# ! Bu araç @keyiflerolsun tarafından | @KekikAkademi için yazılmıştır.
"""CloudStream eklentileri için tek dosyalık araç (harici kütüphane gerektirmez).

Komutlar
--------
  liste    » Depodaki eklentileri sürüm / durum / mainUrl ile listeler
  dogrula  » Eklentilerin eksik veya hatalı kısımlarını raporlar
  yeni     » __Temel şablonundan yeni eklenti üretir

Örnekler
--------
  python3 ARACLAR/eklenti.py liste
  python3 ARACLAR/eklenti.py dogrula --sadece DiziBox
  python3 ARACLAR/eklenti.py dogrula --json > rapor.json
  python3 ARACLAR/eklenti.py yeni --ad DiziOrnek --site https://www.diziornek.com --tip TvSeries
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

KOK     = Path(__file__).resolve().parent.parent
SABLON  = KOK / "__Temel"

# ? Depo kökünde bulunan, eklenti olmayan klasörler
ATLANANLAR = {"__Temel", "ARACLAR", "gradle"}

# ? build.gradle.kts içindeki tvTypes -> Kotlin TvType karşılığı
TIPTEN_KOTLIN = {
    "Movie"       : "TvType.Movie",
    "TvSeries"    : "TvType.TvSeries",
    "Anime"       : "TvType.Anime",
    "AnimeMovie"  : "TvType.AnimeMovie",
    "OVA"         : "TvType.OVA",
    "Cartoon"     : "TvType.Cartoon",
    "Documentary" : "TvType.Documentary",
    "AsianDrama"  : "TvType.AsianDrama",
    "Live"        : "TvType.Live",
}

# ? Klasör adı -> dosya adı (şablon içindeki adlar)
SABLON_DOSYALARI = {
    "Temel.kt"       : "{ad}.kt",
    "TemelPlugin.kt" : "{ad}Plugin.kt",
    "TemelUtils.kt"  : "{ad}Utils.kt",
}

HATA  = "hata"
UYARI = "uyari"
BILGI = "bilgi"


# ----------------------------------------------------------------------------------------------------------
#  Konsol
# ----------------------------------------------------------------------------------------------------------
class Renk:
    KIRMIZI = "\033[91m"
    SARI    = "\033[93m"
    MAVI    = "\033[94m"
    YESIL   = "\033[92m"
    GRI     = "\033[90m"
    BITTI   = "\033[0m"

    @staticmethod
    def aktif(akis) -> bool:
        return hasattr(akis, "isatty") and akis.isatty()


def boya(metin: str, renk: str, aktif: bool) -> str:
    return f"{renk}{metin}{Renk.BITTI}" if aktif else metin


def log(simge: str, mesaj: str, aktif: bool = False, renk: str = "") -> None:
    etiket = boya(simge, renk, aktif) if renk else simge
    print(f"[{etiket}] {mesaj}")


# ----------------------------------------------------------------------------------------------------------
#  Eklenti okuma
# ----------------------------------------------------------------------------------------------------------
@dataclass
class Eklenti:
    ad      : str
    yol     : Path
    surum   : int | None        = None
    durum   : int | None        = None
    main_url: str | None        = None
    api_adi : str | None        = None
    api_yolu: Path | None       = None
    eklenti_yolu: Path | None   = None
    paketler: set[str]          = field(default_factory=set)
    aciklama: str | None        = None
    ikon    : str | None        = None
    tipler  : list[str]         = field(default_factory=list)
    hizli_arama: bool | None    = None
    quick_search_var: bool      = False
    cloudstream_blok: bool      = False
    kotlin_dosyalari: list[Path] = field(default_factory=list)

    @property
    def gradle(self) -> Path:
        return self.yol / "build.gradle.kts"


def _oku(yol: Path) -> str:
    try:
        return yol.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def eklenti_topla(klasor: Path) -> Eklenti | None:
    """Klasörü bir eklenti olarak okur, eklenti değilse None döner."""
    if not (klasor / "build.gradle.kts").exists():
        return None

    eklenti = Eklenti(ad=klasor.name, yol=klasor)
    eklenti.kotlin_dosyalari = sorted(klasor.rglob("*.kt"))

    # * build.gradle.kts
    gradle = _oku(eklenti.gradle)
    eklenti.cloudstream_blok = "cloudstream {" in gradle

    if surum := re.search(r"^\s*version\s*=\s*(\d+)", gradle, re.MULTILINE):
        eklenti.surum = int(surum[1])

    for anahtar, alan in (("description", "aciklama"), ("iconUrl", "ikon")):
        if bulunan := re.search(rf'{anahtar}\s*=\s*"([^"]*)"', gradle):
            setattr(eklenti, alan, bulunan[1])

    if durum := re.search(r"^\s*status\s*=\s*(\d+)", gradle, re.MULTILINE):
        eklenti.durum = int(durum[1])

    if tipler := re.search(r"tvTypes\s*=\s*listOf\(([^)]*)\)", gradle):
        eklenti.tipler = re.findall(r'"([^"]+)"', tipler[1])

    # * Kotlin dosyaları
    for dosya in eklenti.kotlin_dosyalari:
        icerik = _oku(dosya)

        if paket := re.search(r"^\s*package\s+([\w.]+)", icerik, re.MULTILINE):
            eklenti.paketler.add(paket[1])

        if "@CloudstreamPlugin" in icerik:
            eklenti.eklenti_yolu = dosya

        # ? Ana sayfa sınıfı: class X : MainAPI()  »  LiveStreamAPI/ExtractorApi hariç
        if ana_api := re.search(r"class\s+(\w+)\s*:\s*(MainAPI|LiveStreamAPI)\s*\(", icerik):
            eklenti.api_adi  = ana_api[1]
            eklenti.api_yolu = dosya

            if url := re.search(r'override\s+var\s+mainUrl\s*=\s*"([^"]*)"', icerik):
                eklenti.main_url = url[1]

        if re.search(r"override\s+suspend\s+fun\s+quickSearch\s*\(", icerik):
            eklenti.quick_search_var = True

    # * hasQuickSearch
    if eklenti.api_yolu:
        icerik = _oku(eklenti.api_yolu)
        if bulunan := re.search(r"hasQuickSearch\s*=\s*(true|false)", icerik):
            eklenti.hizli_arama = bulunan[1] == "true"

    return eklenti


def eklentileri_topla(sadece: Iterable[str] | None = None) -> list[Eklenti]:
    sadece_liste = {isim.lower() for isim in sadece} if sadece else None
    sonuc: list[Eklenti] = []

    for klasor in sorted(KOK.iterdir()):
        if not klasor.is_dir() or klasor.name.startswith(".") or klasor.name in ATLANANLAR:
            continue
        if sadece_liste and klasor.name.lower() not in sadece_liste:
            continue
        if (eklenti := eklenti_topla(klasor)):
            sonuc.append(eklenti)

    return sonuc


# ----------------------------------------------------------------------------------------------------------
#  liste
# ----------------------------------------------------------------------------------------------------------
DURUMLAR = {0: "Kapalı", 1: "Sağlam", 2: "Yavaş", 3: "Beta"}


def komut_liste(args: argparse.Namespace) -> int:
    eklentiler = eklentileri_topla(args.sadece)
    if not eklentiler:
        log("!", "Eklenti bulunamadı", args.renk)
        return 1

    genislik = max(len(eklenti.ad) for eklenti in eklentiler)

    log("i", f"{len(eklentiler)} eklenti bulundu", args.renk, Renk.MAVI)
    print(f"{'Eklenti'.ljust(genislik)}  {'Sürüm':>5}  {'Durum':<7}  {'Tip':<12}  mainUrl")
    print("-" * (genislik + 46))

    for eklenti in eklentiler:
        tip     = eklenti.tipler[0] if eklenti.tipler else "?"
        durum   = DURUMLAR.get(eklenti.durum, "?") if eklenti.durum is not None else "?"
        surum   = str(eklenti.surum) if eklenti.surum is not None else "?"
        mainurl = eklenti.main_url or boya("YOK", Renk.KIRMIZI, args.renk)

        print(f"{eklenti.ad.ljust(genislik)}  {surum:>5}  {durum:<7}  {tip:<12}  {mainurl}")

    return 0


# ----------------------------------------------------------------------------------------------------------
#  dogrula
# ----------------------------------------------------------------------------------------------------------
# ! CloudStream'de ERROR seviyesinde deprecated olan ve eklentileri etkileyen API'ler » (desen, mesaj, çözüm)
DEPRECATED_API = (
    (r"(?<![\w.])toRatingInt\s*\(",        "toRatingInt() ERROR seviyesinde deprecated", "Score.from10(...) kullan"),
    (r"this\.rating\s*=",                  "this.rating ERROR seviyesinde deprecated", "this.score = ... kullan"),
    (r"(?<![\w.])ExtractorLink\s*\(",      "ExtractorLink(...) yapıcısı ERROR seviyesinde deprecated", "newExtractorLink(source, name, url) { ... } kullan"),
    (r"(?<![\w.])Episode\s*\(",            "Episode(...) yapıcısı ERROR seviyesinde deprecated", "newEpisode(data) { ... } kullan"),
)


def deprecated_api_tara(icerik: str) -> list[tuple[str, str]]:
    """ERROR seviyesinde deprecated API kullanımını bulur (yorum satırları atlanır)."""
    bulgular: list[tuple[str, str]] = []

    for satir_no, satir in enumerate(icerik.splitlines(), start=1):
        # ? yorum ve dize içeriklerini temizle
        kod = re.sub(r'"[^"]*"', '""', satir)
        kod = kod.split("//")[0]
        if not kod.strip() or kod.lstrip().startswith("*"):
            continue

        # ? data class Episode(...) gibi kendi sınıf tanımlarını atla
        if re.search(r"class\s+$", kod[:kod.find("Episode")]) if "Episode(" in kod else False:
            continue

        for desen, mesaj, cozum in DEPRECATED_API:
            if re.search(desen, kod):
                bulgular.append((HATA, f"satır {satir_no} » {mesaj} » {cozum}"))

    return bulgular


def eklenti_denetle(eklenti: Eklenti) -> list[tuple[str, str]]:
    bulgular: list[tuple[str, str]] = []

    # * Dosya yapısı
    if not eklenti.cloudstream_blok:
        bulgular.append((HATA, "build.gradle.kts içinde 'cloudstream { }' bloğu yok"))

    if eklenti.surum is None:
        bulgular.append((HATA, "build.gradle.kts içinde 'version = N' satırı yok"))

    if not (eklenti.yol / "src" / "main" / "AndroidManifest.xml").exists():
        bulgular.append((UYARI, "src/main/AndroidManifest.xml dosyası yok"))

    if not eklenti.kotlin_dosyalari:
        bulgular.append((HATA, "Kotlin dosyası yok (*.kt)"))
        return bulgular

    # * Şablon yer tutucuları kalmış mı?
    for dosya in eklenti.kotlin_dosyalari:
        if yer_tutucu := re.findall(r"__[A-Z_]+__", _oku(dosya)):
            bulgular.append((HATA, f"{dosya.name} içinde doldurulmamış yer tutucu var: {', '.join(sorted(set(yer_tutucu)))}"))

    # * ERROR seviyesinde deprecated API kullanımı (derlemeyi kırar)
    for dosya in eklenti.kotlin_dosyalari:
        for seviye, mesaj in deprecated_api_tara(_oku(dosya)):
            bulgular.append((seviye, f"{dosya.name} {mesaj}"))

    # * Plugin giriş noktası
    if not eklenti.eklenti_yolu:
        bulgular.append((HATA, "@CloudstreamPlugin sınıfı yok (*Plugin.kt)"))
    else:
        icerik = _oku(eklenti.eklenti_yolu)
        if not re.search(r"register(MainAPI|ExtractorAPI|LiveStreamAPI)\s*\(", icerik):
            bulgular.append((UYARI, f"{eklenti.eklenti_yolu.name} içinde registerMainAPI/registerExtractorAPI çağrısı yok"))

    # * Ana API
    if not eklenti.api_yolu:
        bulgular.append((HATA, "'class X : MainAPI()' tanımı bulunamadı"))
    else:
        icerik = _oku(eklenti.api_yolu)

        if not eklenti.main_url:
            bulgular.append((HATA, f"{eklenti.api_yolu.name} içinde 'override var mainUrl' yok"))
        else:
            if eklenti.main_url.endswith("/"):
                bulgular.append((UYARI, f"mainUrl sonunda '/' var, KONTROL.py bunu siler » {eklenti.main_url}"))
            if eklenti.main_url.startswith("http://"):
                bulgular.append((UYARI, f"mainUrl https değil » {eklenti.main_url}"))
            if " " in eklenti.main_url or len(eklenti.main_url) < 10:
                bulgular.append((HATA, f"mainUrl geçersiz görünüyor » {eklenti.main_url!r}"))

        if not re.search(r'override\s+var\s+name\s*=\s*"', icerik):
            bulgular.append((UYARI, "Ana API içinde 'override var name' yok"))

        if eklenti.hizli_arama is True and not eklenti.quick_search_var:
            bulgular.append((UYARI, "hasQuickSearch = true ama quickSearch override edilmemiş"))
        if eklenti.hizli_arama is False and eklenti.quick_search_var:
            bulgular.append((BILGI, "hasQuickSearch = false ama quickSearch fonksiyonu tanımlı (kullanılmaz)"))

        if not re.search(r"override\s+suspend\s+fun\s+search\s*\(", icerik):
            bulgular.append((HATA, "search() fonksiyonu yok"))

        if not re.search(r"override\s+suspend\s+fun\s+loadLinks\s*\(", icerik):
            bulgular.append((HATA, "loadLinks() fonksiyonu yok"))

        if not eklenti.tipler:
            bulgular.append((UYARI, "build.gradle.kts içinde tvTypes tanımlı değil"))
        elif "supportedTypes" not in icerik:
            bulgular.append((UYARI, "tvTypes var ama supportedTypes tanımlı değil"))

    # * Paket adı ile klasör yolu
    for paket in eklenti.paketler:
        beklenen = eklenti.yol / "src" / "main" / "kotlin" / Path(*paket.split("."))
        if not beklenen.exists():
            bulgular.append((HATA, f"'{paket}' paketi ile klasör yolu uyuşmuyor » {beklenen.relative_to(KOK)} yok"))

    if len(eklenti.paketler) > 1:
        bulgular.append((BILGI, f"Birden fazla paket kullanılmış: {', '.join(sorted(eklenti.paketler))}"))

    # * cloudstream bloğu alanları
    if eklenti.cloudstream_blok:
        for alan, etiket in (("aciklama", "description"), ("ikon", "iconUrl")):
            if not getattr(eklenti, alan):
                bulgular.append((UYARI, f"build.gradle.kts içinde {etiket} yok"))
        if eklenti.durum is None:
            bulgular.append((BILGI, "build.gradle.kts içinde status yok (varsayılan 3 » Beta)"))

    return bulgular


def capraz_denetim(eklentiler: list[Eklenti]) -> dict[str, list[tuple[str, str]]]:
    """Eklentiler arası çakışmaları bulur."""
    bulgular: dict[str, list[tuple[str, str]]] = {eklenti.ad: [] for eklenti in eklentiler}

    urller: dict[str, list[str]] = {}
    isimler: dict[str, list[str]] = {}

    for eklenti in eklentiler:
        if eklenti.main_url:
            urller.setdefault(eklenti.main_url.lower(), []).append(eklenti.ad)
        if eklenti.api_adi:
            isimler.setdefault(eklenti.api_adi.lower(), []).append(eklenti.ad)

    for url, adlar in urller.items():
        if len(adlar) > 1:
            for ad in adlar:
                digerleri = ", ".join(sorted(set(adlar) - {ad}))
                bulgular[ad].append((UYARI, f"mainUrl başka eklentiyle aynı » {url} ({digerleri})"))

    for isim, adlar in isimler.items():
        if len(adlar) > 1:
            for ad in adlar:
                bulgular[ad].append((UYARI, f"'{isim}' sınıf adı başka eklentide de var » {', '.join(sorted(set(adlar)))}"))

    # * Klasör adı ile API sınıfı tutarlılığı
    for eklenti in eklentiler:
        if eklenti.api_adi and eklenti.api_adi.lower() != eklenti.ad.lower():
            norm_klasor = eklenti.ad.replace("İ", "I").replace("ı", "i")
            if norm_klasor.lower() != eklenti.api_adi.lower():
                bulgular[eklenti.ad].append((BILGI, f"Klasör adı ({eklenti.ad}) ile sınıf adı ({eklenti.api_adi}) farklı"))

        # * iconUrl domain'i ile mainUrl karşılaştırması
        if eklenti.ikon and eklenti.main_url and "domain=" in eklenti.ikon:
            ikon_domain = urlparse(eklenti.ikon.split("domain=")[-1].split("&")[0].replace("https://", "").replace("http://", "")).netloc or eklenti.ikon.split("domain=")[-1].split("&")[0]
            site_domain = urlparse(eklenti.main_url).netloc
            if ikon_domain and site_domain and ikon_domain.split(".")[-2:] != site_domain.split(".")[-2:]:
                bulgular[eklenti.ad].append((BILGI, f"iconUrl domaini ({ikon_domain}) mainUrl ({site_domain}) ile uyuşmuyor"))

    return bulgular


def komut_dogrula(args: argparse.Namespace) -> int:
    eklentiler = eklentileri_topla(args.sadece)
    if not eklentiler:
        log("!", "Eklenti bulunamadı", args.renk)
        return 1

    caprazlar = capraz_denetim(eklentiler)

    rapor: dict[str, dict[str, list[str]]] = {}
    toplam = {HATA: 0, UYARI: 0, BILGI: 0}

    for eklenti in eklentiler:
        bulgular = sorted(eklenti_denetle(eklenti) + caprazlar.get(eklenti.ad, []), key=lambda b: [HATA, UYARI, BILGI].index(b[0]))
        rapor[eklenti.ad] = {seviye: [m for s, m in bulgular if s == seviye] for seviye in (HATA, UYARI, BILGI)}

        for seviye, _ in bulgular:
            toplam[seviye] += 1

        if not bulgular:
            continue

        if not args.sessiz:
            print()
            log("»", boya(eklenti.ad, Renk.MAVI, args.renk), args.renk)
            for seviye, mesaj in bulgular:
                simge, renk = {
                    HATA : ("x", Renk.KIRMIZI),
                    UYARI: ("!", Renk.SARI),
                    BILGI: ("i", Renk.GRI),
                }[seviye]
                log(simge, mesaj, args.renk, renk)

    if args.json:
        print(json.dumps(rapor, ensure_ascii=False, indent=2))

    if not args.sessiz:
        print()
        log("i", f"{len(eklentiler)} eklenti denetlendi » {toplam[HATA]} hata, {toplam[UYARI]} uyarı, {toplam[BILGI]} bilgi", args.renk, Renk.MAVI)

    if toplam[HATA] or (args.kati and toplam[UYARI]):
        return 1

    if not args.sessiz:
        log("+", "Tüm eklentiler sağlıklı görünüyor", args.renk, Renk.YESIL)

    return 0


# ----------------------------------------------------------------------------------------------------------
#  yeni
# ----------------------------------------------------------------------------------------------------------
def sablon_dosyalari() -> list[tuple[Path, str]]:
    """Şablondaki (kaynak, hedef şablonu) çiftlerini döner."""
    dosyalar: list[tuple[Path, str]] = []

    for dosya in sorted(SABLON.rglob("*")):
        if dosya.is_dir():
            continue
        if dosya.name == "OKUBENI.md":
            continue

        hedef = str(dosya.relative_to(SABLON)).replace("\\", "/")

        if dosya.name in SABLON_DOSYALARI:
            hedef = hedef.replace(dosya.name, SABLON_DOSYALARI[dosya.name])

        dosyalar.append((dosya, hedef))

    return dosyalar


def komut_yeni(args: argparse.Namespace) -> int:
    ad = args.ad

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ad):
        log("x", f"'{ad}' geçerli bir Kotlin sınıf adı değil (harf ile başlamalı, Türkçe karakter içermemeli)", args.renk, Renk.KIRMIZI)
        return 1

    if not re.fullmatch(r"[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)+", args.paket):
        log("x", f"'{args.paket}' geçerli bir paket adı değil (ör. com.keyiflerolsun)", args.renk, Renk.KIRMIZI)
        return 1

    site = args.site.rstrip("/")
    if not re.match(r"^[a-zA-Z][\w+.-]*://", site):
        log("x", f"'{args.site}' şema içermiyor, ör. https://www.site.com", args.renk, Renk.KIRMIZI)
        return 1

    host = urlparse(site).netloc or site.split("//")[-1]
    if not host:
        log("x", f"'{args.site}' içinden alan adı okunamadı", args.renk, Renk.KIRMIZI)
        return 1

    if not all(tip in TIPTEN_KOTLIN for tip in args.tip):
        gecersiz = [tip for tip in args.tip if tip not in TIPTEN_KOTLIN]
        log("x", f"Geçersiz tip: {', '.join(gecersiz)} » Seçenekler: {', '.join(TIPTEN_KOTLIN)}", args.renk, Renk.KIRMIZI)
        return 1

    hedef_klasor = (Path(args.hedef).resolve() / ad)
    if hedef_klasor.exists() and not args.zorla:
        log("x", f"{hedef_klasor} zaten var, üzerine yazmak için --zorla kullan", args.renk, Renk.KIRMIZI)
        return 1

    yer_tutucular = {
        "__AD__"         : ad,
        "__SITE__"       : site,
        "__PAKET__"      : args.paket,
        "__DIL__"        : args.dil,
        "__ACIKLAMA__"   : args.aciklama or f"{ad} » {host} adresindeki içerikler için CloudStream sağlayıcısı.",
        "__YAZARLAR__"   : ", ".join(f'"{yazar}"' for yazar in args.yazar),
        "__TIPLER__"     : ", ".join(TIPTEN_KOTLIN[tip] for tip in args.tip),
        "__TV_TIPLERI__" : ", ".join(f'"{tip}"' for tip in args.tip),
        "__IKON__"       : args.ikon or f"https://www.google.com/s2/favicons?domain={host}&sz=%size%",
    }

    if not SABLON.exists():
        log("x", f"Şablon klasörü bulunamadı » {SABLON}", args.renk, Renk.KIRMIZI)
        return 1

    log("~", f"{ad} » {site} ({', '.join(args.tip)})", args.renk, Renk.MAVI)

    yazilanlar: list[Path] = []

    for kaynak, hedef in sablon_dosyalari():
        hedef_yolu = hedef_klasor / hedef

        for yer_tutucu, deger in yer_tutucular.items():
            hedef_yolu = Path(str(hedef_yolu).replace(yer_tutucu, deger))

        icerik = _oku(kaynak)
        for yer_tutucu, deger in yer_tutucular.items():
            icerik = icerik.replace(yer_tutucu, deger)

        if args.kuru:
            log("+", f"(kuru) {hedef_yolu.relative_to(Path(args.hedef).resolve())}", args.renk, Renk.GRI)
            continue

        hedef_yolu.parent.mkdir(parents=True, exist_ok=True)
        hedef_yolu.write_text(icerik, encoding="utf-8")
        yazilanlar.append(hedef_yolu)
        log("+", f"{hedef_yolu.relative_to(Path(args.hedef).resolve())}", args.renk, Renk.GRI)

    if args.kuru:
        log("i", "Kuru çalıştırma bitti, hiçbir dosya yazılmadı", args.renk, Renk.MAVI)
        return 0

    if yazilanlar and not args.sessiz:
        eklenti = eklenti_topla(hedef_klasor)
        bulgular = eklenti_denetle(eklenti) if eklenti else [(HATA, "Eklenti okunamadı")]

        if bulgular:
            print()
            log("!", "Yeni eklentide dikkat edilecekler", args.renk, Renk.SARI)
            for seviye, mesaj in bulgular:
                simge, renk = {HATA: ("x", Renk.KIRMIZI), UYARI: ("!", Renk.SARI), BILGI: ("i", Renk.GRI)}[seviye]
                log(simge, mesaj, args.renk, renk)

        print()
        log("i", "Sonraki adımlar", args.renk, Renk.MAVI)
        log("»", f"Kotlin içindeki HTML seçicilerini sitenin kaynak koduna göre güncelle", args.renk, Renk.GRI)
        log("»", f"mainUrl dışındaki tüm değişkenleri mainUrl'den türet (sabit adres yazma)", args.renk, Renk.GRI)
        log("»", f"python3 ARACLAR/eklenti.py dogrula --sadece {ad}", args.renk, Renk.GRI)
        log("»", f"Yerelde derle » ./gradlew :{ad}:make", args.renk, Renk.GRI)
        log("»", "settings.gradle.kts yeni klasörü otomatik algılar, ek dosya değişikliği gerekmez", args.renk, Renk.GRI)

    log("+", f"{ad} eklentisi hazır » {hedef_klasor}", args.renk, Renk.YESIL)
    return 0


# ----------------------------------------------------------------------------------------------------------
#  CLI
# ----------------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog        = "eklenti.py",
        description = "CloudStream eklenti aracı » liste / dogrula / yeni",
        formatter_class = argparse.RawDescriptionHelpFormatter,
    )
    alt_komutlar = parser.add_subparsers(dest="komut", required=True)

    # * liste
    liste = alt_komutlar.add_parser("liste", help="Eklentileri listeler")
    liste.add_argument("--sadece", nargs="+", help="Sadece verilen eklentiler")
    liste.set_defaults(func=komut_liste)

    # * dogrula
    dogrula = alt_komutlar.add_parser("dogrula", help="Eklentileri denetler")
    dogrula.add_argument("--sadece", nargs="+", help="Sadece verilen eklentiler")
    dogrula.add_argument("--json", action="store_true", help="Raporu JSON olarak da yazdır")
    dogrula.add_argument("--kati", action="store_true", help="Uyarılar da hata saysın (CI için)")
    dogrula.add_argument("--sessiz", action="store_true", help="Sadece rapor/çıkış kodu")
    dogrula.set_defaults(func=komut_dogrula)

    # * yeni
    yeni = alt_komutlar.add_parser("yeni", help="Şablondan yeni eklenti üretir")
    yeni.add_argument("--ad", required=True, help="Eklenti / sınıf adı (ör. DiziOrnek)")
    yeni.add_argument("--site", required=True, help="Site adresi (ör. https://www.diziornek.com)")
    yeni.add_argument("--tip", nargs="+", default=["TvSeries"], choices=list(TIPTEN_KOTLIN), help="İçerik tipi")
    yeni.add_argument("--yazar", nargs="+", default=["keyiflerolsun"], help="Yazar(lar)")
    yeni.add_argument("--aciklama", help="cloudstream { description }")
    yeni.add_argument("--paket", default="com.keyiflerolsun", help="Kotlin paketi")
    yeni.add_argument("--dil", default="tr", help="İçerik dili")
    yeni.add_argument("--ikon", help="iconUrl (varsayılan: sitenin favicon'u)")
    yeni.add_argument("--hedef", default=str(KOK), help="Üretilecek dizin (varsayılan: depo kökü)")
    yeni.add_argument("--zorla", action="store_true", help="Var olan klasörün üzerine yaz")
    yeni.add_argument("--kuru", action="store_true", help="Dosya yazmadan ne yapacağını göster")
    yeni.set_defaults(func=komut_yeni)

    args = parser.parse_args(argv)
    args.renk = Renk.aktif(sys.stdout)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
