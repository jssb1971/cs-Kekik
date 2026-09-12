#!/usr/bin/env python3
# ! Bu araç @keyiflerolsun tarafından | @KekikAkademi için yazılmıştır.
"""CloudStream API göç aracı » Eski (ERROR seviyesinde deprecated) API'leri yenisine çevirir.

CloudStream, 2026 Temmuz'undan itibaren bazı API'leri `DeprecationLevel.ERROR` seviyesine aldı.
Bu seviyedeki kullanımlar derlemeyi tamamen kırar (ör. toRatingInt, load yanıtındaki rating,
ExtractorLink yapıcısı, Episode yapıcısı). Bu araç depodaki kullanımları yeni API'ye taşır.

Dönüşümler
----------
  X.toRatingInt()     » Score.from10(X)             (eski puan sistemi)
  this.rating = ...   » this.score = ...            (load/episode yanıtı, hizalama korunur)
  ExtractorLink(...)  » newExtractorLink(...) { }   (isM3u8 » type = ExtractorLinkType.M3U8)
  Episode(...)        » newEpisode(...) { }         (data ilk argüman + lambda gövdesi)

Kullanım
--------
  python3 ARACLAR/goc.py                       # kuru çalıştırma, sadece diff gösterir
  python3 ARACLAR/goc.py --uygula              # değişiklikleri dosyalara yazar
  python3 ARACLAR/goc.py --dosya DiziBox.kt    # tek dosya
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import sys
from dataclasses import dataclass, field

KOK        = pathlib.Path(__file__).resolve().parent.parent
ATLANANLAR = {".git", "build", ".gradle", "ARACLAR", "__Temel"}

# ? newExtractorLink parametresi yerine lambda gövdesine yazılacak alanlar
LAMBDA_ALANLARI = ("referer", "quality", "headers", "extractorData")

# ? Eski/yeni ExtractorLink konumsal argüman sırası
KONUMSAL_ALANLAR = ("source", "name", "url", "referer", "quality", "isM3u8", "headers", "extractorData", "isDash")


# ----------------------------------------------------------------------------------------------------------
#  Yardımcılar
# ----------------------------------------------------------------------------------------------------------
def dize_sonu(metin: str, baslangic: int) -> int:
    """baslangic konumundaki tırnaktan sonraki tırnağın konumunu döner (kaçış destekli)."""
    if metin[baslangic:baslangic + 3] == '"""':
        son = metin.find('"""', baslangic + 3)
        return len(metin) - 1 if son == -1 else son + 2

    tirnak = metin[baslangic]
    i = baslangic + 1
    while i < len(metin):
        if metin[i] == "\\":
            i += 2
            continue
        if metin[i] == tirnak:
            return i
        i += 1

    return len(metin) - 1


def eslesmeli_parantez(metin: str, acilis: int) -> int:
    """acilis konumundaki '(' karakterine karşılık gelen ')' konumunu döner."""
    derinlik = 0
    i = acilis
    while i < len(metin):
        karakter = metin[i]
        if karakter == '"':
            i = dize_sonu(metin, i)
        elif karakter == "(":
            derinlik += 1
        elif karakter == ")":
            derinlik -= 1
            if derinlik == 0:
                return i
        i += 1

    return -1


def ust_duzey_ayir(icerik: str) -> list[str]:
    """Parantez ve dizeleri gözeterek üst düzey virgülle ayırır."""
    parcalar : list[str] = []
    derinlik  = 0
    baslangic = 0
    i         = 0

    while i < len(icerik):
        karakter = icerik[i]
        if karakter == '"':
            i = dize_sonu(icerik, i)
        elif karakter in "([{":
            derinlik += 1
        elif karakter in ")]}":
            derinlik -= 1
        elif karakter == "," and derinlik == 0:
            parcalar.append(icerik[baslangic:i])
            baslangic = i + 1
        i += 1

    parcalar.append(icerik[baslangic:])
    return [parca.strip() for parca in parcalar if parca.strip()]


