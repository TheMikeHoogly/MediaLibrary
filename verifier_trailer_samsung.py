#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La photothèque coupe-t-elle le TRAILER des fichiers qu'elle nomme ?
──────────────────────────────────────────────────────────────────────────────

CE QU'ON SAIT DÉJÀ, ET CE QU'ON NE SAIT PAS

Le 27/08, en comparant l'export Google au NAS, **99 photos sont sorties
« même image, trailer différent »** : côté Google, ~2 Ko après le `EOI` — un
bloc **Samsung SEF** (`SEFH`/`SEFT`, `Image_UTC_Data`, `Color_Display_P3`,
`PhotoEditor_Re_Edit_Data` avec les données de ré-édition) ; côté NAS,
**0 octet sur les 99**. Pas une, pas quatre-vingt-dix-huit : les 99.

Le seul programme qui écrit dans ces fichiers est **le nôtre** — exiftool,
quand un nom humain (`personne:Nom`, `animal:Nom`) part dans les XMP. D'où le
soupçon, et son enjeu : si c'est bien lui, ce n'est pas 99 photos, c'est
**tout ce que la photothèque a jamais nommé**.

« Le seul programme qui écrit » est un raisonnement, pas une mesure. Une autre
explication tient debout : la copie du NAS et celle de Google ne viennent
peut-être pas du même chemin — le téléphone a pu envoyer l'une par la synchro
et l'autre autrement, et perdre le SEF en route.

CE QUE CET INSTRUMENT MESURE — ET CE QU'IL NE PROUVE PAS

Il lit des fichiers du fonds, et pour chacun deux faits, **dans le fichier
lui-même**, sans base ni serveur :

  A. porte-t-il un trailer Samsung SEF après le `EOI` ?
  B. porte-t-il un nom écrit par nous (`personne:` / `animal:` dans ses
     segments de métadonnée) ?

Croisés sur des photos d'origine Samsung, ces deux faits font un tableau à
quatre cases. Si les NOMMÉES n'ont jamais de trailer là où les NON NOMMÉES en
ont souvent, la corrélation est établie — et **c'est tout ce qu'une lecture
peut établir**. La CAUSE se prouve autrement : relever le trailer d'une photo,
la nommer, le relever à nouveau. C'est une écriture, donc un geste de Mike,
donc pas ce banc.

Le rapport dit cette limite en toutes lettres. Un instrument qui conclurait
« notre code coupe le trailer » à partir d'une corrélation ferait exactement
ce que ce projet reproche à ses propres bancs.

PORTÉE

**Ce qui vient d'être importé fausse le tableau, et il faut l'exclure à la
main.** Les 3 776 photos rapatriées du Takeout le 27/08 sont des copies de
Google : elles portent leur SEF et ne sont pas encore nommées. Les compter
gonflerait la case « non nommée, avec SEF » et fabriquerait la corrélation
qu'on cherche à établir. `--exclure` retire un morceau de chemin de
l'échantillon, et le rapport DIT ce qui a été exclu — une exclusion muette
serait pire que pas d'exclusion du tout.

Restreint aussi aux JPEG dont l'EXIF dit **SAMSUNG** : eux seuls sont censés porter
un SEF, et compter les autres diluerait le dénominateur jusqu'à rendre
n'importe quel taux rassurant. Ce qui n'est pas jugeable est compté et dit.

Lecture seule, famille `verifier_` : il n'ouvre ni la base, ni le serveur, et
n'écrit aucun fichier du fonds.

USAGE
    python verifier_trailer_samsung.py
    python verifier_trailer_samsung.py --echantillon=800 --json=_sef.json
    python verifier_trailer_samsung.py --racine=b64:XXXX

    Sortie 0 = aucune corrélation qui accuse notre écriture.
    1 = les photos NOMMÉES ont perdu leur trailer là où les autres l'ont.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventaire_fonds as F                                   # noqa: E402
import verifier_google_pixels as P                             # noqa: E402
from verifier_xmp_toutes_personnes import wilson               # noqa: E402

ECHANTILLON_DEFAUT = 400
ENTETE_MAX = 1 << 18          # 256 Ko : EXIF + XMP vivent bien avant le scan
LISTE_MAX = 12

MARQUES_SEF = (b'SEFT', b'SEFH')
NOMS_ECRITS = (b'personne:', b'animal:')


