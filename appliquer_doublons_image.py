#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APPLIQUE le dedoublonnage par l'IMAGE (ROADMAP 1 decies), de facon REVERSIBLE
──────────────────────────────────────────────────────────────────────────────

Lit `docs/doublons_image.json` (banc `mesure_doublons_image.py`, ExifTool
`ImageDataHash` : memes PIXELS, meme si le XMP a diverge) et, pour chaque groupe
IDENTIQUE, retire les copies non canoniques vers la corbeille du NAS —
`Photos\\.corbeille-rangement\\dedup_image_<date>\\<groupe>\\` — avec un
`manifeste.json` que `purger_corbeille.py` (bat 24, 30 jours) reconnait.
JAMAIS de `rm`. Tout est annulable (`--undo`).

Modele : `appliquer_plan.py` (le dedoublonnage au sha256 du 23/08) dont il
reutilise les primitives d'index (`rekey_stores`, `merge_names`, `sha256`) et
la preuve du serveur arrete (`appliquer_plan_annee.refus_d_ecriture`). Ce qui
change : la preuve d'identite est le hachage d'IMAGE du banc, les groupes
peuvent avoir plus de deux copies (167 en ont), et les DECISIONS humaines de la
copie retiree sont FUSIONNEES sur la canonique au lieu de la suivre en corbeille.

A LANCER SERVEUR ARRETE — et PROUVE (HTTP + `BEGIN IMMEDIATE`), pas demande :
ce script ecrit dans `photos.db` (invariant 4, ecrivain unique).

