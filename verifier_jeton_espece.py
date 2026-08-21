#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification EN RÉEL du 5ᵉ axe `espece:` — le serveur fait-il ce qu'on a mesuré ?
──────────────────────────────────────────────────────────────────────────────

POURQUOI CE FICHIER EXISTE

Un banc dit ce qu'une règle RENDRAIT. Il ne dit pas ce que le serveur FAIT :
entre les deux il y a une extraction de jeton, un routeur, un filtre et un
redémarrage. Le projet a déjà payé cet écart — le 20/08, le filtre des noms et
la ligne de faits répondaient à la même question par deux chemins, donc par
deux réponses. Ce script interroge le serveur VIVANT et compare sa réponse,
clé par clé, à la règle partagée (`faits_vue.dit_l_espece`).

CE QU'IL CONTRÔLE

  1. **Le serveur tourne-t-il le code visé ?** `demarre_a`, `uptime_s` et
     surtout `code_a_jour` : sinon la vérification porte sur l'ancien code et
     ne prouve rien.
  2. **Le jeton est-il COMPRIS ?** `/api/search` doit rendre `especes: [chat]`
     et un `reste` vidé du jeton — c'est ce que la page affiche sous « ce que
     j'ai compris ».
  3. **Le jeton rend-il EXACTEMENT la concordance ?** Avec `--base copie.db`,
     l'ensemble rendu est comparé à celui que calcule la règle partagée. Les
     deux doivent être IDENTIQUES : un écart, même d'une photo, dit que le
     filtre et la règle ont divergé.
  4. **Une espèce inconnue ne rend RIEN, et le dit.** `espece:licorne` doit
     rendre zéro photo et l'annoncer — un filtre impossible qui rendrait tout
     le fonds serait lu comme un accord.
  5. **Le jeton se COMBINE** avec les quatre autres axes (nom, lieu, période,
     sens) : `espece:chat Luna` doit rendre moins que `espece:chat`.

CE QU'IL NE FAIT PAS

Aucune écriture, aucun accès NAS. Lecture seule sur une COPIE pour le contrôle
3, et de simples GET pour le reste.

USAGE
    python verifier_jeton_espece.py
    python verifier_jeton_espece.py --base copie.db --nom Luna
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import faits_vue

BASE_URL = 'http://127.0.0.1:8080'
PLAFOND_PAGE = 1500


def _get(url, timeout=180):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def serveur(base_url=BASE_URL):
    try:
        return _get(base_url + '/api/serveur', timeout=10)
    except Exception as e:                                    # noqa: BLE001
        raise SystemExit(f"Le serveur ne répond pas ({e}) — rien à vérifier.")


def chercher(q, base_url=BASE_URL, n=PLAFOND_PAGE):
    url = f"{base_url}/api/search?q={urllib.parse.quote(q)}&n={n}"
    try:
        return _get(url)
    except Exception as e:                                    # noqa: BLE001
        raise SystemExit(f"/api/search a échoué sur « {q} » : {e}")


def concordance(base, mot):
    """Les clés que la RÈGLE PARTAGÉE retient — le juge du contrôle 3.

    Les photos taguées AVEC les faits (`pipe`) sont GARDÉES ici : le filtre les
    garde aussi. Le banc, lui, les écarte — il mesure un ACCORD, et un accord
    soufflé ne prouve rien. Deux buts, deux populations, dit dans les deux."""
    import sqlite3
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais lire photos.db. "
                         "Fabriquer une copie (mesure_copie_base.py).")
    label = faits_vue.label_de_l_espece(mot)
    import mesure_copie_base
    cx = sqlite3.connect(mesure_copie_base.uri_lecture_seule(p), uri=True)
    try:
        vus = set()
        for k, v in cx.execute('SELECT k, v FROM animals'):
            try:
                d = json.loads(v)
            except ValueError:
                continue
            if not any(isinstance(a, dict) and a.get('species') == label
                       for a in (d.get('animals') or [])):
                continue
            vus.add(k)
        out = set()
        for k, v in cx.execute('SELECT k, v FROM tags'):
            if k not in vus:
                continue
            try:
                e = json.loads(v)
            except ValueError:
                continue
            if isinstance(e, dict) and not e.get('failed') \
                    and any(faits_vue.dit_l_espece(e, mot)):
                out.add(k)
        return out
    finally:
        cx.close()


