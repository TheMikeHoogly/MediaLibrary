#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de `verifier_xmp_personnes.py` — sans serveur, sans ExifTool, sans NAS.

Ce banc juge un ECART entre l'index et les fichiers. Un instrument qui se
trompe sur cet ecart est pire qu'absent : il ferait croire le fonds a jour, ou
il ferait reecrire des milliers de fichiers pour rien. Les tests portent donc
sur l'ARITHMETIQUE (chaque cle dans une case et une seule) et sur ce que le
banc refuse de conclure quand il n'a pas vu.

SORTIE EN ASCII PUR : l'agent git lance les tests sans PYTHONUTF8, et sur une
console cp1252 un symbole leve une UnicodeEncodeError qui fait passer des tests
au rouge sans nommer sa cause (constate le 22/08).

    python test_verifier_xmp_personnes.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_xmp_personnes as V  # noqa: E402

ECHECS = []
RESULTATS = []


def verifie(nom, condition, detail=""):
    RESULTATS.append((nom, bool(condition), detail))
    if not condition:
        ECHECS.append("%s - %s" % (nom, detail))


def t_dossier_uploads(tmp):
    (tmp / "dossier_uploads.txt").write_text(
        "# un commentaire\n\n\\\\NAS\\home\\Photos\\_Uploads\n# autre\n",
        encoding='utf-8')
    d = V.dossier_uploads(tmp)
    verifie("dossier_uploads saute commentaires et lignes vides",
            str(d).endswith("_Uploads"), repr(d))
    verifie("dossier_uploads rend None si le fichier manque",
            V.dossier_uploads(tmp / "vide") is None)


def t_chemin_de_cle(tmp):
    up = Path("/fonds/uploads")
    verifie("cle simple vit sous UPLOAD_DIR",
            V.chemin_de_cle("a/b.jpg", up) == up / "a/b.jpg")
    abs_cle = "/ailleurs/x.jpg" if not sys.platform.startswith('win') \
        else "C:\\ailleurs\\x.jpg"
    verifie("cle absolue est un chemin, pas un relatif",
            V.chemin_de_cle(abs_cle, up) == Path(abs_cle))
    verifie("sans UPLOAD_DIR, une cle simple n'a pas de chemin",
            V.chemin_de_cle("a.jpg", None) is None)


def t_normalisation_et_mots(tmp):
    verifie("normalise: casse et separateurs",
            V._normalise("C:\\A\\B.JPG") == V._normalise("c:/a/b.jpg"))
    verifie("mots: une chaine seule est un mot",
            V._mots("personne:Flo") == ["personne:Flo"])
    verifie("mots: une liste reste une liste",
            V._mots(["a", "b"]) == ["a", "b"])
    verifie("mots: None ne fabrique pas de mot", V._mots(None) == [])


def t_comparer_cases_exclusives(tmp):
    up = Path("/f")
    tags = {
        V._normalise(up / "porte.jpg"): {"personne:florine", "vacances"},
        V._normalise(up / "manque.jpg"): {"vacances"},
        V._normalise(up / "fantome.jpg"): {"personne:flo"},
        V._normalise(up / "les_deux.jpg"): {"personne:florine", "personne:flo"},
    }
    cles = ["porte.jpg", "manque.jpg", "fantome.jpg", "les_deux.jpg",
            "jamais_lu.jpg"]
    r = V.comparer(cles, up, tags, "Florine", absent="Flo")
    verifie("porte le nom", r['porte'] == ["porte.jpg", "les_deux.jpg"],
            str(r['porte']))
    verifie("manque = la file le doit encore",
            r['manque'] == ["manque.jpg", "fantome.jpg"], str(r['manque']))
    verifie("fantome = l'ancien nom est encore dans le fichier",
            r['fantome'] == ["fantome.jpg", "les_deux.jpg"], str(r['fantome']))
    verifie("un fichier non lu est ILLISIBLE, jamais conforme",
            r['illisible'] == ["jamais_lu.jpg"], str(r['illisible']))
    somme = (len(r['porte']) + len(r['manque']) + len(r['illisible'])
             + len(r['introuvable']))
    verifie("chaque cle dans une case et une seule", somme == len(cles),
            "somme=%d sur %d" % (somme, len(cles)))


def t_comparer_casse_et_introuvable(tmp):
    up = Path("/f")
    tags = {V._normalise(up / "a.jpg"): {"Personne:FLORINE".lower()}}
    r = V.comparer(["a.jpg"], up, tags, "Florine")
    verifie("le nom se compare sans egard a la casse", r['porte'] == ["a.jpg"],
            str(r))
    r2 = V.comparer(["b.jpg"], None, {}, "Florine")
    verifie("sans UPLOAD_DIR la cle est INTROUVABLE, pas un ecart",
            r2['introuvable'] == ["b.jpg"] and not r2['manque'], str(r2))


