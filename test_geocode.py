#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests purs de geocode.py — aucun réseau, aucun GPU, aucune base réelle.
Gazetteer synthétique en mémoire + un cities1000 minuscule écrit en tempfile.

Lancer :  python test_geocode.py
"""

import math
import tempfile
from pathlib import Path

import geocode as g

_ok = 0
_ko = 0


def check(cond, label):
    global _ok, _ko
    if cond:
        _ok += 1
    else:
        _ko += 1
        print(f"  ECHEC : {label}")


# ── Fixtures : quelques villes réelles (lat, lon, cc, admin1, pop) ────────────
BREMBLENS = g.Place('Bremblens', 46.5468, 6.5310, 'CH', 'VD', 1200)
LAUSANNE = g.Place('Lausanne', 46.5197, 6.6323, 'CH', 'VD', 139111)
GENEVE = g.Place('Genève', 46.2044, 6.1432, 'CH', 'GE', 183981)
PARIS = g.Place('Paris', 48.8566, 2.3522, 'FR', '11', 2138551)
LAPAZ = g.Place('La Paz', -16.5000, -68.1500, 'BO', '02', 812799)
GAZ = [BREMBLENS, LAUSANNE, GENEVE, PARIS, LAPAZ]


def test_parse_locaux_lit_les_deux_syntaxes():
    lignes = [
        "# commentaire",
        "",
        "Bremblens ; 46.54605 ; 6.51821 ; 1.5",
        "Sanstruc ; 47.0 ; 7.0",            # rayon par défaut
        "Sitten => Sion",
        "Paris 16 Passy   =>   Paris",
        "ligne bancale sans rien",          # ignorée, pas d'exception
        "Faux ; pas_un_nombre ; 7.0",       # ignorée
        "  => Vide",                        # ignorée (ancien manquant)
    ]
    locaux, alias = g.parse_locaux(lignes)
    check(len(locaux) == 2, f'2 lieux locaux (obtenu {len(locaux)})')
    check(locaux[0].label == 'Bremblens' and locaux[0].rayon == 1.5,
          'Bremblens avec son rayon')
    check(locaux[1].rayon == g.RAYON_LOCAL_DEFAUT, 'rayon par defaut applique')
    check(alias.get('sitten') == 'Sion', 'alias Sitten -> Sion')
    check(alias.get('paris 16 passy') == 'Paris', 'alias espaces nettoyes')
    check(len(alias) == 2, f'2 alias (obtenu {len(alias)})')


def test_nearest_local_gagne_dans_son_rayon():
    locaux, _ = g.parse_locaux(["Bremblens ; 46.54605 ; 6.51821 ; 1.5"])
    pl = g.nearest_local(46.54605, 6.51821, locaux)
    check(pl is not None and pl.label == 'Bremblens', 'centroide -> Bremblens')


def test_nearest_local_navale_pas_la_commune_voisine():
    """Le garde-fou du rayon : l'amas « Bussigny » mesuré à 2,44 km du domicile
    ne doit PAS être capté par le lieu local, sinon on corrige un faux par un
    autre."""
    locaux, _ = g.parse_locaux(["Bremblens ; 46.54605 ; 6.51821 ; 1.5"])
    d = g.haversine_km(46.54605, 6.51821, 46.55146, 6.54904)
    check(d > 1.5, f'amas voisin hors rayon (mesure {d:.2f} km)')
    check(g.nearest_local(46.55146, 6.54904, locaux) is None,
          'amas voisin non capte par le lieu local')


def test_nearest_local_sans_fichier():
    check(g.nearest_local(46.5, 6.5, []) is None, 'aucun lieu local -> None')
    check(g.nearest_local(46.5, 6.5, None) is None, 'locaux None -> None')


def test_appliquer_alias():
    alias = {'sitten': 'Sion', 'geneva': 'Genève'}
    check(g.appliquer_alias('Sitten', alias) == 'Sion', 'Sitten -> Sion')
    check(g.appliquer_alias('Geneva', alias) == 'Genève', 'Geneva -> Genève')
    check(g.appliquer_alias('Lausanne', alias) == 'Lausanne', 'sans alias : intact')
    check(g.appliquer_alias(None, alias) is None, 'None reste None')
    check(g.appliquer_alias('Sitten', {}) == 'Sitten', 'table vide : intact')


def test_load_locaux_fichier_absent():
    locaux, alias = g.load_locaux(Path(tempfile.gettempdir()) / 'nexiste_pas_xyz.txt')
    check(locaux == [] and alias == {}, 'fichier absent -> ([], {})')


def test_sans_accents():
    check(g.sans_accents('Genève') == 'geneve', 'sans_accents Genève')
    check(g.sans_accents('PÉROU') == 'perou', 'sans_accents PEROU')


def test_haversine():
    # Lausanne <-> Genève : ~50 km à vol d'oiseau (réel ~53 km).
    d = g.haversine_km(LAUSANNE.lat, LAUSANNE.lon, GENEVE.lat, GENEVE.lon)
    check(45 < d < 60, f'haversine Lausanne-Genève ~50km (obtenu {d:.1f})')
    # distance à soi-même = 0
    check(g.haversine_km(46.5, 6.5, 46.5, 6.5) == 0.0, 'haversine self=0')
    # symétrie
    a = g.haversine_km(0, 0, 10, 10)
    b = g.haversine_km(10, 10, 0, 0)
    check(abs(a - b) < 1e-9, 'haversine symétrique')


def test_valide_latlon():
    check(g._valide_latlon(0, 0) is None, '(0,0) rejeté (GPS nul)')
    check(g._valide_latlon(None, 6.5) is None, 'None rejeté')
    check(g._valide_latlon(91, 0) is None, 'lat>90 rejeté')
    check(g._valide_latlon(46.5, 6.5) == (46.5, 6.5), 'point valide accepté')
    check(g._valide_latlon('46.5', '6.5') == (46.5, 6.5), 'strings castées')
    check(g._valide_latlon(float('nan'), 6.5) is None, 'NaN rejeté')


def test_nearest_basic():
    # Un point à 500 m au nord de Bremblens -> Bremblens.
    near = g.nearest(46.5513, 6.5310, GAZ)
    check(near is BREMBLENS, f'plus proche de Bremblens (obtenu {near})')
    # Un point sur Paris -> Paris.
    check(g.nearest(48.857, 2.352, GAZ) is PARIS, 'plus proche de Paris')
    # Hémisphère sud -> La Paz.
    check(g.nearest(-16.49, -68.14, GAZ) is LAPAZ, 'plus proche de La Paz')


def test_nearest_max_km():
    # Milieu de l'Atlantique : aucune ville sous 100 km.
    check(g.nearest(30.0, -40.0, GAZ, max_km=100) is None,
          'océan -> None sous max_km')
    # Sans borne, il rend quand même la moins lointaine (pas None).
    check(g.nearest(30.0, -40.0, GAZ) is not None, 'sans borne -> un résultat')


def test_nearest_pop_tiebreak():
    # Deux villes quasi au même endroit : la plus peuplée gagne.
    petit = g.Place('Hameau', 46.5200, 6.6320, 'CH', 'VD', 50)
    gros = g.Place('Lausanne', 46.5197, 6.6323, 'CH', 'VD', 139111)
    # point pile entre les deux (à quelques dizaines de mètres)
    near = g.nearest(46.5198, 6.6321, [petit, gros])
    check(near is gros, f'ex aequo -> plus peuplée (obtenu {near})')


def test_nearest_vides():
    check(g.nearest(46.5, 6.5, []) is None, 'gazetteer vide -> None')
    check(g.nearest(None, None, GAZ) is None, 'coord invalide -> None')


def test_cluster_separes():
    # 3 points Bremblens + 2 Paris + 1 La Paz -> 3 clusters.
    pts = [
        (46.5468, 6.5310), (46.5470, 6.5312), (46.5465, 6.5308),  # Bremblens
        (48.8566, 2.3522), (48.8570, 2.3525),                     # Paris
        (-16.50, -68.15),                                         # La Paz
    ]
    cl = g.cluster_points(pts, eps_km=2.0)
    check(len(cl) == 3, f'3 clusters attendus (obtenu {len(cl)})')
    # trié par taille : le plus gros (Bremblens, 3) en tête
    check(cl[0]['n'] == 3, f'plus gros cluster = 3 membres (obtenu {cl[0]["n"]})')
    # les indices d'origine sont préservés
    tous = sorted(i for c in cl for i in c['members'])
    check(tous == [0, 1, 2, 3, 4, 5], 'indices d\'origine préservés')


def test_cluster_centroid():
    pts = [(46.0, 6.0), (46.0, 6.0), (46.02, 6.0)]  # tous < 2km
    cl = g.cluster_points(pts, eps_km=5.0)
    check(len(cl) == 1, 'un seul cluster')
    lat, lon = cl[0]['centroid']
    check(abs(lat - 46.00667) < 1e-3, f'centroïde lat moyen (obtenu {lat:.5f})')


def test_cluster_ignore_invalides():
    pts = [(46.5, 6.5), (0, 0), (None, None), (46.5001, 6.5001)]
    cl = g.cluster_points(pts, eps_km=2.0)
    check(len(cl) == 1, 'invalides ignorés, 1 cluster')
    check(cl[0]['n'] == 2, '2 membres valides')


def test_label():
    check(g.label_place(BREMBLENS) == 'Bremblens', 'label simple')
    check(g.label_place(None) is None, 'label None -> None')
    check(g.label_place(LAPAZ, avec_pays=True) == 'La Paz (BO)', 'label + pays')


def test_load_gazetteer():
    # Mini cities1000 : colonnes GeoNames, séparées par des tabulations.
    # 0 id, 1 name, 2 ascii, 3 alt, 4 lat, 5 lon, 6 fclass, 7 fcode, 8 cc,
    # 9 cc2, 10 admin1, ... 14 population
    lignes = [
        "2659811\tBremblens\tBremblens\t\t46.5468\t6.5310\tP\tPPL\tCH\t\tVD\t\t\t\t1200",
        "2659496\tLausanne\tLausanne\t\t46.5197\t6.6323\tP\tPPLA\tCH\t\tVD\t\t\t\t139111",
        "malforme\ttrop\tcourt",                        # ignorée (trop peu de cols)
        "0\tPointNul\tPointNul\t\t0\t0\tP\tPPL\tXX\t\t\t\t\t\t10",  # (0,0) ignoré
    ]
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "cities1000.txt"
        f.write_text("\n".join(lignes) + "\n", encoding='utf-8')
        gaz = g.load_gazetteer(f)
        check(len(gaz) == 2, f'2 villes chargées (obtenu {len(gaz)})')
        noms = {p.label for p in gaz}
        check(noms == {'Bremblens', 'Lausanne'}, 'noms corrects')
        laus = [p for p in gaz if p.label == 'Lausanne'][0]
        check(laus.pop == 139111, 'population parsée')
        check(laus.cc == 'CH' and laus.admin1 == 'VD', 'cc/admin1 parsés')
        # min_pop filtre
        gaz2 = g.load_gazetteer(f, min_pop=100000)
        check(len(gaz2) == 1 and gaz2[0].label == 'Lausanne', 'min_pop filtre')


def test_bout_en_bout():
    # Un lot de points bruts -> clusters -> libellés géocodés.
    pts = [(46.5468, 6.5310), (46.5470, 6.5312),   # Bremblens x2
           (48.8566, 2.3522)]                       # Paris x1
    cl = g.cluster_points(pts, eps_km=2.0)
    labels = [g.label_place(g.nearest(c['centroid'][0], c['centroid'][1], GAZ))
              for c in cl]
    check('Bremblens' in labels and 'Paris' in labels,
          f'bout-en-bout donne Bremblens+Paris (obtenu {labels})')


def main():
    for nom, fn in sorted(globals().items()):
        if nom.startswith('test_') and callable(fn):
            fn()
    total = _ok + _ko
    print(f"\n{_ok}/{total} verifications OK, {_ko} echec(s).")
    return 0 if _ko == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
