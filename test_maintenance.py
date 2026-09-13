#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de l'orchestrateur maintenance.run_cycle avec un FAUX serveur (sv) :
stores/rekey/FS simules, is_busy pilotable, dry. Verifie cadence, autonomie,
priorite UI, et un cycle reel (dedup in-process + purge).
"""

import ast
import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import maintenance as M

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def check_cablage_refus_standalone():
    """1 sexdecies (03/09, demande de Mike) : main() DOIT verifier le verrou
    (refus_d_ecriture) AVANT make_standalone_sv/run_cycle -- sur le texte
    source (ast), jamais en executant main() pour de vrai : ce lanceur mute
    photos.db si le verrou est absent."""
    print("0) cablage : main() verifie le verrou avant de muter (1 sexdecies)")
    source = Path(__file__).resolve().parent.joinpath('maintenance.py') \
        .read_text(encoding='utf-8')
    tree = ast.parse(source)
    main_fn = next((n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == 'main'), None)
    check(main_fn is not None, "main() trouvable dans maintenance.py")
    if main_fn is None:
        return

    def nom_appel(n):
        if isinstance(n.func, ast.Attribute):
            return n.func.attr
        return getattr(n.func, 'id', None)

    appels = [(getattr(n, 'lineno', 0), nom_appel(n))
              for n in ast.walk(main_fn) if isinstance(n, ast.Call)]
    noms = [nom for _, nom in appels]
    check('refus_d_ecriture' in noms,
          "main() appelle refus_d_ecriture (le verrou n'est plus une simple promesse en commentaire)")

    ordre = sorted(appels)
    premiers = [nom for _, nom in ordre if nom in ('refus_d_ecriture', 'make_standalone_sv')]
    check(bool(premiers) and premiers[0] == 'refus_d_ecriture',
          "refus_d_ecriture est appele AVANT make_standalone_sv (sinon le cycle "
          "standalone peut deja avoir mute l'index avant le refus)")

    src_main = ast.get_source_segment(source, main_fn) or ''
    check("'--dry' in sys.argv" in src_main and "'--forcer' in sys.argv" in src_main,
          "dry et forcer restent lisibles depuis la ligne de commande, comme les autres appliquer_*.py")


class FakeSv:
    def __init__(self, tmp, busy=False, dry=False, autonomy=None):
        self.dry = dry
        self.busy = busy
        self.autonomy = dict(M.AUTONOMY, **(autonomy or {}))
        self.intervals = dict(M.INTERVALS)
        self.tags = {}
        self.rekeys = []
        self.readonly_calls = []
        self.logs = []
        self.paths = {
            'corbeille': str(tmp / '.corbeille-rangement'),
            'plan': str(tmp / 'plan.json'),
            'recensement': str(tmp / 'rec.json'),
            'state': str(tmp / 'state.json'),
            'report': str(tmp / 'report.json'),
            'racine': str(tmp),
        }

    def rekey(self, old, new):
        self.rekeys.append((old, new))
        return True

    def tags_get(self, k):
        return self.tags.get(k)

    def tags_set(self, k, e):
        self.tags[k] = e

    def tags_save(self):
        pass

    def is_busy(self):
        return self.busy

    def log(self, m):
        self.logs.append(m)

    def run_readonly(self, args):
        self.readonly_calls.append(args)
        return 0


def check_gps_standalone():
    """1 sexdecies suite (04/09) : StandaloneSv.rekey() doit transporter
    gps_places.json (7e magasin) -- AP.rekey_stores seul l'ignore
    (deplacer_dossiers.py le dit de lui-meme : "Il ignore aussi
    gps_places.json"), exactement la divergence que redoute l'item
    ROADMAP "UNIFIER le re-cle". `appliquer_plan` est bouchonne : ni vraie
    base ni vrai gps_places.json touches."""
    print("0 ter) StandaloneSv transporte gps_places.json au re-cle (1 sexdecies)")
    import appliquer_plan as AP

    tmp = Path(tempfile.mkdtemp(prefix="maint_gps_"))
    try:
        gps_path = tmp / 'gps_places.json'
        gps_path.write_text(json.dumps({'\\\\nas\\a.jpg': 'Lausanne'}),
                            encoding='utf-8')

        appels = []
        original_open, original_rekey = AP.open_stores, AP.rekey_stores
        AP.open_stores = lambda db: ({}, None)
        AP.rekey_stores = (lambda old, new, stores, semantic, compte=None:
                            appels.append((old, new)) or True)
        try:
            sv = M.StandaloneSv(db=str(tmp / 'photos.db'), gps=str(gps_path))
            ok = sv.rekey('\\\\nas\\a.jpg', '\\\\nas\\b.jpg')
            check(ok, "rekey() renvoie vrai (delegue a rekey_stores bouchonne)")
            check(appels == [('\\\\nas\\a.jpg', '\\\\nas\\b.jpg')],
                  "rekey_stores a bien recu les deux cles")
            avant = json.loads(gps_path.read_text(encoding='utf-8'))
            check(avant == {'\\\\nas\\a.jpg': 'Lausanne'},
                  "gps_places.json pas encore ecrit avant gps_save (dirty en memoire seulement)")
            sv.gps_save()
            relu = json.loads(gps_path.read_text(encoding='utf-8'))
            check(relu == {'\\\\nas\\b.jpg': 'Lausanne'},
                  "gps_places.json suit le re-cle (7e magasin, plus jamais silencieux)")
        finally:
            AP.open_stores, AP.rekey_stores = original_open, original_rekey
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_scan_nas_fait_ceder_la_maintenance():
    """06/09, 11h38 : le scan enumerait DEJA la racine (rglob de 44 000
    fichiers sur SMB) quand la passe de maintenance est tombee dessus. Deux
    balayages SMB concurrents -- plus de 85 minutes au lieu de 632 s, et deux
    heures de GPU au repos derriere. `is_busy` cedait a l'UI et a la charge
    machine, jamais au SCAN : la seule des trois qui tenait le disque."""
    print("0 quater) la maintenance cede a un balayage NAS en cours")
    src = Path(__file__).resolve().parent.joinpath('server.py') \
        .read_text(encoding='utf-8')
    tree = ast.parse(src)

    def corps(nom):
        n = next((x for x in ast.walk(tree)
                  if isinstance(x, ast.FunctionDef) and x.name == nom), None)
        check(n is not None, nom + " trouvable dans server.py")
        return (ast.get_source_segment(src, n) or '') if n else ''

    ib = corps('is_busy')
    check('scan_nas_en_cours()' in ib,
          "is_busy() compte le balayage NAS, pas seulement l'UI et la charge")
    check('ui_recent()' in ib and 'system_busy()' in ib,
          "les deux gardes d'origine sont conservees")

    ml = corps('maintenance_loop')
    check('scan_nas_debut()' in ml and 'scan_nas_fin()' in ml,
          "le drapeau est pose et leve autour du scan")
    apres = ml[ml.index('scan_nas_debut()'):]
    check('finally:' in apres
          and apres.index('finally:') < apres.index('scan_nas_fin()'),
          "leve DANS le finally qui suit la pose : un scan qui meurt ne "
          "laisse pas la maintenance en retrait pour toujours")
    check(apres.index('scan_uploads(') < apres.index('scan_nas_fin()'),
          "le drapeau couvre bien le scan lui-meme")
    check(ml.count('if nas:') >= 2,
          "seul un tour QUI TOUCHE LE NAS pose le drapeau (Uploads est local)")

    # Un drapeau qu'on ne voit pas ne se prouve pas : tant qu'aucune etape
    # n'est due, le journal reste muet et rien ne dit si le drapeau est pose.
    check("scan_nas=scan_nas_en_cours()" in src,
          "l'etat du balayage NAS est LISIBLE (/api/maint/status -> boucle)")

    # Le compteur, pas le booleen : deux scans ne se relachent pas l'un l'autre.
    check('max(0, SCAN_NAS_EN_COURS - 1)' in src,
          "le compteur ne descend jamais sous zero")

    # Et le journal doit nommer LA BONNE cause : il disait « UI active » quoi
    # qu'il arrive -- il aurait donc envoye chercher la panne du 06/09 du
    # mauvais cote.
    class SvScan:
        dry = False
        autonomy = dict(M.AUTONOMY)
        intervals = dict(M.INTERVALS)
        paths = {}
        def is_busy(self):
            return True
        def raison_busy(self):
            return "scan NAS en cours"
    dit = M._raison(SvScan())
    check(dit == "scan NAS en cours",
          "le journal nomme le scan NAS, pas l'UI")

    class SvMuet:
        pass
    check(M._raison(SvMuet()) == "occupee",
          "un pont sans raison_busy (StandaloneSv) continue de tourner")


def check_l_autre_moitie_du_garde_fou():
    """Et le SENS INVERSE : une etape lourde deja partie, un scan NAS qui
    tombe dessus. `is_busy` ne protege que le DEPART d'une etape ; une fois
    lancee, plus rien ne parlait au scan. Meme panne que le 06/09, jouee dans
    l'autre ordre."""
    print("0 quinquies) le scan NAS cede a une etape lourde deja partie")
    ici = Path(__file__).resolve().parent
    src = ici.joinpath('server.py').read_text(encoding='utf-8')
    tree = ast.parse(src)

    def corps(nom):
        n = next((x for x in ast.walk(tree)
                  if isinstance(x, ast.FunctionDef) and x.name == nom), None)
        check(n is not None, nom + " trouvable dans server.py")
        return (ast.get_source_segment(src, n) or '') if n else ''

    # 1. Le VRAI service porte les deux crochets. C'est ce qui ferme le trou
    #    ouvert par le `getattr` de maintenance.py : l'optionalite y est faite
    #    pour les services de banc, pas pour laisser _MaintSv sans rien.
    sv = next((x for x in ast.walk(tree)
               if isinstance(x, ast.ClassDef) and x.name == '_MaintSv'), None)
    check(sv is not None, "_MaintSv trouvable")
    methodes = {m.name for m in (sv.body if sv else [])
                if isinstance(m, ast.FunctionDef)}
    check('etape_lourde_debut' in methodes and 'etape_lourde_fin' in methodes,
          "_MaintSv implemente les deux crochets (l'optionalite du getattr "
          "est pour les bancs, pas pour le vrai service)")

    # 2. La boucle REPORTE, elle ne bloque pas.
    ml = corps('maintenance_loop')
    check('maint_lourde_en_cours()' in ml,
          "la boucle de scan consulte l'etape lourde")
    check('nas_reporte' in ml and 'NAS_REPORTS_MAX' in ml,
          "elle REPORTE (et plafonne les reports) au lieu de bloquer")
    check('.acquire(' not in ml and 'with MAINT_LOURDE_LOCK' not in ml,
          "aucun verrou pris dans la boucle : bloquer ferait attendre la file "
          "de retag derriere un recensement de vingt minutes")

    # 3. L'echeance n'est pas PERDUE, et le premier scan n'est jamais reporte.
    check('nas = nas or nas_reporte' in ml,
          "un volet NAS reporte revient au tour suivant : un `deep` tombe "
          "pendant un recensement ne perd pas son lot de retag")
    check('not first and maint_lourde_en_cours()' in ml,
          "le scan de DEMARRAGE n'est jamais reporte : l'index en depend")

    # 4. Le drapeau se leve dans un finally, cote maintenance.
    m = ici.joinpath('maintenance.py').read_text(encoding='utf-8')
    check('etape_lourde_debut' in m and 'etape_lourde_fin' in m,
          "maintenance.py appelle les deux crochets")
    i_d = m.index('etape_lourde_debut')
    apres = m[i_d:]
    check('finally:' in apres
          and apres.index('finally:') < apres.index('etape_lourde_fin'),
          "leve DANS le finally : une etape qui plante ne laisse pas le scan "
          "en retrait pour toujours")
    check(m.index('LOURDES = ') < i_d and '_lourde = step in LOURDES' in m,
          "seules les etapes LOURDES posent le drapeau")


def check_le_drapeau_lourd_compte_au_lieu_de_basculer():
    """Deux etapes lourdes ne doivent pas se relacher l'une l'autre -- meme
    raison que pour le scan, ou le booleen avait ete refuse."""
    print("0 sexies) le drapeau d'etape lourde COMPTE")
    import importlib.util
    ici = Path(__file__).resolve().parent
    src = ici.joinpath('server.py').read_text(encoding='utf-8')
    check('MAINT_LOURDE_EN_COURS = 0' in src, "un compteur, pas un booleen")
    check('MAINT_LOURDE_EN_COURS = max(0, MAINT_LOURDE_EN_COURS - 1)' in src,
          "le compteur ne descend jamais sous zero")
    # Rejoue la mecanique sans importer le serveur (il ouvrirait la base).
    lock, n = __import__('threading').Lock(), [0]
    def debut():
        with lock: n[0] += 1
    def fin():
        with lock: n[0] = max(0, n[0] - 1)
    def en_cours():
        with lock: return n[0] > 0
    debut(); debut(); fin()
    check(en_cours(), "deux etapes lourdes : la premiere qui finit ne "
                      "relache pas le drapeau de la seconde")
    fin()
    check(not en_cours(), "les deux finies : le drapeau retombe")
    fin()
    check(not en_cours(), "un `fin` en trop ne rend pas le compteur negatif")


def check_une_etape_lourde_dit_quand_elle_FINIT():
    """MESURE du 13/09 : le recensement a annonce son depart a 16h43 et plus
    rien pendant 40 minutes. Pour savoir s'il tournait encore il fallait
    croiser le journal, `maintenance_report.json` et `recensement.json`.
    Une etape qui dit << je pars >> et jamais << j'arrive >> est le mode de
    panne que ce projet paye le plus cher."""
    print("0 septies) une etape lourde dit sa FIN, sa DUREE et son VERDICT")
    # UN DOSSIER NEUF PAR SCENARIO. `run_cycle` ecrit `state.json` : reutiliser
    # le meme temporaire rendait les cycles suivants VIDES (plus rien de du),
    # donc leurs journaux vides -- et un banc qui cherche l'ABSENCE d'une ligne
    # serait alors passe au vert sans avoir rien mesure. Trouve en ecrivant ce
    # banc, le 13/09.
    faits = []

    def neuf(prefixe, cls=None, **kw):
        d = Path(tempfile.mkdtemp(prefix=prefixe))
        faits.append(d)
        return (cls or FakeSv)(d, **kw)

    try:
        sv = neuf("maint_fin_", autonomy={'recensement': 'auto'})
        M.run_cycle(sv, now=time.time())
        fins = [l for l in sv.logs if l.startswith('recensement : terminee en ')]
        check(len(fins) == 1, "la fin est DITE, une seule fois : %r" % (sv.logs,))
        check(' s' in fins[0] or ' min ' in fins[0], "elle porte une DUREE")

        print("   et elle la dit AUSSI quand l'etape casse")

        class SvQuiCasse(FakeSv):
            def run_readonly(self, args):
                raise RuntimeError('le NAS a disparu')

        sv2 = neuf("maint_casse_", SvQuiCasse, autonomy={'recensement': 'auto'})
        leve = False
        try:
            M.run_cycle(sv2, now=time.time())
        except RuntimeError:
            leve = True
        check(leve, "l'exception n'est pas avalee -- elle remonte")
        fins2 = [l for l in sv2.logs if l.startswith('recensement : interrompue')]
        check(len(fins2) == 1,
              "une etape qui LEVE le dit au lieu de disparaitre : %r" % (sv2.logs,))

        print("   un code de retour non nul est DIT, pas seulement classe")

        class SvQuiEchoue(FakeSv):
            def run_readonly(self, args):
                self.readonly_calls.append(args)
                return 3

        sv3 = neuf("maint_echec_", SvQuiEchoue, autonomy={'recensement': 'auto'})
        M.run_cycle(sv3, now=time.time())
        check(any('ECHEC (code 3)' in l for l in sv3.logs),
              "le code de retour du recensement est dans le journal")
        check(any("plan de rangement n'a PAS ete lance" in l for l in sv3.logs),
              "et le journal dit la CONSEQUENCE : le plan est saute avec lui")
        check(not any('plan de rangement (lecture seule)' in l for l in sv3.logs),
              "le plan n'annonce pas un depart qui n'a pas eu lieu")
        check(len(sv3.readonly_calls) == 1,
              "le plan n'est effectivement pas lance apres un recensement KO")

        print("   les DEUX sous-processus annoncent le leur, separement")
        sv5 = neuf("maint_deux_", autonomy={'recensement': 'auto'})
        M.run_cycle(sv5, now=time.time())
        check(any(l.startswith('recensement : lu en ') for l in sv5.logs),
              "le recensement dit sa propre duree")
        check(any(l.startswith('plan de rangement : bati en ') for l in sv5.logs),
              "le plan dit la sienne -- mesure le 13/09 : 9 min contre 22, "
              "une seule ligne pour les deux ne disait pas ou on en etait")

        print("   une etape LEGERE ne bavarde pas pour rien")
        # Les LOURDES coupees : sinon elles tournent aussi (dossier neuf =
        # tout est du) et le banc ne mesurerait pas ce qu'il croit.
        sv4 = neuf("maint_legere_", autonomy={'recensement': 'off',
                                              'dedup': 'off',
                                              'rename': 'propose'})
        M.run_cycle(sv4, now=time.time())
        check(sv4.logs, "le cycle a bien FAIT quelque chose (sinon ce banc "
                        "mesurerait le vide)")
        check(not any(' : terminee en ' in l for l in sv4.logs),
              "seules les etapes LOURDES annoncent leur fin : %r" % (sv4.logs,))
    finally:
        for d in faits:
            shutil.rmtree(d, ignore_errors=True)


def check_la_duree_se_lit_a_l_oeil():
    """Un journal se lit a l'oeil : << 2412 s >> ne dit pas la meme chose que
    << 40 min 12 s >> a quelqu'un qui se demande si une etape part en vrille."""
    print("0 octies) la duree est ecrite en clair")
    check(M._duree(0) == '0 s', "zero")
    check(M._duree(59) == '59 s', "sous la minute : en secondes")
    check(M._duree(60) == '1 min 00 s', "la minute pile")
    check(M._duree(2412) == '40 min 12 s', "la vraie mesure du 13/09")
    check(M._duree(3600) == '1 h 00 min', "l'heure pile")
    check(M._duree(4050) == '1 h 07 min', "au-dela de l'heure : les secondes ne servent plus")
    check(M._duree(-5) == '0 s', "une horloge qui recule ne fabrique pas une duree negative")


def check_l_etape_lourde_en_cours_est_INTERROGEABLE():
    """Le journal dit ce qui s'est PASSE. `/api/maint/status` doit dire ce qui
    se passe MAINTENANT : le rapport de cycle, lui, n'est ecrit qu'a la FIN --
    donc muet pendant l'etape la plus longue, celle sur laquelle on se pose la
    question."""
    print("0 nonies) l'etape lourde en cours se lit dans /api/maint/status")
    ici = Path(__file__).resolve().parent
    src = ici.joinpath('server.py').read_text(encoding='utf-8')
    arbre = ast.parse(src)
    noms = {n.name for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)}
    check('maint_lourde_etat' in noms, "la sonde existe")
    check("'lourde': maint_lourde_etat()" in src,
          "et elle est BRANCHEE dans la reponse de /api/maint/status")
    check('MAINT_LOURDE_DEPUIS = None' in src,
          "le depuis retombe a None quand plus rien ne tourne")
    # Rejoue la mecanique du `depuis` sans importer le serveur.
    lock, n, depuis = __import__('threading').Lock(), [0], [None]
    def debut():
        with lock:
            if n[0] == 0:
                depuis[0] = 1000.0
            n[0] += 1
    def fin():
        with lock:
            n[0] = max(0, n[0] - 1)
            if n[0] == 0:
                depuis[0] = None
    debut()
    t1 = depuis[0]
    debut()
    check(depuis[0] == t1,
          "une SECONDE etape lourde ne rajeunit pas le depart de la premiere")
    fin()
    check(depuis[0] == t1, "et la premiere qui finit ne l'efface pas non plus")
    fin()
    check(depuis[0] is None, "les deux finies : plus rien ne tourne, plus de depart")


