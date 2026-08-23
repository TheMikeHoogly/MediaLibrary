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
     que `queues.personnes` n'est pas à 0, ce script n'écrit RIEN : il ATTEND
     qu'elle retombe (patience bornée, `--patience`), et ne refuse que si elle
     ne retombe pas. Le 22/08, la fusion et le curateur se sont battus une
     heure sur le même fonds : 60 auto-ajouts, 17 092 écritures pour un geste
     qui en demandait 11 814. Deux écrivains, c'est la même chose en pire —
     `person_writer` est l'écrivain unique tant qu'il vit.
     **Attendre, et non abandonner (23/08).** La version qui s'arrêtait au
     premier signe est morte à 4 800 photos sur 18 900, onze secondes après un
     « Auto-ajout : 14 visage(s) » — le curateur en pose un toutes les quatre
     minutes, et une passe de cinq heures ne survit pas à ça. L'invariant n'a
     pas bougé d'un pouce : attendre n'est pas écrire.
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


# ─────────────────────────── Le fonds entier (--tous) ───────────────────────

FAITS_TOUS = CORBEILLE / "_tous_faits.txt"
NOMS_SAUTES = CORBEILLE / "_tous_noms_sautes.txt"


def attendu_par_photo(serveur, uploads, ecrire=print):
    """`chemin normalisé -> (Path, {noms attendus})` — par PHOTO, pas par
    couple nom–photo.

    POURQUOI PAR PHOTO. Le mode `--nom` traite un nom à la fois : une photo qui
    manque DEUX noms coûte alors deux lectures et deux invocations ExifTool,
    dont le prix est le démarrage du processus (3,5 s mesurés sur le NAS le
    23/08). Groupées, elles n'en coûtent qu'une — c'est exactement la leçon que
    `write_person_tags` avait tirée côté serveur, et que ce script devait
    reprendre avant d'engager cinq heures d'écritures."""
    import verifier_xmp_toutes_personnes as T
    par_chemin = {}
    sautes = []
    noms = T.noms_du_serveur(serveur)
    ecrire("  %d nom(s) de personne ; collecte des cles..." % len(noms))
    for nom, _n in noms:
        try:
            cles = V.cles_du_nom(nom, serveur)
        except Exception as e:                                # noqa: BLE001
            sautes.append(nom)
            ecrire("  ! %s : cles non lues (%s) — ce nom sera SAUTE" % (nom, e))
            continue
        for cle in cles:
            chemin = V.chemin_de_cle(cle, uploads)
            if chemin is None:
                continue
            k = V._normalise(chemin)
            if k not in par_chemin:
                par_chemin[k] = (chemin, set())
            par_chemin[k][1].add(nom)
    if sautes:
        # Sur DISQUE, parce que la console defile pendant cinq heures et que
        # ces noms-la sont precisement ceux qu'il ne faut pas oublier : leurs
        # photos seront marquees FAITES si elles portent un autre nom.
        try:
            NOMS_SAUTES.parent.mkdir(parents=True, exist_ok=True)
            with NOMS_SAUTES.open('a', encoding='utf-8') as f:
                for nom in sautes:
                    f.write(nom + '\n')
        except OSError:
            pass
    return par_chemin, sautes


def charger_faits(chemin=None):
    """Les photos déjà traitées lors d'un passage précédent.

    La reprise est un SET de chemins, pas une position : entre deux passages
    l'index a pu bouger, et une position dans une liste qui n'est plus la même
    ferait sauter des photos sans que personne le sache."""
    chemin = Path(chemin or FAITS_TOUS)
    if not chemin.is_file():
        return set()
    try:
        return {l.strip() for l in
                chemin.read_text(encoding='utf-8').splitlines() if l.strip()}
    except OSError:
        return set()


def a_faire_photo(par_chemin, tags):
    """Ce qui manque à chaque photo LUE, d'après ce qu'elle porte maintenant.

    Une photo non lue ne rend rien : on ne devine pas ce qu'un fichier porte.
    Elle n'est pas non plus marquée faite — elle repassera."""
    plan = []
    for k, (chemin, noms) in par_chemin.items():
        mots = tags.get(k)
        if mots is None:
            continue
        manque = sorted(n for n in noms
                        if ("%s:%s" % (V.PREFIXE, n)).lower() not in mots)
        plan.append({'cle': str(chemin), 'chemin': str(chemin),
                     'ajoute': manque, 'retire': [],
                     'avant': sorted(mots), 'k': k})
    return plan


