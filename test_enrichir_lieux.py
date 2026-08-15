#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests purs du cœur de enrichir_lieux.py — pas de base, pas de réseau.
Lancer :  python test_enrichir_lieux.py
"""

import geocode as g
import enrichir_lieux as e

_ok = 0
_ko = 0


def check(cond, label):
    global _ok, _ko
    if cond:
        _ok += 1
    else:
        _ko += 1
        print(f"  ECHEC : {label}")


GAZ = [
    g.Place('Bremblens', 46.5468, 6.5310, 'CH', 'VD', 1200),
    g.Place('Lausanne', 46.5197, 6.6323, 'CH', 'VD', 139111),
    g.Place('Paris', 48.8566, 2.3522, 'FR', '11', 2138551),
    g.Place('La Paz', -16.5000, -68.1500, 'BO', '02', 812799),
]


def test_construire_places_de_base():
    gps = [
        ('a.jpg', 46.5468, 6.5310),   # Bremblens
        ('b.jpg', 46.5470, 6.5312),   # Bremblens
        ('c.jpg', 48.8566, 2.3522),   # Paris
    ]
    par_cle, infos = e.construire_places(gps, GAZ, eps_km=2.0)
    check(par_cle['a.jpg'] == 'Bremblens', 'a -> Bremblens')
    check(par_cle['b.jpg'] == 'Bremblens', 'b -> Bremblens')
    check(par_cle['c.jpg'] == 'Paris', 'c -> Paris')
    check(len(infos) == 2, f'2 clusters (obtenu {len(infos)})')
    check(infos[0]['effectif'] == 2, 'plus gros cluster = 2 (Bremblens)')


def test_construire_ignore_hors_borne():
    # Point au milieu de l'océan : cluster non nommé (max_km).
    gps = [('sea.jpg', 30.0, -40.0), ('home.jpg', 46.5468, 6.5310)]
    par_cle, infos = e.construire_places(gps, GAZ, eps_km=2.0, max_km=25.0)
    check('sea.jpg' not in par_cle, 'point océan non nommé')
    check(par_cle.get('home.jpg') == 'Bremblens', 'home nommé')
    non = [i for i in infos if not i['lieu']]
    check(len(non) == 1, 'un cluster non nommé rapporté')


def test_construire_ignore_gps_nul():
    gps = [('z.jpg', 0.0, 0.0), ('h.jpg', 46.5468, 6.5310)]
    par_cle, _infos = e.construire_places(gps, GAZ)
    check('z.jpg' not in par_cle, '(0,0) écarté')
    check('h.jpg' in par_cle, 'point valide gardé')


def test_construire_lieu_local_prioritaire():
    """Le cas mesuré le 14/08 : 1 257 photos du domicile nommées « Bussigny »,
    la commune voisine, parce que le village est absent du gazetteer."""
    gaz = [g.Place('Bussigny', 46.55560, 6.54640, 'CH', 'VD', 8000)]
    locaux, alias = g.parse_locaux(["Bremblens ; 46.54605 ; 6.51821 ; 1.5"])
    gps = [('maison1.jpg', 46.54605, 6.51821), ('maison2.jpg', 46.54610, 6.51830)]
    par_cle, infos = e.construire_places(gps, gaz, locaux=locaux, alias=alias)
    check(par_cle['maison1.jpg'] == 'Bremblens', 'domicile -> Bremblens')
    check(infos[0]['source'] == 'local', 'source signalee comme locale')
    # sans le fichier de corrections, on retombe sur le gazetteer
    par_cle2, infos2 = e.construire_places(gps, gaz)
    check(par_cle2['maison1.jpg'] == 'Bussigny', 'sans correction -> Bussigny')
    check(infos2[0]['source'] == 'gazetteer', 'source signalee comme gazetteer')


def test_construire_applique_les_alias():
    gaz = [g.Place('Sitten', 46.2331, 7.3606, 'CH', 'VS', 34978)]
    _locaux, alias = g.parse_locaux(["Sitten => Sion"])
    gps = [('valais.jpg', 46.2331, 7.3606)]
    par_cle, infos = e.construire_places(gps, gaz, alias=alias)
    check(par_cle['valais.jpg'] == 'Sion', 'Sitten renomme en Sion')
    check(infos[0]['lieu'] == 'Sion', 'rapport affiche le libelle corrige')


def test_construire_sans_corrections_inchange():
    """Compatibilité : sans lieux_locaux.txt, le comportement d'avant."""
    gps = [('a.jpg', 46.5468, 6.5310), ('c.jpg', 48.8566, 2.3522)]
    avant, _ = e.construire_places(gps, GAZ)
    apres, _ = e.construire_places(gps, GAZ, locaux=[], alias={})
    check(avant == apres, 'listes vides = comportement d origine')


def test_fusionner_ajoute_nouveaux():
    existant = [
        "# entete",
        "#",
        "Bremblens",
        "Lausanne",
        "#",
        "# --- Rejetes (non-lieux), conserves pour reference ---",
        "# Tagliani",
    ]
    nouvelles, ajouts = e.fusionner_lieux(existant, ['Paris', 'Bremblens', 'La Paz'])
    # Bremblens déjà présent -> non réajouté ; Paris + La Paz nouveaux
    check(sorted(ajouts) == ['La Paz', 'Paris'], f'ajouts corrects (obtenu {ajouts})')
    # bloc inséré AVANT la section Rejetes
    txt = "\n".join(nouvelles)
    i_bloc = nouvelles.index(e.MARK_START)
    i_rej = next(k for k, l in enumerate(nouvelles)
                 if l.startswith('# --- Rejetes'))
    check(i_bloc < i_rej, 'bloc géré avant les rejetés')
    check('Paris' in nouvelles and 'La Paz' in nouvelles, 'labels présents')
    check('# Tagliani' in nouvelles, 'rejetés préservés')


def test_fusionner_idempotent():
    existant = ["# entete", "Bremblens", "# --- Rejetes ---"]
    n1, a1 = e.fusionner_lieux(existant, ['Paris'])
    check(a1 == ['Paris'], 'premier passage gère Paris')
    # rejouer sur le résultat avec les MÊMES labels : le fichier est STABLE
    # (le bloc géré est reconstruit à l'identique, pas dupliqué).
    n2, a2 = e.fusionner_lieux(n1, ['Paris'])
    check(a2 == ['Paris'], 'second passage : Paris toujours géré')
    check(n2.count('Paris') == 1, 'Paris présent une seule fois (pas de doublon)')
    check(n2.count(e.MARK_START) == 1, 'un seul bloc marqué')
    check(n1 == n2, 'sortie stable entre deux passages (idempotent)')


def test_fusionner_sans_section_rejetes():
    existant = ["# entete", "Bremblens", ""]
    nouvelles, ajouts = e.fusionner_lieux(existant, ['Paris'])
    check(ajouts == ['Paris'], 'ajout sans section rejetes')
    check(e.MARK_START in nouvelles and 'Paris' in nouvelles, 'bloc présent')


def test_fusionner_rien_a_faire():
    existant = ["# entete", "Bremblens", "Paris"]
    nouvelles, ajouts = e.fusionner_lieux(existant, ['Paris', 'Bremblens'])
    check(ajouts == [], 'aucun nouveau -> aucun ajout')
    check(e.MARK_START not in nouvelles, 'pas de bloc si rien ajouté')


def main():
    for nom, fn in sorted(globals().items()):
        if nom.startswith('test_') and callable(fn):
            fn()
    total = _ok + _ko
    print(f"\n{_ok}/{total} verifications OK, {_ko} echec(s).")
    return 0 if _ko == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
