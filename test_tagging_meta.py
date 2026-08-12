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


def test_parse_taken():
    ok = True
    # La plus ANCIENNE des dates EXIF gagne (evite la date de modification)
    kw, desc, gps, taken = tm.parse_meta_gps_taken_item({
        "Subject": ["chat"],
        "DateTimeOriginal": "2018:12:11 23:01:48",
        "ModifyDate": "2026:08:12 10:00:00"})
    ok &= _check(taken == tm.parse_exif_dt("2018:12:11 23:01:48"),
                 "taken = plus ancienne des dates EXIF")
    ok &= _check(kw == ["chat"], "kw inchanges par l'ajout de la date")

    # Pas de date -> None ; annee aberrante rejetee
    _, _, _, t2 = tm.parse_meta_gps_taken_item({"Subject": "x"})
    ok &= _check(t2 is None, "aucune date EXIF -> None")
    ok &= _check(tm.parse_exif_dt("1889:01:01 00:00:00") is None,
                 "annee aberrante rejetee")
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


if __name__ == "__main__":
    print("== parse_meta_gps_item ==")
    a = test_parse()
    print("== merge_named_tags ==")
    b = test_merge_named()
    print("== parse_meta_gps_taken_item ==")
    c = test_parse_taken()
    print("== format_date_fr ==")
    d = test_format_date()
    print("== noms_depuis_kw ==")
    e = test_noms_depuis_kw()
    print("== prompt_tagging (v2ctx) ==")
    f = test_prompt()
    print("== faits_structures (provenance) ==")
    g = test_faits_structures()
    print()
    if all([a, b, c, d, e, f, g]):
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