Sequence par copie a retirer (l'ordre EST la garantie « rien ne se perd ») :
  1. PREUVE NON PERIMEE : la copie et la canonique existent et ont la TAILLE
     que le banc a vue ; sinon on SAUTE (le fichier a change depuis la nuit).
     `--sans-verif` ne saute que l'egalite de taille, jamais l'existence.
  2. NOMS D'ABORD (regle 2) : les `personne:`/`animal:` que la copie porte et
     que la canonique n'a pas — ceux du rapport ET ceux de l'index d'aujourd'hui
     — sont ecrits dans le XMP de la canonique (ExifTool, argfile UTF-8 : un
     accent passe en ligne de commande arrive faux sous Windows), PUIS dans
     l'index. Si le XMP ne peut pas etre ecrit, la copie n'est PAS retiree.
  3. TEXTE IA (regle de Mike, 30/08) : la canonique garde son texte ; si elle
     n'en a AUCUN (jamais taguee), elle herite de celui de la copie.
  4. Libelle de lieu (`gps_places.json`) : recopie sur la canonique si elle
     n'en a pas.
  5. DEPLACEMENT src -> corbeille, manifeste (canonique, sha256 de la canonique
     lu MAINTENANT, hachage d'image du banc).
  6. RE-CLE de l'index vers la corbeille (7 magasins, `rekey_stores`), puis
     FUSION des decisions humaines sur la canonique : exclusions et
     confirmations toujours ; un visage `[copie, i]` seulement si la canonique
     a une detection d'indice i (memes pixels, meme detecteur : meme ordre),
     sinon il reste sur la cle de corbeille, que la chaine des journaux
     (`journaux_deplacements`) sait remonter. Jamais de doublon.
  7. Journal `docs/undo_doublons_<date>.json` : chaque op porte `canonique`.

`--undo` remet les fichiers et re-cle l'index vers l'origine ; les noms, le
texte et les decisions fusionnes sur la canonique sont CONSERVES (additifs,
sans risque ; les defaire serait plus dangereux qu'utile — comme au 23/08).

Modes :
    python appliquer_doublons_image.py                      # APERCU (= verifier_doublons_image)
    python appliquer_doublons_image.py --appliquer --entre-proprietaires --limite 20
    python appliquer_doublons_image.py --appliquer --entre-proprietaires   # lot 1 : Flo+Mike
    python appliquer_doublons_image.py --appliquer                          # tout
    python appliquer_doublons_image.py --undo docs/undo_doublons_XXXX.json --appliquer
Options : --rapport, --db, --forcer, --sans-verif, --sans-xmp (n ecrit pas les
noms dans le XMP : la copie qui en porte est alors GARDEE).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from appliquer_plan import open_stores, rekey_stores, merge_names, sha256
from appliquer_plan_annee import refus_d_ecriture, charger_gps, ecrire_gps, recler_gps
from recle_decisions import _paire
import auteurs as _au
import verifier_doublons_image as V

RACINE = Path(__file__).resolve().parent
STORES_PAR_NOM = (('people', 'faces'), ('pets', 'animals'))   # fiche -> detections
CHAMPS_TEXTE = ('desc', 'kw_fr', 'kw_en')


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


# ── ExifTool : les noms dans le XMP de la canonique ──────────────────────────

def exiftool():
    """`exiftool*/exiftool.exe` dans le projet, sinon le PATH (comme le banc)."""
    for c in sorted(RACINE.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return str(p)
    return shutil.which('exiftool')


def xmp_ajouter_noms(exe, chemin, noms, timeout=120):
    """Ecrit `noms` dans XMP-dc:Subject et IPTC:Keywords de `chemin`, sans
    doublon (-= puis +=, comme `server.write_person_tags`). Argfile UTF-8 avec
    BOM et `-charset filename=UTF8`. Rend vrai si ExifTool a reussi."""
    if not noms:
        return True
    if not exe:
        return False
    args = ['-overwrite_original', '-P', '-q', '-m', '-charset', 'filename=UTF8',
            '-codedcharacterset=utf8']
    for n in noms:
        args += ['-XMP-dc:Subject-=%s' % n, '-IPTC:Keywords-=%s' % n,
                 '-XMP-dc:Subject+=%s' % n, '-IPTC:Keywords+=%s' % n]
    args.append(str(chemin))
    argfile = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                         encoding='utf-8-sig') as tf:
            tf.write('\n'.join(args))
            argfile = tf.name
        r = subprocess.run([exe, '-@', argfile], capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False
    finally:
        if argfile:
            try:
                os.unlink(argfile)
            except OSError:
                pass


# ── texte IA, decisions ──────────────────────────────────────────────────────

def heriter_texte(stores, canon, copie):
    """La canonique sans AUCUN texte herite de celui de la copie (desc, kw_fr,
    kw_en). Les noms deja fusionnes dans `kw_fr` de la canonique sont gardes.
    Rend vrai si quelque chose a ete herite."""
    ec = stores['tags'].data.get(canon)
    ecop = stores['tags'].data.get(copie)
    if ec is None or not V.texte_vide(ec) or V.texte_vide(ecop):
        return False
    e = dict(ec)
    noms_canon = [t for t in (e.get('kw_fr') or []) if isinstance(t, str)
                  and t.startswith(V.PREFIXES_NOMS)]
    for fld in CHAMPS_TEXTE:
        if fld in ecop:
            e[fld] = ecop[fld] if not isinstance(ecop[fld], list) else list(ecop[fld])
    kw = list(e.get('kw_fr') or [])
    e['kw_fr'] = kw + [n for n in noms_canon if n not in kw]
    stores['tags'].set(canon, e, save=False)
    return True


def fusionner_fiche(fiche, old, canon, n_det):
    """(champs a reassigner, nombre de decisions fusionnees) : les decisions
    de `old` passent sur `canon`. Regle pure, miroir de
    `recle_decisions.recler_fiche`, a une difference : un visage `[old, i]`
    n'est deplace que si `i < n_det` (la canonique a cette detection) — sinon
    il reste ou il est. Jamais de doublon : une cible deja jugee absorbe."""
    if not isinstance(fiche, dict) or old == canon:
        return {}, 0
    champs, n = {}, 0
    faces = fiche.get('faces')
    if isinstance(faces, (list, tuple)) and any(
            (_paire(x) or ('', 0))[0] == old for x in faces):
        vus, sortie, bouge = set(), [], False
        for x in faces:
            p = _paire(x)
            if p is None:
                sortie.append(x)
                continue
            cle, i = p
            if cle == old and i < n_det:
                cle, bouge = canon, True
                n += 1
            if (cle, i) in vus:
                continue
            vus.add((cle, i))
            sortie.append([cle, i])
        if bouge:
            champs['faces'] = sortie
    for champ in ('exclude', 'confirmed'):
        lst = fiche.get(champ)
        if not isinstance(lst, (list, tuple)) or old not in lst:
            continue
        vus, sortie = set(), []
        for x in lst:
            y = canon if x == old else x
            if y in vus:
                continue
            vus.add(y)
            sortie.append(y)
        champs[champ] = sortie
        n += 1
    av = _paire(fiche.get('avatar'))
    if av and av[0] == old and av[1] < n_det:
        champs['avatar'] = [canon, av[1]]
    auteurs = fiche.get('auteurs')
    if isinstance(auteurs, dict):
        out, recles = {}, []
        for k, v in auteurs.items():
            champ, cle, i, conteste = _au.lire_ident(k)
            if cle == old and (champ != 'faces' or (i or 0) < n_det):
                recles.append((_au.ident(champ, canon, i) + (_au.CONTESTE if conteste else ''), v))
            else:
                out[k] = v
        if recles:
            for nk, v in recles:
                out.setdefault(nk, v)
            champs['auteurs'] = out
    return champs, n


def n_detections(stores, table, cle):
    fe = stores[table].data.get(cle) if table in stores else None
    if not isinstance(fe, dict) or fe.get('failed'):
        return 0
    return len(fe.get('faces') or [])


def absorber_decisions(stores, old, canon):
    """Fusionne sur `canon` les decisions humaines posees sur `old` dans les
    fiches personnes (detections `faces`) et animaux (`animals`). Rend le compte."""
    n = 0
    for table, dets in STORES_PAR_NOM:
        st = stores.get(table)
        if st is None:
            continue
        n_det = n_detections(stores, dets, canon)
        for pk in list(st.data.keys()):
            pe = st.data.get(pk)
            if not isinstance(pe, dict):
                continue
            champs, k = fusionner_fiche(pe, old, canon, n_det)
            if not champs:
                continue
            for c, v in champs.items():
                pe[c] = v
            st.set(pk, pe, save=False)
            n += k
        st.save()
    return n


# ── application ──────────────────────────────────────────────────────────────

def racine_photos(canon):
    """La racine du fonds (le dossier qui contient « Photos <Nom> »)."""
    p = Path(canon)
    for i, part in enumerate(p.parts):
        if part.lower().startswith('photos ') or part == 'Photos':
            return Path(*p.parts[:i]) if part.lower().startswith('photos ') else Path(*p.parts[:i + 1])
    return p.parent.parent


def destination(trash, fournee, canon, src):
    groupe = hashlib.sha1(str(canon).encode('utf-8')).hexdigest()[:8]
    tag = hashlib.sha1(str(src).encode('utf-8')).hexdigest()[:4]
    return trash / fournee / groupe / ('%s_%s' % (tag, Path(src).name)), groupe


def appliquer_retrait(groupe, r, ctx, journal, compte):
    """Une copie a retirer, dans l'ordre de l'en-tete. Rend 'ok' ou 'skip'."""
    stores, semantic, gps = ctx['stores'], ctx['semantic'], ctx['gps']
    canon, src = groupe['canonique'], r['cle']
    p_src, p_canon = Path(src), Path(canon)
    log = ctx['log']

    # 1) preuve non perimee
    v, _ = V.controle_disque(src, None if ctx['sans_verif'] else V.octets_de(groupe, src))
    if v != 'ok':
        log('  [skip] copie %s : %s' % ('absente' if v == 'absent' else 'de taille changee (preuve perimee)', src))
        return 'skip'
    v, _ = V.controle_disque(canon, None if ctx['sans_verif'] else V.octets_de(groupe, canon))
    if v != 'ok':
        log('  [skip] canonique %s, on ne retire pas : %s' % ('absente' if v == 'absent' else 'de taille changee', canon))
        return 'skip'
    dst, gid = destination(ctx['trash'], ctx['fournee'], canon, src)
    if dst.exists():
        log('  [skip] destination deja prise : %s' % dst)
        return 'skip'

    # 2) noms d'abord — rapport ET index d'aujourd'hui
    noms = set(r.get('noms_a_recopier') or [])
    noms |= set(V.noms_de(stores['tags'].data.get(src))) - set(V.noms_de(stores['tags'].data.get(canon)))
    noms = sorted(noms)
    if noms:
        if ctx['sans_xmp'] or not xmp_ajouter_noms(ctx['exiftool'], p_canon, noms):
            log('  [skip] GARDEE, noms a recopier mais XMP non ecrit (%s) : %s' % (
                ', '.join(noms), src))
            compte['skip_xmp'] = compte.get('skip_xmp', 0) + 1
            return 'skip'
        merge_names(stores, canon, noms)
        stores['tags'].save()

    # 3) texte IA, 4) lieu
    texte = heriter_texte(stores, canon, src)
    lieu = False
    if gps is not None and src in gps and canon not in gps:
        gps[canon] = gps[src]
        lieu = True

    # 5) deplacement + manifeste
    try:
        sha_canon = ctx['sha'].get(canon)
        if sha_canon is None:
            sha_canon = ctx['sha'][canon] = sha256(p_canon)
        dst.parent.mkdir(parents=True, exist_ok=True)
        mani = dst.parent / 'manifeste.json'
        if not mani.exists():
            mani.write_text(json.dumps({
                'origine': src, 'canonique': canon, 'sha256': sha_canon,
                'hachage_image': (groupe.get('hachages') or [None])[0],
                'groupe': gid, 'date_application': ctx['now'],
                'motif': 'meme image (ImageDataHash), dedup_image'},
                ensure_ascii=False, indent=1), encoding='utf-8')
        shutil.move(str(p_src), str(dst))
    except OSError as e:
        log('  [skip] deplacement impossible (SMB ?) : %s (%s)' % (src, e))
        return 'skip'

    # 6) fusion des decisions sur la canonique, PUIS re-cle du reste vers la
    #    corbeille (ce qui n'a pas pu etre fusionne — un visage sans detection
    #    en face — suit le fichier, et la chaine des journaux le retrouve)
    fusionnees = 0
    try:
        fusionnees = absorber_decisions(stores, src, canon)
    except Exception as e:  # noqa: BLE001
        log('    ! fusion des decisions %s : %s' % (src, e))
    if fusionnees:
        compte['fusionnees'] = compte.get('fusionnees', 0) + fusionnees
    rekeyed = False
    try:
        rekeyed = rekey_stores(src, str(dst), stores, semantic, compte=compte)
    except Exception as e:  # noqa: BLE001
        log('    ! re-cle index %s : %s' % (src, e))
    if rekeyed and gps is not None:
        recler_gps(gps, src, str(dst))

    # 7) journal
    journal['operations'].append({
        'src': src, 'dst': str(dst), 'old_key': src, 'new_key': str(dst),
        'canonique': canon, 'noms_fusionnes': noms, 'texte_herite': texte,
        'lieu_herite': lieu, 'decisions_fusionnees': fusionnees,
        'index_rekey': rekeyed, 'groupe': gid})
    log('  [ok]  %s\n        -> corbeille %s%s%s' % (
        src, gid, '  (noms: %s)' % ', '.join(noms) if noms else '',
        '  (texte herite)' if texte else ''))
    return 'ok'


def undo(journal_path, stores, semantic, dry=True, gps=None, log=print):
    j = json.loads(Path(journal_path).read_text(encoding='utf-8'))
    ops = list(reversed(j.get('operations', [])))
    log('Undo : %d operation(s) a inverser depuis %s' % (len(ops), journal_path))
    n = 0
    for op in ops:
        src, dst = op['src'], op['dst']
        p_src, p_dst = Path(src), Path(dst)
        if not p_dst.exists():
            log('  [skip] a la corbeille, introuvable : %s' % dst)
            continue
        if p_src.exists():
            log('  [skip] l origine existe deja : %s' % src)
            continue
        if dry:
            log('  [dry] restaure %s -> %s' % (dst, src))
            continue
        try:
            p_src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p_dst), str(p_src))
        except OSError as e:
            log('  [skip] restauration impossible : %s (%s)' % (dst, e))
            continue
        if op.get('index_rekey') and stores is not None:
            try:
                rekey_stores(dst, src, stores, semantic)
                recler_gps(gps, dst, src)
            except Exception as e:  # noqa: BLE001
                log('    ! re-cle d annulation : %s' % e)
        mani = p_dst.parent / 'manifeste.json'
        reste = [f for f in p_dst.parent.iterdir()] if p_dst.parent.exists() else []
        if mani.exists() and all(f.name == 'manifeste.json' for f in reste):
            try:
                mani.unlink()
                p_dst.parent.rmdir()
            except OSError:
                pass
        log('  [ok]  %s -> %s' % (dst, src))
        n += 1
    if not dry:
        log('Undo termine : %d fichier(s) restaure(s). Noms, texte et decisions fusionnes CONSERVES.' % n)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true', help='executer (sinon apercu)')
    ap.add_argument('--entre-proprietaires', action='store_true', help='lot 1 : Flo+Mike')
    ap.add_argument('--limite', type=int, default=0, help='N groupes au plus')
    ap.add_argument('--undo', metavar='JOURNAL', help='inverser une application')
    ap.add_argument('--rapport', default=str(V.RAPPORT))
    ap.add_argument('--db', default=str(RACINE / 'photos.db'))
    ap.add_argument('--forcer', action='store_true', help='ecrire meme si le serveur semble vivant')
    ap.add_argument('--sans-verif', action='store_true', help='ne controle pas les tailles')
    ap.add_argument('--sans-xmp', action='store_true', help='n ecrit pas le XMP (les copies a noms sont gardees)')
    a = ap.parse_args(argv)
    log = lambda m: print(asc(m), flush=True)  # noqa: E731
    dry = not a.appliquer

    if a.undo:
        refus = refus_d_ecriture(a.db, dry, a.forcer)
        if refus:
            log(refus)
            return 1
        stores = semantic = None
        if not dry and Path(a.db).exists():
            stores, semantic = open_stores(a.db)
        gps = charger_gps() if not dry else None
        undo(a.undo, stores, semantic, dry=dry, gps=gps, log=log)
        if gps is not None:
            ecrire_gps(gps)
        return 0

    if dry:
        argv2 = ['--rapport', a.rapport, '--detail']
        if a.entre_proprietaires:
            argv2.append('--entre-proprietaires')
        if a.limite:
            argv2 += ['--limite', str(a.limite)]
        log('APERCU (rien n est ecrit ; --appliquer pour executer, serveur ARRETE)')
        return V.main(argv2)

    try:
        rap = V.charger_rapport(a.rapport)
    except (OSError, ValueError) as e:
        log('REFUS : %s' % e)
        return 2
    groupes = V.selectionner(rap, a.entre_proprietaires, a.limite)
    log('APPLICATION : %d groupe(s), %d retrait(s) proposes%s' % (
        len(groupes), sum(len(g['retraits']) for g in groupes),
        ' (entre proprietaires)' if a.entre_proprietaires else ''))
    refus = refus_d_ecriture(a.db, dry, a.forcer)
    if refus:
        log(refus)
        return 1
    if not Path(a.db).exists():
        log('REFUS : %s absent — sans index, les noms et decisions ne peuvent pas etre fusionnes.' % a.db)
        return 1
    exe = exiftool()
    if not exe and not a.sans_xmp:
        log('  ! ExifTool absent : les copies qui portent un nom seront GARDEES.')
    stores, semantic = open_stores(a.db)
    if not groupes:
        return 0
    stamp = time.strftime('%Y%m%d-%H%M%S')
    ctx = {'stores': stores, 'semantic': semantic, 'gps': charger_gps(), 'log': log,
           'exiftool': exe, 'sans_xmp': a.sans_xmp, 'sans_verif': a.sans_verif,
           'trash': racine_photos(groupes[0]['canonique']) / '.corbeille-rangement',
           'fournee': 'dedup_image_' + stamp, 'now': time.strftime('%Y-%m-%d %H:%M:%S'),
           'sha': {}}
    journal = {'genere_le': ctx['now'], 'rapport': a.rapport, 'fournee': ctx['fournee'],
               'corbeille': str(ctx['trash']), 'operations': []}
    compte = {'ok': 0, 'skip': 0}
    jp = RACINE / 'docs' / ('undo_doublons_%s.json' % stamp.replace('-', '_'))
    t0 = time.time()
    try:
        for i, g in enumerate(groupes, 1):
            for r in g['retraits']:
                res = appliquer_retrait(g, r, ctx, journal, compte)
                compte[res] = compte.get(res, 0) + 1
            if i % 100 == 0:
                log('  ... %d/%d groupes (%.0f s)' % (i, len(groupes), time.time() - t0))
                jp.write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding='utf-8')
    finally:
        # Le journal d'undo est ecrit meme si la boucle meurt : ce qui a bouge est connu.
        if journal['operations']:
            jp.write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding='utf-8')
            log('\nJournal undo : %s' % jp)
        if ctx['gps'] is not None:
            ecrire_gps(ctx['gps'])
        for s in stores.values():
            try:
                s.save()
            except Exception as e:  # noqa: BLE001
                log('    ! save : %s' % e)
    log('\nBilan : %s' % compte)
    if compte.get('decisions'):
        log('  dont %d decision(s) humaine(s) re-clee(s), %d fusionnee(s) sur la canonique.' % (
            compte['decisions'], compte.get('fusionnees', 0)))
    log('Corbeille : %s' % (ctx['trash'] / ctx['fournee']))
    log('Reversible : appliquer_doublons_image.py --undo %s --appliquer ; le bat 24 la videra apres 30 j.' % jp.name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