def verifier(base=None, mot='chat', nom=None, base_url=BASE_URL):
    L, ok = [], True
    A = L.append
    A("=" * 78)
    A("  VÉRIFICATION EN RÉEL — le jeton `espece:` sur le serveur vivant")
    A("=" * 78)

    s = serveur(base_url)
    a_jour = bool(s.get('code_a_jour'))
    ok = ok and a_jour
    A("1. Le serveur tourne-t-il le code visé ?")
    A(f"   demarre_a {time.strftime('%d/%m %H:%M:%S', time.localtime(s.get('demarre_a', 0)))}"
      f"   uptime {int(s.get('uptime_s', 0))} s"
      f"   code_a_jour {'OUI' if a_jour else 'NON'}")
    if not a_jour:
        A("   ARRÊT DE LECTURE : ce qui suit porterait sur l'ancien code.")
        return "\n".join(L), False

    d = chercher(f'espece:{mot}', base_url)
    compris = (d.get('especes') or []) == [mot]
    reste_vide = not (d.get('reste') or '').strip()
    ok = ok and compris and reste_vide
    A("")
    A("2. Le jeton est-il COMPRIS ?")
    A(f"   especes={d.get('especes')}   inconnues={d.get('especes_inconnues')}"
      f"   reste={d.get('reste')!r}   → {'OK' if compris and reste_vide else 'ÉCART'}")
    rendus = {x['key'] for x in (d.get('results') or [])}
    A(f"   {len(rendus)} photos rendues pour `espece:{mot}`")

    A("")
    A("3. Le jeton rend-il EXACTEMENT la concordance ?")
    if base:
        att = concordance(base, mot)
        manquent, en_trop = att - rendus, rendus - att
        plafond = len(att) > PLAFOND_PAGE
        A(f"   règle partagée : {len(att)} photos ; serveur : {len(rendus)}")
        if plafond:
            A(f"   (plus de {PLAFOND_PAGE} : la page plafonne, "
              "seul « en trop » fait foi)")
        A(f"   manquent : {len(manquent)}   en trop : {len(en_trop)}")
        for k in sorted(en_trop)[:5]:
            A(f"      en trop  {k[-64:]}")
        for k in sorted(manquent)[:5]:
            A(f"      manque   {k[-64:]}")
        bon = not en_trop and (plafond or not manquent)
        ok = ok and bon
        A(f"   → {'OK' if bon else 'ÉCART'}")
    else:
        A("   (sauté : pas de --base ; c'est le contrôle qui compare "
          "clé par clé, ne pas le sauter avant de livrer)")

    d2 = chercher('espece:licorne', base_url)
    zero = not (d2.get('results') or [])
    dit = (d2.get('especes_inconnues') or []) == ['licorne']
    ok = ok and zero and dit
    A("")
    A("4. Une espèce inconnue ne rend RIEN, et le dit ?")
    A(f"   {len(d2.get('results') or [])} photo(s), inconnues="
      f"{d2.get('especes_inconnues')} → {'OK' if zero and dit else 'ÉCART'}")

    A("")
    A("5. Le jeton se COMBINE-t-il avec les autres axes ?")
    if nom:
        d3 = chercher(f'espece:{mot} {nom}', base_url)
        n3 = len(d3.get('results') or [])
        moins = n3 <= len(rendus)
        ok = ok and moins
        A(f"   `espece:{mot} {nom}` → {n3} photos, noms={d3.get('noms')}, "
          f"especes={d3.get('especes')} → {'OK' if moins else 'ÉCART'}")
    else:
        A("   (sauté : pas de --nom)")

    d4 = chercher(mot, base_url)
    A("")
    A("Pour mémoire — le MOT NU reste du SENS (forme A) :")
    A(f"   `{mot}` → {len(d4.get('results') or [])} photos, "
      f"especes={d4.get('especes')} (vide attendu), reste={d4.get('reste')!r}")
    ok = ok and not (d4.get('especes') or [])
    A("=" * 78)
    A("VERDICT : " + ("tout est vert." if ok else "AU MOINS UN ÉCART — lire ci-dessus."))
    return "\n".join(L), ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', help="COPIE de photos.db (contrôle 3)")
    ap.add_argument('--espece', default='chat')
    ap.add_argument('--nom', help="un nom attribué, pour le contrôle 5")
    ap.add_argument('--url', default=BASE_URL)
    a = ap.parse_args(argv)
    texte, ok = verifier(a.base, a.espece, a.nom, a.url)
    print(texte)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