PATIENCE_S = 1800        # 30 min : le curateur passe toutes les ~4 min


def attendre_la_file(serveur, patience_s=PATIENCE_S, pas_s=10, ecrire=print,
                     dormir=None, horloge=None):
    """Attend que `queues.personnes` retombe a zero. Rend (libre, attendu_s, file).

    POURQUOI, ET CE QUE CA NE DESSERRE PAS (23/08, observe)

    Le curateur rattache des visages TOUT SEUL — « Auto-ajout : 14 visage(s)
    rattache(s) » — toutes les quatre a cinq minutes, et chacun remplit
    `PERSON_QUEUE` pour quelques secondes. La passe `--tous` s ARRETAIT au
    premier : lancee a 21:38, morte a 22:09:40, onze secondes apres l auto-ajout
    de 22:09:29, a **4 800 photos sur 18 900**. Une passe de cinq heures qui
    renonce sur un evenement qui se produit toutes les quatre minutes ne finira
    jamais, et personne n etait la pour la relancer.

    L invariant 1 est INTACT : on n ecrit toujours pas pendant que le serveur
    ecrit. On cesse seulement d ABANDONNER — attendre n est pas ecrire.

    La patience est BORNEE : un script qui attend sans fin est pire qu un
    script qui echoue (lecon du `{ready}` avale par `-q`, 23/08). Epuisee, on
    rend `False` et l appelant s arrete comme avant.

    Serveur MUET : rend `libre`, parce que personne d autre n ecrit — mais le
    DIT, un silence ne s interprete pas tout seul."""
    # Resolus a l APPEL, jamais en defaut : un defaut fige le `time.sleep` du
    # jour de la definition, et un test qui remplace l horloge dort pour de vrai.
    dormir = dormir or time.sleep
    horloge = horloge or time.monotonic
    file = V.file_du_serveur(serveur)
    if not file:                       # 0 (vide) ou None (muet) : rien a attendre
        return True, 0.0, file
    t0 = horloge()
    ecrire("  la file du serveur travaille (%d operation(s)) — j attends, "
           "je n ecris pas (patience %d s)." % (file, patience_s))
    while True:
        attendu = horloge() - t0
        if attendu >= patience_s:
            return False, attendu, file
        dormir(min(pas_s, max(0.0, patience_s - attendu)))
        file = V.file_du_serveur(serveur)
        attendu = horloge() - t0
        if not file:
            ecrire("  file retombee a zero apres %d s — je reprends." % attendu)
            return True, attendu, file