def alici_araligi(metin: str, bitis: int) -> tuple[int, str] | None:
    """`bitis` konumunda biten ifadenin alıcısını bulur » (başlangıç, metin)

    Çok satırlı zincirleri ( `?.` ile devam edenler ) de destekler.
    """
    i        = bitis
    derinlik = 0

    while i >= 0:
        karakter = metin[i]

        if karakter == '"':
            j = i - 1
            while j >= 0:
                if metin[j] == karakter and metin[j - 1] != "\\":
                    break
                j -= 1
            i = j - 1
            continue

        if karakter in ")]}":
            derinlik += 1
        elif karakter in "([{":
            if derinlik == 0:
                break
            derinlik -= 1
        elif derinlik == 0:
            if karakter == "\n":
                # ? zincir sonraki satırda `?.` ile devam ediyorsa geç
                if metin[i + 1:].lstrip().startswith((".", "?.")):
                    i -= 1
                    continue
                break
            if karakter not in " \t" and not (karakter.isalnum() or karakter in "_.$?!"):
                break

        i -= 1

    baslangic = i + 1
    ham       = metin[baslangic:bitis + 1]
    bosluk    = ham[:len(ham) - len(ham.lstrip())]
    alici     = ham.strip()

    return (baslangic, bosluk, alici) if alici else None


def yorum_satiri_mi(metin: str, konum: int) -> bool:
    """Eşleşme bir yorumun içinde mi? (dize içindeki // ve /* sayılmaz)"""
    satir_basi = metin.rfind("\n", 0, konum) + 1
    i = satir_basi

    while i < konum:
        if metin[i] == '"':
            i = dize_sonu(metin, i)
        elif metin[i:i + 2] in ("//", "/*"):
            return True
        i += 1

    return False


def girinti_bul(metin: str, konum: int) -> str:
    satir = metin[:konum].split("\n")[-1]
    return " " * (len(satir) - len(satir.lstrip()))


def adli_argumanlar(icerik: str) -> dict[str, str] | None:
    """`anahtar = değer` listesini sözlüğe çevirir; konumsal argüman varsa None döner."""
    adli: dict[str, str] = {}
    for arguman in ust_duzey_ayir(icerik):
        if not re.match(r"^\w+\s*=", arguman):
            return None
        anahtar, deger = arguman.split("=", 1)
        adli[anahtar.strip()] = deger.strip()
    return adli


def konumsal_argumanlar(icerik: str) -> dict[str, str] | None:
    """Konumsal ExtractorLink argümanlarını isimlendirir (6-9 argüman desteklenir)."""
    parcalar = ust_duzey_ayir(icerik)
    if not 6 <= len(parcalar) <= 9:
        return None

    adli: dict[str, str] = {}
    for sira, parca in enumerate(parcalar):
        alan = KONUMSAL_ALANLAR[sira]
        # ? 6. argüman ya isM3u8 (bool) ya da type (ExtractorLinkType.X / INFER_TYPE)
        if alan == "isM3u8" and parca not in ("true", "false"):
            alan, parca = "type", parca
        adli[alan] = parca

    return adli


def import_ekle(metin: str, satir: str) -> str:
    """Import satırını, cloudstream importlarının bittiği yere ekler."""
    importlar = list(re.finditer(r"^import .*$", metin, re.MULTILINE))
    if not importlar:
        return metin

    yer = next(
        (m for m in reversed(importlar) if m.group(0).startswith("import com.lagradost.")),
        importlar[-1],
    )
    return metin[:yer.end()] + "\n" + satir + metin[yer.end():]


# ----------------------------------------------------------------------------------------------------------
#  Dönüşümler
# ----------------------------------------------------------------------------------------------------------
@dataclass
class Rapor:
    dosya   : pathlib.Path
    degisim : list[str] = field(default_factory=list)
    atlanan : list[str] = field(default_factory=list)


def to_rating_int_goc(metin: str, rapor: Rapor) -> str:
    """`X.toRatingInt()` » `Score.from10(X)`"""
    desen = re.compile(r"\??\.toRatingInt\(\)")
    konum = 0

    while True:
        eslesme = desen.search(metin, konum)
        if not eslesme:
            break

        if yorum_satiri_mi(metin, eslesme.start()):
            rapor.atlanan.append("toRatingInt » yorum satırı, atlandı")
            konum = eslesme.end()
            continue

        sonuc = alici_araligi(metin, eslesme.start() - 1)
        if not sonuc or len(sonuc[1]) > 400:
            rapor.atlanan.append(f"toRatingInt » alıcı çözümlenemedi » {metin[max(0, eslesme.start()-70):eslesme.end()]!r}")
            konum = eslesme.end()
            continue

        baslangic, bosluk, alici = sonuc
        yeni  = f"{bosluk}Score.from10({alici})"
        metin = metin[:baslangic] + yeni + metin[eslesme.end():]
        konum = baslangic + len(yeni)
        rapor.degisim.append(f"toRatingInt » {yeni[:100]}")

    return metin


