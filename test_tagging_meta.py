"""Tests de tagging_meta : parsing exiftool combine (tags+desc+GPS) et
reintegration des noms humains. Purement en memoire — aucun acces NAS/photos.db,
donc executable dans le bac a sable.

    python test_tagging_meta.py
"""
import tagging_meta as tm


def _check(cond, label):
    print(("  OK  " if cond else "  ECHEC ") + label)
    return bool(cond)


def test_parse():
    ok = True
    # Subject en liste + tag nomme (casse preservee) + GPS + description simple
    kw, desc, gps = tm.parse_meta_gps_item({
        "Subject": ["Chat", "personne:Mike", "EXTERIEUR"],
        "Description": "Un chat dans le jardin",
        "GPSLatitude": 46.5197, "GPSLongitude": 6.6323})
    ok &= _check(kw == ["chat", "personne:Mike", "exterieur"],
                 "tags normalises, casse preservee pour personne:Mike")
    ok &= _check(desc == "Un chat dans le jardin", "description simple")
    ok &= _check(gps == [46.5197, 6.6323], "GPS parse (degres decimaux signes)")

    # Subject en chaine simple -> enveloppee en liste
    kw, _, _ = tm.parse_meta_gps_item({"Subject": "Vacances"})
    ok &= _check(kw == ["vacances"], "Subject chaine -> liste")

    # Keywords (IPTC) en repli quand pas de Subject
    kw, _, _ = tm.parse_meta_gps_item({"Keywords": ["animal:Luna"]})
    ok &= _check(kw == ["animal:Luna"], "repli sur Keywords IPTC, casse preservee")

    # Description localisee (dict) -> premiere valeur
    _, desc, _ = tm.parse_meta_gps_item({"Description": {"x-default": "Hello"}})
    ok &= _check(desc == "Hello", "description localisee (dict) -> texte")

    # Aucun mot-cle -> None ; pas de GPS -> None
    kw, desc, gps = tm.parse_meta_gps_item({"Description": ""})
    ok &= _check(kw is None, "aucun mot-cle -> None")
    ok &= _check(gps is None, "aucun GPS -> None")

    # GPS (0,0) rejete (null island), hors bornes rejete
    _, _, gps0 = tm.parse_meta_gps_item({"GPSLatitude": 0, "GPSLongitude": 0})
    ok &= _check(gps0 is None, "GPS (0,0) rejete")
    _, _, gpsx = tm.parse_meta_gps_item({"GPSLatitude": 999, "GPSLongitude": 6})
    ok &= _check(gpsx is None, "GPS hors bornes rejete")
    return ok


def test_merge_named():
    ok = True
    # Un nom present dans le fichier mais absent du re-tagging IA est reintegre
    kw = tm.merge_named_tags(["chat", "jardin"], ["chat", "personne:Mike", "animal:Luna"])
    ok &= _check(kw == ["chat", "jardin", "personne:Mike", "animal:Luna"],
                 "noms humains reintegres, ordre preserve")

    # Pas de doublon si deja present
    kw = tm.merge_named_tags(["personne:Mike"], ["personne:Mike"])
    ok &= _check(kw == ["personne:Mike"], "pas de doublon")

    # Les tags non nommes du fichier ne sont PAS reimportes (l'IA regenere)
    kw = tm.merge_named_tags(["neuf"], ["vieux", "obsolete"])
    ok &= _check(kw == ["neuf"], "tags non nommes ignores")

    # existing_kw None -> inchange (aucun nom a perdre)
    kw = tm.merge_named_tags(["a"], None)
    ok &= _check(kw == ["a"], "existing_kw None gere")

    # INVARIANT SACRE : aucun nom humain perdu apres re-tagging complet
    avant = ["personne:Flo", "animal:Inti"]
    kw = tm.merge_named_tags(["nouveau1", "nouveau2"], avant)
    ok &= _check(all(n in kw for n in avant), "aucun nom humain perdu (invariant)")

    # Doublon de casse : « personne:luna » (importe du fichier) vs
    # « personne:Luna » (fiche) ne doivent pas cohabiter — dedup insensible
    # a la casse, premier arrive garde sa casse (_kw_has cote serveur).
    kw = tm.merge_named_tags(["chat", "personne:luna"], ["personne:Luna"])
    ok &= _check(kw == ["chat", "personne:luna"],
                 "pas de doublon de casse personne:luna/Luna")
    return ok


def test_format_date():
    ok = True
    ep = tm.parse_exif_dt("2018:12:11 23:01:48")
    ok &= _check(tm.format_date_fr(ep) == "11 decembre 2018",
                 "format deterministe sans locale")
    ok &= _check(tm.format_date_fr(None) is None, "epoch None -> None")
    ok &= _check(tm.format_date_fr("abc") is None, "epoch invalide -> None")
    return ok


