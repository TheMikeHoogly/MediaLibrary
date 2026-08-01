#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de l'orchestrateur maintenance.run_cycle avec un FAUX serveur (sv) :
stores/rekey/FS simules, is_busy pilotable, dry. Verifie cadence, autonomie,
priorite UI, et un cycle reel (dedup in-process + purge).
"""

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


def main():
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
