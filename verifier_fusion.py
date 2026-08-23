#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification — une fusion de fiches a-t-elle tenu ses deux promesses ?
──────────────────────────────────────────────────────────────────────────────

CE QUE CE BANC JUGE, ET POURQUOI IL EXISTE

Fusionner deux noms est le geste le plus lourd du projet sur le fonds : Flo
vers Florine, le 22/08, c'est **5 907 photos et 11 814 opérations exiftool**.
Depuis `dd33a26` il est aussi le seul geste destructeur devenu réversible
(`_corbeille_fusions/`). Deux promesses sont donc faites à chaque fusion :

  P1  **Aucune décision humaine n'est perdue** (règle 2). `SubjectStore.rename`
      transporte `confirmed`, `exclude`, `nomerge`, `faces`, l'avatar et la
      date la plus ancienne. Jusqu'au 22/08 elle en oubliait trois — 143 « oui,
      c'est bien elle » seraient partis en silence. Un défaut de cette nature
      ne se voit pas : il faut le CALCULER.
  P2  **Le geste se défait.** Le journal note, photo par photo, si elle portait
      DÉJÀ le nom d'arrivée ; sans ce détail, annuler volerait le nouveau nom à
      celles qui le portaient avant.

Rien ne vérifiait ces deux promesses APRÈS coup. Ce banc le fait, et il le fait
par l'ARITHMÉTIQUE des ensembles notés dans le journal — pas en relisant le
code, pas en faisant confiance au rapport de la fonction qui vient d'agir.

CE QU'IL SAIT VOIR QU'UN OEIL NE VOIT PAS

**Les passes multiples.** La boucle de `rename` balaye les photos une par une
et ne rend la main qu'à la fin — deux minutes sur une machine calme, une HEURE
le 22/08 pendant qu'elle se battait avec le curateur. Un bouton muet appelle un
deuxième clic, et un deuxième clic lance une passe complète de plus, dans un
autre thread. Le fonds y survit (les écritures sont idempotentes), mais
l'ANNULATION, non : `annuler_fusion` prend le DERNIER journal, or c'est le
PREMIER qui dit vrai — lui seul a vu la fiche d'origine, et lui seul sait
quelles photos portaient déjà le nom d'arrivée AVANT que la première passe ne
le pose partout. Ce banc compte les journaux d'un même couple et NOMME celui
qui peut annuler.

CE QU'IL N'OUVRE JAMAIS

`photos.db` : le serveur en est l'écrivain unique. Tout ce qui est vivant est
demandé au SERVEUR en HTTP (`/api/names`, `/api/people/list`,
`/api/maint/status`) ; tout le reste vient des journaux, qui sont des fichiers
inertes. Sans serveur joignable, le banc juge quand même les journaux — et il
DIT ce qu'il n'a pas pu vérifier, au lieu de conclure à moitié.

USAGE
    python verifier_fusion.py
    python verifier_fusion.py --serveur http://192.168.0.13:8080
    python verifier_fusion.py --attendu 5907 --json rapport.json
    python verifier_fusion.py --journal _corbeille_fusions/fusion_20260822_161200.jsonl
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent
CORBEILLE = RACINE / "_corbeille_fusions"
ENSEMBLES = ("confirmed", "exclude", "nomerge")


# ─────────────────────────── Lecture des journaux ───────────────────────────

def journaux(dossier=None):
    """Les journaux de fusion, du plus ancien au plus récent (ordre du nom)."""
    d = Path(dossier) if dossier else CORBEILLE
    try:
        return sorted(d.glob('fusion_*.jsonl'))
    except OSError:
        return []


