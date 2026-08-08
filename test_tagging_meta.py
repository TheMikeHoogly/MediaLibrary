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
    return ok


if __name__ == "__main__":
    print("== parse_meta_gps_item ==")
    a = test_parse()
    print("== merge_named_tags ==")
    b = test_merge_named()
    print()
    if a and b:
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
