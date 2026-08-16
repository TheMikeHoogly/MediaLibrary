#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-cle l'echantillon FIGE du banc de tagging apres un rangement de fichiers.

LE PROBLEME (constate le 15/08/2026)
    `eval/tagging_v1.json` fige 150 photos depuis le 30/07 — c'est ce qui rend
    deux mesures comparables entre elles, et le protocole 3b interdit de le
    REGENERER. Mais entre-temps « Ranger par annee » a deplace les fichiers :

        AVANT  ...\\Photos\\_A TRIER\\250914_Samsung_Mike\\20250730_151021.jpg
        APRES  ...\\Photos\\2025\\20250730_151021.jpg

    65 des 150 cles ne resolvaient plus. Le banc les a sautees une par une et a
    tourne 25 minutes sur 85 photos, sans jamais dire le total — avec deux
    degats : le critere pre-enregistre (>= 88 sur 150) devenait hors d'atteinte,
    et les quotas de strates que l'echantillon existe pour preserver etaient
    casses (pieges 12/30).

CE QUE FAIT CE SCRIPT
    Il SUIT le renommage au lieu de refaire l'echantillon : meme photo, meme
    strate, cle mise a jour. C'est le meme geste que `rekey_everywhere` et
    `gps_places_rekey` ailleurs dans le projet.

    Appariement par NOM DE FICHIER, et **seulement si le jumeau est UNIQUE**.
    Deux candidats = on ne devine pas : la cle reste morte et le rapport le dit.
    Un nom de fichier en double dans deux dossiers est frequent ici (chantier
    « doublons proches ») — choisir au hasard mettrait une AUTRE photo dans
    l'echantillon, c'est-a-dire mesurer autre chose en croyant reparer.

    LECTURE SEULE par defaut. `--ecrire` sauvegarde `tagging_v1.json.bak` puis
    ecrit. La logique pure est testee hors machine par
    `test_recler_echantillon.py`.

USAGE
    python recler_echantillon.py            # rapport, n'ecrit rien
    python recler_echantillon.py --ecrire   # applique (backup .bak d'abord)
"""
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = SCRIPT_DIR / "eval" / "tagging_v1.json"


def nom_de_fichier(cle):
    """Dernier segment d'une cle, quel que soit le separateur, en minuscules."""
    return str(cle).replace('\\', '/').rsplit('/', 1)[-1].lower()


def recler(echantillon, cles_index):
    """{cle: strate} + cles vivantes -> (nouvel echantillon, rapport).

    `echantillon` : le contenu de `tagging_v1.json`.
    `cles_index`  : toutes les cles connues de l'index (`STORE.data`).

    Rapport : `vivantes`, `reclees` [(avant, apres)], `ambigues` [(cle, [cands])],
    `perdues` [cle]. La strate suit la photo — c'est la photo qui est figee, pas
    son chemin.
    """
    vivantes = set(cles_index)
    par_nom = {}
    for k in vivantes:
        par_nom.setdefault(nom_de_fichier(k), []).append(k)

    nouveau = {}
    rapport = {'vivantes': [], 'reclees': [], 'ambigues': [], 'perdues': []}
    for cle, strate in echantillon.items():
        if cle in vivantes:
            nouveau[cle] = strate
            rapport['vivantes'].append(cle)
            continue
        candidats = sorted(par_nom.get(nom_de_fichier(cle), []))
        if len(candidats) == 1:
            nouveau[candidats[0]] = strate
            rapport['reclees'].append((cle, candidats[0]))
        elif candidats:
            # On garde la cle MORTE telle quelle : la retirer masquerait le trou,
            # et en choisir une au hasard mettrait une autre photo dans le banc.
            nouveau[cle] = strate
            rapport['ambigues'].append((cle, candidats))
        else:
            nouveau[cle] = strate
            rapport['perdues'].append(cle)
    return nouveau, rapport


def taux_de_cles_mortes(echantillon, cles_index):
    """Part (0-100) des cles de l'echantillon absentes de l'index."""
    if not echantillon:
        return 0.0
    vivantes = set(cles_index)
    morts = sum(1 for k in echantillon if k not in vivantes)
    return 100.0 * morts / len(echantillon)


def main():
    ecrire = '--ecrire' in sys.argv[1:]
    if not SAMPLE_FILE.exists():
        print(f"  Echantillon introuvable : {SAMPLE_FILE}")
        return 1

    # Import TARDIF : charger l'index coute quelques secondes, inutile si le
    # fichier manque. `server` a des effets de bord a l'import (voir son entete).
    import server as s

    echantillon = json.loads(SAMPLE_FILE.read_text(encoding='utf-8'))
    nouveau, rap = recler(echantillon, s.STORE.data.keys())

    print("=" * 70)
    print("  RE-CLE DE L ECHANTILLON FIGE DU BANC DE TAGGING")
    print("=" * 70)
    print(f"  {len(echantillon)} photo(s) dans l echantillon")
    print(f"    deja valides : {len(rap['vivantes'])}")
    print(f"    RE-CLEES     : {len(rap['reclees'])}")
    print(f"    ambigues     : {len(rap['ambigues'])}"
          f"  (nom de fichier en double — non devinees)")
    print(f"    perdues      : {len(rap['perdues'])}")
    print()
    for avant, apres in rap['reclees'][:5]:
        print(f"    {avant}\n      -> {apres}")
    if len(rap['reclees']) > 5:
        print(f"    … et {len(rap['reclees']) - 5} autre(s)")
    for cle, cands in rap['ambigues']:
        print(f"    AMBIGUE {nom_de_fichier(cle)} : {len(cands)} candidats")
        for c in cands:
            print(f"      {c}")
    for cle in rap['perdues']:
        print(f"    PERDUE  {cle}")
    print()

    utilisables = len(rap['vivantes']) + len(rap['reclees'])
    print(f"  Photos utilisables apres re-cle : {utilisables}"
          f" / {len(echantillon)}")
    if not ecrire:
        print("  (rapport a blanc — relance avec --ecrire pour appliquer)")
        return 0
    if not rap['reclees']:
        print("  Rien a re-cler : fichier inchange.")
        return 0

    backup = SAMPLE_FILE.with_suffix(SAMPLE_FILE.suffix + '.bak')
    backup.write_text(SAMPLE_FILE.read_text(encoding='utf-8'), encoding='utf-8')
    SAMPLE_FILE.write_text(json.dumps(nouveau, ensure_ascii=False, indent=1),
                           encoding='utf-8')
    print(f"  Sauvegarde : {backup.name}")
    print(f"  Ecrit      : {SAMPLE_FILE.name}")
    print("  Les RESULTATS d un run precedent restent cles a l ancienne :")
    print("  relance le banc en entier plutot que de recoller deux passes.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
