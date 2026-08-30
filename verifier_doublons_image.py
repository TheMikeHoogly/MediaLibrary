#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APERCU a blanc du dedoublonnage par l'IMAGE (ROADMAP 1 decies) — LECTURE SEULE
──────────────────────────────────────────────────────────────────────────────

Lit `docs/doublons_image.json` (ecrit par `mesure_doublons_image.py`, 8 passes
dans la nuit du 29 au 30/08 : 2 757 groupes IDENTIQUES au pixel, 2 929 retraits,
10,45 Go) et dit, groupe par groupe, ce que `appliquer_doublons_image.py`
FERAIT : quelle copie reste (la canonique), lesquelles partent en corbeille,
quels noms humains doivent etre recopies AVANT, et ce qui serait SAUTE parce
que la preuve est perimee (fichier absent, taille changee depuis le banc).

Ce script n'ecrit RIEN et ne lit jamais `photos.db` : avec `--base copie.db`
(une copie, `mesure_copie_base.py`) il recalcule les noms a recopier sur
l'index d'AUJOURD'HUI — le rapport les a calcules cette nuit, et Mike nomme
des gens entre-temps. Sans `--base`, ce sont les noms du rapport.

C'est la famille `verifier_` : l'agent banc (fenetre « Bancs ») peut le lancer
sur le NAS, la ou le bac a sable ne voit pas. La famille `appliquer_` ne passe
pas par lui, et c'est voulu.

    verifier_doublons_image.py [--base copie.db] [--entre-proprietaires]
                               [--limite N] [--sans-disque] [--detail]

`--entre-proprietaires` : les 833 groupes Flo+Mike seulement (le premier lot,
tranche par Mike le 30/08). `--sans-disque` : ne touche pas au NAS (compte
seulement). `--detail` : une ligne par copie a retirer, sinon un resume.
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'doublons_image.json'
PREFIXES_NOMS = ('personne:', 'animal:')


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def charger_rapport(chemin=None):
    p = Path(chemin or RAPPORT)
    rap = json.loads(p.read_text(encoding='utf-8'))
    if not rap.get('termine'):
        raise ValueError('le rapport %s n est pas TERMINE : relancer mesure_doublons_image.py'
                         % p.name)
    return rap


def noms_de(entree):
    """Les noms humains d'une entree d'index (`kw_fr`/`kw_en`), tries."""
    if not isinstance(entree, dict):
        return []
    return sorted({t for fld in ('kw_fr', 'kw_en') for t in (entree.get(fld) or [])
                   if isinstance(t, str) and t.startswith(PREFIXES_NOMS)})


def texte_vide(entree):
    """Vrai si l'entree n'a ni description ni mot-cle IA (les noms humains ne
    comptent pas : ils sont recopies a part). Regle de Mike (30/08) : la
    canonique garde SON texte, sauf si elle n'en a pas."""
    if not isinstance(entree, dict):
        return True
    if (entree.get('desc') or '').strip():
        return False
    for fld in ('kw_fr', 'kw_en'):
        if any(isinstance(t, str) and not t.startswith(PREFIXES_NOMS)
               for t in (entree.get(fld) or [])):
            return False
    return True


def charger_index(base):
    """L'index depuis une COPIE de la base (jamais photos.db) : {cle: entree}."""
    import sqlite3
    if Path(base).name == 'photos.db':
        raise ValueError('ce script lit une COPIE (mesure_copie_base.py), jamais photos.db')
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    out = {}
    try:
        for k, v in cx.execute('SELECT k, v FROM tags'):
            try:
                e = json.loads(v)
            except ValueError:
                continue
            if isinstance(e, dict):
                out[k] = e
    finally:
        cx.close()
    return out


def selectionner(rapport, entre_proprietaires=False, limite=0):
    """Les groupes IDENTIQUES qui ont au moins un retrait, dans l'ordre du
    rapport ; `entre_proprietaires` ne garde que ceux dont les copies sont
    chez deux proprietaires (Flo + Mike) ; `limite` borne le nombre de GROUPES."""
    out = []
    for g in rapport.get('groupes') or []:
        if g.get('verdict') != 'IDENTIQUE' or not g.get('retraits'):
            continue
        if entre_proprietaires and not g.get('entre_proprietaires'):
            continue
        out.append(g)
    return out[:limite] if limite else out


def octets_de(groupe, cle):
    try:
        return groupe['octets'][groupe['cles'].index(cle)]
    except (KeyError, ValueError, IndexError):
        return None


def controle_disque(chemin, octets_attendus):
    """(verdict, detail) — 'ok', 'absent' ou 'taille' (la preuve du banc est
    perimee : le fichier a change depuis la nuit). Un stat par fichier, pas
    de lecture de contenu."""
    try:
        st = os.stat(chemin)
    except OSError:
        return 'absent', None
    if octets_attendus is not None and st.st_size != octets_attendus:
        return 'taille', st.st_size
    return 'ok', st.st_size