def test_noms_depuis_kw():
    ok = True
    p, a = tm.noms_depuis_kw(["chat", "personne:Mike", "animal:Luna",
                              "PERSONNE:Flo", "animal:Luna", "personne: "])
    ok &= _check(p == ["Flo", "Mike"], "personnes triees, casse du prefixe ignoree")
    ok &= _check(a == ["Luna"], "animaux dedoublonnes, nom vide ignore")
    p, a = tm.noms_depuis_kw(None)
    ok &= _check(p == [] and a == [], "kw None gere")
    return ok


def test_prompt():
    ok = True
    a = {'persons': ["Mike"], 'animals': ["Luna"], 'species': ["cat"],
         'lieu': "Bremblens", 'date': "11 decembre 2018",
         'tags_fr': ["chat", "jardin"]}
    pr = tm.prompt_tagging(a)
    # Variante ADOPTEE : assertions en contexte, SANS imperatif de noms
    ok &= _check('IMPERATIF' not in pr, "PAS de bloc IMPERATIF (variante adoptee)")
    ok &= _check('Faits deja etablis' in pr, "bloc d'assertions present")
    ok &= _check('traite-les comme la verite' in pr, "cadrage v2 present")
    ok &= _check('Mike' in pr and 'Luna' in pr and '(cat)' in pr,
                 "noms et espece dans les assertions (contexte, pas exigence)")
    ok &= _check('Bremblens' in pr and '11 decembre 2018' in pr, "lieu et date")
    ok &= _check('(EXIF)' in pr and '(chemin du dossier)' in pr,
                 "libelles par defaut = ceux de l'eval")
    ok &= _check('keywords_en' in pr and 'description_fr' in pr, "regles JSON")

    # Provenance honnete : la source affichee suit date_src/lieu_src
    a2 = dict(a, date="2016", date_src='annee du dossier',
              lieu_src='gps')
    b2 = tm.bloc_assertions(a2)
    ok &= _check('- Date : 2016 (annee du dossier)' in b2,
                 "date deduite du dossier PAS etiquetee EXIF")
    ok &= _check('- Lieu : Bremblens (geocodage GPS)' in b2,
                 "lieu geocode PAS etiquete chemin du dossier")

    # Aucun fait -> ligne explicite, prompt toujours valide
    pr0 = tm.prompt_tagging({})
    ok &= _check('aucun fait structure disponible' in pr0,
                 "photo sans fait : ligne explicite")
    return ok


def test_faits_structures():
    ok = True
    a = {'persons': ["Mike"], 'animals': ["Luna"], 'species': ["cat"],
         'lieu': "Bremblens", 'lieu_src': 'gps',
         'date': "11 decembre 2018", 'date_src': 'exif', 'noms_src': 'xmp'}
    F = tm.faits_structures(a)
    ok &= _check(len(F) == 5, "5 faits produits")
    ok &= _check(all(set(f) == {'t', 'v', 'src'} for f in F),
                 "chaque fait porte type/valeur/source (provenance)")
    ok &= _check({'t': 'personne', 'v': 'Mike', 'src': 'xmp'} in F, "personne sourcee xmp")
    ok &= _check({'t': 'lieu', 'v': 'Bremblens', 'src': 'gps'} in F, "lieu source gps")
    ok &= _check({'t': 'date', 'v': '11 decembre 2018', 'src': 'exif'} in F,
                 "date sourcee exif")
    ok &= _check(tm.faits_structures({}) == [], "aucun fait -> liste vide")
    return ok


def test_valeurs_a_ecrire():
    """Le garde-fou anti-empoisonnement des backfills.

    Un lot rate doit rester SANS effet : sinon un hoquet du NAS marque des
    milliers de photos « pas de date », definitivement (l'entree porte alors la
    cle, et le backfill ne la represente plus jamais).
    """
    ok = True
    lot = [("cle/a.jpg", "A"), ("cle/b.jpg", "B"), ("cle/c.jpg", "C")]

    # Cas nominal : ExifTool a parle des trois, deux ont une date
    v = tm.valeurs_a_ecrire(lot, {"A": 111, "C": 333}, {"A", "B", "C"})
    ok &= _check(v == {"cle/a.jpg": 111, "cle/b.jpg": None, "cle/c.jpg": 333},
                 "valeurs trouvees ecrites, 'lu sans date' memorise a None")

    # Lot entierement rate (NAS muet) : AUCUNE ecriture, tout sera represente
    ok &= _check(tm.valeurs_a_ecrire(lot, {}, set()) == {},
                 "lot rate -> aucune ecriture (pas d'empoisonnement)")

    # Lot partiel : seuls les fichiers vus sont decides
    v = tm.valeurs_a_ecrire(lot, {"A": 111}, {"A"})
    ok &= _check(v == {"cle/a.jpg": 111},
                 "lot partiel -> les fichiers muets restent a representer")

    # Une valeur trouvee pour un fichier dont ExifTool n'a pas parle est
    # ignoree : `vus` fait autorite, pas `lues`.
    ok &= _check(tm.valeurs_a_ecrire(lot, {"B": 222}, set()) == {},
                 "`vus` fait autorite sur `lues`")

    # Le GPS passe par la meme porte (valeur = liste, pas un nombre)
    v = tm.valeurs_a_ecrire([("k", "K")], {"K": [46.5, 6.6]}, {"K"})
    ok &= _check(v == {"k": [46.5, 6.6]}, "meme regle pour le GPS")
    return ok


