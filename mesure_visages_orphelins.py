#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — les décisions humaines posées sur des clés que l'index a oubliées
──────────────────────────────────────────────────────────────────────────────

CE QU'ON A TROUVÉ LE 21/08, ET POURQUOI IL FAUT UN INSTRUMENT AVANT UN GESTE

Le magasin de visages garde **2 374** fiches dont la clé n'est plus dans
l'index — exactement les 2 374 clés dont la purge du 17/08 avait retiré les
vecteurs SigLIP en laissant les visages. Le curateur les re-score toutes les
240 s et le garde-fou des clés fantômes les rejette en silence.

Purger paraît évident. Ça ne l'est pas : **125 décisions humaines vivent sur
ces clés** — 104 rattachements, 11 exclusions, 10 confirmations. La règle 2 du
projet dit que les noms humains ne se perdent jamais, et une décision humaine
en est un. On mesure donc AVANT de toucher : pour chacune, la photo vit-elle
sous une AUTRE clé, et cette autre clé porte-t-elle déjà le nom ?

DEUX FAÇONS DE RECONNAÎTRE UN JUMEAU, ET ELLES NE DISENT PAS LA MÊME CHOSE

  * par NOM DE FICHIER : `ARZOPA/x.jpg` et `…\\_Uploads\\ARZOPA\\x.jpg` sont la
    même photo sous deux clés — c'est la forme dominante. Rapide, mais aveugle
    au renommage, et le projet a appliqué 7 058 renommages.
  * par VISAGE : le même fichier produit les mêmes embeddings. Un visage
    retrouvé à ≥ 0,999 sur une clé vivante identifie la photo quel que soit son
    nom. Plus lent, insensible au renommage — et c'est le CONTENU qui parle,
    pas une convention de nommage.

Les deux sont mesurées côte à côte. Quand elles se contredisent, l'écart est le
résultat : un jumeau trouvé par le visage mais pas par le nom, c'est une photo
que le rangement a renommée ; l'inverse, c'est un homonyme.

CE QUE CE BANC NE FAIT PAS

Aucune écriture. Il ne reporte aucun nom, il ne purge rien : il produit la
LISTE de travail et, surtout, il **nomme les décisions qui n'ont aucun jumeau
vivant** — les seules qu'une purge perdrait vraiment. Le report des noms et la
purge sont des gestes de Mike.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_visages_orphelins.py --base copie.db
    python mesure_visages_orphelins.py --base copie.db --json orphelines.json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import mesure_propagation_noms as MP
from verifier_orphelins import basename_cle

# Deux visages issus du MÊME fichier donnent le même vecteur au bruit de
# quantification float16 près. 0,999 laisse passer ce bruit et rien d'autre :
# deux photos différentes d'une même personne plafonnent bien plus bas (le
# meilleur voisin médian du fonds est à 0,21).
SIM_MEME_PHOTO = 0.999


def chemin_cache(cle):
    """Réplique de `server._is_hidden_path` : un composant commence par
    `.`, `@` ou `#` (`.thumbs`, `@eaDir`, `#recycle`, `.corbeille-rangement`).

    C'est LA porte de sortie sans cascade : au démarrage, `maintenance_loop`
    retire ces clés de l'index par `STORE.remove_many` seul — les détections de
    visages, elles, restent."""
    return any(part.startswith(('.', '@', '#'))
               for part in str(cle).replace('\\', '/').split('/'))


def sous_une_racine(cle, racines):
    """La clé tombe-t-elle sous une racine scannée ? Une clé absolue hors de
    toute racine n'est vue par AUCUN scan : personne ne la retirera jamais
    (les « 91 photos muettes à vie » du 17/08)."""
    c = str(cle).replace('\\', '/').lower()
    if not (c.startswith('/') or (len(c) > 2 and c[1] == ':')):
        return True                      # clé relative : sous Uploads
    return any(c.startswith(str(r).replace('\\', '/').lower().rstrip('/') + '/')
               for r in racines)


