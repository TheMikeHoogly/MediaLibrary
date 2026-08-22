#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — un rattachement d'ANIMAL désigne-t-il encore le bon animal ?
──────────────────────────────────────────────────────────────────────────────

D'OÙ VIENT LA QUESTION

Le chantier des rattachements de VISAGES est clos : 42 couples `[photo, index]`
désignaient le mauvais visage, 33 recalés, 2 retirés. Tout ce travail s'est
arrêté à la porte des animaux, et le code le dit lui-même
(`server.appliquer_recalage` : « LES ANIMAUX NE SONT PAS TRAITES ICI »).
`PETS_STORE` a pourtant la MÊME forme d'entrée que `PEOPLE_STORE` — `name`,
`refs`, `faces = [[clé, index], …]`, `species` — et le même mode de panne est
donc possible : l'index survit, sa cible non.

Personne ne l'a jamais mesuré. Réparer un magasin qu'on n'a pas mesuré est un
pari ; ce module ne répare rien, il compte.

CE QU'ON CROIT SAVOIR, ET CE QUE CHAQUE CHIFFRE DÉCIDERA
(hypothèses écrites AVANT la mesure — `vision-eval`, étape 0)

  H1  **Le décalage devrait être RARE ici, pour une raison de code.** Côté
      visages, `reembed_one_batch` REMPLACE `e['faces']` sur une photo déjà
      connue : l'ordre change sous les index. Côté animaux il n'existe aucune
      boucle de ce genre — `animal_worker` saute toute photo déjà présente
      (`ANIMAL_STORE.has(name)`), et le seul geste qui réécrit les détections
      est `migrate_animal_pipeline()`, qui VIDE l'index entier ET remet
      `pe['faces'] = []`. **Prédiction : décalés ≈ 0.** Si le chiffre est haut,
      c'est le mécanisme qui est mal compris, et c'est ça le résultat.

  H2  **Les index HORS BORNES sont le risque réel.** `_serve_animalcrop` fait
      exactement ce que `_serve_facecrop` fait : `if i < 0 or i >= len(animals):
      i = 0`. Un index périmé ne rend pas une erreur, il rend un AUTRE animal,
      en silence, à l'endroit précis où un humain juge. Toute photo dont
      l'entrée `animals` a été retirée puis reconstruite (purges, `failed`,
      balayages) peut en produire.

  H3  **Les clés MORTES.** `PEOPLE` et `PETS` sont les deux seuls magasins keyés
      par NOM : leurs chemins vivent DANS la fiche, et `rekey_everywhere` ne les
      transportait pas — corrigé le 22/08, mais la réparation rétroactive n'a
      porté que sur les décisions retrouvées. Un couple dont la clé n'est plus
      dans l'index est une décision humaine qui ne montre plus rien.

  H4  **L'ESPÈCE tranche sans seuil — RÉFUTÉE le 22/08, 6 fois sur 6.**
      L'hypothèse disait : un couple qui désigne une détection `dog` sur la
      fiche d'un chat est faux, et aucun score n'a besoin de le dire. C'était
      « le seul verdict qui ne dépende d'aucune valeur réglable, donc le plus
      solide » — et c'est celui qui est tombé. Les six couples ont été
      REGARDÉS : six chats crème, dont un vu deux fois sous deux chemins, et
      deux boîtes qui se recouvrent sur le même animal. **C'est l'ÉTIQUETTE
      d'espèce de YOLO qui ment, pas le rattachement.** La population reste
      séparée — une espèce contredite est un vrai signal, et elle range Luna
      sous « chien » dans l'axe espèce — mais elle ne se lit plus comme un
      compte de fautes du fonds. Un score parfait est une alarme, y compris
      quand c'est le sien.

  H5  **Un score bas nomme une CÉCITÉ, pas une faute** (`eval/METHODE.md`,
      22/08 : sur 13 couples de visages sous le seuil, Mike en a confirmé 12).
      DINOv2 lit une robe, une posture, une lumière — pas une identité. La
      colonne « sous le seuil » est donc rapportée à part et ne doit jamais
      être lue comme un compte de défauts.

  H6  **Des empreintes de DIMENSION périmée traînent.** Le code s'en protège à
      DEUX endroits (`_gather_cats`, `_filter_known_cats`), signe qu'il en a
      déjà vu. Une protection qui s'annule doit se COMPTER (`eval/METHODE.md`).