def lire_journal(chemin):
    """Entête + lignes photo d'un journal. Ne lève pas : un journal illisible
    est un FAIT à rapporter, pas une exception à propager."""
    r = {'fichier': str(chemin), 'nom': Path(chemin).name, 'erreur': '',
         'entete': None, 'photos_lues': 0, 'deja': 0, 'cles': 0,
         'doublons': 0}
    try:
        lignes = Path(chemin).read_text(encoding='utf-8').splitlines()
    except OSError as e:
        r['erreur'] = f"illisible : {e}"
        return r
    lignes = [x for x in lignes if x.strip()]
    if not lignes:
        r['erreur'] = "vide"
        return r
    try:
        r['entete'] = json.loads(lignes[0])
    except ValueError as e:
        r['erreur'] = f"entête illisible : {e}"
        return r
    vues = set()
    for ligne in lignes[1:]:
        try:
            o = json.loads(ligne)
        except ValueError:
            r['erreur'] = "au moins une ligne photo illisible"
            continue
        k = o.get('k')
        if k in vues:
            r['doublons'] += 1
        vues.add(k)
        r['photos_lues'] += 1
        if o.get('deja'):
            r['deja'] += 1
    r['cles'] = len(vues)
    return r


# ────────────────────────── P1 : règle 2, par calcul ──────────────────────────

def _ens(fiche, champ):
    if not isinstance(fiche, dict):
        return set()
    return {str(x) for x in (fiche.get(champ) or [])}


def _faces(fiche):
    if not isinstance(fiche, dict):
        return set()
    out = set()
    for x in (fiche.get('faces') or []):
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            out.add((str(x[0]), x[1]))
    return out


def regle_deux(entete):
    """Ce que les deux fiches portaient AVANT doit se retrouver APRÈS.

    L'inclusion, pas l'égalité : la fiche d'arrivée a le droit d'avoir plus
    (une décision prise entre-temps), jamais moins.
    """
    anc = entete.get('fiche_ancienne')
    av = entete.get('fiche_cible_avant')
    ap = entete.get('fiche_cible_apres')
    v = {'fiche_ancienne_notee': isinstance(anc, dict),
         'fiche_apres_notee': isinstance(ap, dict), 'manques': {}, 'ok': True,
         'refs_plafond': False, 'avatar': 'sans objet', 'at': 'sans objet'}
    if not isinstance(ap, dict):
        v['ok'] = False
        v['manques']['*'] = ["fiche d'arrivée non notée : rien n'est vérifiable"]
        return v
    for champ in ENSEMBLES:
        attendu = _ens(anc, champ) | _ens(av, champ)
        perdus = sorted(attendu - _ens(ap, champ))
        v[f'{champ}_attendus'] = len(attendu)
        v[f'{champ}_apres'] = len(_ens(ap, champ))
        if perdus:
            v['ok'] = False
            v['manques'][champ] = perdus
    perdus_f = sorted(str(x) for x in ((_faces(anc) | _faces(av)) - _faces(ap)))
    v['faces_attendus'] = len(_faces(anc) | _faces(av))
    v['faces_apres'] = len(_faces(ap))
    if perdus_f:
        v['ok'] = False
        v['manques']['faces'] = perdus_f
    # `refs` est PLAFONNÉ à 80 par `rename` : un manque n'y est pas une perte de
    # décision humaine (ce sont des vignettes de référence), mais il doit se
    # DIRE — sans quoi on lirait « tout est là » sur une liste tronquée.
    refs_attendus = len(_ens(anc, 'refs') | _ens(av, 'refs'))
    v['refs_attendus'] = refs_attendus
    v['refs_apres'] = len(_ens(ap, 'refs'))
    v['refs_plafond'] = refs_attendus > v['refs_apres']
    if isinstance(anc, dict) or isinstance(av, dict):
        avaient = bool((anc or {}).get('avatar') or (av or {}).get('avatar'))
        if avaient:
            v['avatar'] = 'présent' if ap.get('avatar') else 'PERDU'
            if not ap.get('avatar'):
                v['ok'] = False
        ats = [x.get('at') for x in (anc, av)
               if isinstance(x, dict) and isinstance(x.get('at'), (int, float))]
        if ats:
            attendu = min(ats)
            reel = ap.get('at')
            v['at'] = ('la plus ancienne' if reel == attendu
                       else f"attendu {attendu}, noté {reel}")
            if reel != attendu:
                v['ok'] = False
    return v


# ─────────────────────── P2 : le geste se défait-il ? ───────────────────────

