#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Réparation — remettre dans les FICHIERS les noms que l'index porte déjà
──────────────────────────────────────────────────────────────────────────────

POURQUOI, ET CE QUE ÇA RÉPARE

`verifier_xmp_personnes.py` sait NOMMER les photos dont le fichier ne porte pas
le nom que l'index leur donne. Il ne sait pas les réparer — et sans réparation,
nommer l'écart ne fait que documenter la perte. Ce script est l'autre moitié :
il refait, photo par photo, ce que `PERSON_QUEUE` n'a pas eu le temps de faire.

Le cas réel : le 23/08, la fusion Flo → Florine a mis 10 800 opérations dans
une file EN MÉMOIRE, à 0,28 op/s — onze heures pendant lesquelles une coupure
de courant laissait ~5 400 photos avec `Flo` dans leurs métadonnées et
`Florine` dans l'index. Un nom fantôme, et rien pour dire lesquelles.

CE QUI EST NON NÉGOCIABLE

  1. **Jamais deux écrivains sur les mêmes fichiers.** Si le serveur répond et
     que `queues.personnes` n'est pas à 0, ce script REFUSE. Le 22/08, la
     fusion et le curateur se sont battus une heure sur le même fonds : 60
     auto-ajouts, 17 092 écritures pour un geste qui en demandait 11 814. Deux
     écrivains, c'est la même chose en pire — `person_writer` est l'écrivain
     unique tant qu'il vit.
  2. **À blanc par défaut.** Sans `--appliquer`, rien n'est écrit et tout est
     dit.
  3. **Journal d'abord, écriture ensuite, `finally` toujours.** Chaque photo
     touchée est notée dans `_corbeille_xmp/` : ce qui a été retiré, ce qui a
     été ajouté, ce que le fichier portait avant. Interrompu = annulable, et
     RELANCER REPREND : le script relit les tags avant d'écrire, donc une photo
     déjà réparée n'est pas réécrite. (Leçon du 23/08 : la fusion mourait après
     la boucle, sans journal, donc sans rien à annuler.)
  4. **Famille `appliquer_` : hors de portée du banc.** Ce qui modifie le fonds
     reste un geste de Mike (`banc_agent.py` ne lance que ce qui MESURE).

CE QUE ÇA COÛTE, ET QU'IL FAUT SAVOIR

Une écriture change le `mtime` du fichier : le balayage des modifiés du serveur
relira ces photos. C'est sans danger — leurs XMP porteront alors le bon nom,
donc l'index ne bougera pas — mais c'est du travail de scan, et il faut le
vouloir.

USAGE
    python appliquer_xmp_personnes.py --rapport _xmp_florine.json
    python appliquer_xmp_personnes.py --rapport _xmp_florine.json --appliquer
    python appliquer_xmp_personnes.py --nom Florine --absent Flo --appliquer
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import verifier_xmp_personnes as V

RACINE = Path(__file__).resolve().parent
CORBEILLE = RACINE / "_corbeille_xmp"


def horodatage(maintenant=None):
    return time.strftime('%Y%m%d_%H%M%S', time.localtime(maintenant))


def candidats(rapport=None, nom='', absent='', serveur=''):
    """Les clés à examiner, et d'où elles viennent.

    Un rapport de `verifier_xmp_personnes.py` est une LISTE DE CANDIDATS, pas
    un ordre : les tags sont relus avant d'écrire. Sans rapport, on redemande
    la vérité d'index au serveur."""
    if rapport:
        data = json.loads(Path(rapport).read_text(encoding='utf-8'))
        cles = list(dict.fromkeys((data.get('manque') or [])
                                  + (data.get('fantome') or [])))
        return cles, (data.get('nom') or nom), (data.get('absent') or absent)
    return V.cles_du_nom(nom, serveur), nom, absent


def a_faire(cles, uploads, tags, nom, absent):
    """Pour chaque clé : ce qu'il faut RETIRER et AJOUTER, d'après ce que le
    fichier porte MAINTENANT. Une photo déjà conforme ne rend rien."""
    attendu = ("%s:%s" % (V.PREFIXE, nom)).lower()
    ancien = ("%s:%s" % (V.PREFIXE, absent)).lower() if absent else None
    plan = []
    for cle in cles:
        chemin = V.chemin_de_cle(cle, uploads)
        if chemin is None:
            continue
        mots = tags.get(V._normalise(chemin))
        if mots is None:                     # non lu : on ne devine pas
            continue
        ajoute = [] if attendu in mots else [nom]
        retire = [absent] if (ancien and ancien in mots) else []
        if ajoute or retire:
            plan.append({'cle': cle, 'chemin': str(chemin), 'ajoute': ajoute,
                         'retire': retire, 'avant': sorted(mots)})
    return plan


