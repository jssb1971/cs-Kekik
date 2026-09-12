version = 0

cloudstream {
    authors     = listOf(__YAZARLAR__)
    language    = "__DIL__"
    description = "__ACIKLAMA__"

    /**
     * Status int as the following:
     * 0: Down
     * 1: Ok
     * 2: Slow
     * 3: Beta only
    **/
    status  = 1 // will be 3 if unspecified
    tvTypes = listOf(__TV_TIPLERI__)
    iconUrl = "__IKON__"
}