def annulabilite(rapports):
    """Quel journal peut ANNULER, et lequel `annuler_fusion` prendrait.

    Ils diffèrent dès qu'un couple a plusieurs journaux : la fonction prend le
    dernier, la vérité est dans le premier.
    """
    v = {'couples': {}, 'passes_multiples': False, 'pris_par_defaut': '',
         'a_utiliser': '', 'accord': True}
    if not rapports:
        return v
    for r in rapports:
        e = r.get('entete') or {}
        cle = f"{e.get('prefix', '?')}:{e.get('ancien', '?')}->{e.get('nouveau', '?')}"
        v['couples'].setdefault(cle, []).append(r['nom'])
    v['passes_multiples'] = any(len(x) > 1 for x in v['couples'].values())
    v['pris_par_defaut'] = rapports[-1]['nom']
    # Le journal qui peut rendre la fiche absorbée est le premier qui l'a VUE.
    complet = [r for r in rapports if isinstance(
        (r.get('entete') or {}).get('fiche_ancienne'), dict)]
    v['a_utiliser'] = complet[0]['nom'] if complet else ''
    v['accord'] = bool(v['a_utiliser']) and v['a_utiliser'] == v['pris_par_defaut']
    return v


# ────────────────────────────── Côté serveur ──────────────────────────────

def _get(base, chemin, timeout=20):
    url = base.rstrip('/') + chemin
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def cote_serveur(base, ancien, nouveau):
    """Ce que le serveur VIVANT dit des deux noms. Lecture seule."""
    v = {'joignable': False, 'erreur': '', 'fiche_ancienne': None,
         'fiche_nouvelle': None, 'photos_ancien': None, 'photos_nouveau': None,
         'file_personnes': None}
    if not base:
        v['erreur'] = "pas de serveur interrogé (--serveur vide)"
        return v
    try:
        noms = _get(base, '/api/names').get('noms') or []
        v['joignable'] = True
        for n in noms:
            if (n.get('nom') or '').lower() == (ancien or '').lower():
                v['fiche_ancienne'] = True
                v['photos_ancien'] = n.get('n')
            if (n.get('nom') or '').lower() == (nouveau or '').lower():
                v['fiche_nouvelle'] = True
                v['photos_nouveau'] = n.get('n')
        v['fiche_ancienne'] = bool(v['fiche_ancienne'])
        v['fiche_nouvelle'] = bool(v['fiche_nouvelle'])
        try:
            v['file_personnes'] = (_get(base, '/api/maint/status')
                                   .get('queues', {}).get('personnes'))
        except (urllib.error.URLError, OSError, ValueError):
            pass
    except (urllib.error.URLError, OSError, ValueError) as e:
        v['erreur'] = f"{type(e).__name__} : {e}"
    return v


# ──────────────────────────────── Rapport ────────────────────────────────