def juger_groupe(groupe, index=None, disque=True):
    """Ce que l'applicateur ferait de ce groupe : un dict
    {canonique, retraits: [{cle, noms, texte_herite, verdict, octets}], saute}.
    `index` (copie) affine les noms a recopier ; sans lui, ceux du rapport."""
    canon = groupe['canonique']
    ec = index.get(canon) if index is not None else None
    noms_canon = set(noms_de(ec)) if index is not None else None
    canon_vide = texte_vide(ec) if index is not None else False
    res = {'canonique': canon, 'retraits': [], 'saute': None}
    if disque:
        v, _ = controle_disque(canon, octets_de(groupe, canon))
        if v != 'ok':
            res['saute'] = 'canonique %s' % ('absente' if v == 'absent' else 'de taille changee')
            return res
    for r in groupe.get('retraits') or []:
        cle = r['cle']
        noms = set(r.get('noms_a_recopier') or [])
        if index is not None:
            noms |= set(noms_de(index.get(cle))) - noms_canon
        item = {'cle': cle, 'noms': sorted(noms), 'proprietaire': r.get('proprietaire'),
                'texte_herite': bool(canon_vide and index is not None
                                     and not texte_vide(index.get(cle))),
                'octets': octets_de(groupe, cle), 'verdict': 'ok'}
        if disque:
            v, _ = controle_disque(cle, item['octets'])
            item['verdict'] = v
        res['retraits'].append(item)
    return res


def resumer(jugements):
    """Les compteurs de l'apercu, a partir des jugements de `juger_groupe`."""
    c = defaultdict(int)
    par_prop = defaultdict(int)
    for j in jugements:
        c['groupes'] += 1
        if j['saute']:
            c['groupes_sautes'] += 1
            continue
        for r in j['retraits']:
            if r['verdict'] != 'ok':
                c['sautes_' + r['verdict']] += 1
                continue
            c['retraits'] += 1
            c['octets'] += r['octets'] or 0
            c['noms'] += bool(r['noms'])
            c['texte_herite'] += bool(r['texte_herite'])
            par_prop[r['proprietaire'] or '(racine)'] += 1
    return c, par_prop


def lignes_resume(c, par_prop, entre_proprietaires):
    out = ['APERCU A BLANC du dedoublonnage par l image%s' % (
        ' (entre proprietaires seulement)' if entre_proprietaires else '')]
    out.append('  groupes : %d   retraits : %d fichier(s), %.2f Go' % (
        c['groupes'], c['retraits'], c['octets'] / 1e9))
    out.append('  a recopier AVANT retrait : noms sur %d copie(s) ; texte IA herite par %d canonique(s) vide(s)' % (
        c['noms'], c['texte_herite']))
    sautes = c['groupes_sautes'] + c['sautes_absent'] + c['sautes_taille']
    out.append('  SAUTES (preuve perimee) : %d  [groupes a canonique absente/changee : %d ; copies absentes : %d ; copies de taille changee : %d]' % (
        sautes, c['groupes_sautes'], c['sautes_absent'], c['sautes_taille']))
    for p, n in sorted(par_prop.items(), key=lambda kv: -kv[1]):
        out.append('    %5d  retrait(s) chez %s' % (n, p))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', help='COPIE de photos.db (noms et textes d aujourd hui)')
    ap.add_argument('--rapport', default=str(RAPPORT))
    ap.add_argument('--entre-proprietaires', action='store_true')
    ap.add_argument('--limite', type=int, default=0, help='N groupes au plus')
    ap.add_argument('--sans-disque', action='store_true', help='ne touche pas au NAS')
    ap.add_argument('--detail', action='store_true', help='une ligne par copie')
    a = ap.parse_args(argv)
    log = lambda m: print(asc(m), flush=True)  # noqa: E731
    t0 = time.time()
    try:
        rap = charger_rapport(a.rapport)
    except (OSError, ValueError) as e:
        log('REFUS : %s' % e)
        return 2
    index = None
    if a.base:
        try:
            index = charger_index(a.base)
        except Exception as e:  # noqa: BLE001
            log('REFUS : %s' % e)
            return 2
        log('index (copie) : %d entree(s)' % len(index))
    else:
        log('sans --base : noms a recopier = ceux du rapport (%s)' % rap.get('genere_le'))
    groupes = selectionner(rap, a.entre_proprietaires, a.limite)
    log('rapport %s : %d groupe(s) retenu(s)%s' % (
        rap.get('genere_le'), len(groupes), ' (disque non consulte)' if a.sans_disque else ''))
    jugements = []
    for i, g in enumerate(groupes, 1):
        j = juger_groupe(g, index, disque=not a.sans_disque)
        jugements.append(j)
        if a.detail:
            if j['saute']:
                log('  [SAUT] groupe entier, %s : %s' % (j['saute'], j['canonique']))
                continue
            for r in j['retraits']:
                sup = []
                if r['noms']:
                    sup.append('noms->canonique: ' + ', '.join(r['noms']))
                if r['texte_herite']:
                    sup.append('texte IA -> canonique vide')
                etiq = '[dry]' if r['verdict'] == 'ok' else '[SAUT %s]' % r['verdict']
                log('  %s %s  (garde: %s)%s' % (etiq, r['cle'], j['canonique'],
                                                 ('  + ' + ' ; '.join(sup)) if sup else ''))
        elif not a.sans_disque and i % 250 == 0:
            log('  ... %d/%d groupes controles' % (i, len(groupes)))
    c, par_prop = resumer(jugements)
    for l in lignes_resume(c, par_prop, a.entre_proprietaires):
        log(l)
    log('(lecture seule : rien deplace, rien ecrit - %.0f s)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