def pourquoi_elles_survivent(orphelines, vivantes, upload_dir, racines):
    """Classe les clés orphelines par la RAISON qui les a laissées là.

    Trois familles, et ce ne sont pas les mêmes bugs :
      * `chemin_cache`   : retirées de l'index par la purge des dossiers cachés,
        qui n'appelle PAS `forget_everywhere` — la cascade est sautée ;
      * `jumeau_qui_resout` : un doublon de même nom de fichier existe et se
        résout — `purge_cles_fantomes` aurait dû les emporter ;
      * `personne_ne_les_voit` : le fichier a disparu ET aucun jumeau ne se
        résout. `_sync_dir` ne les voit pas (elles n'appartiennent à aucun
        dossier listé) et la purge par COLLISION ne se déclenche pas (elle
        exige un jumeau VIVANT). Personne n'est chargé de les retirer.
    """
    par_basename = {}
    for k in list(orphelines) + list(vivantes):
        par_basename.setdefault(basename_cle(k), []).append(k)

    familles = Counter()
    exemples = defaultdict(list)
    for k in sorted(orphelines):
        existe = False
        try:
            existe = MP.resoudre(k, upload_dir).is_file()
        except OSError:
            pass
        if existe:
            fam = ('chemin_cache' if chemin_cache(k)
                   else ('hors_racine_scannee'
                         if not sous_une_racine(k, racines)
                         else 'fichier_present_inexplique'))
        else:
            jumeaux = [a for a in par_basename.get(basename_cle(k), [])
                       if a != k]
            resout = False
            for a in jumeaux:
                try:
                    if MP.resoudre(a, upload_dir).is_file():
                        resout = True
                        break
                except OSError:
                    pass
            fam = 'jumeau_qui_resout' if resout else 'personne_ne_les_voit'
        familles[fam] += 1
        if len(exemples[fam]) < 4:
            exemples[fam].append(k)
    return dict(familles), {k: v for k, v in exemples.items()}


def decisions_humaines(people, pets):
    """Toutes les décisions humaines, par clé.

    Renvoie une liste de dicts : `{type, cle, i, nom}` où `type` vaut
    `rattachement` (niveau VISAGE, donc avec un index), `exclusion` ou
    `confirmation` (niveau PHOTO). Les trois comptent dans la vérité terrain —
    « ce visage n'est PAS Flo » évalue un clustering aussi bien qu'un
    rattachement (`eval/METHODE.md`, 21/08).
    """
    out = []
    for store in (people, pets):
        for pe in store.data.values():
            if not isinstance(pe, dict):
                continue
            nom = pe.get('name')
            if not nom:
                continue
            for kf in (pe.get('faces') or []):
                if isinstance(kf, (list, tuple)) and len(kf) == 2:
                    out.append({"type": "rattachement", "cle": kf[0],
                                "i": int(kf[1] or 0), "nom": nom})
            for cle in (pe.get('exclude') or []):
                out.append({"type": "exclusion", "cle": cle, "i": None,
                            "nom": nom})
            for cle in (pe.get('confirmed') or []):
                out.append({"type": "confirmation", "cle": cle, "i": None,
                            "nom": nom})
    return out


def index_par_nom_de_fichier(cles):
    """{nom de fichier en minuscules: [clés]} — pour le jumeau par NOM."""
    par_nom = defaultdict(list)
    for k in cles:
        par_nom[Path(k.replace('\\', '/')).name.lower()].append(k)
    return par_nom


def vecteurs_vivants(faces, vivantes):
    """(matrice des visages des clés VIVANTES, liste de (clé, index)).

    Renvoie (None, []) s'il n'y en a aucun — le banc le dit au lieu de
    planter."""
    import numpy as np
    lignes, ou = [], []
    for k in vivantes:
        e = faces.data.get(k)
        if not isinstance(e, dict) or e.get('failed'):
            continue
        for i, f in enumerate(e.get('faces') or []):
            if not isinstance(f, dict):
                continue
            s = f.get('emb')
            if not s:
                continue
            try:
                lignes.append(MP.emb_de_b64(s))
            except Exception:                                  # noqa: BLE001
                continue
            ou.append((k, i))
    if not lignes:
        return None, []
    return np.stack(lignes).astype(np.float32), ou


