#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test end-to-end de appliquer_doublons_image.py sur une base + un faux fonds
TEMPORAIRES (jamais le vrai NAS, jamais la vraie photos.db).

Scenario : un groupe IDENTIQUE a TROIS copies — la canonique chez Mike
(`Photos Mike\\2015\\`), une copie chez Flo qui porte un nom humain
« animal:Caline » ABSENT de la canonique (+ une exclusion, une confirmation,
un visage juge, un lieu), et une copie sans rien. La canonique n'a AUCUN texte
IA ; la copie Flo en a un. On verifie que l'application :
  - ne retire PAS la copie a nom tant que le XMP n'a pas ete ecrit (--sans-xmp
    la GARDE ; le retrait des autres copies continue),
  - avec un ExifTool factice qui reussit : recopie le nom dans la canonique
    AVANT le deplacement (regle 2), et l'ordre est prouve par le faux ExifTool
    qui constate que la copie est encore la quand il ecrit,
  - herite le texte IA sur la canonique VIDE, et le lieu,
  - deplace en corbeille avec manifeste (jamais de rm), re-cle l'index,
  - FUSIONNE exclusion/confirmation/visage/auteur sur la canonique, sans doublon,
  - saute une copie dont la taille a change (preuve perimee),
  - est annulable (undo restaure fichiers et index ; les fusions restent).

