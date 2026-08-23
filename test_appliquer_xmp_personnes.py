#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de `appliquer_xmp_personnes.py` — sans ExifTool, sans NAS, sans serveur.

Ce script ECRIT dans les fichiers du fonds : c'est le seul de sa famille ici, et
c'est celui dont une erreur ne se rattrape pas au clavier. Les tests portent
donc d'abord sur ce qu'il REFUSE de faire, ensuite sur ce qu'il fait.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).

    python test_appliquer_xmp_personnes.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appliquer_xmp_personnes as A  # noqa: E402
import verifier_xmp_personnes as V   # noqa: E402

ECHECS = []
RESULTATS = []


def verifie(nom, condition, detail=""):
    RESULTATS.append((nom, bool(condition), detail))
    if not condition:
        ECHECS.append("%s - %s" % (nom, detail))


class FauxExif:
    """Compte les invocations et retient les arguments de chacune."""

    def __init__(self, echoue_sur=()):
        self.appels = []
        self.echoue_sur = set(echoue_sur)

    def run(self, cmd, **kw):
        argfile = Path(cmd[cmd.index('-@') + 1])
        args = argfile.read_text(encoding='utf-8-sig').split('\n')
        self.appels.append(args)

        class R:
            pass
        r = R()
        r.returncode = 1 if any(e in args[-1] for e in self.echoue_sur) else 0
        r.stderr = "faux echec" if r.returncode else ""
        return r


def t_refus_si_la_file_tourne(tmp):
    """LA garde principale : deux ecrivains sur les memes fichiers."""
    vrai = V.file_du_serveur
    V.file_du_serveur = lambda *a, **k: 10801
    try:
        code = A.main(['--nom', 'Florine', '--appliquer'])
        verifie("REFUS tant que la file du serveur n'est pas vide", code == 3,
                "code=%r" % code)
    finally:
        V.file_du_serveur = vrai


def t_refus_sans_verite_dindex(tmp):
    vrai = V.file_du_serveur
    V.file_du_serveur = lambda *a, **k: None      # serveur muet
    try:
        code = A.main(['--nom', 'Florine', '--appliquer'])
        verifie("serveur muet et pas de rapport : on n'invente pas l'index",
                code == 2, "code=%r" % code)
    finally:
        V.file_du_serveur = vrai


def t_a_faire_ne_reecrit_pas_le_conforme(tmp):
    up = Path("/f")
    tags = {
        V._normalise(up / "ok.jpg"): {"personne:florine"},
        V._normalise(up / "manque.jpg"): {"vacances"},
        V._normalise(up / "fantome.jpg"): {"personne:florine", "personne:flo"},
        V._normalise(up / "les_deux.jpg"): {"personne:flo"},
    }
    cles = ["ok.jpg", "manque.jpg", "fantome.jpg", "les_deux.jpg", "jamais_lu.jpg"]
    plan = A.a_faire(cles, up, tags, "Florine", "Flo")
    par_cle = {o['cle']: o for o in plan}
    verifie("une photo deja conforme n'est pas reecrite (relancer REPREND)",
            "ok.jpg" not in par_cle, str(sorted(par_cle)))
    verifie("il manque le nom : on l'ajoute, sans retrait",
            par_cle['manque.jpg']['ajoute'] == ['Florine']
            and par_cle['manque.jpg']['retire'] == [], str(par_cle.get('manque.jpg')))
    verifie("l'ancien nom traine alors que le bon est la : retrait seul",
            par_cle['fantome.jpg']['retire'] == ['Flo']
            and par_cle['fantome.jpg']['ajoute'] == [], str(par_cle.get('fantome.jpg')))
    verifie("les deux gestes pour une meme photo",
            par_cle['les_deux.jpg']['ajoute'] == ['Florine']
            and par_cle['les_deux.jpg']['retire'] == ['Flo'],
            str(par_cle.get('les_deux.jpg')))
    verifie("un fichier NON LU n'est jamais reecrit a l'aveugle",
            "jamais_lu.jpg" not in par_cle)
    verifie("le plan note ce que le fichier portait AVANT",
            par_cle['manque.jpg']['avant'] == ["vacances"],
            str(par_cle['manque.jpg']['avant']))