def vecteurs_de(faces, cle):
    """Vecteurs des visages d'une clé, dans l'ordre des index."""
    e = faces.data.get(cle)
    if not isinstance(e, dict):
        return []
    out = []
    for i, f in enumerate(e.get('faces') or []):
        if not isinstance(f, dict) or not f.get('emb'):
            continue
        try:
            out.append((i, MP.emb_de_b64(f['emb'])))
        except Exception:                                      # noqa: BLE001
            pass
    return out


def porte_deja_le_nom(tags, cle, nom):
    """La clé vivante porte-t-elle déjà `personne:Nom` (ou `animal:`) ?"""
    e = tags.data.get(cle)
    if not isinstance(e, dict):
        return False
    cible = nom.lower()
    for kw in (e.get('kw_fr') or []):
        kw = str(kw).lower()
        if kw.startswith(('personne:', 'animal:')) and kw.split(':', 1)[1] == cible:
            return True
    return False


def mesurer(base, projet, exemples=8, fichiers=False):
    """Le rapport complet. Ferme la base avant de rendre la main (Windows
    refuse d'effacer un fichier SQLite encore ouvert)."""
    tags, faces, people = MP.ouvrir_stores(base)
    from store_sqlite import SqliteStore
    pets = SqliteStore(Path(base), 'pets')
    try:
        return _mesurer(tags, faces, people, pets, projet, exemples,
                        fichiers)
    finally:
        for st in (tags, faces, people, pets):
            try:
                st.cx.close()
            except Exception:                                  # noqa: BLE001
                pass