def lire_faits(chemin):
    """{samsung, nomme, trailer, octets} pour un JPEG, ou None si illisible.

    Un seul passage, deux lectures bornées : l'en-tête (là où vivent l'EXIF et
    les XMP) et la queue (là où vit le trailer). On ne décode aucune image et
    on ne lit jamais le flux compressé — sur un partage SMB, c'est la
    différence entre une minute et une heure."""
    try:
        taille = os.path.getsize(chemin)
        with open(chemin, 'rb') as f:
            if f.read(2) != b'\xff\xd8':
                return None
            f.seek(0)
            entete = f.read(min(ENTETE_MAX, taille))
            fin = P.fin_du_flux(f, taille)
    except OSError:
        return None
    if fin is None:
        return None
    return {
        'samsung': b'SAMSUNG' in entete or b'samsung' in entete,
        'nomme': any(n in entete for n in NOMS_ECRITS),
        'trailer': taille - fin,
        'octets': taille,
    }


def a_un_sef(chemin, trailer, fenetre=1 << 16):
    """Le trailer porte-t-il la signature Samsung ? (`SEFT` en fin de bloc).

    Un trailer non vide n'est pas forcément un SEF : une vignette oubliée, un
    octet de bourrage. On demande la marque, pas la taille."""
    if trailer <= 0:
        return False
    try:
        with open(chemin, 'rb') as f:
            f.seek(max(0, os.path.getsize(chemin) - min(fenetre, trailer + 64)))
            queue = f.read()
    except OSError:
        return False
    return any(m in queue for m in MARQUES_SEF)


def echantillon(racines, combien, parcours=None, exclure=()):
    """Des JPEG du fonds, pris à intervalle RÉGULIER sur la liste triée.

    Pas de tirage au sort : deux exécutions doivent juger les mêmes fichiers,
    sinon un écart de résultat ne se distingue pas d'un écart d'échantillon."""
    tous, ecartes = [], 0
    for r in racines:
        for chemin, _octets in (parcours or F.parcourir)(r):
            if os.path.splitext(chemin)[1].lower() not in ('.jpg', '.jpeg'):
                continue
            if any(m and m.lower() in str(chemin).lower() for m in exclure):
                ecartes += 1
                continue
            tous.append(str(chemin))
    tous.sort()
    globals()['_ECARTES_CHEMIN'] = ecartes
    if not tous or combien <= 0 or len(tous) <= combien:
        return tous, len(tous)
    pas = len(tous) / float(combien)
    return [tous[int(i * pas)] for i in range(combien)], len(tous)


def croiser(chemins, lire=lire_faits, sef=a_un_sef, ecrire=print, chaque=100):
    """Le tableau à quatre cases, et ce qui n'a pas pu être jugé."""
    t = {('nomme', 'sef'): 0, ('nomme', 'sans'): 0,
         ('libre', 'sef'): 0, ('libre', 'sans'): 0}
    hors, exemples = {'illisible': 0, 'pas_samsung': 0}, {}
    for i, c in enumerate(chemins, 1):
        faits = lire(c)
        if faits is None:
            hors['illisible'] += 1
            continue
        if not faits['samsung']:
            hors['pas_samsung'] += 1
            continue
        cle = ('nomme' if faits['nomme'] else 'libre',
               'sef' if sef(c, faits['trailer']) else 'sans')
        t[cle] += 1
        if len(exemples.setdefault('%s/%s' % cle, [])) < LISTE_MAX:
            exemples['%s/%s' % cle].append(os.path.basename(c))
        if chaque and i % chaque == 0:
            ecrire("    %d / %d" % (i, len(chemins)))
    return t, hors, exemples


def _pc(a, b):
    return (100.0 * a / b) if b else 0.0