def alan_goc(metin: str, rapor: Rapor) -> str:
    """`this.rating = ...` » `this.score = ...` (? = işareti aynı sütunda kalır)"""
    def degistir(eslesme: re.Match[str]) -> str:
        return "this.score" + " " * (len(eslesme.group(1)) + 1) + "="

    yeni, adet = re.subn(r"this\.rating(\s*)=", degistir, metin)
    if adet:
        rapor.degisim.append(f"this.rating » this.score ({adet} adet)")

    return yeni


def extractor_link_goc(metin: str, rapor: Rapor) -> str:
    """`ExtractorLink(...)` » `newExtractorLink(...) { ... }`"""
    desen = re.compile(r"(?<![\w.])ExtractorLink\s*\(")

    # ? sondan başa doğru işle ki konumlar kaymasın
    for eslesme in reversed(list(desen.finditer(metin))):
        if yorum_satiri_mi(metin, eslesme.start()):
            rapor.atlanan.append("ExtractorLink » yorum satırı, atlandı")
            continue

        bas_parantez = metin.index("(", eslesme.start())
        son_parantez = eslesmeli_parantez(metin, bas_parantez)
        if son_parantez == -1:
            rapor.atlanan.append("ExtractorLink » kapanış parantezi bulunamadı")
            continue

        icerik = metin[bas_parantez + 1:son_parantez]
        adli   = adli_argumanlar(icerik) or konumsal_argumanlar(icerik)

        if adli is None or not {"source", "name", "url"} <= set(adli):
            rapor.atlanan.append(f"ExtractorLink » elle bakılmalı » {metin[eslesme.start():son_parantez + 1][:100]!r}")
            continue

        adli = dict(adli)

        # * tip belirleme (isM3u8/isDash » type)
        tip = None
        if "type" in adli:
            tip = adli.pop("type")
        elif "isM3u8" in adli:
            tip = "ExtractorLinkType.M3U8" if adli.pop("isM3u8").lower() == "true" else "ExtractorLinkType.VIDEO"

        if "isDash" in adli and adli.pop("isDash").lower() == "true":
            tip = "ExtractorLinkType.DASH"

        govde = [f"this.{alan} = {adli.pop(alan)}" for alan in LAMBDA_ALANLARI if alan in adli]

        kaynak, ad, adres = adli.pop("source"), adli.pop("name"), adli.pop("url")

        if adli:
            rapor.atlanan.append(f"ExtractorLink » bilinmeyen argüman ({', '.join(adli)}) » elle bakılmalı")
            continue

        satirlar = [
            "newExtractorLink(",
            f"    source = {kaynak},",
            f"    name   = {ad},",
            f"    url    = {adres},",
        ]

        if tip is not None:
            satirlar.append(f"    type   = {tip},")

        satirlar.append(")")
        if govde:
            satirlar[-1] = ") {"
            satirlar.extend(f"    {satir}" for satir in govde)
            satirlar.append("}")

        # ? çağrı satır başında değilse devam satırlarını bir kademe içeri al
        oncesi  = metin[:eslesme.start()].split("\n")[-1]
        girinti = girinti_bul(metin, eslesme.start()) + ("" if not oncesi.strip() else "    ")

        yeni  = ("\n" + girinti).join(satirlar)
        metin = metin[:eslesme.start()] + yeni + metin[son_parantez + 1:]
        rapor.degisim.append("ExtractorLink » newExtractorLink")

    return metin


def episode_goc(metin: str, rapor: Rapor) -> str:
    """`Episode(data = X, ...)` » `newEpisode(X) { ... }`"""
    desen = re.compile(r"(?<![\w.])Episode\s*\(")

    for eslesme in reversed(list(desen.finditer(metin))):
        oncesi = metin[:eslesme.start()].split("\n")[-1]
        if re.search(r"class\s*$", oncesi) or yorum_satiri_mi(metin, eslesme.start()):
            continue

        bas_parantez = metin.index("(", eslesme.start())
        son_parantez = eslesmeli_parantez(metin, bas_parantez)
        if son_parantez == -1:
            continue

        adli = adli_argumanlar(metin[bas_parantez + 1:son_parantez])
        if adli is None or "data" not in adli:
            rapor.atlanan.append(f"Episode » elle bakılmalı » {metin[eslesme.start():son_parantez + 1][:90]!r}")
            continue

        veri  = adli.pop("data")
        govde = [f"this.{anahtar} = {deger}" for anahtar, deger in adli.items()]

        girinti  = girinti_bul(metin, eslesme.start())
        satirlar = [f"newEpisode({veri}) {{", *[f"    {satir}" for satir in govde], "}"]
        yeni     = ("\n" + girinti).join(satirlar)

        metin = metin[:eslesme.start()] + yeni + metin[son_parantez + 1:]
        rapor.degisim.append("Episode » newEpisode")

    return metin


