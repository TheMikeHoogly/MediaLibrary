#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — SigLIP retrouve-t-il ce que YOLO a vu ? (chantier 14a-iv, l'ESPÈCE)
──────────────────────────────────────────────────────────────────────────────

LA QUESTION

Le filtre déterministe de la recherche (noms, lieux, période) atteint 27 936
des 30 122 photos qui portent un fait NON-date. Les 2 186 restantes n'ont pour
matière qu'une ESPÈCE détectée par YOLO. Faut-il en faire un cinquième axe ?

La règle du chantier dit non a priori : **on filtre ce que le modèle ne peut
pas voir, on classe ce qu'il voit.** Un nom, un lieu, une date sont invisibles
aux pixels ; une espèce, non — c'est exactement ce que SigLIP regarde. Le
principe suffirait à clore le dossier, et c'est pour cela qu'on le mesure : un
principe qui n'a jamais été confronté à un chiffre n'est pas un résultat.

CE QUE CE BANC MESURE, ET DANS QUEL ORDRE

  1. **Les détections sont-elles seulement ATTEIGNABLES ?** Une photo sans
     vecteur SigLIP est muette pour la recherche sémantique quoi qu'on fasse ;
     si beaucoup l'étaient, l'axe espèce serait le SEUL moyen de les sortir.
  2. **Le rappel** : sur les photos où YOLO a vu l'espèce X, combien SigLIP
     en rend-il dans son top-1500 quand on tape le mot français ? 1500 est le
     plafond de `/files?q=` — c'est ce que l'utilisateur peut voir, pas une
     borne théorique. Quand |détections| > 1500, le rappel est PLAFONNÉ par la
     page : le banc l'affiche, sinon on lirait un échec de SigLIP là où il n'y
     a qu'une limite d'affichage.
  3. **De quel côté tombe l'écart** — et c'est la seule partie qui décide.
     Une détection manquée par SigLIP est soit un vrai animal qu'il n'a pas vu
     (l'espèce apporterait quelque chose), soit un faux positif de YOLO qu'il
     a eu raison d'ignorer (l'espèce apporterait du bruit). Le banc ÉCHANTILLONNE
     les manquées, avec leur `det_score` et leurs mots-clés, POUR QU'ON LES
     REGARDE. Un compte d'écarts sans leur nature ne tranche rien
     (`eval/METHODE.md`, 19/08 : compter les faux qu'on retire sans compter les
     vrais qu'on emporte, c'est mesurer une moitié).

CE QU'IL NE FAIT PAS

Aucun `UPDATE`, aucun accès NAS, aucun modèle chargé. Il refuse d'ouvrir un
fichier nommé `photos.db` : le serveur est l'écrivain unique, on mesure sur une
COPIE. Le seul appel réseau est `GET /api/search` sur le serveur LOCAL — c'est
lui qui détient SigLIP, et l'INTERROGER est plus honnête que de recopier son
pipeline (`eval/METHODE.md`, 14/08 : un banc qui recopie la prod mesure autre
chose qu'elle).

FUSEAU HORAIRE : sans objet ici, aucune date n'est lue.

USAGE
    python mesure_espece_recherche.py --base copie.db
    python mesure_espece_recherche.py --base copie.db --seuil 0.5 --exemples 14
    python mesure_espece_recherche.py --base copie.db --json rapport.json
"""

import argparse
import json
import random
import sqlite3
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

# Le mot que TAPE un humain, pour chaque étiquette COCO que rend YOLO. Ce n'est
# pas une traduction de dictionnaire : c'est la requête réelle. « oiseau » et
# non « passereau », « vache » et non « bovin ».
MOTS = {
    'cat': 'chat', 'dog': 'chien', 'bird': 'oiseau',
    'cow': 'vache', 'horse': 'cheval', 'sheep': 'mouton',
}

API = 'http://127.0.0.1:8080/api/search'
PLAFOND_PAGE = 1500          # `/files?q=` et `/api/search?n=` s'arrêtent là


def ouvrir(base):
    """Ouvre la COPIE. Refuse `photos.db` : le serveur est l'écrivain unique."""
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais mesurer sur photos.db. "
                         "Copie la base d'abord, puis --base copie.db")
    if not p.exists():
        raise SystemExit(f"Base introuvable : {p}")
    return sqlite3.connect(str(p))