def t_une_seule_invocation_par_photo(tmp):
    args = A.args_exiftool("/f/x.jpg", ["Florine"], ["Flo"])
    verifie("retrait ET ajout dans le MEME appel (person_writer en fait deux)",
            "-XMP-dc:Subject-=personne:Flo" in args
            and "-XMP-dc:Subject+=personne:Florine" in args, str(args))
    verifie("l'ajout fait -= puis += (pas de doublon, comme write_person_tag)",
            args.index("-XMP-dc:Subject-=personne:Florine")
            < args.index("-XMP-dc:Subject+=personne:Florine"), str(args))
    verifie("IPTC suit XMP", "-IPTC:Keywords+=personne:Florine" in args)
    verifie("le chemin est le dernier argument", args[-1] == "/f/x.jpg")
    verifie("ecriture en place, sans copie _original",
            "-overwrite_original" in args)


def t_journal_et_finally(tmp):
    faux = FauxExif(echoue_sur=("casse.jpg",))
    vrai = A.subprocess.run
    A.subprocess.run = faux.run
    try:
        plan = [{'cle': 'a.jpg', 'chemin': str(tmp / 'a.jpg'),
                 'ajoute': ['Florine'], 'retire': ['Flo'], 'avant': ['personne:flo']},
                {'cle': 'casse.jpg', 'chemin': str(tmp / 'casse.jpg'),
                 'ajoute': ['Florine'], 'retire': [], 'avant': []}]
        jp = tmp / "journal.jsonl"
        faits, rates = A.appliquer(plan, "exiftool.exe", jp, ecrire=lambda s: None)
        verifie("une invocation par photo, pas deux", len(faux.appels) == 2,
                str(len(faux.appels)))
        verifie("les succes et les echecs sont comptes a part",
                (faits, rates) == (1, 1), "%r" % ((faits, rates),))
        lignes = [json.loads(l) for l in
                  jp.read_text(encoding='utf-8').splitlines() if l.strip()]
        verifie("le journal a une ligne par photo TOUCHEE", len(lignes) == 2,
                str(len(lignes)))
        verifie("le journal note ce qui a ete retire et ajoute",
                lignes[0]['retire'] == ['Flo'] and lignes[0]['ajoute'] == ['Florine'],
                str(lignes[0]))
        verifie("le journal note l'etat AVANT (donc il peut defaire)",
                lignes[0]['avant'] == ['personne:flo'], str(lignes[0]['avant']))
        verifie("un echec est NOMME, pas avale",
                lignes[1]['ok'] is False and lignes[1]['erreur'],
                str(lignes[1]))
    finally:
        A.subprocess.run = vrai


def t_journal_survit_a_une_interruption(tmp):
    """Lecon du 23/08 : la fusion mourait apres la boucle, sans journal."""
    class Explose:
        def __init__(self):
            self.n = 0

        def run(self, cmd, **kw):
            self.n += 1
            if self.n == 2:
                raise KeyboardInterrupt("Mike ferme la fenetre")

            class R:
                returncode = 0
                stderr = ""
            return R()

    boum = Explose()
    vrai = A.subprocess.run
    A.subprocess.run = boum.run
    try:
        plan = [{'cle': '%d.jpg' % i, 'chemin': str(tmp / ('%d.jpg' % i)),
                 'ajoute': ['Florine'], 'retire': [], 'avant': []}
                for i in range(5)]
        jp = tmp / "interrompu.jsonl"
        try:
            A.appliquer(plan, "exiftool.exe", jp, ecrire=lambda s: None)
        except KeyboardInterrupt:
            pass
        lignes = [l for l in jp.read_text(encoding='utf-8').splitlines() if l.strip()]
        verifie("interrompue, la passe laisse quand meme son journal",
                len(lignes) == 1, str(len(lignes)))
        verifie("et ce journal est du JSONL relisible",
                json.loads(lignes[0])['cle'] == '0.jpg')
    finally:
        A.subprocess.run = vrai


def t_candidats_depuis_un_rapport(tmp):
    rap = tmp / "r.json"
    rap.write_text(json.dumps({'nom': 'Florine', 'absent': 'Flo',
                               'manque': ['a.jpg', 'b.jpg'],
                               'fantome': ['b.jpg', 'c.jpg']}),
                   encoding='utf-8')
    cles, nom, absent = A.candidats(str(rap))
    verifie("candidats = manque + fantome, sans doublon",
            cles == ['a.jpg', 'b.jpg', 'c.jpg'], str(cles))
    verifie("le rapport porte le nom et l'ancien nom",
            (nom, absent) == ('Florine', 'Flo'), "%r" % ((nom, absent),))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="test_appl_xmp_"))
    tests = [t_refus_si_la_file_tourne, t_refus_sans_verite_dindex,
             t_a_faire_ne_reecrit_pas_le_conforme,
             t_une_seule_invocation_par_photo, t_journal_et_finally,
             t_journal_survit_a_une_interruption, t_candidats_depuis_un_rapport]
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