def afficher(r):
    L = []
    A = L.append
    A("VÉRIFICATION D'UNE FUSION DE FICHES")
    A("=" * 74)
    js = r['journaux']
    if not js:
        A("AUCUN journal dans _corbeille_fusions/.")
        A("  Deux lectures, et elles n'ont pas le même poids :")
        A("  — aucune fusion n'a eu lieu depuis que le journal existe ;")
        A("  — ou une fusion TOURNE ENCORE : le journal s'écrit à la FIN de la")
        A("    boucle. Dans ce cas le geste n'est PAS annulable pour l'instant,")
        A("    et un redémarrage du serveur le laisserait à moitié fait.")
        A("  Le serveur tranche : une file « personnes » qui grossit = ça tourne.")
    for j in js:
        e = j.get('entete') or {}
        A("")
        A(f"Journal {j['nom']}")
        if j['erreur']:
            A(f"  ⚠ {j['erreur']}")
        annonce = e.get('photos')
        A(f"  {e.get('prefix', '?')} : {e.get('ancien', '?')} -> "
          f"{e.get('nouveau', '?')}")
        A(f"  photos annoncées {annonce} / lignes lues {j['photos_lues']}"
          + ("  ⚠ ÉCART" if annonce != j['photos_lues'] else ""))
        A(f"  portaient déjà le nom d'arrivée : {j['deja']}")
        if j['doublons']:
            A(f"  ⚠ {j['doublons']} clé(s) en double")
        v = j.get('regle2') or {}
        if not v:
            continue
        if v.get('ok'):
            A(f"  RÈGLE 2 tenue — confirmations {v.get('confirmed_attendus')} "
              f"-> {v.get('confirmed_apres')}, exclusions "
              f"{v.get('exclude_attendus')} -> {v.get('exclude_apres')}, "
              f"nomerge {v.get('nomerge_attendus')} -> "
              f"{v.get('nomerge_apres')}, visages "
              f"{v.get('faces_attendus')} -> {v.get('faces_apres')}")
            A(f"  avatar : {v.get('avatar')} · date de fiche : {v.get('at')}")
        else:
            A("  ⚠ RÈGLE 2 VIOLÉE — des décisions humaines manquent :")
            for champ, perdus in (v.get('manques') or {}).items():
                A(f"     {champ} : {len(perdus)} manquant(s) — "
                  f"{', '.join(str(x) for x in perdus[:5])}"
                  + (" …" if len(perdus) > 5 else ""))
        if v.get('refs_plafond'):
            A(f"  (refs : {v.get('refs_attendus')} -> {v.get('refs_apres')} — "
              f"plafond de 80, ce ne sont pas des décisions)")
        if not v.get('fiche_ancienne_notee'):
            A("  (fiche absorbée non notée : cette passe n'a plus rien trouvé "
              "à fusionner — une autre l'avait déjà fait)")

    a = r['annulabilite']
    if js:
        A("")
        A("ANNULATION")
        if a['passes_multiples']:
            A("  ⚠ PASSES MULTIPLES : un même couple a plusieurs journaux.")
            for cle, noms in a['couples'].items():
                if len(noms) > 1:
                    A(f"     {cle} — {len(noms)} passes : {', '.join(noms)}")
            A("  Le fonds y survit (les écritures sont idempotentes), pas")
            A("  l'annulation : les passes tardives ont noté « portait déjà le")
            A("  nom d'arrivée » pour des photos que la PREMIÈRE passe venait")
            A("  de taguer. Annuler avec l'une d'elles laisserait le nouveau")
            A("  nom sur des photos qui ne l'ont jamais porté.")
        A(f"  `Annuler la derniere fusion` prendrait : {a['pris_par_defaut']}")
        A(f"  Le journal qui dit vrai : {a['a_utiliser'] or 'AUCUN'}")
        if not a['accord']:
            A("  ⚠ CE N'EST PAS LE MÊME. Ne pas cliquer le bouton en l'état :")
            A("     écarter les journaux tardifs du dossier avant d'annuler.")

    s = r['serveur']
    A("")
    A("SERVEUR VIVANT")
    if not s['joignable']:
        A(f"  non interrogé — {s['erreur']}")
        A("  Ce qui suit n'a donc PAS été vérifié : la disparition de")
        A("  l'ancien nom, le compte de photos du nouveau, la file d'écriture.")
    else:
        A(f"  fiche « {r['ancien']} » : "
          + ("ENCORE LÀ ⚠" if s['fiche_ancienne'] else "disparue"))
        A(f"  fiche « {r['nouveau']} » : "
          + (f"présente, {s['photos_nouveau']} photo(s)"
             if s['fiche_nouvelle'] else "ABSENTE ⚠"))
        if s['fiche_ancienne'] and s['photos_ancien']:
            A(f"  ⚠ {s['photos_ancien']} photo(s) portent encore l'ancien nom")
            A("     — soit la boucle tourne encore, soit elle s'est arrêtée en")
            A("     chemin. La file d'écriture le dit.")
        if s['file_personnes'] is not None:
            A(f"  file d'écriture XMP « personnes » : {s['file_personnes']}")
            attendu = r.get('ops_attendues')
            if attendu and s['file_personnes'] > attendu:
                A(f"     ⚠ elle dépasse le coût total du geste ({attendu} "
                  "opérations) : plusieurs passes écrivent en même temps.")
            elif s['file_personnes'] == 0:
                A("     vide : le fonds est à jour, les XMP portent le nouveau nom.")
            else:
                A("     elle se vide en tâche de fond (des heures sur le NAS).")

    A("")
    A("VERDICT")
    for ligne in r['verdict']:
        A(f"  {ligne}")
    return "\n".join(L)