def balayer(par_chemin, exe, journal_path, faits_path, serveur='',
            lot=200, appliquer_vrai=False, ecrire=print,
            patience_s=PATIENCE_S):
    """Lit et répare le fonds par tranches, en marquant chaque photo FAITE.

    Trois choses tiennent ce mode :

    1. **La reprise.** Chaque photo traitée est ajoutée à `_tous_faits.txt`
       APRÈS son écriture et son journal. Une fenêtre fermée, une coupure, un
       Ctrl-C : relancer reprend, et ne réécrit pas ce qui l'a déjà été.
    2. **L'écrivain reste unique — et on ATTEND au lieu d'abandonner.** La
       file du serveur est re-testée AVANT chaque tranche ; si elle travaille,
       ce script ne écrit rien et ATTEND qu'elle retombe à zéro (patience
       bornée). Il ne s'arrête que si elle ne retombe pas. Le 23/08, arrêter
       au premier signe a coûté la nuit : le curateur rattache des visages tout
       seul toutes les quatre minutes, et la passe est morte à 4 800 photos sur
       18 900, onze secondes après un « Auto-ajout : 14 visage(s) ».
    3. **Rien n'est tu.** Ce qui n'a pas été lu, pas écrit, ou sauté parce que
       la file s'est remise à tourner est COMPTÉ et dit à la fin — le temps
       passé à attendre aussi : une passe deux fois plus lente sans qu'on
       sache pourquoi est une mesure fausse."""
    restants = [k for k in sorted(par_chemin) if k not in charger_faits(faits_path)]
    total = len(restants)
    vues = reecrites = rates = 0
    attentes, attente_s = 0, 0.0
    arret = ''
    t0 = time.time()
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    fh = journal_path.open('a', encoding='utf-8') if appliquer_vrai else None
    fa = open(faits_path, 'a', encoding='utf-8') if appliquer_vrai else None
    try:
        for debut in range(0, total, lot):
            if serveur:
                libre, attendu, file = attendre_la_file(
                    serveur, patience_s=patience_s, ecrire=ecrire)
                if attendu:
                    attentes += 1
                    attente_s += attendu
                if not libre:
                    arret = ("la file du serveur travaille encore apres %d s "
                             "d attente (%d operation(s)) : deux ecrivains sur "
                             "les memes fichiers, jamais." % (attendu, file))
                    break
            tranche = restants[debut:debut + lot]
            chemins = [par_chemin[k][0] for k in tranche]
            tags = V.lire_tags(chemins, exe, journal=None)
            sous = {k: par_chemin[k] for k in tranche}
            for op in a_faire_photo(sous, tags):
                vues += 1
                if op['ajoute']:
                    if appliquer_vrai:
                        ok, err = ecrire_une(exe, op['chemin'], op['ajoute'],
                                             op['retire'])
                        fh.write(json.dumps(dict(op, ok=ok, erreur=err,
                                                 quand=time.time()),
                                            ensure_ascii=False) + '\n')
                        fh.flush()
                        reecrites += 1 if ok else 0
                        rates += 0 if ok else 1
                    else:
                        reecrites += 1
                if appliquer_vrai:
                    fa.write(op['k'] + '\n')
                    fa.flush()
            ecoule = time.time() - t0
            reste = (total - min(debut + lot, total))
            vitesse = (min(debut + lot, total)) / ecoule if ecoule else 0
            ecrire("  %d/%d photos vues — %d reecrite(s), %d echec(s)%s"
                   % (min(debut + lot, total), total, reecrites, rates,
                      (" — reste ~%d min" % int(reste / vitesse / 60))
                      if vitesse else ""))
    finally:
        if fh:
            fh.close()
        if fa:
            fa.close()
    return {'total': total, 'vues': vues, 'reecrites': reecrites,
            'rates': rates, 'non_lues': vues and (total - vues) or 0,
            'arret': arret, 'attentes': attentes, 'attente_s': attente_s}


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