def _mesurer(tags, faces, people, pets, projet, exemples, fichiers):
    import numpy as np
    vivantes = set(tags.data)
    orphelines = set(faces.data) - vivantes

    toutes = decisions_humaines(people, pets)
    en_danger = [d for d in toutes if d["cle"] in orphelines]
    hors_tout = [d for d in toutes
                 if d["cle"] not in vivantes and d["cle"] not in orphelines]

    rap = {
        "fonds": {
            "cles_vivantes": len(vivantes),
            "fiches_visages": len(faces.data),
            "cles_orphelines": len(orphelines),
        },
        "decisions": {
            "total": len(toutes),
            "par_type": dict(Counter(d["type"] for d in toutes)),
            "sur_cle_orpheline": len(en_danger),
            "en_danger_par_type": dict(Counter(d["type"] for d in en_danger)),
            "sur_cle_inconnue_partout": len(hors_tout),
        },
    }
    # ── POURQUOI elles survivent (opt-in : un stat par clé orpheline) ───────
    if fichiers and orphelines:
        import mesure_faits_vue as MFV
        racines = MFV.racines_media(projet)
        fam, ex = pourquoi_elles_survivent(
            orphelines, vivantes, MP.dossier_uploads(projet), racines)
        rap["causes"] = {"familles": fam, "exemples": ex,
                         "racines_scannees": [str(r) for r in racines]}

    if not en_danger:
        rap["verdict"] = "aucune decision humaine sur une cle orpheline"
        return rap

    # ── jumeau par NOM DE FICHIER ──────────────────────────────────────────
    par_nom = index_par_nom_de_fichier(vivantes)

    # ── jumeau par VISAGE ──────────────────────────────────────────────────
    M, ou = vecteurs_vivants(faces, vivantes)

    resultats = []
    for d in en_danger:
        cle = d["cle"]
        base_nom = Path(cle.replace('\\', '/')).name.lower()
        jumeaux_nom = [k for k in par_nom.get(base_nom, []) if k != cle]

        jumeau_visage, sim_visage = None, 0.0
        vs = vecteurs_de(faces, cle)
        if d["i"] is not None:
            vs = [(i, v) for i, v in vs if i == d["i"]] or vs
        if M is not None and vs:
            for _i, v in vs:
                sims = M @ v
                j = int(np.argmax(sims))
                if float(sims[j]) > sim_visage:
                    sim_visage = float(sims[j])
                    jumeau_visage = ou[j]
        meme_photo = (jumeau_visage is not None
                      and sim_visage >= SIM_MEME_PHOTO)

        retenu = (jumeaux_nom[0] if jumeaux_nom
                  else (jumeau_visage[0] if meme_photo else None))
        resultats.append({
            "type": d["type"], "nom": d["nom"], "cle": cle, "i": d["i"],
            "jumeaux_par_nom": jumeaux_nom[:3],
            "jumeau_par_visage": (jumeau_visage[0] if meme_photo else None),
            "sim_visage": round(sim_visage, 4),
            "jumeau_retenu": retenu,
            "jumeau_porte_deja_le_nom": bool(
                retenu and porte_deja_le_nom(tags, retenu, d["nom"])),
        })

    aucun = [r for r in resultats if not r["jumeau_retenu"]]
    deja = [r for r in resultats if r["jumeau_porte_deja_le_nom"]]
    a_reporter = [r for r in resultats
                  if r["jumeau_retenu"] and not r["jumeau_porte_deja_le_nom"]]
    par_nom_seul = [r for r in resultats
                    if r["jumeaux_par_nom"] and not r["jumeau_par_visage"]]
    par_visage_seul = [r for r in resultats
                       if r["jumeau_par_visage"] and not r["jumeaux_par_nom"]]

    rap["sauvetage"] = {
        "decisions_examinees": len(resultats),
        "jumeau_trouve": len(resultats) - len(aucun),
        "jumeau_porte_deja_le_nom": len(deja),
        "a_reporter": len(a_reporter),
        "AUCUN_JUMEAU": len(aucun),
        "jumeau_par_nom_SEUL": len(par_nom_seul),
        "jumeau_par_visage_SEUL": len(par_visage_seul),
    }
    # La liste qui DÉCIDE : ce qu'une purge perdrait vraiment. Complète, jamais
    # échantillonnée — c'est elle qu'on relit avant le geste.
    rap["sans_jumeau"] = [{"type": r["type"], "nom": r["nom"], "cle": r["cle"],
                           "i": r["i"], "meilleure_sim": r["sim_visage"]}
                          for r in aucun]
    rap["exemples_a_reporter"] = a_reporter[:exemples]
    rap["exemples_desaccord"] = (par_nom_seul[:exemples // 2]
                                 + par_visage_seul[:exemples // 2])
    return rap


def afficher(r):
    f, d = r["fonds"], r["decisions"]
    L = []
    A = L.append
    A("MESURE — LES DECISIONS HUMAINES POSEES SUR DES CLES OUBLIEES")
    A("=" * 78)
    A("")
    A(f"Fonds : {f['cles_vivantes']} cles dans l'index, "
      f"{f['fiches_visages']} fiches de visages, "
      f"dont {f['cles_orphelines']} ORPHELINES (plus dans l'index).")
    A(f"Decisions humaines : {d['total']} au total {d['par_type']}")
    A(f"  sur une cle ORPHELINE : {d['sur_cle_orpheline']} "
      f"{d['en_danger_par_type']}")
    A(f"  sur une cle inconnue PARTOUT : {d['sur_cle_inconnue_partout']}")
    A("")
    if "causes" in r:
        A("-" * 78)
        A("POURQUOI ELLES SURVIVENT — la cause, pas le symptome")
        A("-" * 78)
        libelles = {
            'chemin_cache':
                "dossier cache (.thumbs, @eaDir, .corbeille-rangement) : la "
                "purge de demarrage retire l'index SANS cascade",
            'jumeau_qui_resout':
                "un doublon de meme nom se resout : purge_cles_fantomes "
                "aurait du les emporter",
            'personne_ne_les_voit':
                "fichier disparu ET aucun jumeau vivant : _sync_dir ne les "
                "voit pas, la purge par collision ne se declenche pas",
            'hors_racine_scannee':
                "le fichier EXISTE mais hors de toute racine scannee : "
                "muette a vie",
            'fichier_present_inexplique':
                "le fichier existe, sous une racine scannee, et l'index l'a "
                "quand meme oublie — INEXPLIQUE",
        }
        for fam, n in sorted(r["causes"]["familles"].items(),
                             key=lambda x: -x[1]):
            A(f"  {n:>6}  {fam}")
            A(f"          {libelles.get(fam, '')}")
            for e in r["causes"]["exemples"].get(fam, [])[:2]:
                A(f"          ex. {e}")
        A("")
    if "sauvetage" not in r:
        A(r.get("verdict", ""))
        return "\n".join(L)
    s = r["sauvetage"]
    A("-" * 78)
    A("LE SAUVETAGE — la photo vit-elle sous une autre cle ?")
    A("-" * 78)
    A(f"  examinees                      : {s['decisions_examinees']}")
    A(f"  jumeau trouve                  : {s['jumeau_trouve']}")
    A(f"    dont le jumeau porte DEJA le nom : {s['jumeau_porte_deja_le_nom']} "
      "(rien a faire)")
    A(f"    a REPORTER                       : {s['a_reporter']}")
    A(f"  >>> AUCUN JUMEAU (ce qu'une purge perdrait) : {s['AUCUN_JUMEAU']}")
    A("")
    A(f"  trouve par le NOM seul    : {s['jumeau_par_nom_SEUL']}")
    A(f"  trouve par le VISAGE seul : {s['jumeau_par_visage_SEUL']}  "
      "(photo renommee : le nom de fichier ne suffisait pas)")
    A("")
    if r.get("exemples_desaccord"):
        A("  ou les deux methodes divergent :")
        for e in r["exemples_desaccord"]:
            A(f"    {e['nom']:<16} {e['cle']}")
            A(f"        nom -> {e['jumeaux_par_nom'] or '-'}")
            A(f"        visage ({e['sim_visage']:.4f}) -> "
              f"{e['jumeau_par_visage'] or '-'}")
        A("")
    if r.get("exemples_a_reporter"):
        A("  a reporter (exemples) :")
        for e in r["exemples_a_reporter"]:
            A(f"    {e['type']:<13} {e['nom']:<16} {e['cle']}")
            A(f"        -> {e['jumeau_retenu']}")
        A("")
    A("-" * 78)
    A("SANS AUCUN JUMEAU — la liste complete, a relire AVANT toute purge")
    A("-" * 78)
    if not r["sans_jumeau"]:
        A("  (aucune : tout se reporte)")
    for e in r["sans_jumeau"]:
        A(f"  {e['type']:<13} {e['nom']:<16} {e['cle']}"
          + (f"#{e['i']}" if e['i'] is not None else "")
          + f"   (meilleure sim {e['meilleure_sim']:.4f})")
    A("")
    A("LIMITES DECLAREES : aucune ecriture, aucun acces NAS, aucun modele "
      "charge. Un jumeau par NOM peut etre un homonyme ; un jumeau par VISAGE "
      f"exige >= {SIM_MEME_PHOTO} de cosinus, soit le meme fichier. Le report "
      "des noms et la purge restent des gestes de Mike.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', required=True, help="COPIE de photos.db")
    ap.add_argument('--projet', default='.')
    ap.add_argument('--exemples', type=int, default=8)
    ap.add_argument('--fichiers', action='store_true',
                    help="classe les orphelines par CAUSE (un stat par cle)")
    ap.add_argument('--json', dest='sortie_json')
    a = ap.parse_args(argv)
    rap = mesurer(a.base, a.projet, a.exemples, a.fichiers)
    print(afficher(rap))
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\nJSON : {a.sortie_json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