def main():
    check_scan_nas_fait_ceder_la_maintenance()
    print()
    check_l_autre_moitie_du_garde_fou()
    print()
    check_le_drapeau_lourd_compte_au_lieu_de_basculer()
    print()
    check_une_etape_lourde_dit_quand_elle_FINIT()
    print()
    check_la_duree_se_lit_a_l_oeil()
    print()
    check_l_etape_lourde_en_cours_est_INTERROGEABLE()
    print()
    check_cablage_refus_standalone()
    print()
    check_gps_standalone()
    print()

    tmp = Path(tempfile.mkdtemp(prefix="maint_"))
    try:
        # --- fabrique un plan de dedoublonnage avec 1 quarantaine reelle ---
        contenu = b"DUP" * 500
        sha = hashlib.sha256(contenu).hexdigest()
        canon = tmp / "2015" / "photo.jpg"
        src = tmp / "_A TRIER" / "photo.jpg"
        canon.parent.mkdir(parents=True)
        src.parent.mkdir(parents=True)
        canon.write_bytes(contenu)
        src.write_bytes(contenu)
        dst = tmp / ".corbeille-rangement" / sha[:8] / "aa11_photo.jpg"
        plan = {'corbeille': str(tmp / ".corbeille-rangement"), 'operations': [{
            'id': 'q0001', 'type': 'quarantine', 'src': str(src), 'dst': str(dst),
            'fusion_noms': ['personne:Zoe'],
            'preuve': {'sha256': sha, 'taille': len(contenu),
                       'canonique': str(canon), 'n_copies': 2},
            'manifeste': {'groupe': sha[:8]}}]}

        print("1) cadence : une etape recente n'est pas re-lancee")
        st = {'purge': time.time()}
        check(not M.due('purge', st, time.time(), M.INTERVALS), "purge recente -> pas due")
        check(M.due('purge', {}, time.time(), M.INTERVALS), "jamais faite -> due")

        print("2) cycle complet (recensement force en auto pour le tester)")
        sv = FakeSv(tmp, autonomy={'recensement': 'auto'})
        Path(sv.paths['plan']).write_text(json.dumps(plan), encoding='utf-8')
        sv.tags[str(canon)] = {'kw_fr': [], 'desc': 'x'}
        # une vieille corbeille a purger
        vieux = Path(sv.paths['corbeille']) / "old12345"
        vieux.mkdir(parents=True)
        (vieux / "aa11_x.jpg").write_bytes(b"z" * 100)
        (vieux / "manifeste.json").write_text(json.dumps({
            'canonique': str(canon), 'sha256': sha,
            'date_application': time.strftime('%Y-%m-%d %H:%M:%S',
                                              time.localtime(time.time() - 40 * 86400))}),
            encoding='utf-8')

        lance = M.run_cycle(sv)
        check('recensement' in lance and sv.readonly_calls,
              "recensement (lecture seule) lance en sous-processus")
        check(lance.get('dedup', {}).get('ok') == 1, "dedup : 1 quarantaine appliquee")
        check(not src.exists() and dst.exists(), "source deplacee en quarantaine")
        check((str(src), str(dst)) in sv.rekeys, "index re-cle via sv.rekey")
        check('personne:Zoe' in sv.tags[str(canon)]['kw_fr'],
              "nom fusionne dans la canonique avant retrait")
        check(not vieux.exists(), "vieille corbeille purgee (>30j, canonique presente)")
        check(lance.get('rangement') == 'propose', "rangement par annee : propose")
        check(lance.get('rename') == 'propose', "rename : propose (application a venir)")

        print("3) re-lance aussitot : plus rien de du")
        lance2 = M.run_cycle(sv)
        check(lance2 == {}, "toutes les etapes recemment faites -> cycle vide")

        print("4) priorite UI : is_busy saute les etapes lourdes")
        sv2 = FakeSv(tmp / "b", busy=True)
        (tmp / "b").mkdir()
        for k in ('plan', 'corbeille', 'state', 'report'):
            sv2.paths[k] = str((tmp / "b") / Path(sv.paths[k]).name)
        sv2.paths['corbeille'] = str(tmp / "b" / ".corbeille-rangement")
        Path(sv2.paths['plan']).write_text(json.dumps(
            {'corbeille': sv2.paths['corbeille'], 'operations': []}), encoding='utf-8')
        lance3 = M.run_cycle(sv2)
        check('recensement' not in lance3 and 'dedup' not in lance3,
              "UI active : recensement + dedup reportes")
        check('purge' in lance3, "purge (legere) tourne meme si UI active")

        print("5) autonomie 'off' desactive une etape")
        sv3 = FakeSv(tmp / "c", autonomy={'purge': 'off'})
        (tmp / "c").mkdir()
        sv3.paths['corbeille'] = str(tmp / "c" / ".corbeille-rangement")
        Path(sv3.paths['plan']).write_text(json.dumps(
            {'corbeille': sv3.paths['corbeille'], 'operations': []}), encoding='utf-8')
        lance4 = M.run_cycle(sv3)
        check('purge' not in lance4, "purge off -> jamais lancee")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert — orchestrateur : cadence, autonomie, priorite UI, cycle reel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