def tour_du_fonds(a, exe, uploads, ecrire=print):
    """Le fonds entier, par photo, avec reprise. Rend le code de sortie."""
    par_chemin, sautes = attendu_par_photo(a.serveur, uploads, ecrire=ecrire)
    deja = charger_faits()
    restants = [k for k in sorted(par_chemin) if k not in deja]
    plafonne = 0
    if a.max_photos and len(restants) > a.max_photos:
        plafonne = len(restants) - a.max_photos
        restants = restants[:a.max_photos]
        par_chemin = {k: par_chemin[k] for k in restants}
    ecrire("")
    ecrire("=" * 74)
    ecrire("  REPARATION DU FONDS — toutes les personnes, par PHOTO")
    ecrire("=" * 74)
    ecrire("  photos portant au moins un nom : %d" % (len(deja) + len(restants)
                                                      + plafonne))
    ecrire("  deja traitees (reprise)        : %d" % len(deja))
    ecrire("  a examiner maintenant          : %d" % len(restants))
    if plafonne:
        ecrire("  LAISSEES DE COTE par --max-photos: %d "
               "(un plafond tu se lirait comme un fonds propre)" % plafonne)
    if not a.appliquer:
        ecrire("")
        ecrire("  A BLANC : la lecture a lieu, aucune ecriture. Ajouter "
               "--appliquer.")
    ecrire("=" * 74)
    jp = CORBEILLE / ("xmp_tous_%s.jsonl" % horodatage())
    if a.appliquer:
        ecrire("  journal  : %s" % jp)
        ecrire("  reprise  : %s" % FAITS_TOUS)
    r = balayer(par_chemin, exe, jp, FAITS_TOUS, serveur=a.serveur,
                lot=max(1, a.lot), appliquer_vrai=a.appliquer, ecrire=ecrire,
                patience_s=max(0, a.patience))
    ecrire("")
    ecrire("=" * 74)
    ecrire("  photos lues        : %d sur %d" % (r['vues'], r['total']))
    ecrire("  reecrites          : %d" % r['reecrites'])
    ecrire("  en echec           : %d" % r['rates'])
    if r.get('attentes'):
        ecrire("  attentes de la file: %d fois, %d s au total (le curateur "
               "rattache des visages tout seul)"
               % (r['attentes'], int(r['attente_s'])))
    if r['total'] > r['vues']:
        ecrire("  NON LUES           : %d (ni reparees, ni marquees faites : "
               "elles repasseront)" % (r['total'] - r['vues']))
    if plafonne:
        ecrire("  hors plafond       : %d" % plafonne)
    if sautes:
        ecrire("")
        ecrire("  %d NOM(S) SAUTE(S) — leurs cles n ont pas pu etre lues :"
               % len(sautes))
        for nom in sautes:
            ecrire("    - %s" % nom)
        ecrire("  Leurs photos ont pu etre marquees FAITES parce qu elles")
        ecrire("  portent un AUTRE nom : la reprise ne les rattrapera pas.")
        ecrire("  Les reprendre un par un, ce mode ignore le fichier de")
        ecrire("  reprise :  --nom NOM --appliquer")
        ecrire("  Liste gardee dans %s" % NOMS_SAUTES)
    if r['arret']:
        ecrire("  ARRET AVANT LA FIN : %s" % r['arret'])
        ecrire("  Relancer reprendra ou ca s est arrete.")
    ecrire("  Verifier avec verifier_xmp_toutes_personnes.py.")
    ecrire("=" * 74)
    return 1 if (r['rates'] or r['arret']) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--rapport', default='',
                    help="le --json de verifier_xmp_personnes.py")
    ap.add_argument('--nom', default='')
    ap.add_argument('--absent', default='')
    ap.add_argument('--serveur', default='http://127.0.0.1:8080')
    ap.add_argument('--appliquer', action='store_true',
                    help="ecrire pour de vrai (sans lui : a blanc)")
    ap.add_argument('--tous', action='store_true',
                    help="balayer TOUS les noms, par PHOTO, avec reprise")
    ap.add_argument('--lot', type=int, default=200,
                    help="photos lues par tranche en mode --tous (defaut 200)")
    ap.add_argument('--max-photos', type=int, default=0,
                    help="plafond d essai en mode --tous (0 = tout)")
    ap.add_argument('--patience', type=int, default=PATIENCE_S,
                    help="secondes d attente quand la file du serveur "
                         "travaille (0 = ne pas attendre, comme avant)")
    a = ap.parse_args(argv)

    if a.tous and (a.rapport or a.nom):
        print("--tous balaie le fonds entier : il ne se combine ni avec "
              "--rapport ni avec --nom.")
        return 2
    if not a.tous and not a.rapport and not a.nom:
        print("il faut --tous, --rapport, ou --nom (la verite d'index vient "
              "de l'un des trois).")
        return 2

    libre, attendu, file = attendre_la_file(a.serveur,
                                            patience_s=max(0, a.patience))
    if not libre:
        print("REFUS : le serveur a encore %d operation(s) en file apres %d s "
              "d attente." % (file, attendu))
        print("  `person_writer` est l'ecrivain unique tant qu'il vit. Deux")
        print("  ecrivains sur les memes fichiers, c'est la bagarre du 22/08")
        print("  en pire. Attendre queues.personnes = 0, ou arreter le serveur.")
        return 3
    file = V.file_du_serveur(a.serveur)
    if file is None and not a.rapport:
        print("le serveur ne repond pas : sans lui, la verite d'index doit "
              "venir d'un --rapport ecrit quand il repondait encore.")
        return 2

    exe = V.exiftool_exe()
    if exe is None:
        print("ExifTool introuvable : rien a faire sans lui.")
        return 2

    if a.tous:
        return tour_du_fonds(a, V.exiftool_exe(), V.dossier_uploads())

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