def lire_json(v):
    try:
        e = json.loads(v)
        return e if isinstance(e, dict) else {}
    except (ValueError, TypeError):
        return {}


def detections(cx):
    """{espèce: {clé: meilleur det_score}} — les photos VIVANTES seulement.

    `failed` est respecté comme partout ailleurs : une photo dont
    l'illisibilité est déjà constatée ne sortira d'aucune recherche, et la
    compter gonflerait le dénominateur sans rien dire."""
    tags = {k: lire_json(v) for k, v in cx.execute('SELECT k, v FROM tags')}
    par = defaultdict(dict)
    try:
        cur = cx.execute('SELECT k, v FROM animals')
    except sqlite3.Error:
        return par, tags
    for k, v in cur:
        e = tags.get(k)
        if not isinstance(e, dict) or e.get('failed'):
            continue
        for a in (lire_json(v).get('animals') or []):
            if not isinstance(a, dict) or not a.get('species'):
                continue
            s = float(a.get('det_score') or 0.0)
            d = par[a['species']]
            if s > d.get(k, -1.0):
                d[k] = s
    return par, tags


def avec_vecteur(cx):
    """Clés qui portent un vecteur SigLIP — les seules que la recherche
    sémantique peut rendre, quoi qu'on fasse par ailleurs."""
    try:
        return {k for k, in cx.execute(
            "SELECT k FROM vectors WHERE kind='photo'")}
    except sqlite3.Error:
        return set()


def interroger(mot, n=PLAFOND_PAGE, api=API):
    """Clés rendues par le serveur VIVANT, dans l'ordre. C'est lui qui détient
    SigLIP ; on l'interroge au lieu de recopier son pipeline."""
    url = f"{api}?q={urllib.parse.quote(mot)}&n={n}"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            d = json.loads(r.read().decode('utf-8'))
    except Exception as e:                                    # noqa: BLE001
        raise SystemExit(
            f"Le serveur ne répond pas ({e}). Il détient SigLIP : sans lui ce "
            "banc ne mesure rien. Lancer « 0 - Démarrer le serveur.bat ».")
    # `noms` / `lieux` non vides voudrait dire que le mot a été mangé par un
    # AUTRE axe (quelqu'un s'appelle « Mai », un lieu s'appelle « Vache ») —
    # le rappel mesuré ne serait alors plus celui de SigLIP.
    return ([x['key'] for x in d.get('results', [])],
            d.get('noms') or [], d.get('lieux') or [])


def mesurer(base, seuil, exemples, graine, api=API, especes=None):
    cx = ouvrir(base)
    par, tags = detections(cx)
    if especes:
        par = {e: d for e, d in par.items() if e in set(especes)}
    vect = avec_vecteur(cx)
    rnd = random.Random(graine)

    toutes = set()
    for d in par.values():
        toutes |= set(d)
    hautes = {k for d in par.values() for k, s in d.items() if s >= seuil}

    rapport = {
        'base': str(base), 'seuil': seuil,
        'photos_indexees': len(tags),
        'photos_avec_vecteur': len(vect),
        'photos_avec_detection': len(toutes),
        'photos_avec_detection_sure': len(hautes),
        'detections_sans_vecteur': len(toutes - vect),
        'especes': [],
    }

    for esp, d in sorted(par.items(), key=lambda x: -len(x[1])):
        mot = MOTS.get(esp, esp)
        rendus, noms, lieux = interroger(mot, PLAFOND_PAGE, api)
        rang = {k: i + 1 for i, k in enumerate(rendus)}
        Y = set(d)
        Yh = {k for k, s in d.items() if s >= seuil}
        trouvees = Y & set(rang)
        trouvees_h = Yh & set(rang)
        manquees = sorted(Y - set(rang), key=lambda k: -d[k])
        ech = rnd.sample(manquees, min(exemples, len(manquees)))
        rapport['especes'].append({
            'espece': esp, 'mot': mot,
            'detectees': len(Y), 'detectees_sures': len(Yh),
            'sans_vecteur': len(Y - vect),
            'rendus': len(rendus),
            'trouvees': len(trouvees), 'trouvees_sures': len(trouvees_h),
            'plafonne_par_la_page': len(Y) > PLAFOND_PAGE,
            'plafond': min(1.0, PLAFOND_PAGE / max(1, len(Y))),
            'mot_mange_par': {'noms': noms, 'lieux': lieux},
            'manquees': len(manquees),
            'manquees_sures': len(Yh - set(rang)),
            'exemples': [{
                'cle': k, 'det_score': round(d[k], 3),
                'kw': [str(x) for x in (tags.get(k, {}).get('kw_fr') or [])][:6],
            } for k in ech],
        })
    return rapport