def verdict(r):
    V = []
    js = r['journaux']
    if not js:
        V.append("Rien à juger : aucun journal. Si une fusion tourne, elle "
                 "n'est pas encore annulable — ne pas redémarrer le serveur.")
        return V
    viole = [j for j in js if not (j.get('regle2') or {}).get('ok', True)]
    if viole:
        V.append(f"⚠ RÈGLE 2 : {len(viole)} journal(aux) montrent des "
                 "décisions humaines perdues. C'est le défaut le plus grave "
                 "que ce projet connaisse — regarder les manques ci-dessus.")
    else:
        V.append("Règle 2 tenue : chaque décision humaine des deux fiches se "
                 "retrouve dans la fiche d'arrivée.")
    a = r['annulabilite']
    if a['passes_multiples'] and not a['accord']:
        V.append("⚠ Annulation FAUSSÉE en l'état : le bouton prendrait un "
                 f"journal tardif ({a['pris_par_defaut']}). Utiliser "
                 + (a['a_utiliser'] or "aucun : pas un seul journal complet"))
    elif a['a_utiliser']:
        V.append(f"Annulable : {a['a_utiliser']}.")
    s = r['serveur']
    if s['joignable']:
        if s['fiche_ancienne']:
            V.append("⚠ L'ancien nom vit encore côté serveur : la fusion n'est "
                     "pas terminée, ou elle s'est arrêtée en chemin.")
        elif s['fiche_nouvelle']:
            V.append(f"Côté serveur : un seul nom, {r['nouveau']}, "
                     f"{s['photos_nouveau']} photo(s).")
    else:
        V.append("Le vivant n'a pas été interrogé : ce verdict ne porte que "
                 "sur les journaux.")
    return V


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--journal', default='',
                    help="un journal précis ; par défaut, tous")
    ap.add_argument('--dossier', default='',
                    help="dossier des journaux (défaut _corbeille_fusions)")
    ap.add_argument('--serveur', default='http://127.0.0.1:8080',
                    help="serveur vivant, ou vide pour ne juger que les journaux")
    ap.add_argument('--attendu', type=int, default=0,
                    help="photos attendues (contrôle du coût annoncé)")
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    chemins = ([Path(a.journal)] if a.journal
               else journaux(a.dossier or None))
    rapports = [lire_journal(c) for c in chemins]
    for j in rapports:
        if j.get('entete'):
            j['regle2'] = regle_deux(j['entete'])
    entetes = [j['entete'] for j in rapports if j.get('entete')]
    ancien = entetes[0].get('ancien', '') if entetes else ''
    nouveau = entetes[0].get('nouveau', '') if entetes else ''
    photos = entetes[0].get('photos', 0) if entetes else 0
    serveur = cote_serveur(a.serveur, ancien, nouveau)
    # Le coût du geste n'est PAS « photos touchées x 2 ». `rename` réécrit
    # aussi le FICHIER des photos qui portaient déjà le nom d'arrivée — c'est
    # ce qui empêche un nom fantôme d'y renaître. Le compte du serveur les
    # inclut, le journal non (elles ne s'annulent pas). Prendre le plus grand
    # des deux, sinon l'instrument crie au loup sur son propre correctif.
    portees = serveur.get('photos_nouveau') or 0
    r = {'journaux': rapports, 'ancien': ancien, 'nouveau': nouveau,
         'annulabilite': annulabilite([x for x in rapports if x.get('entete')]),
         'serveur': serveur,
         'ops_attendues': max(a.attendu or photos, portees) * 2}
    r['verdict'] = verdict(r)
    print(afficher(r))
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"\nJSON : {a.sortie_json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
