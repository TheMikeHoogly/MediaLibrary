#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du depouillement du banc 3b. Pur : ni serveur, ni base, ni GPU."""
import depouillement as d


def _check(cond, label):
    print(f"  {'OK ' if cond else 'ECHEC'} {label}")
    return bool(cond)


def carte(cat, best, halluc=()):
    return {'cat': cat, 'best': best, 'halluc': set(halluc)}


def test_binom_p():
    ok = True
    ok &= _check(abs(d.binom_p(88, 150) - 0.0409) < 0.0005,
                 "88/150 -> p = 0,041 (valeur du protocole)")
    ok &= _check(abs(d.binom_p(87, 150) - 0.0600) < 0.0005,
                 "87/150 -> p = 0,060 (le protocole cite le seuil EXACT)")
    ok &= _check(d.binom_p(0, 0) == 1.0, "n = 0 -> p = 1, pas de division")
    ok &= _check(d.binom_p(5, 10) == 1.0, "5/10 -> p = 1 (egalite parfaite)")
    ok &= _check(d.binom_p(3, 10) == d.binom_p(7, 10),
                 "bilaterale : symetrique autour de n/2")
    return ok


def test_seuil_significatif():
    ok = True
    ok &= _check(d.seuil_significatif(150) == 88, "n = 150 -> 88")
    ok &= _check(d.seuil_significatif(147) == 86, "n = 147 -> 86 (apres re-cle)")
    ok &= _check(d.seuil_significatif(117) == 70, "n = 117 -> 70 (hors pieges)")
    ok &= _check(d.seuil_significatif(30) == 21, "n = 30 -> 21")
    ok &= _check(d.seuil_significatif(4) is None,
                 "n = 4 : aucun seuil atteignable -> None, pas une exception")
    return ok


def test_paires_ignore_les_cles_techniques():
    notes = {"0": {"best": "A", "halluc": ["B"]}}
    mapping = {"0": {"A": "V0", "B": "V2CTX", "_key": "x.jpg", "_cat": "riche"}}
    lg = d.paires(notes, mapping)
    ok = _check(len(lg) == 1, "une carte")
    ok &= _check(lg[0]['best'] == "V0", "la lettre est traduite en variante")
    ok &= _check(lg[0]['halluc'] == {"V2CTX"}, "hallucination traduite aussi")
    ok &= _check(lg[0]['cat'] == "riche", "strate lue depuis _cat")
    return ok


def test_carte_non_notee_nest_pas_un_match_nul():
    """Une carte sans choix ne compte pas — elle n'existe pas."""
    notes = {"0": {"best": None, "halluc": []}, "1": {"best": "A"}}
    mapping = {"0": {"A": "V0", "B": "V2CTX"}, "1": {"A": "V0", "B": "V2CTX"}}
    return _check(len(d.paires(notes, mapping)) == 1, "seule la carte notee compte")


def test_hallucinations_appariees():
    lg = [carte('riche', 'V2CTX', ['V2CTX']),      # V2CTX seul
          carte('riche', 'V0', ['V2CTX']),         # V2CTX seul
          carte('riche', 'V0', ['V0']),            # V0 seul
          carte('riche', 'V2CTX', ['V0', 'V2CTX']),  # les deux
          carte('riche', 'V2CTX')]                 # aucune
    h = d.hallucinations_appariees(lg, 'V2CTX', 'V0')
    ok = _check(h['seule_variante'] == 2, "V2CTX seul : 2")
    ok &= _check(h['seule_reference'] == 1, "V0 seul : 1")
    ok &= _check(h['les_deux'] == 1, "les deux : 1")
    ok &= _check(h['discordantes'] == 3, "discordantes = 3 (les deux exclues)")
    ok &= _check(h['total_variante'] == 3 and h['total_reference'] == 2,
                 "totaux bruts conserves a cote de l apparie")
    ok &= _check(h['en_hausse'] is True, "en hausse")
    return ok