LA RÈGLE VIENT DE LA PROD, PAS D'UN SOUVENIR

  * les VECTEURS sont relus par le loader de prod (`store_sqlite.SqliteStore`,
    via `mesure_propagation_noms.ouvrir_table`), qui réinjecte les BLOB
    exactement comme `server.py` les reçoit ;
  * les SEUILS et `ANIMAL_NAMEABLE` sont LUS dans le source de `server.py`
    (analyse syntaxique, jamais `import server` : un import ouvrirait
    `photos.db`, dont le serveur est l'écrivain unique), `seuils.txt` appliqué
    par-dessus comme le fait la prod, et affichés dans le rapport ;
  * la signature d'une fiche est la MOYENNE normalisée de ses `refs` — réplique
    de `server.cat_centroid`, trois lignes sans état, pas les prototypes en
    k-moyennes des personnes. Ce n'est pas la même règle des deux côtés, et
    prendre celle des visages mesurerait un autre magasin.

CE QUE LE CHIFFRE NE PEUT PAS DIRE, ET IL FAUT LE SAVOIR

  * La signature est faite des empreintes des photos déjà attribuées. Un couple
    FAUX y a donc versé son empreinte et blanchit son propre score : le banc
    rend une BORNE BASSE du décalage, jamais un compte exact.
  * Les couples que ce banc ÉCARTE sont nommés un par un dans le rapport
    (`eval/METHODE.md`, 22/08 : une population écartée sans être nommée devient
    une conclusion).
  * Un couple juste sur une photo dont le fichier a disparu du disque reste
    « juste » ici : le banc ne touche pas au NAS.

LES 21 COUPLES À TRANCHER (`--a-juger`)

Deux populations que la mesure a isolées et qu'aucun seuil ne tranchera : les
clés MORTES (la photo n'est plus dans l'index) et les couples d'ESPÈCE
incohérente. Ce mode ne juge rien et ne répare rien : il cherche la
CONTREPARTIE de chaque couple et rend l'indice, nommé.

  * clé morte → où la photo est-elle passée ? Les JOURNAUX d'annulation
    d'abord (`journaux_deplacements`) : le geste lui-même, écrit par le
    programme qui l'a fait. À défaut, une clé vivante de MÊME nom de fichier —
    preuve faible, donc exigée corroborée DEUX fois : la cible porte le tag
    `animal:Nom`, et la détection d'indice `i` y existe avec la bonne espèce.
    Ni l'une ni l'autre → le couple RESTE. Il ne se purge pas : le 22/08, 787
    décisions déclarées perdues sont revenues dès qu'une source de preuve
    nouvelle est apparue, et le résidu des visages a été gardé pour ça.
  * espèce incohérente → la photo porte-t-elle un animal de l'espèce de la
    FICHE ? Un seul → l'index à viser est nommé (un recalage, pas un retrait) ;
    plusieurs → à l'œil ; aucun → ni recalage ni certitude.

L'index est CONSERVÉ par une re-clé, et ce n'est pas un pari : `rekey_everywhere`
déplace l'entrée d'`ANIMAL_STORE` en bloc, l'ordre des détections avec
(`recle_decisions`). Une contrepartie trouvée par le NOM du fichier, elle, mène
à une AUTRE entrée, calculée à part : d'où les deux corroborations exigées.

Le score du candidat est RAPPORTÉ, jamais décisif : 37 % des rattachements
confirmés par un humain scorent sous `PET_MATCH_SIM` (22/08).

Aucune écriture : ni base, ni tag, ni fichier (hors `--json`, sur demande).
Lecture seule sur COPIE.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_copie_base.py
    python mesure_rattachements_animaux.py --base copie.db
    python mesure_rattachements_animaux.py --base copie.db --exemples 20
    python mesure_rattachements_animaux.py --base copie.db --a-juger
    python mesure_rattachements_animaux.py --base copie.db --json r.json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import journaux_deplacements as J
import mesure_propagation_noms as M
from verifier_orphelins import basename_cle

# Un autre animal de la MÊME photo doit dépasser le désigné d'au moins ça pour
# qu'on parle de décalage. Même valeur que le banc des visages, et pour la même
# raison : deux animaux qui se ressemblent (deux chats de la même portée, le
# même chat détecté deux fois) ne sont pas une erreur.
ECART_DEFAUT = 0.10

# Constantes de prod dont ce banc a besoin. Absentes → il s'arrête au lieu de
# mesurer avec une valeur inventée.
CONSTANTES = ('PET_MATCH_SIM', 'PET_CLUSTER_SIM', 'ANIMAL_NAMEABLE',
              'ANIMAL_PIPELINE_VERSION')
# Ce que `seuils.txt` peut redéfinir parmi elles (liste de la prod).
REGLABLES = ('PET_MATCH_SIM', 'PET_CLUSTER_SIM')

# Les deux populations de `--a-juger` sont petites (21 couples le 22/08). Le
# plafond n'est là que pour qu'un emballement ne noie pas un rapport — et ce
# qu'il coupe se COMPTE, jamais en silence.
PLAFOND_A_JUGER = 500
PREUVE_JOURNAL = 'journal'
PREUVE_MEME_NOM = 'meme_nom'


# ─────────────────────────── la règle de prod, importée ──────────────────────

def signature(pe):
    """Moyenne normalisée des `refs` d'une fiche — réplique de
    `server.cat_centroid`.

    Recopiée et non importée pour la même raison que les seuils : importer
    `server` ouvrirait `photos.db`. Trois lignes, sans état, et surtout PAS la
    règle des personnes : les visages passent par `classifier.prototypes`
    (k-moyennes), les animaux par une simple moyenne. Prendre l'une pour
    l'autre mesurerait un magasin qui n'existe pas.
    """
    import numpy as np
    vs = []
    for s in (pe.get('refs') or []):
        try:
            vs.append(M.emb_de_b64(s))
        except Exception:                                      # noqa: BLE001
            pass
    if not vs:
        return None, 0
    dims = Counter(v.shape[0] for v in vs)
    dim = dims.most_common(1)[0][0]
    gardes = [v for v in vs if v.shape[0] == dim]
    c = np.mean(np.stack(gardes), axis=0)
    n = np.linalg.norm(c)
    return (c / n if n else c), len(vs) - len(gardes)


def nommable(a, nameable):
    """Réplique de `server._nommable` : une détection contredite par la
    vérification d'espèce (SigLIP) ou hors des espèces nommables n'est pas un
    sujet. `nameable` vient du source de la prod, pas d'un souvenir."""
    if (not isinstance(a, dict) or a.get('suspect') or a.get('inconnu')
            or a.get('non_group')):
        return False
    return a.get('species') in nameable


# ────────────────── l'enquête sur les couples à trancher ─────────────────────
# Règles PURES : elles ne prennent que des dicts et des fonctions. C'est ce qui
# les rend testables sans base — et réutilisables par le serveur le jour où le
# geste existera, plutôt que réécrites une seconde fois.

def index_par_basename(cles):
    """{nom de fichier: [clés]} — ici la COLLISION est le signal, pas le bruit.

    `basename_cle` est importé de `verifier_orphelins` : le projet a déjà payé
    le prix de deux implémentations d'une même règle.
    """
    out = defaultdict(list)
    for k in cles:
        out[basename_cle(k)].append(k)
    return out


def contrepartie(cle, chaine, vivantes, par_basename):
    """(cible vivante, preuve) pour une clé morte, ou (None, None).

    Deux sources, dans cet ordre de force. Les JOURNAUX disent le geste qui a
    été fait ; le NOM DE FICHIER ne dit qu'une ressemblance, et n'est retenu
    que s'il désigne UNE seule clé vivante — deux candidates, c'est un choix,
    et un choix n'est pas une preuve.
    """
    cible = J.suivre(chaine, cle, vivantes)
    if cible:
        return cible, PREUVE_JOURNAL
    memes = [k for k in par_basename.get(basename_cle(cle), ())
             if k != cle and k in vivantes]
    if len(memes) == 1:
        return memes[0], PREUVE_MEME_NOM
    return None, None


def corroborer(cible, i, nom, espece_fiche, entree_tag, liste, nameable):
    """(ce qui confirme, ce qui refuse) — pour une cible et un index donnés.

    `liste` est la liste `(détection, vecteur)` de la CIBLE, telle que le banc
    la décode ; `entree_tag` son entrée d'index (ou None). Aucun score n'entre
    ici : un score bas nomme une cécité de l'empreinte, pas une faute.
    """
    pour, contre = [], []
    kws = [str(x).lower() for x in ((entree_tag or {}).get('kw_fr') or [])]
    if f'animal:{nom}'.lower() in kws:
        pour.append('porte_le_tag')
    else:
        contre.append('pas_de_tag')
    if not liste or i < 0 or i >= len(liste):
        # Re-cler là-dessus fabriquerait un index hors bornes, c'est-à-dire le
        # mensonge muet de `_serve_animalcrop`. Jamais.
        contre.append('index_absent_chez_la_cible')
        return pour, contre
    a, _v = liste[i]
    sp = a.get('species')
    if espece_fiche and sp and sp != espece_fiche:
        contre.append('espece_contredite')
    elif not nommable(a, nameable):
        contre.append('detection_non_nommable')
    else:
        pour.append('index_et_espece_tiennent')
    return pour, contre


def verdict_cle_morte(preuve, pour, contre):
    """Le verdict, et rien de plus que ce que les indices autorisent."""
    if not preuve:
        return 'sans_contrepartie'
    if 'index_absent_chez_la_cible' in contre:
        return 'a_l_oeil'
    if preuve == PREUVE_JOURNAL:
        return 'recle_par_journal'
    return 'recle_par_meme_nom' if not contre else 'a_l_oeil'


def candidats_de_l_espece(liste, espece_fiche, nameable, P=None):
    """Les indices des détections nommables de l'espèce de la FICHE.

    Le score n'est là que pour être LU : il ne choisit pas, il ne filtre pas.
    """
    out = []
    for j, (a, v) in enumerate(liste or ()):
        if a.get('species') != espece_fiche or not nommable(a, nameable):
            continue
        s = None
        if P is not None and v is not None and v.shape[0] == P.shape[0]:
            s = round(float(P @ v), 3)
        out.append({'i': j, 'sim': s})
    return out


def score_designe(liste, i, P):
    """Le score de la détection DÉSIGNÉE contre la signature de la fiche.

    C'est lui qui départage les deux lectures d'une espèce incohérente : un
    `dog` qui ressemble beaucoup au chat de la fiche est un chat mal
    ÉTIQUETÉ — le rattachement est juste et c'est l'espèce qui ment ; un
    `dog` qui ne lui ressemble pas est un rattachement faux. Sans ce
    chiffre, H4 (« faux sans qu'aucun seuil ait à le dire ») se croit sur
    parole.
    """
    if P is None or not liste or i < 0 or i >= len(liste):
        return None
    _a, v = liste[i]
    if v is None or v.shape[0] != P.shape[0]:
        return None
    return round(float(P @ v), 3)


def verdict_espece(candidats):
    if not candidats:
        return 'aucune_detection_de_l_espece'
    return 'recalage_evident' if len(candidats) == 1 else 'a_l_oeil_plusieurs'


def instruire(morts, especes, tags, animaux_de, fiches_par_nom, signatures,
              nameable, projet):
    """Le dossier des couples à trancher — contrepartie et indices, nommés.

    Ne juge pas, ne répare rien, n'écrit rien. Le verdict qu'il pose est le
    verdict d'un INSTRUMENT : « voilà ce que les indices autorisent », pas
    « voilà ce qu'il faut faire ».
    """
    chaine = J.chaines(Path(projet) / 'docs')
    vivantes = set(tags.data)
    parbn = index_par_basename(vivantes)

    def _liste(cle):
        liste, presente, echec = animaux_de(cle)
        return [] if (not presente or echec) else liste

    cas_morts, cas_esp, verdicts = [], [], Counter()
    for m in morts:
        nom, cle, i = m['pet'], m['key'], m['i']
        esp = (fiches_par_nom.get(nom) or {}).get('species')
        cible, preuve = contrepartie(cle, chaine, vivantes, parbn)
        pour, contre = [], []
        if cible:
            pour, contre = corroborer(cible, i, nom, esp,
                                      tags.data.get(cible), _liste(cible),
                                      nameable)
        v = verdict_cle_morte(preuve, pour, contre)
        verdicts[v] += 1
        cas_morts.append({'pet': nom, 'key': cle, 'i': i, 'cible': cible,
                          'preuve': preuve, 'pour': pour, 'contre': contre,
                          # Les détections ont-elles survécu à la purge sous
                          # l'ancien chemin ? Si oui, la vignette existe encore
                          # et un humain peut REGARDER ce couple.
                          'detections_restantes': len(_liste(cle)),
                          'verdict': v})

    for e in especes:
        nom, cle, i = e['pet'], e['key'], e['i']
        esp = (fiches_par_nom.get(nom) or {}).get('species')
        liste = _liste(cle)
        P = signatures.get(nom)
        cands = candidats_de_l_espece(liste, esp, nameable, P)
        v = verdict_espece(cands)
        verdicts[v] += 1
        cas_esp.append({'pet': nom, 'key': cle, 'i': i, 'espece_fiche': esp,
                        'espece_detection': e.get('espece_detection'),
                        'sim_designe': score_designe(liste, i, P),
                        'detections': len(liste),
                        'candidats': cands, 'verdict': v})

    return {'deplacements_connus': len(chaine),
            'cles_mortes': cas_morts, 'especes': cas_esp,
            'verdicts': dict(verdicts)}


# ─────────────────────────────── la mesure ───────────────────────────────────

def mesurer(base, projet, ecart, exemples, a_juger=False):
    tags = animaux = pets = None
    try:
        tags = M.ouvrir_table(base, 'tags')
        animaux = M.ouvrir_table(base, 'animals')
        pets = M.ouvrir_table(base, 'pets')
        return _mesurer(tags, animaux, pets, projet, ecart, exemples,
                        a_juger)
    finally:
        for st in (tags, animaux, pets):
            try:
                st.cx.close()
            except Exception:                                  # noqa: BLE001
                pass


def _fiches(pets):
    """(nom, fiche) des fiches d'animaux, et ce qu'on écarte, nommé."""
    out, ecartes = [], Counter()
    for pk, pe in pets.data.items():
        if not isinstance(pe, dict):
            ecartes['entree_qui_n_est_pas_une_fiche'] += 1
            continue
        out.append((pe.get('name') or pk, pe))
    return out, ecartes


def _mesurer(tags, animaux, pets, projet, ecart, exemples, a_juger=False):
    import numpy as np
    vals = M.lire_constantes(projet, CONSTANTES)
    surcharges = M.appliquer_seuils_txt(projet, vals, REGLABLES)
    seuil = float(vals['PET_MATCH_SIM'])
    nameable = set(vals['ANIMAL_NAMEABLE'])

    fiches, ecartes = _fiches(pets)
    if not fiches:
        raise SystemExit("Aucune fiche d'animal : rien a verifier.")

    # Les animaux d'une photo, décodés une seule fois — plusieurs fiches
    # peuvent citer la même photo.
    cache = {}

    def animaux_de(cle):
        if cle not in cache:
            e = animaux.data.get(cle)
            liste, echec = [], False
            presente = isinstance(e, dict)
            if presente:
                echec = bool(e.get('failed'))
                for a in (e.get('animals') or []):
                    v = None
                    if isinstance(a, dict) and a.get('emb'):
                        try:
                            v = M.emb_de_b64(a['emb'])
                        except Exception:                      # noqa: BLE001
                            v = None
                    liste.append((a if isinstance(a, dict) else {}, v))
            cache[cle] = (liste, presente, echec)
        return cache[cle]

    c = Counter()
    par_fiche = {}
    scores = []
    ex_hors_bornes, ex_decales, ex_espece, ex_bas, ex_mortes = [], [], [], [], []
    # Les deux populations que `--a-juger` instruit sont gardées EN ENTIER,
    # hors du plafond des exemples : on ne peut pas trancher 21 couples en
    # n'en voyant que 12.
    tous_morts, tous_especes, signatures = [], [], {}
    fiches_mesurees = 0

    def garder(liste, cas, debordement):
        if len(liste) < PLAFOND_A_JUGER:
            liste.append(cas)
        else:
            c[debordement] += 1

    for nom, pe in fiches:
        couples_bruts = [(kf[0], int(kf[1] or 0)) for kf in (pe.get('faces') or [])
                         if isinstance(kf, (list, tuple)) and len(kf) == 2]
        f = par_fiche.setdefault(nom, Counter())
        f['couples'] = len(couples_bruts)
        vus = set()
        couples = []
        for ki in couples_bruts:
            if ki in vus:
                c['couple_cite_deux_fois'] += 1
                f['double'] += 1
                continue
            vus.add(ki)
            couples.append(ki)
        f['espece_fiche'] = pe.get('species') or '?'

        if not couples:
            ecartes['fiche_sans_rattachement'] += 1
            continue
        P, refs_hors_dim = signature(pe)
        c['refs_de_dimension_perimee'] += refs_hors_dim
        if P is None:
            ecartes['fiche_sans_signature'] += 1
            c['couples_de_fiche_sans_signature'] += len(couples)
            continue
        fiches_mesurees += 1
        signatures[nom] = P
        espece_fiche = pe.get('species')
        # Combien de fois CETTE fiche cite CETTE photo. Un décalage sur une
        # photo citée une seule fois est un index qui a glissé ; sur une photo
        # citée plusieurs fois, c'est le geste de nommage qui a rattaché
        # plusieurs détections de la même image — deux choses différentes, et
        # seule la première serait une avarie (`eval/METHODE.md`, 22/08 : un
        # FICHIER n'est pas une SCÈNE).
        citations = Counter(cle for cle, _i in couples)

        for cle, i in couples:
            c['couples'] += 1
            if cle not in tags.data:
                c['cle_absente_de_l_index'] += 1
                f['cle_morte'] += 1
                garder(tous_morts, {"pet": nom, "key": cle, "i": i},
                       'cles_mortes_non_listees')
                if len(ex_mortes) < exemples:
                    ex_mortes.append({"pet": nom, "key": cle, "i": i})
                continue
            liste, presente, echec = animaux_de(cle)
            if not presente:
                c['photo_sans_fiche_animaux'] += 1
                f['sans_matiere'] += 1
                continue
            if echec:
                c['fiche_animaux_en_echec'] += 1
                f['sans_matiere'] += 1
                continue
            if not liste:
                c['photo_sans_animal_detecte'] += 1
                f['sans_matiere'] += 1
                continue
            if i < 0 or i >= len(liste):
                # Le mensonge muet : `_serve_animalcrop` sert l'animal 0.
                c['index_hors_bornes'] += 1
                f['hors_bornes'] += 1
                if len(ex_hors_bornes) < exemples:
                    ex_hors_bornes.append({"pet": nom, "key": cle, "i": i,
                                           "animaux": len(liste)})
                continue
            a, v = liste[i]
            sp = a.get('species')
            if espece_fiche and sp and sp != espece_fiche:
                # H4 : faux sans qu'aucun seuil ait à le dire.
                c['espece_incoherente'] += 1
                f['espece'] += 1
                garder(tous_especes, {"pet": nom, "key": cle, "i": i,
                                      "espece_fiche": espece_fiche,
                                      "espece_detection": sp},
                       'especes_non_listees')
                if len(ex_espece) < exemples:
                    ex_espece.append({"pet": nom, "key": cle, "i": i,
                                      "espece_fiche": espece_fiche,
                                      "espece_detection": sp})
                continue
            if not nommable(a, nameable):
                c['detection_non_nommable'] += 1
                f['non_nommable'] += 1
                continue
            if v is None:
                c['animal_designe_sans_vecteur'] += 1
                f['sans_matiere'] += 1
                continue
            if v.shape[0] != P.shape[0]:
                c['dimension_incompatible'] += 1
                f['dimension'] += 1
                continue

            c['mesurables'] += 1
            s_i = float(P @ v)
            scores.append(s_i)
            if s_i < seuil:
                # CÉCITÉ de l'empreinte, pas faute du fonds (H5).
                c['sous_le_seuil_de_match'] += 1
                f['sous_seuil'] += 1
                if len(ex_bas) < exemples:
                    ex_bas.append({"pet": nom, "key": cle, "i": i,
                                   "sim": round(s_i, 3), "animaux": len(liste)})
            # Un AUTRE animal de la même photo ressemble-t-il nettement plus ?
            # Restreint à la même espèce et aux détections nommables : un
            # mouton qui « ressemble » plus au chien n'est pas un candidat.
            autres = []
            for j, (aj, vj) in enumerate(liste):
                if j == i or vj is None or vj.shape[0] != P.shape[0]:
                    continue
                if not nommable(aj, nameable):
                    continue
                if espece_fiche and aj.get('species') != espece_fiche:
                    continue
                autres.append((float(P @ vj), j))
            if not autres:
                c['seul_candidat_de_la_photo'] += 1
                f['juste'] += 1
                continue
            s_best, j_best = max(autres)
            if s_best - s_i >= ecart:
                c['decale'] += 1
                f['decale'] += 1
                n_cite = citations[cle]
                c['decale_photo_citee_une_fois' if n_cite == 1
                  else 'decale_photo_citee_plusieurs_fois'] += 1
                if len(ex_decales) < exemples:
                    ex_decales.append({"pet": nom, "key": cle, "i": i,
                                       "sim": round(s_i, 3), "mieux": j_best,
                                       "sim_mieux": round(s_best, 3),
                                       "animaux": len(liste), "cite": n_cite})
            else:
                c['designe_le_meilleur_ou_presque'] += 1
                f['juste'] += 1

    # ── Deuxième chemin : le TAG. La fiche dit « cet animal est sur cette
    # photo » ; le tag `animal:Nom` de l'index le dit aussi, ailleurs. Deux
    # chemins qui tombent sur le même compte font une mesure ; s'ils divergent,
    # l'écart est le résultat (`eval/METHODE.md`, 17/08).
    # Le champ est `kw_fr` et la comparaison est INSENSIBLE A LA CASSE :
    # réplique de `server._kw_has`, pas un souvenir. La première version de ce
    # banc lisait `kw` et rendait **0 photo taguée pour les douze fiches** —
    # un zéro parfait, donc une alarme, et c'était l'instrument qui avait tort.
    tags_par_nom = defaultdict(set)
    for k, e in tags.data.items():
        if not isinstance(e, dict):
            continue
        for kw in (e.get('kw_fr') or []):
            kw = str(kw)
            if kw.lower().startswith('animal:'):
                tags_par_nom[kw[len('animal:'):].strip().lower()].add(k)
    croise = {}
    for nom, pe in fiches:
        photos_fiche = {kf[0] for kf in (pe.get('faces') or [])
                        if isinstance(kf, (list, tuple)) and len(kf) == 2}
        photos_tag = tags_par_nom.get((pe.get('name') or nom).strip().lower(), set())
        croise[nom] = {"photos_citees_par_la_fiche": len(photos_fiche),
                       "photos_portant_le_tag": len(photos_tag),
                       "citees_sans_le_tag": len(photos_fiche - photos_tag),
                       "taguees_sans_couple": len(photos_tag - photos_fiche)}

    # ── Le fonds, pour donner un dénominateur aux comptes ci-dessus.
    dims = Counter()
    det_total = det_emb = 0
    for e in animaux.data.values():
        if not isinstance(e, dict):
            continue
        for a in (e.get('animals') or []):
            if not isinstance(a, dict):
                continue
            det_total += 1
            if a.get('emb'):
                det_emb += 1
                try:
                    dims[M.emb_de_b64(a['emb']).shape[0]] += 1
                except Exception:                              # noqa: BLE001
                    dims['illisible'] += 1

    rap = {"constantes": {k: (sorted(v) if isinstance(v, set) else v)
                          for k, v in vals.items()},
           "surcharges": surcharges,
           "ecart": ecart,
           "fiches": {"total": len(fiches), "mesurees": fiches_mesurees},
           "ecartes": dict(ecartes),
           "comptes": dict(c),
           "par_fiche": {k: dict(v) for k, v in sorted(par_fiche.items())},
           "croisement_tag": croise,
           "fonds": {"photos_avec_entree_animaux": len(animaux.data),
                     "detections": det_total,
                     "detections_avec_empreinte": det_emb,
                     "dimensions": {str(k): v for k, v in dims.items()}},
           "exemples_hors_bornes": ex_hors_bornes,
           "exemples_decales": ex_decales,
           "exemples_espece": ex_espece,
           "exemples_sous_le_seuil": ex_bas,
           "exemples_cles_mortes": ex_mortes}
    if a_juger:
        rap["a_juger"] = instruire(tous_morts, tous_especes, tags, animaux_de,
                                   {n: pe for n, pe in fiches}, signatures,
                                   nameable, projet)
    if scores:
        a = np.asarray(scores, dtype=np.float32)
        rap["scores"] = {"n": len(scores),
                         "median": round(float(np.median(a)), 3),
                         "p10": round(float(np.percentile(a, 10)), 3),
                         "p90": round(float(np.percentile(a, 90)), 3),
                         "min": round(float(a.min()), 3),
                         "max": round(float(a.max()), 3)}
    return rap


# ─────────────────────────────── le rapport ──────────────────────────────────

def part(a, b):
    return f"{100.0 * a / b:.1f} %" if b else "—"


def afficher(r):
    c = r["comptes"]
    n = c.get('couples', 0)
    m = c.get('mesurables', 0)
    k = r["constantes"]
    L = ["=" * 78,
         "RATTACHEMENTS ANIMAUX — le couple [photo, animal] designe-t-il le bon ?",
         "=" * 78,
         f"Pipeline : {k.get('ANIMAL_PIPELINE_VERSION')}   "
         f"PET_MATCH_SIM = {k.get('PET_MATCH_SIM')}   ecart = {r['ecart']}",
         f"Especes nommables : {', '.join(k.get('ANIMAL_NAMEABLE') or [])}"]
    if r.get("surcharges"):
        L.append(f"Surcharges seuils.txt : {r['surcharges']}")
    L += ["",
          f"Fiches d'animaux : {r['fiches']['total']}  "
          f"(mesurees : {r['fiches']['mesurees']})",
          f"Couples examines : {n}", ""]

    L.append("CE QUI EST ECARTE, nomme (une population muette devient une conclusion) :")
    for cle, v in sorted(r["ecartes"].items()):
        L.append(f"    {cle:<36} {v:>7}")
    for cle in ('couples_de_fiche_sans_signature', 'couple_cite_deux_fois'):
        if c.get(cle):
            L.append(f"    {cle:<36} {c[cle]:>7}")
    if not r["ecartes"] and not c.get('couple_cite_deux_fois'):
        L.append("    (rien)")

    L += ["", "Sur les couples examines :"]
    # `espece_incoherente` a longtemps voulu dire « faux certain ». Les six
    # cas ont ete REGARDES le 22/08 : six chats etiquetes `dog`. Le mot doit
    # dire ce que la mesure a trouve, sinon le rapport reconduit l'erreur.
    for cle in ('mesurables', 'index_hors_bornes', 'cle_absente_de_l_index',
                'espece_incoherente', 'detection_non_nommable',
                'photo_sans_fiche_animaux', 'fiche_animaux_en_echec',
                'photo_sans_animal_detecte', 'animal_designe_sans_vecteur',
                'dimension_incompatible'):
        if c.get(cle):
            L.append(f"    {cle:<36} {c[cle]:>7}   {part(c[cle], n)}")

    L += ["", "Sur les couples MESURABLES :"]
    for cle in ('designe_le_meilleur_ou_presque', 'decale',
                'seul_candidat_de_la_photo', 'sous_le_seuil_de_match'):
        if c.get(cle):
            L.append(f"    {cle:<36} {c[cle]:>7}   {part(c[cle], m)}")
    L.append("    `sous_le_seuil_de_match` n'est PAS un compte de fautes : il")
    L.append("    mesure la cecite de l'empreinte DINOv2, pas le fonds (22/08).")
    if c.get('espece_incoherente'):
        L.append("    `espece_incoherente` non plus : les 6 cas du 22/08 ont ete")
        L.append("    regardes, 6 sur 6 etaient des chats etiquetes `dog`. Le")
        L.append("    defaut est dans l'ETIQUETTE de YOLO — il range l'animal")
        L.append("    sous la mauvaise espece — pas dans le rattachement.")
    if c.get('decale'):
        L += ["", "    Le decalage se separe en DEUX, et un seul serait une avarie :",
              f"        photo citee UNE fois par la fiche      "
              f"{c.get('decale_photo_citee_une_fois', 0):>5}"
              "   <- un index qui a glisse",
              f"        photo citee PLUSIEURS fois             "
              f"{c.get('decale_photo_citee_plusieurs_fois', 0):>5}"
              "   <- le nommage a pris",
              "                                                     "
              "     plusieurs detections de la meme image"]

    s = r.get("scores")
    if s:
        L += ["",
              f"Score de l'animal designe : median {s['median']}  p10 {s['p10']}  "
              f"p90 {s['p90']}  min {s['min']}  max {s['max']}"]

    L += ["", "PAR FICHE — un defaut concentre ne se voit pas dans un taux (22/08) :",
          "    fiche                 esp   couples  juste  decal  h.born  esp!  "
          "s.seuil  morte"]
    for nom, v in sorted(r["par_fiche"].items(),
                         key=lambda kv: -kv[1].get('couples', 0)):
        L.append(f"    {nom[:20]:<20} {str(v.get('espece_fiche'))[:5]:<5} "
                 f"{v.get('couples', 0):>7} {v.get('juste', 0):>6} "
                 f"{v.get('decale', 0):>6} {v.get('hors_bornes', 0):>7} "
                 f"{v.get('espece', 0):>5} {v.get('sous_seuil', 0):>7} "
                 f"{v.get('cle_morte', 0):>6}")

    f = r["fonds"]
    L += ["", "Le fonds, pour donner un denominateur :",
          f"    photos avec entree animaux   {f['photos_avec_entree_animaux']:>8}",
          f"    detections                   {f['detections']:>8}",
          f"    dont avec empreinte          {f['detections_avec_empreinte']:>8}   "
          f"{part(f['detections_avec_empreinte'], f['detections'])}",
          f"    dimensions d'empreinte       {f['dimensions']}"]
    if c.get('refs_de_dimension_perimee'):
        L.append(f"    refs de dimension perimee    "
                 f"{c['refs_de_dimension_perimee']:>8}   "
                 "(une protection qui s'annule se COMPTE)")

    L += ["", "DEUXIEME CHEMIN — la fiche et le TAG disent-ils la meme chose ?",
          "    fiche                 photos_fiche  photos_tag  citees_sans_tag  "
          "taguees_sans_couple"]
    for nom, v in sorted(r["croisement_tag"].items(),
                         key=lambda kv: -kv[1]['photos_portant_le_tag']):
        L.append(f"    {nom[:20]:<20} {v['photos_citees_par_la_fiche']:>12} "
                 f"{v['photos_portant_le_tag']:>11} "
                 f"{v['citees_sans_le_tag']:>16} {v['taguees_sans_couple']:>19}")
    L.append("    `taguees_sans_couple` n'est pas un defaut : une photo peut porter")
    L.append("    le nom sans qu'aucune detection ne lui soit rattachee. C'est la")
    L.append("    reserve dans laquelle un rattachement pourrait etre propose.")

    for titre, cle, ligne in (
            ("HORS BORNES — _serve_animalcrop sert l'animal 0, en silence",
             "exemples_hors_bornes",
             lambda e: f"i={e['i']:<4} sur {e['animaux']} animal(aux)"),
            ("ESPECE INCOHERENTE — l'etiquette de YOLO, pas le rattachement",
             "exemples_espece",
             lambda e: f"i={e['i']:<4} fiche={e['espece_fiche']} "
                       f"detection={e['espece_detection']}"),
            ("DECALES — un autre animal de la MEME photo ressemble plus",
             "exemples_decales",
             lambda e: f"i={e['i']} ({e['sim']}) -> i={e['mieux']} "
                       f"({e['sim_mieux']}) sur {e['animaux']}"
                       f"  cite x{e['cite']}"),
            ("CLES MORTES — la photo n'est plus dans l'index",
             "exemples_cles_mortes", lambda e: f"i={e['i']}"),
            ("SOUS LE SEUIL — cecite de l'empreinte, a ne pas lire comme des fautes",
             "exemples_sous_le_seuil",
             lambda e: f"i={e['i']:<4} ({e['sim']}) sur {e['animaux']} animal(aux)"),
    ):
        ex = r.get(cle) or []
        if not ex:
            continue
        L += ["", titre + " :"]
        for e in ex:
            L.append(f"    {e['pet'][:18]:<18} {ligne(e):<44} "
                     f"{Path(e['key']).name[:34]}")

    L += lignes_a_juger(r.get("a_juger"))
    return "\n".join(L)


def lignes_a_juger(aj):
    """Le dossier des couples a trancher. ASCII pur : la sortie part dans une
    console Windows et l'agent git la capture."""
    if not aj:
        return []
    morts, esp = aj.get('cles_mortes') or [], aj.get('especes') or []
    L = ["", "=" * 78,
         "LES COUPLES A TRANCHER — la contrepartie, pas le verdict",
         "=" * 78,
         f"Journaux d'annulation : {aj.get('deplacements_connus', 0)} "
         "deplacements connus"]

    L += ["", f"CLES MORTES ({len(morts)}) — ou la photo est-elle passee ?"]
    if not morts:
        L.append("    (aucune)")
    for e in morts:
        cible = Path(e['cible']).name[:30] if e.get('cible') else "-"
        indices = "+".join(e.get('pour') or []) or "-"
        refus = "-".join(e.get('contre') or []) or ""
        L.append(f"    {e['pet'][:12]:<12} i={e['i']:<3} "
                 f"{e['verdict']:<20} {str(e.get('preuve') or '-'):<9} "
                 f"{cible:<30} {indices}{(' !' + refus) if refus else ''}")
        L.append(f"        depuis {Path(e['key']).name[:56]}"
                 f"  [{e.get('detections_restantes', 0)} det.]")
    L += ["    Une contrepartie par le NOM du fichier n'est retenue que",
          "    corroboree DEUX fois : le tag, puis l'index et l'espece chez la",
          "    cible. Ce qui n'a AUCUNE contrepartie ne se purge pas — le 22/08,",
          "    787 decisions declarees perdues sont revenues avec une preuve",
          "    nouvelle, et le residu des visages a ete garde pour cette raison."]

    L += ["", f"ESPECE INCOHERENTE ({len(esp)}) — la photo porte-t-elle "
          "l'espece de la fiche ?"]
    if not esp:
        L.append("    (aucune)")
    for e in esp:
        cands = ", ".join(f"i={x['i']}"
                          + (f" ({x['sim']})" if x.get('sim') is not None else "")
                          for x in (e.get('candidats') or [])) or "aucun"
        sim = e.get('sim_designe')
        L.append(f"    {e['pet'][:12]:<12} i={e['i']:<3} "
                 f"fiche={e.get('espece_fiche')} detection="
                 f"{e.get('espece_detection')}  {e['verdict']:<28} "
                 f"{Path(e['key']).name[:28]}")
        L.append(f"        designe : {sim if sim is not None else '?'} sur "
                 f"{e.get('detections')} detection(s)  |  candidats "
                 f"{e.get('espece_fiche')} : {cands}")
    L += ["    Le score DESIGNE departage les deux lectures : haut, la",
          "    detection est un sujet mal ETIQUETE et le rattachement tient ;",
          "    bas, il ne tient pas. Il ne DECIDE pas pour autant — le 22/08,",
          "    un couple a 0.441 s'est revele JUSTE a l'oeil : un seuil bas",
          "    nomme une cecite. Et un `recalage_evident` a +0.036 etait deux",
          "    BOITES du meme chat : verifier avant de recaler."]

    L += ["", "VERDICTS :"]
    for k, v in sorted((aj.get('verdicts') or {}).items()):
        L.append(f"    {k:<36} {v:>5}")
    L.append("    Un verdict d'INSTRUMENT dit ce que les indices autorisent,")
    L.append("    pas ce qu'il faut faire. Le geste reste a Mike.")
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', help="COPIE de photos.db")
    ap.add_argument('--projet', default='.')
    ap.add_argument('--ecart', type=float, default=ECART_DEFAUT)
    ap.add_argument('--exemples', type=int, default=12)
    ap.add_argument('--a-juger', dest='a_juger', action='store_true',
                    help="instruire les cles mortes et les especes incoherentes")
    ap.add_argument('--json', dest='sortie_json')
    a = ap.parse_args(argv)
    if not a.base:
        ap.error("--base est requis (une COPIE : mesure_copie_base.py)")
    rap = mesurer(a.base, a.projet, a.ecart, a.exemples, a.a_juger)
    print(afficher(rap))
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