def rapport(t, hors, total_fonds, juges, exclure=(), ecartes=0,
            ecrire=print):
    """True si RIEN n'accuse notre écriture. False si la corrélation est là."""
    nommes = t[('nomme', 'sef')] + t[('nomme', 'sans')]
    libres = t[('libre', 'sef')] + t[('libre', 'sans')]
    ecrire("")
    ecrire("=" * 74)
    ecrire("  LE TRAILER SAMSUNG SURVIT-IL A NOTRE ECRITURE XMP ?")
    ecrire("=" * 74)
    ecrire("  fonds : %d JPEG ; echantillon : %d ; juges (Samsung) : %d"
           % (total_fonds, juges, nommes + libres))
    ecrire("  ecartes : %d illisibles, %d pas Samsung"
           % (hors['illisible'], hors['pas_samsung']))
    if exclure:
        ecrire("  EXCLUS du fonds avant tirage : %d fichier(s) dont le chemin"
               % ecartes)
        ecrire("  porte %s" % ', '.join(repr(m) for m in exclure))
    else:
        ecrire("  aucune exclusion de chemin. Si un lot vient d etre importe")
        ecrire("  (Takeout), il fausse la ligne << non nommees >> : --exclure.")
    ecrire("")
    ecrire("                        avec SEF     sans SEF     total")
    ecrire("  photos NOMMEES par nous %6d %12d %9d"
           % (t[('nomme', 'sef')], t[('nomme', 'sans')], nommes))
    ecrire("  photos non nommees      %6d %12d %9d"
           % (t[('libre', 'sef')], t[('libre', 'sans')], libres))
    ecrire("")
    if not nommes or not libres:
        ecrire("  Une des deux lignes est VIDE : ce tableau ne compare rien.")
        ecrire("  Elargir l echantillon (--echantillon) avant de conclure.")
        ecrire("=" * 74)
        return False

    p_nom, p_lib = _pc(t[('nomme', 'sef')], nommes), _pc(t[('libre', 'sef')], libres)
    bn, hn = wilson(t[('nomme', 'sef')], nommes)
    bl, hl = wilson(t[('libre', 'sef')], libres)
    ecrire("  part des photos qui ONT encore leur SEF :")
    ecrire("    nommees     %5.1f %%   (Wilson 95 %% : %.1f – %.1f)"
           % (p_nom, 100 * bn, 100 * hn))
    ecrire("    non nommees %5.1f %%   (Wilson 95 %% : %.1f – %.1f)"
           % (p_lib, 100 * bl, 100 * hl))
    ecrire("")
    accuse = hn < bl                   # les intervalles ne se chevauchent pas
    if accuse:
        ecrire("  LES DEUX INTERVALLES NE SE CHEVAUCHENT PAS.")
        ecrire("  Les photos que nous avons nommees ont perdu leur trailer la")
        ecrire("  ou les autres l ont garde. La correlation est etablie.")
    elif p_nom < p_lib:
        ecrire("  Ecart dans le sens du soupcon, mais les intervalles se")
        ecrire("  CHEVAUCHENT : l echantillon ne tranche pas. Elargir.")
    else:
        ecrire("  Rien n accuse notre ecriture sur cet echantillon.")
    ecrire("")
    ecrire("  CE QUE CE BANC NE PROUVE PAS : la CAUSE. Une correlation ne dit")
    ecrire("  pas qui coupe. La preuve est un avant/apres sur LE MEME fichier")
    ecrire("  - relever le trailer, nommer la photo, relever a nouveau. C est")
    ecrire("  une ecriture, donc un geste de Mike, donc pas ce banc.")
    ecrire("=" * 74)
    return not accuse


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Le trailer Samsung survit-il a notre ecriture XMP ?")
    ap.add_argument('--racine', action='append', default=None)
    ap.add_argument('--echantillon', type=int, default=ECHANTILLON_DEFAUT)
    ap.add_argument('--exclure', action='append', default=None,
                    help='morceau de chemin a retirer de l echantillon ; '
                         'repeter l option pour plusieurs (le canal du banc '
                         'refuse les virgules et les espaces)')
    ap.add_argument('--json', dest='sortie_json', default=None)
    a = ap.parse_args(argv)

    racines = a.racine or F.racines(('dossiers_a_taguer.txt',))
    if not racines:
        print("aucune racine de fonds lisible (dossiers_a_taguer.txt).")
        return 2
    print("  enumeration de %s..." % ', '.join(racines))
    chemins, total = echantillon(racines, a.echantillon,
                                 exclure=a.exclure or ())
    print("  %d JPEG au fonds ; %d juges." % (total, len(chemins)))
    t, hors, exemples = croiser(chemins)
    ok = rapport(t, hors, total, len(chemins), exclure=a.exclure or (),
                 ecartes=globals().get('_ECARTES_CHEMIN', 0))
    if a.sortie_json:
        Path(a.sortie_json).write_text(json.dumps(
            {'racines': racines, 'fonds_jpeg': total,
             'exclure': a.exclure or [],
             'ecartes_chemin': globals().get('_ECARTES_CHEMIN', 0),
             'echantillon': len(chemins),
             'tableau': {'%s/%s' % k: v for k, v in t.items()},
             'ecartes': hors, 'exemples': exemples, 'ok': ok},
            indent=2, ensure_ascii=False), encoding='utf-8')
        print("  rapport JSON : %s" % a.sortie_json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