def test_les_deux_hallucinent_nest_pas_un_ecart():
    """Le point de McNemar : les cartes concordantes ne portent aucun signal."""
    lg = [carte('riche', 'V0', ['V0', 'V2CTX']) for _ in range(40)]
    h = d.hallucinations_appariees(lg, 'V2CTX', 'V0')
    ok = _check(h['discordantes'] == 0, "aucune discordante")
    ok &= _check(h['en_hausse'] is False, "40 hallucinations de chaque : pas de hausse")
    ok &= _check(h['p'] == 1.0, "p = 1, pas une division par zero")
    return ok


def test_verdict_close_si_hallucinations_en_hausse():
    """LE cas du 16/08 : la preference gagne, les hallucinations perdent.

    Le critere est un ET. Une preference ecrasante ne rachete pas une hausse
    des hallucinations — c'est ecrit dans le protocole, avant la mesure.
    """
    lg = ([carte('riche', 'V2CTX', ['V2CTX']) for _ in range(94)]
          + [carte('riche', 'V0') for _ in range(53)])
    res = d.verdict_3b(lg)
    ok = _check(res['global']['k'] == 94 and res['global']['atteint'],
                "la preference EST au-dessus du seuil")
    ok &= _check(res['decision'] == 'close',
                 "et la decision est CLOSE quand meme")
    ok &= _check('hallucination' in res['motif'], "le motif nomme la cause")
    return ok


def test_verdict_justifiee():
    lg = ([carte('riche', 'V2CTX') for _ in range(94)]
          + [carte('riche', 'V0') for _ in range(53)])
    res = d.verdict_3b(lg)
    return _check(res['decision'] == 'justifiee',
                  "preference atteinte + pas de hausse -> justifiee")


def test_verdict_non_demontree():
    lg = ([carte('riche', 'V2CTX') for _ in range(80)]
          + [carte('riche', 'V0') for _ in range(67)])
    res = d.verdict_3b(lg)
    ok = _check(res['decision'] == 'non_demontree', "sous le seuil -> non demontree")
    ok &= _check(not res['global']['atteint'], "et le seuil n est pas atteint")
    return ok


def test_les_pieges_se_depouillent_a_part():
    """Sans separer les pieges, un gain sur 30 documents deguise le reste.

    Reproduit la forme du 16/08 : ecrasant sur les pieges, plat ailleurs.
    """
    lg = ([carte('piege', 'V2CTX') for _ in range(25)]
          + [carte('piege', 'V0') for _ in range(5)]
          + [carte('riche', 'V2CTX') for _ in range(59)]
          + [carte('riche', 'V0') for _ in range(58)])
    res = d.verdict_3b(lg)
    ok = _check(res['global']['k'] == 84, "global : 84/147")
    ok &= _check(res['hors_pieges']['k'] == 59 and res['hors_pieges']['n'] == 117,
                 "hors pieges : 59/117")
    ok &= _check(res['par_strate']['piege']['atteint'],
                 "les pieges passent le seuil…")
    ok &= _check(not res['hors_pieges']['atteint'],
                 "…mais pas les vraies photos")
    return ok


def test_lignes_de_verdict_lisibles():
    lg = [carte('riche', 'V2CTX'), carte('piege', 'V0', ['V2CTX'])]
    txt = '\n'.join(d.lignes_de_verdict(d.verdict_3b(lg)))
    ok = _check('DÉCISION' in txt, "le verdict est ecrit en toutes lettres")
    ok &= _check('hors pièges' in txt, "le hors-pieges est toujours montre")
    return ok


if __name__ == "__main__":
    res = []
    for nom, fn in [
        ("binom_p", test_binom_p),
        ("seuil_significatif", test_seuil_significatif),
        ("paires", test_paires_ignore_les_cles_techniques),
        ("carte non notee", test_carte_non_notee_nest_pas_un_match_nul),
        ("hallucinations appariees", test_hallucinations_appariees),
        ("concordantes sans signal", test_les_deux_hallucinent_nest_pas_un_ecart),
        ("verdict close", test_verdict_close_si_hallucinations_en_hausse),
        ("verdict justifiee", test_verdict_justifiee),
        ("verdict non demontree", test_verdict_non_demontree),
        ("pieges a part", test_les_pieges_se_depouillent_a_part),
        ("texte du verdict", test_lignes_de_verdict_lisibles),
    ]:
        print(f"== {nom} ==")
        res.append(fn())
    print()
    if all(res):
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