def t_echantillon_reproductible(tmp):
    cles = ["p%03d.jpg" % i for i in range(500)]
    a, coupe = V.echantillonner(cles, 50)
    b, _ = V.echantillonner(cles, 50)
    verifie("echantillon de la taille demandee", len(a) == 50, str(len(a)))
    verifie("echantillon reproductible (graine fixe)", a == b)
    verifie("echantillon signale qu'il coupe", coupe is True)
    tout, coupe2 = V.echantillonner(cles, 0)
    verifie("taille 0 = tout le fonds, sans coupe",
            len(tout) == 500 and coupe2 is False)
    trop, coupe3 = V.echantillonner(cles, 9000)
    verifie("une taille plus grande que le fonds ne coupe pas",
            len(trop) == 500 and coupe3 is False)


def t_lire_tags_lots_et_pannes(tmp):
    """ExifTool est REMPLACE : on juge le decoupage en lots et la panne."""
    appels = {'n': 0, 'tailles': []}

    class Faux:
        def __init__(self, stdout):
            self.stdout = stdout
            self.returncode = 0

    def faux_run(cmd, **kw):
        appels['n'] += 1
        argfile = Path(cmd[cmd.index('-@') + 1])
        lignes = argfile.read_text(encoding='utf-8-sig').split('\n')
        fichiers = [l for l in lignes if l.endswith('.jpg')]
        appels['tailles'].append(len(fichiers))
        return Faux(json.dumps([{'SourceFile': f, 'Subject': ['personne:Flo']}
                                for f in fichiers]))

    vrai = V.subprocess.run
    V.subprocess.run = faux_run
    try:
        chemins = [Path("/f/p%03d.jpg" % i) for i in range(7)]
        vus = V.lire_tags(chemins, "exiftool.exe", lot=3)
        verifie("un seul processus par LOT (et non un par fichier)",
                appels['n'] == 3, "appels=%d" % appels['n'])
        verifie("les lots couvrent tous les fichiers",
                appels['tailles'] == [3, 3, 1], str(appels['tailles']))
        verifie("les tags sont rendus en minuscules, par chemin normalise",
                vus.get(V._normalise(chemins[0])) == {"personne:flo"},
                str(vus.get(V._normalise(chemins[0]))))

        def run_qui_plante(cmd, **kw):
            raise OSError("ExifTool absent")
        V.subprocess.run = run_qui_plante
        dits = []
        vus2 = V.lire_tags(chemins, "exiftool.exe", lot=3, journal=dits.append)
        verifie("un lot en panne ne rend RIEN plutot que du faux",
                vus2 == {}, str(vus2))
        verifie("un lot en panne le DIT", len(dits) == 3, str(dits))
    finally:
        V.subprocess.run = vrai


def t_rapport_ascii(tmp):
    """La sortie doit traverser une console cp1252 sans lever."""
    r = {'porte': ['a'], 'manque': ['b'], 'fantome': ['b'],
         'introuvable': [], 'illisible': ['c']}
    lignes = []
    V.rapporter(r, "Florine", "Flo", 3, False, 42, ecrire=lignes.append)
    texte = '\n'.join(lignes)
    try:
        texte.encode('cp1252')
        ok = True
    except UnicodeEncodeError as e:
        ok, texte = False, str(e)
    verifie("le rapport passe en cp1252 (console de l'agent git)", ok, texte)
    verifie("le rapport dit ce qu'il n'a PAS verifie",
            "NON VERIFIE" in texte and "illisible" in texte)
    verifie("le rapport donne les deux chiffres cote a cote",
            "OPERATION" in texte and "MANQUE" in texte)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="test_xmp_"))
    tests = [t_dossier_uploads, t_chemin_de_cle, t_normalisation_et_mots,
             t_comparer_cases_exclusives, t_comparer_casse_et_introuvable,
             t_echantillon_reproductible, t_lire_tags_lots_et_pannes,
             t_rapport_ascii]
    for t in tests:
        sous = tmp / t.__name__
        sous.mkdir(parents=True, exist_ok=True)
        try:
            t(sous)
        except Exception as e:                              # noqa: BLE001
            import traceback
            ECHECS.append("%s a leve %r" % (t.__name__, e))
            RESULTATS.append((t.__name__, False, repr(e)))
            traceback.print_exc()

    print("")
    print("=" * 74)
    print("  RESULTATS")
    print("=" * 74)
    for nom, ok, detail in RESULTATS:
        print("  %s %s%s" % ("OK  " if ok else "ECHEC", nom,
                             "" if ok else "  -> " + detail))
    print("=" * 74)
    n_ok = sum(1 for _, ok, _ in RESULTATS if ok)
    print("  %d/%d verifications passees" % (n_ok, len(RESULTATS)))
    print("  %s" % ("aucun echec" if not ECHECS
                    else "%d echec(s)" % len(ECHECS)))
    print("=" * 74)
    import shutil as _sh
    _sh.rmtree(tmp, ignore_errors=True)
    return 1 if ECHECS else 0


if __name__ == '__main__':
    sys.exit(main())
