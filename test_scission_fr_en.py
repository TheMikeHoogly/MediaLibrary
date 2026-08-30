#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de la scission FR/EN : la regle pure (`scission_fr_en`) et l'applicateur
(`appliquer_scission_fr_en`) sur une base TEMPORAIRE (jamais photos.db).

Lance : python test_scission_fr_en.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

import scission_fr_en as S
import appliquer_scission_fr_en as A
from store_sqlite import SqliteStore

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def main():
    print("1) regle pure")
    saines = [
        {"kw_fr": ["chat", "fenêtre", "ciel", "table"], "kw_en": ["cat", "window", "sky", "table"]},
        {"kw_fr": ["femme", "arbre", "table"], "kw_en": ["woman", "tree", "sky"]},
        {"kw_fr": ["chat", "orange"], "kw_en": ["cat", "orange"]},
    ]
    vfr, ven = S.vocabulaires(saines)
    check(vfr["chat"] == 2 and ven["cat"] == 2 and vfr["table"] == 2 and ven["table"] == 1,
          "vocabulaires appris sur les entrees a kw_en")
    check(S.vote("chat", vfr, ven) == 1 and S.vote("cat", vfr, ven) == -1
          and S.vote("orange", vfr, ven) == 0 and S.vote("inconnu", vfr, ven) == 0,
          "votes : +1 FR, -1 EN, 0 a egalite ou inconnu")
    fr, en, ex, i = S.scinder(["chat", "fenêtre", "ciel", "cat", "window", "sky"], vfr, ven)
    check(fr == ["chat", "fenêtre", "ciel"] and en == ["cat", "window", "sky"] and ex == 1,
          "coupure unique au bon endroit")
    fr, en, ex, i = S.scinder(["chat", "ciel", "orange", "cat", "sky"], vfr, ven)
    check(fr == ["chat", "ciel", "orange"] and en == ["cat", "sky"] and ex == 2,
          "tag neutre a la frontiere : ex aequo tranche par le milieu (orange reste FR)")
    fr, en, ex, i = S.scinder(["chat", "ciel"], vfr, ven)
    check(en == [] and fr == ["chat", "ciel"], "tout francais : rien en EN")
    fr, en, ex, i = S.scinder(["cat", "sky"], vfr, ven)
    check(fr == [] and en == ["cat", "sky"], "tout anglais : rien en FR")
    r = S.scinder_entree({"kw_fr": ["chat", "ciel", "cat", "sky", "animal:Caline"], "kw_en": []}, vfr, ven)
    check(r is not None and r[0] == ["chat", "ciel", "animal:Caline"] and r[1] == ["cat", "sky"],
          "scinder_entree : le nom reste en kw_fr, le bloc anglais part en kw_en")
    check(S.scinder_entree({"kw_fr": ["chat", "cat"], "kw_en": ["cat"]}, vfr, ven) is None,
          "une entree qui a deja un kw_en n est pas touchee")
    check(S.scinder_entree({"kw_fr": ["animal:Caline"], "kw_en": []}, vfr, ven) is None,
          "une entree sans mot-cle (noms seuls) n est pas touchee")

    print("2) applicateur sur une base temporaire")
    tmp = Path(tempfile.mkdtemp(prefix="scission_"))
    try:
        db = tmp / "photos.db"
        st = SqliteStore(db, 'tags')
        for i, e in enumerate(saines):
            st.set('sain%d' % i, dict(e, desc='x'))
        st.set('mixte', {"kw_fr": ["chat", "fenêtre", "ciel", "cat", "window", "sky", "animal:Caline"],
                         "kw_en": [], "desc": "Un chat", "in_file": True, "taken": 1.0})
        st.set('mixte_exaequo', {"kw_fr": ["chat", "ciel", "orange", "cat", "sky"], "kw_en": []})
        st.set('video', {"video": True, "kw_fr": [], "kw_en": []})
        st.set('rate', {"failed": True})
        st.save()
        ops, _ = A.plan(st.data)
        check([o[0] for o in ops] == ['mixte', 'mixte_exaequo'], "plan : les deux entrees melangees, rien d autre")
        ops_u, _ = A.plan(st.data, sans_ex_aequo=True)
        check([o[0] for o in ops_u] == ['mixte'], "--sans-ex-aequo ne garde que la coupure unique")
        n, journal = A.appliquer(st, ops, lambda m: None)
        e = st.data.get('mixte')
        check(n == 2 and list(e['kw_fr']) == ["chat", "fenêtre", "ciel", "animal:Caline"]
              and list(e['kw_en']) == ["cat", "window", "sky"], "entree scindee dans l index")
        check(e.get('desc') == "Un chat" and e.get('in_file') is True and e.get('taken') == 1.0,
              "rien d autre n a bouge (desc, in_file, taken)")
        check(len(journal['operations']) == 2 and journal['operations'][0]['kw_fr_avant'][:2] == ["chat", "fenêtre"],
              "journal : les listes d avant")
        st2 = SqliteStore(db, 'tags')
        check(list(st2.data.get('mixte')['kw_en']) == ["cat", "window", "sky"], "persiste sur disque")
        jp = tmp / "undo.json"
        jp.write_text(json.dumps(journal, ensure_ascii=False), encoding='utf-8')
        A.undo(st2, str(jp), dry=False, log=lambda m: None)
        e = st2.data.get('mixte')
        check(list(e['kw_fr']) == ["chat", "fenêtre", "ciel", "cat", "window", "sky", "animal:Caline"] and e['kw_en'] == [],
              "undo remet les listes d avant")
        st.cx.close(); st2.cx.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print("ECHEC : %d assertion(s) fausse(s)" % len(FAIL))
        return 1
    print("Tout est vert - la scission est pure, appliquee, et reversible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