def afficher(rap):
    L = []
    A = L.append
    A("=" * 74)
    A("  MESURE — SigLIP retrouve-t-il ce que YOLO a vu ?")
    A("=" * 74)
    A(f"Base   : {rap['base']}   seuil de confiance : {rap['seuil']}")
    A(f"Index  : {rap['photos_indexees']} photos, "
      f"{rap['photos_avec_vecteur']} avec un vecteur SigLIP")
    A(f"YOLO   : {rap['photos_avec_detection']} photos avec une détection, "
      f"dont {rap['photos_avec_detection_sure']} sûres (>= {rap['seuil']})")
    A(f"         {rap['detections_sans_vecteur']} sans vecteur "
      "— muettes pour la recherche sémantique quoi qu'on fasse")
    A("")
    A("-- RAPPEL DANS LE TOP-1500 (ce que l'utilisateur peut VOIR) ---------")
    A("%-8s %-8s %9s %9s %9s %9s" %
      ('espece', 'mot', 'detect.', 'trouvees', '%', 'plafond'))
    for e in rap['especes']:
        pct = 100.0 * e['trouvees'] / max(1, e['detectees'])
        pla = ('%.0f %%' % (100 * e['plafond'])) if e['plafonne_par_la_page'] else '-'
        A("%-8s %-8s %9d %9d %8.1f %% %9s" %
          (e['espece'], e['mot'], e['detectees'], e['trouvees'], pct, pla))
        if e['mot_mange_par']['noms'] or e['mot_mange_par']['lieux']:
            A("        ATTENTION : le mot a été pris pour un nom/lieu %s — "
              "ce rappel n'est pas celui de SigLIP."
              % (e['mot_mange_par'],))
    A("")
    A("-- DE QUEL CÔTÉ TOMBE L'ÉCART (à REGARDER, pas à croire) -----------")
    for e in rap['especes']:
        A(f"  {e['espece']} : {e['manquees']} manquées, "
          f"dont {e['manquees_sures']} avec un det_score >= {rap['seuil']}")
        for x in e['exemples']:
            A("      %.3f  %-50s %s" %
              (x['det_score'], x['cle'][-50:], ", ".join(x['kw'][:4])))
    A("=" * 74)
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', required=True, help="COPIE de photos.db")
    ap.add_argument('--seuil', type=float, default=0.5,
                    help="det_score au-dessus duquel une détection est dite SÛRE")
    ap.add_argument('--exemples', type=int, default=12)
    ap.add_argument('--graine', type=int, default=20260820)
    ap.add_argument('--api', default=API)
    ap.add_argument('--especes', nargs='+',
                    help="n'en mesurer qu'une ou deux (rejeu, mise au point)")
    ap.add_argument('--json', dest='sortie_json')
    a = ap.parse_args(argv)
    rap = mesurer(a.base, a.seuil, a.exemples, a.graine, a.api, a.especes)
    texte = afficher(rap)
    print(texte)
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\nJSON : {a.sortie_json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