def test_date_fiable():
    """Le garde-fou des photos SCANNEES.

    Un tirage de 1995 numerise en 2005 ne porte souvent qu'un ModifyDate = la
    date du scan. Le croire ferait sortir la photo de 1995 dans toute vue
    chronologique : regression silencieuse sur la partie la plus ancienne de
    la phototheque.
    """
    ok = True
    prise = tm.parse_exif_dt("1995:07:04 10:00:00")
    scan = tm.parse_exif_dt("2005:03:02 09:00:00")

    ok &= _check(tm.date_fiable({'o': prise, 'm': scan}, {1995}) == prise,
                 "DateTimeOriginal l'emporte sur ModifyDate")
    ok &= _check(tm.date_fiable({'o': None, 'm': scan}, {1995}) is None,
                 "scan de 2005 dans un dossier 1995 -> refuse (repli annee)")
    ok &= _check(tm.date_fiable({'o': None, 'm': scan}, {2005}) == scan,
                 "ModifyDate cru quand l'annee concorde")
    ok &= _check(tm.date_fiable({'o': None, 'm': scan}, set()) == scan,
                 "aucune annee dans le chemin -> rien a contredire")
    ok &= _check(tm.date_fiable({'o': None, 'm': None}, {2005}) is None,
                 "aucune date -> None")
    ok &= _check(tm.date_fiable({}, set()) is None, "champs vides -> None")

    # Une date de prise de vue qui contredit le dossier reste CRUE : l'appareil
    # sait mieux que le rangement (photo classee dans le mauvais dossier).
    ok &= _check(tm.date_fiable({'o': prise, 'm': None}, {2010}) == prise,
                 "DateTimeOriginal cru meme s'il contredit le dossier")

    # REGRESSION (relecture du 13/08) : un dossier qui porte une PLAGE
    # (« Photos 2005-2010\\2008\\… ») donne plusieurs annees. Comparer a la
    # seule plus ancienne refusait la date et faisait RECULER la photo de
    # trois ans dans toute vue chronologique.
    m2008 = tm.parse_exif_dt("2008:07:04 15:00:00")
    ok &= _check(tm.date_fiable({'o': None, 'm': m2008}, {2005, 2008, 2010}) == m2008,
                 "annee presente dans une plage de dossier -> acceptee")
    ok &= _check(tm.date_fiable({'o': None, 'm': m2008}, {1995, 1999}) is None,
                 "annee absente de toutes celles du chemin -> refusee")
    return ok


def test_champs_dates_item():
    ok = True
    c = tm.champs_dates_item({"DateTimeOriginal": "2018:12:11 23:01:48",
                              "CreateDate": "2018:12:11 23:01:50",
                              "ModifyDate": "2026:08:12 10:00:00"})
    ok &= _check(c['o'] == tm.parse_exif_dt("2018:12:11 23:01:48"),
                 "o = la plus ancienne de DateTimeOriginal/CreateDate")
    ok &= _check(c['m'] == tm.parse_exif_dt("2026:08:12 10:00:00"),
                 "m = ModifyDate, JAMAIS fondu dans o")
    c = tm.champs_dates_item({"ModifyDate": "2005:03:02 09:00:00"})
    ok &= _check(c['o'] is None and c['m'], "scan : o vide, m seul")
    ok &= _check(tm.champs_dates_item(None) == {'o': None, 'm': None},
                 "item None gere")
    return ok


if __name__ == "__main__":
    print("== parse_meta_gps_item ==")
    a = test_parse()
    print("== merge_named_tags ==")
    b = test_merge_named()
    print("== format_date_fr ==")
    d = test_format_date()
    print("== noms_depuis_kw ==")
    e = test_noms_depuis_kw()
    print("== prompt_tagging (v2ctx) ==")
    f = test_prompt()
    print("== faits_structures (provenance) ==")
    g = test_faits_structures()
    print("== valeurs_a_ecrire (garde-fou des backfills) ==")
    h = test_valeurs_a_ecrire()
    print("== champs_dates_item (prise de vue vs ecriture) ==")
    i = test_champs_dates_item()
    print("== date_fiable (garde-fou des photos scannees) ==")
    jj = test_date_fiable()
    print()
    if all([a, b, d, e, f, g, h, i, jj]):
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