def import_duzenle(metin: str, rapor: Rapor) -> str:
    """Kullanılmayan importu kaldırır, eksik olanı ekler."""
    yildiz_cs    = "import com.lagradost.cloudstream3.*" in metin
    yildiz_utils = "import com.lagradost.cloudstream3.utils.*" in metin

    if "toRatingInt(" not in metin:
        yeni, adet = re.subn(r"^import com\.lagradost\.cloudstream3\.toRatingInt\s*\n", "", metin, flags=re.MULTILINE)
        if adet:
            metin = yeni
            rapor.degisim.append("import » toRatingInt kaldırıldı")

    if "Score." in metin and not yildiz_cs and not re.search(r"^import com\.lagradost\.cloudstream3\.Score\s*$", metin, re.MULTILINE):
        metin = import_ekle(metin, "import com.lagradost.cloudstream3.Score")
        rapor.degisim.append("import » Score eklendi")

    if "ExtractorLinkType." in metin and not yildiz_utils and not re.search(r"^import com\.lagradost\.cloudstream3\.utils\.ExtractorLinkType\s*$", metin, re.MULTILINE):
        metin = import_ekle(metin, "import com.lagradost.cloudstream3.utils.ExtractorLinkType")
        rapor.degisim.append("import » ExtractorLinkType eklendi")

    return metin


# ----------------------------------------------------------------------------------------------------------
#  Çalıştırma
# ----------------------------------------------------------------------------------------------------------
def dosyalari_topla(sadece: list[str] | None) -> list[pathlib.Path]:
    hepsi = [
        dosya for dosya in sorted(KOK.rglob("*.kt"))
        if not any(parca in ATLANANLAR for parca in dosya.relative_to(KOK).parts)
    ]

    if not sadece:
        return hepsi

    isimler = {pathlib.Path(y).name for y in sadece}
    return [dosya for dosya in hepsi if dosya.name in isimler]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="goc.py", description="CloudStream API göç aracı")
    parser.add_argument("--uygula", action="store_true", help="Değişiklikleri dosyalara yaz")
    parser.add_argument("--dosya", nargs="+", help="Sadece verilen dosyalar")
    parser.add_argument("--ozet", action="store_true", help="Diff yerine sadece özet göster")
    args = parser.parse_args(argv)

    raporlar : list[Rapor] = []
    degisen  = 0
    atlanan  = 0

    for dosya in dosyalari_topla(args.dosya):
        eski  = dosya.read_text(encoding="utf-8")
        rapor = Rapor(dosya=dosya)

        yeni = eski
        yeni = to_rating_int_goc(yeni, rapor)
        yeni = alan_goc(yeni, rapor)
        yeni = extractor_link_goc(yeni, rapor)
        yeni = episode_goc(yeni, rapor)
        yeni = import_duzenle(yeni, rapor)

        if rapor.degisim or rapor.atlanan:
            raporlar.append(rapor)
            atlanan += len(rapor.atlanan)

        if yeni == eski:
            continue

        degisen += 1

        if args.uygula:
            dosya.write_text(yeni, encoding="utf-8")

        if not args.ozet:
            sys.stdout.writelines(difflib.unified_diff(
                eski.splitlines(keepends=True),
                yeni.splitlines(keepends=True),
                fromfile=f"a/{dosya.relative_to(KOK)}",
                tofile=f"b/{dosya.relative_to(KOK)}",
            ))

    print()
    print(f"[i] {degisen} dosya {'güncellendi' if args.uygula else 'güncellenecek'}, {atlanan} kullanım elle incelenmeli")

    if not args.uygula:
        print("[i] Yazmak için: python3 ARACLAR/goc.py --uygula")

    if atlanan:
        print("\n[!] Elle bakılması gerekenler:")
        for rapor in raporlar:
            for mesaj in rapor.atlanan:
                print(f"    {rapor.dosya.relative_to(KOK)} » {mesaj}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