def args_exiftool(chemin, ajoute, retire):
    """UNE invocation pour les deux gestes d'une photo.

    `person_writer` en lance DEUX (un `del`, un `add`) : le coût d'ExifTool est
    son démarrage, et le payer deux fois par photo double la facture d'un
    renommage. Ici, retrait et ajout tiennent dans le même appel. `-=` avant
    `+=` sur l'ajout : c'est ainsi que `write_person_tag` évite un doublon."""
    args = ["-overwrite_original", "-q", "-m", "-charset", "filename=UTF8",
            "-codedcharacterset=utf8"]
    for tag in retire:
        t = "%s:%s" % (V.PREFIXE, tag)
        args += ["-XMP-dc:Subject-=%s" % t, "-IPTC:Keywords-=%s" % t]
    for tag in ajoute:
        t = "%s:%s" % (V.PREFIXE, tag)
        args += ["-XMP-dc:Subject-=%s" % t, "-XMP-dc:Subject+=%s" % t,
                 "-IPTC:Keywords-=%s" % t, "-IPTC:Keywords+=%s" % t]
    return args + [str(chemin)]


def ecrire_une(exe, chemin, ajoute, retire):
    argfile = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                         encoding='utf-8-sig') as tf:
            tf.write('\n'.join(args_exiftool(chemin, ajoute, retire)))
            argfile = tf.name
        r = subprocess.run([str(exe), '-@', argfile], capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=300)
        return r.returncode == 0, (r.stderr or '').strip()[:200]
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)[:200]
    finally:
        if argfile:
            try:
                os.unlink(argfile)
            except OSError:
                pass


def appliquer(plan, exe, journal_path, ecrire=print):
    """Écrit, en notant AVANT de continuer. Le journal est fermé dans un
    `finally` : une interruption laisse un journal complet de ce qui a été
    fait — c'est ce qui rend le geste annulable."""
    faits, rates = 0, 0
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    fh = journal_path.open('w', encoding='utf-8')
    try:
        for i, op in enumerate(plan, 1):
            ok, err = ecrire_une(exe, op['chemin'], op['ajoute'], op['retire'])
            ligne = dict(op, ok=ok, erreur=err, quand=time.time())
            fh.write(json.dumps(ligne, ensure_ascii=False) + '\n')
            fh.flush()
            faits += 1 if ok else 0
            rates += 0 if ok else 1
            if i % 100 == 0:
                ecrire("  %d/%d ecrites (%d en echec)" % (i, len(plan), rates))
    finally:
        fh.close()
    return faits, rates


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--rapport', default='',
                    help="le --json de verifier_xmp_personnes.py")
    ap.add_argument('--nom', default='')
    ap.add_argument('--absent', default='')
    ap.add_argument('--serveur', default='http://127.0.0.1:8080')
    ap.add_argument('--appliquer', action='store_true',
                    help="ecrire pour de vrai (sans lui : a blanc)")
    a = ap.parse_args(argv)

    if not a.rapport and not a.nom:
        print("il faut --rapport, ou --nom (la verite d'index vient de l'un "
              "des deux).")
        return 2

    file = V.file_du_serveur(a.serveur)
    if file:
        print("REFUS : le serveur a encore %d operation(s) en file." % file)
        print("  `person_writer` est l'ecrivain unique tant qu'il vit. Deux")
        print("  ecrivains sur les memes fichiers, c'est la bagarre du 22/08")
        print("  en pire. Attendre queues.personnes = 0, ou arreter le serveur.")
        return 3
    if file is None and not a.rapport:
        print("le serveur ne repond pas : sans lui, la verite d'index doit "
              "venir d'un --rapport ecrit quand il repondait encore.")
        return 2

    exe = V.exiftool_exe()
    if exe is None:
        print("ExifTool introuvable : rien a faire sans lui.")
        return 2

    cles, nom, absent = candidats(a.rapport, a.nom, a.absent, a.serveur)
    if not cles:
        print("aucune candidate.")
        return 0
    uploads = V.dossier_uploads()
    chemins = [c for c in (V.chemin_de_cle(k, uploads) for k in cles)
               if c is not None]
    print("  relecture des tags de %d fichier(s)..." % len(chemins))
    tags = V.lire_tags(chemins, exe, journal=print)
    plan = a_faire(cles, uploads, tags, nom, absent)

    print("")
    print("=" * 74)
    print("  REPARATION personne:%s%s" % (nom, (" (retrait de %s)" % absent)
                                          if absent else ""))
    print("=" * 74)
    print("  candidates          : %d" % len(cles))
    print("  deja conformes      : %d" % (len(cles) - len(plan)))
    print("  a reecrire          : %d" % len(plan))
    print("  dont retrait de %-4s: %d" % (absent or '-',
                                          sum(1 for o in plan if o['retire'])))
    if not a.appliquer:
        print("")
        print("  A BLANC : rien n'a ete ecrit. Ajouter --appliquer.")
        print("=" * 74)
        return 0

    jp = CORBEILLE / ("xmp_%s.jsonl" % horodatage())
    print("  journal             : %s" % jp)
    faits, rates = appliquer(plan, exe, jp)
    print("")
    print("  reecrites           : %d" % faits)
    print("  en echec            : %d" % rates)
    print("  Relancer ce script REPREND : les photos deja reparees ne le sont")
    print("  pas deux fois. Verifier avec verifier_xmp_personnes.py.")
    print("=" * 74)
    return 0 if not rates else 1


if __name__ == '__main__':
    sys.exit(main())