Lance : python test_appliquer_doublons_image.py
"""
import base64
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import appliquer_doublons_image as A
import verifier_doublons_image as V
from store_sqlite import SqliteStore
from vectors import VectorStore

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def emb():
    return base64.b64encode(os.urandom(260)).decode()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dedup_image_"))
    try:
        nas = tmp / "Photos"
        canon = nas / "Photos Mike" / "2015" / "IMG_1.jpg"
        flo = nas / "Photos Flo" / "Calinous" / "IMG_1.jpg"
        nue = nas / "Photos Flo" / "2015 Vrac" / "IMG_1.jpg"
        perimee = nas / "Photos Mike" / "Divers" / "IMG_1.jpg"
        for p in (canon, flo, nue, perimee):
            p.parent.mkdir(parents=True, exist_ok=True)
        contenu = os.urandom(4096)
        canon.write_bytes(contenu)
        flo.write_bytes(contenu + b'\x00' * 300)      # XMP diverge : +300 octets
        nue.write_bytes(contenu)
        perimee.write_bytes(contenu)
        ck, fk, nk, pk = str(canon), str(flo), str(nue), str(perimee)

        db = tmp / "photos.db"
        stores = {t: SqliteStore(db, t) for t in ('tags', 'faces', 'people', 'animals', 'pets')}
        semantic = VectorStore(stores['tags'].cx)
        stores['tags'].set(ck, {"kw_fr": [], "kw_en": [], "desc": "", "size": 4096})
        stores['tags'].set(fk, {"kw_fr": ["chat", "animal:Caline"], "kw_en": ["cat"],
                                "desc": "Un chat calme dormant sur une couverture", "size": 4396})
        stores['tags'].set(nk, {"kw_fr": ["chat calico"], "desc": "Un chat calico", "size": 4096})
        stores['tags'].set(pk, {"kw_fr": [], "desc": "", "size": 4096})
        stores['faces'].set(ck, {"faces": [{"bbox": [1, 2, 3, 4], "emb": emb()}], "n": 1})
        stores['faces'].set(fk, {"faces": [{"bbox": [1, 2, 3, 4], "emb": emb()},
                                           {"bbox": [5, 6, 7, 8], "emb": emb()}], "n": 2})
        stores['animals'].set(ck, {"faces": [{"bbox": [1, 2, 3, 4], "emb": emb()}], "n": 1})
        stores['animals'].set(fk, {"faces": [{"bbox": [1, 2, 3, 4], "emb": emb()}], "n": 1})
        # fiche personne : visage 0 (existe chez la canonique) et 1 (n'existe pas),
        # une exclusion, une confirmation deja posee AUSSI sur la canonique
        stores['people'].set('mike', {"name": "Mike", "faces": [[fk, 0], [fk, 1]],
                                      "exclude": [fk], "confirmed": [fk, ck],
                                      "auteurs": {"faces:%s:0" % fk: "Flo", "exclude:%s" % fk: "Flo"}})
        stores['pets'].set('caline', {"name": "Caline", "faces": [[fk, 0]], "exclude": [], "confirmed": []})
        semantic.put_b64('photo', fk, emb())
        for s in stores.values():
            s.save()
        gps = {fk: "Bremblens"}

        groupe = {
            'verdict': 'IDENTIQUE', 'cles': [fk, nk, pk, ck],
            'hachages': ['h'] * 4, 'octets': [4396, 4096, 4096, 4096],
            'canonique': ck, 'entre_proprietaires': True,
            'retraits': [
                {'cle': fk, 'noms_a_recopier': ['animal:Caline'], 'gps_a_recopier': False, 'proprietaire': 'Flo'},
                {'cle': nk, 'noms_a_recopier': [], 'gps_a_recopier': False, 'proprietaire': 'Flo'},
                {'cle': pk, 'noms_a_recopier': [], 'gps_a_recopier': False, 'proprietaire': 'Mike'},
            ]}
        perimee.write_bytes(contenu + b'x')            # la taille a change depuis le banc

        print("0) verifier_doublons_image : apercu, lecture seule")
        j = V.juger_groupe(groupe, index=None, disque=True)
        verdicts = {r['cle']: r['verdict'] for r in j['retraits']}
        check(verdicts[fk] == 'ok' and verdicts[nk] == 'ok' and verdicts[pk] == 'taille',
              "apercu : deux retraits ok, la copie de taille changee SAUTEE")
        c, par = V.resumer([j])
        check(c['retraits'] == 2 and c['sautes_taille'] == 1 and par['Flo'] == 2,
              "apercu : compteurs (2 retraits, 1 saute, 2 chez Flo)")
        check(all(p.exists() for p in (canon, flo, nue, perimee)), "apercu : rien n a bouge")

        print("1) regle pure : fusionner_fiche")
        fiche = stores['people'].data.get('mike')
        champs, n = A.fusionner_fiche(dict(fiche), fk, ck, n_det=1)
        check(champs['faces'] == [[ck, 0], [fk, 1]],
              "visage 0 fusionne sur la canonique, visage 1 (sans detection en face) reste")
        check(champs['exclude'] == [ck] and champs['confirmed'] == [ck] and n == 3,
              "exclusion fusionnee, confirmation deja presente absorbee sans doublon, 3 decisions")
        check(champs['auteurs'] == {"faces:%s:0" % ck: "Flo", "exclude:%s" % ck: "Flo"},
              "auteurs suivent leurs decisions")
        champs2, n2 = A.fusionner_fiche({"faces": [[nk, 0]]}, fk, ck, 1)
        check(champs2 == {} and n2 == 0, "une fiche qui ne cite pas la copie est intacte")

        ctx = {'stores': stores, 'semantic': semantic, 'gps': gps, 'log': lambda m: None,
               'exiftool': None, 'sans_xmp': True, 'sans_verif': False,
               'trash': nas / '.corbeille-rangement', 'fournee': 'dedup_image_test',
               'now': '2026-08-30 08:00:00', 'sha': {}}
        journal = {'operations': []}
        compte = {}

        print("2) --sans-xmp : la copie a NOM est GARDEE, les autres partent")
        res = [A.appliquer_retrait(groupe, r, ctx, journal, compte) for r in groupe['retraits']]
        check(res == ['skip', 'ok', 'skip'], "resultats : skip (nom, XMP non ecrit) / ok / skip (perimee)")
        check(flo.exists() and 'animal:Caline' not in (stores['tags'].data.get(ck) or {}).get('kw_fr', []),
              "copie a nom toujours la, canonique sans le nom (rien de partiel)")
        check(not nue.exists() and perimee.exists(), "copie nue retiree, copie perimee gardee")
        dst_nue = journal['operations'][0]['dst']
        check(Path(dst_nue).exists() and Path(dst_nue).read_bytes() == contenu, "copie nue en corbeille, octets intacts")
        mani = json.loads((Path(dst_nue).parent / 'manifeste.json').read_text(encoding='utf-8'))
        check(mani['canonique'] == ck and mani['sha256'] == A.sha256(canon) and mani['date_application'],
              "manifeste : canonique, sha256 lu maintenant, date (purger_corbeille le lit)")
        check(nk not in stores['tags'].data and dst_nue in stores['tags'].data, "index re-cle vers la corbeille")
        check((stores['tags'].data.get(ck) or {}).get('desc') == "Un chat calico",
              "canonique VIDE herite du texte IA de la premiere copie retiree")

        print("3) ExifTool factice : le nom est ecrit AVANT le deplacement")
        vu = {}

        def faux_exiftool(exe, chemin, noms, timeout=120):
            vu['copie_encore_la'] = flo.exists()
            vu['noms'] = list(noms)
            vu['cible'] = str(chemin)
            return True
        A.xmp_ajouter_noms, vrai = faux_exiftool, A.xmp_ajouter_noms
        try:
            ctx['sans_xmp'] = False
            ctx['exiftool'] = 'factice'
            r = A.appliquer_retrait(groupe, groupe['retraits'][0], ctx, journal, compte)
        finally:
            A.xmp_ajouter_noms = vrai
        check(r == 'ok', "copie a nom retiree")
        check(vu.get('copie_encore_la') is True and vu.get('cible') == ck and vu.get('noms') == ['animal:Caline'],
              "XMP de la CANONIQUE ecrit pendant que la copie existe encore (noms d abord)")
        check('animal:Caline' in (stores['tags'].data.get(ck) or {}).get('kw_fr', []),
              "nom fusionne dans l index de la canonique")
        check(not flo.exists(), "copie a nom partie en corbeille")
        check((stores['tags'].data.get(ck) or {}).get('desc') == "Un chat calico",
              "texte de la canonique (deja herite) conserve : elle n est plus vide")
        mike = stores['people'].data.get('mike')
        check([list(x) for x in mike['faces']] == [[ck, 0], [journal['operations'][-1]['dst'], 1]],
              "visage 0 fusionne sur la canonique ; visage 1 suit le fichier en corbeille")
        check(list(mike['exclude']) == [ck] and list(mike['confirmed']) == [ck],
              "exclusion et confirmation sur la canonique, sans doublon")
        check(mike['auteurs'].get("faces:%s:0" % ck) == "Flo", "auteur fusionne")
        cal = stores['pets'].data.get('caline')
        check([list(x) for x in cal['faces']] == [[ck, 0]], "fiche animal : detection fusionnee (magasin animals)")
        check(gps.get(ck) == "Bremblens", "lieu herite par la canonique")
        check(journal['operations'][-1]['decisions_fusionnees'] == 4 and journal['operations'][-1]['noms_fusionnes'] == ['animal:Caline'],
              "journal : 4 decisions fusionnees (2 visages, 1 exclusion, 1 confirmation), noms")
        check(all(op.get('canonique') == ck for op in journal['operations']),
              "chaque op du journal porte `canonique` (journaux_deplacements)")

        print("4) UNDO : fichiers et index reviennent, les fusions restent")
        jp = tmp / "undo.json"
        jp.write_text(json.dumps(journal, ensure_ascii=False), encoding='utf-8')
        n = A.undo(str(jp), stores, semantic, dry=False, gps=gps, log=lambda m: None)
        check(n == 2 and flo.exists() and nue.exists(), "2 fichiers restaures")
        check(fk in stores['tags'].data and nk in stores['tags'].data, "index re-cle vers l origine")
        check('animal:Caline' in (stores['tags'].data.get(ck) or {}).get('kw_fr', []),
              "nom fusionne CONSERVE apres undo")
        check(not any((nas / '.corbeille-rangement' / 'dedup_image_test').rglob('*.jpg')),
              "corbeille vide de fichiers")

        for s in stores.values():
            s.cx.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print("ECHEC : %d assertion(s) fausse(s)" % len(FAIL))
        return 1
    print("Tout est vert - noms d abord, fusion sans doublon, corbeille reversible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
