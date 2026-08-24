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
    """LA garde principale : deux ecrivains sur les memes fichiers.

    `--patience 0` : on mesure le REFUS, pas l'attente. Depuis le 23/08 le
    script attend d'abord que la file retombe (le curateur en remplit une
    toutes les quatre minutes) — mais la garde, elle, n'a pas bouge d'un
    pouce, et c'est ce que ce test tient."""
    vrai = V.file_du_serveur
    V.file_du_serveur = lambda *a, **k: 10801
    try:
        code = A.main(['--nom', 'Florine', '--appliquer', '--patience', '0'])
        verifie("REFUS tant que la file du serveur n'est pas vide", code == 3,
                "code=%r" % code)
    finally:
        V.file_du_serveur = vrai


def t_la_patience_par_defaut_est_une_CONSTANTE_lisible(tmp):
    """Une patience choisie dans le code au cas par cas ne se discute pas.
    30 min : le curateur passe toutes les 4 a 5 min, une attente qui abandonne
    avant six passages abandonnerait pour rien."""
    verifie("patience par defaut lisible et bornee",
            A.PATIENCE_S == 1800, "PATIENCE_S=%r" % A.PATIENCE_S)


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


# ───────────────────────────── Le mode --tous ────────────────────────────────
#
# Il engage cinq heures d'ecritures sans surveillance. Ce qui le rend
# acceptable tient en quatre points, et chacun a son test : il groupe par
# PHOTO (une invocation, pas une par nom), il REPREND ou il s'est arrete, il
# s'ARRETE si le serveur se remet a ecrire, et il DIT ce qu'il n'a pas fait.


def t_tous_groupe_par_PHOTO(tmp):
    """Une photo qui manque DEUX noms coute UNE invocation, pas deux.
    A 3,5 s l'invocation sur le NAS, c'est la moitie de la soiree."""
    a = Path(tmp) / "a.jpg"
    par_chemin = {V._normalise(a): (a, {"Ellie", "Mike"})}
    tags = {V._normalise(a): {"personne:florine"}}
    plan = A.a_faire_photo(par_chemin, tags)
    verifie("--tous : une entree par PHOTO, pas par couple", len(plan) == 1,
            "plan=%r" % plan)
    verifie("--tous : les deux noms manquants dans le MEME geste",
            plan and plan[0]['ajoute'] == ["Ellie", "Mike"],
            "ajoute=%r" % (plan[0]['ajoute'] if plan else None))


def t_tous_ne_reecrit_pas_le_conforme(tmp):
    a = Path(tmp) / "a.jpg"
    par_chemin = {V._normalise(a): (a, {"Ellie"})}
    plan = A.a_faire_photo(par_chemin, {V._normalise(a): {"personne:ellie"}})
    verifie("--tous : une photo conforme ne demande aucun geste",
            plan and plan[0]['ajoute'] == [], "plan=%r" % plan)


def t_tous_ne_devine_pas_ce_qu_il_n_a_pas_lu(tmp):
    """Un fichier non lu n'est ni repare ni marque fait : il repassera.
    Le declarer conforme serait exactement la faute qu'on repare aujourd'hui."""
    a = Path(tmp) / "a.jpg"
    plan = A.a_faire_photo({V._normalise(a): (a, {"Ellie"})}, {})
    verifie("--tous : non lu = rien, surtout pas 'conforme'", plan == [],
            "plan=%r" % plan)


def t_tous_REPREND_ou_il_s_est_arrete(tmp):
    tmp = Path(tmp)
    a, b = tmp / "a.jpg", tmp / "b.jpg"
    for f in (a, b):
        f.write_bytes(b"jpeg")
    faits = tmp / "faits.txt"
    faits.write_text(V._normalise(a) + "\n", encoding='utf-8')
    par_chemin = {V._normalise(a): (a, {"Ellie"}),
                  V._normalise(b): (b, {"Ellie"})}
    vrai_lire, vrai_run = V.lire_tags, A.subprocess.run
    faux = FauxExif()
    V.lire_tags = lambda chemins, exe, **kw: {V._normalise(c): set()
                                              for c in chemins}
    A.subprocess.run = faux.run
    try:
        r = A.balayer(par_chemin, "exiftool", tmp / "j.jsonl", faits,
                      serveur='', lot=10, appliquer_vrai=True,
                      ecrire=lambda *x: None)
    finally:
        V.lire_tags, A.subprocess.run = vrai_lire, vrai_run
    verifie("--tous : la photo deja faite n'est pas reprise", r['total'] == 1,
            "total=%r" % r['total'])
    verifie("--tous : une seule invocation ExifTool au second passage",
            len(faux.appels) == 1, "appels=%d" % len(faux.appels))
    verifie("--tous : la photo traitee s'ajoute au fichier de reprise",
            V._normalise(b) in A.charger_faits(faits))


def t_tous_S_ARRETE_si_le_serveur_se_remet_a_ecrire(tmp):
    """Deux ecrivains sur les memes fichiers, c'est la bagarre du 22/08.
    Le test verifie qu'il s'arrete ET qu'il le DIT. `--patience 0` = l'ancien
    comportement, celui qui n'attend pas : la garde ne depend PAS de l'attente.
    """
    tmp = Path(tmp)
    a = tmp / "a.jpg"
    a.write_bytes(b"jpeg")
    vrai = V.file_du_serveur
    V.file_du_serveur = lambda *x, **k: 42
    try:
        r = A.balayer({V._normalise(a): (a, {"Ellie"})}, "exiftool",
                      tmp / "j.jsonl", tmp / "faits.txt",
                      serveur='http://x', lot=10, appliquer_vrai=True,
                      ecrire=lambda *x: None, patience_s=0)
    finally:
        V.file_du_serveur = vrai
    verifie("--tous : il s'arrete quand la file du serveur repart",
            r['reecrites'] == 0 and r['arret'], "r=%r" % r)
    verifie("--tous : l'arret est NOMME, pas silencieux",
            "file du serveur" in (r['arret'] or ""), "arret=%r" % r['arret'])


class FileQuiRetombe:
    """La file du serveur : occupee `n` fois, puis vide. Comme le curateur."""

    def __init__(self, occupee, valeur=14):
        self.reste = occupee
        self.valeur = valeur
        self.lectures = 0

    def __call__(self, *a, **k):
        self.lectures += 1
        if self.reste > 0:
            self.reste -= 1
            return self.valeur
        return 0


def t_attente_le_curateur_ne_tue_plus_la_passe(tmp):
    """LE defaut du 23/08 : la passe est morte a 4 800 photos sur 18 900,
    onze secondes apres un « Auto-ajout : 14 visage(s) ». Le curateur en pose
    un toutes les quatre minutes ; abandonner au premier, c'est ne jamais
    finir."""
    dormis = []
    faux_temps = [0.0]

    def dormir(s):
        dormis.append(s)
        faux_temps[0] += s

    vrai = V.file_du_serveur
    V.file_du_serveur = FileQuiRetombe(occupee=3)
    try:
        libre, attendu, file = A.attendre_la_file(
            'http://x', patience_s=600, pas_s=10, ecrire=lambda *x: None,
            dormir=dormir, horloge=lambda: faux_temps[0])
    finally:
        V.file_du_serveur = vrai
    verifie("attente : la file retombe, on REPREND au lieu d'abandonner",
            libre is True, "libre=%r" % libre)
    verifie("attente : le temps attendu est COMPTE, pas tu",
            attendu == 30.0, "attendu=%r dormis=%r" % (attendu, dormis))
    verifie("attente : on n'a pas dormi plus que necessaire",
            dormis == [10, 10, 10], "dormis=%r" % dormis)


def t_attente_BORNEE_un_script_qui_se_fige_est_pire(tmp):
    """Lecon du `{ready}` avale par `-q` (23/08) : un banc doit ECHOUER,
    jamais attendre sans fin."""
    faux_temps = [0.0]

    def dormir(s):
        faux_temps[0] += s

    vrai = V.file_du_serveur
    V.file_du_serveur = lambda *a, **k: 7          # jamais vide
    try:
        libre, attendu, file = A.attendre_la_file(
            'http://x', patience_s=60, pas_s=10, ecrire=lambda *x: None,
            dormir=dormir, horloge=lambda: faux_temps[0])
    finally:
        V.file_du_serveur = vrai
    verifie("attente : la patience est BORNEE", libre is False,
            "libre=%r attendu=%r" % (libre, attendu))
    verifie("attente : la patience epuisee rend la file RESTANTE",
            file == 7, "file=%r" % file)


def t_attente_ne_desserre_RIEN_on_n_ecrit_pas_pendant(tmp):
    """L'invariant 1 est intact : tant que la file travaille, ExifTool n'est
    pas invoque une seule fois. Attendre n'est pas ecrire."""
    tmp = Path(tmp)
    a = tmp / "a.jpg"
    a.write_bytes(b"jpeg")
    faux = FauxExif()
    vrai_file, vrai_run = V.file_du_serveur, A.subprocess.run
    V.file_du_serveur = lambda *x, **k: 5          # occupee, et le reste
    A.subprocess.run = faux.run
    try:
        r = A.balayer({V._normalise(a): (a, {"Ellie"})}, "exiftool",
                      tmp / "j.jsonl", tmp / "faits.txt",
                      serveur='http://x', lot=10, appliquer_vrai=True,
                      ecrire=lambda *x: None, patience_s=0)
    finally:
        V.file_du_serveur, A.subprocess.run = vrai_file, vrai_run
    verifie("attente : AUCUNE invocation d'ExifTool pendant que la file "
            "travaille", faux.appels == [], "appels=%r" % faux.appels)
    verifie("attente : rien n'est marque FAIT non plus",
            not (tmp / "faits.txt").exists()
            or (tmp / "faits.txt").read_text(encoding='utf-8').strip() == "",
            "reprise polluee")
    verifie("attente : et l'arret est dit", bool(r['arret']))


def t_attente_serveur_MUET_est_libre_mais_se_dit(tmp):
    """Un serveur qui ne repond pas n'ecrit pas : on peut travailler. Mais un
    silence ne s'interprete pas tout seul — il rend None, jamais 0."""
    vrai = V.file_du_serveur
    V.file_du_serveur = lambda *a, **k: None
    try:
        libre, attendu, file = A.attendre_la_file('http://x', patience_s=60,
                                                  ecrire=lambda *x: None)
    finally:
        V.file_du_serveur = vrai
    verifie("attente : serveur muet = libre, sans attendre",
            libre is True and attendu == 0.0, "libre=%r a=%r" % (libre, attendu))
    verifie("attente : muet se distingue de vide (None, pas 0)",
            file is None, "file=%r" % file)


def t_demarrage_ATTEND_au_lieu_de_refuser_tout_de_suite(tmp):
    """La relance de 23 h ne doit pas buter sur un auto-ajout qui dure trois
    secondes. Avec --patience 0, le vieux refus immediat est intact."""
    vrai = V.file_du_serveur
    V.file_du_serveur = lambda *a, **k: 9
    try:
        code = A.main(['--nom', 'Florine', '--appliquer', '--patience', '0'])
    finally:
        V.file_du_serveur = vrai
    verifie("--patience 0 : le refus immediat est intact", code == 3,
            "code=%r" % code)


def t_le_temps_attendu_est_DIT_dans_le_rapport(tmp):
    """Une passe deux fois plus lente sans qu'on sache pourquoi est une mesure
    fausse."""
    tmp = Path(tmp)
    a = tmp / "a.jpg"
    a.write_bytes(b"jpeg")
    faux_temps = [0.0]

    def dormir(s):
        faux_temps[0] += s

    vrai_dormir, vrai_horloge = A.time.sleep, A.time.monotonic
    vrai_file, vrai_lire = V.file_du_serveur, V.lire_tags
    V.file_du_serveur = FileQuiRetombe(occupee=2)
    V.lire_tags = lambda chemins, exe, **kw: {V._normalise(c): set()
                                              for c in chemins}
    A.time.sleep = dormir
    A.time.monotonic = lambda: faux_temps[0]
    try:
        r = A.balayer({V._normalise(a): (a, {"Ellie"})}, "exiftool",
                      tmp / "j.jsonl", tmp / "faits.txt",
                      serveur='http://x', lot=10, appliquer_vrai=False,
                      ecrire=lambda *x: None, patience_s=600)
    finally:
        V.file_du_serveur, V.lire_tags = vrai_file, vrai_lire
        A.time.sleep, A.time.monotonic = vrai_dormir, vrai_horloge
    verifie("attente : le rapport COMPTE les attentes",
            r.get('attentes') == 1, "r=%r" % r)
    verifie("attente : le rapport dit les secondes attendues",
            r.get('attente_s') == 20.0, "r=%r" % r)
    verifie("attente : et la passe a bien continue apres",
            not r['arret'] and r['vues'] == 1, "r=%r" % r)


def t_tous_a_blanc_n_ecrit_RIEN(tmp):
    tmp = Path(tmp)
    a = tmp / "a.jpg"
    a.write_bytes(b"jpeg")
    faits = tmp / "faits.txt"
    vrai_lire, vrai_run = V.lire_tags, A.subprocess.run
    faux = FauxExif()
    V.lire_tags = lambda chemins, exe, **kw: {V._normalise(c): set()
                                              for c in chemins}
    A.subprocess.run = faux.run
    try:
        r = A.balayer({V._normalise(a): (a, {"Ellie"})}, "exiftool",
                      tmp / "j.jsonl", faits, serveur='', lot=10,
                      appliquer_vrai=False, ecrire=lambda *x: None)
    finally:
        V.lire_tags, A.subprocess.run = vrai_lire, vrai_run
    verifie("--tous a blanc : aucune invocation ExifTool en ecriture",
            len(faux.appels) == 0, "appels=%d" % len(faux.appels))
    verifie("--tous a blanc : rien n'est marque fait", not faits.exists())
    verifie("--tous a blanc : il compte quand meme ce qu'il ferait",
            r['reecrites'] == 1, "r=%r" % r)


def t_tous_refuse_de_se_melanger_a_nom(tmp):
    code = A.main(['--tous', '--nom', 'Ellie'])
    verifie("--tous ne se combine pas avec --nom", code == 2, "code=%r" % code)


def t_une_requete_qui_lache_est_REESSAYEE(tmp):
    """Le 23/08, le premier balayage a perdu Val — 1 205 photos — sur un
    « Remote end closed connection ». Un nom perdu ici ne revient jamais :
    ses photos sont marquees faites parce qu'elles portent un autre nom."""
    essais = {'n': 0}

    class R:
        def read(self_):
            return b'{"photos": [{"key": "a.jpg"}]}'

        def __enter__(self_):
            return self_

        def __exit__(self_, *a):
            return False

    def urlopen(*a, **k):
        essais['n'] += 1
        if essais['n'] < 3:
            raise ConnectionResetError("Remote end closed connection")
        return R()

    vrai = V.urllib.request.urlopen
    V.urllib.request.urlopen = urlopen
    try:
        cles = V.cles_du_nom('Val', 'http://x')
    finally:
        V.urllib.request.urlopen = vrai
    verifie("une requete qui lache est reessayee", cles == ['a.jpg'],
            "cles=%r apres %d essai(s)" % (cles, essais['n']))


def t_ce_qui_lache_TROIS_fois_leve(tmp):
    """Rendre une liste vide ferait passer un nom perdu pour un nom sans
    photo : c'est la difference entre « rien a faire » et « on ne sait pas »."""
    def urlopen(*a, **k):
        raise ConnectionResetError("toujours ferme")

    vrai = V.urllib.request.urlopen
    V.urllib.request.urlopen = urlopen
    leve = False
    try:
        V.cles_du_nom('Val', 'http://x')
    except OSError:
        leve = True
    finally:
        V.urllib.request.urlopen = vrai
    verifie("ce qui lache trois fois LEVE, au lieu de rendre une liste vide",
            leve)


def t_un_nom_saute_est_ECRIT_sur_disque_et_redit(tmp):
    """La console defile pendant cinq heures. Ces noms-la sont ceux qu il ne
    faut pas oublier."""
    tmp = Path(tmp)
    vrai_sautes, vrai_cles = A.NOMS_SAUTES, V.cles_du_nom
    A.NOMS_SAUTES = tmp / "sautes.txt"
    import verifier_xmp_toutes_personnes as T
    vrai_noms = T.noms_du_serveur
    T.noms_du_serveur = lambda *a, **k: [('Val', 1205), ('Ellie', 346)]

    def cles(nom, serveur, **k):
        if nom == 'Val':
            raise ConnectionResetError("ferme")
        return ['e.jpg']

    V.cles_du_nom = cles
    try:
        par_chemin, sautes = A.attendu_par_photo('http://x', Path('/f'),
                                                 ecrire=lambda *x: None)
    finally:
        V.cles_du_nom, T.noms_du_serveur = vrai_cles, vrai_noms
        lu = A.NOMS_SAUTES.read_text(encoding='utf-8') if A.NOMS_SAUTES.exists() else ''
        A.NOMS_SAUTES = vrai_sautes
    verifie("un nom saute est rendu a l appelant", sautes == ['Val'],
            "sautes=%r" % sautes)
    verifie("un nom saute est ecrit sur DISQUE", 'Val' in lu, "lu=%r" % lu)
    verifie("le nom saute ne laisse pas de photo fantome dans le plan",
            len(par_chemin) == 1, "par_chemin=%r" % list(par_chemin))



class ExifQuiEchoue(FauxExif):
    """Un ExifTool qui echoue avec une CAUSE nommee, comme le vrai.

    Les 13 echecs de la passe du 24/08 avaient deux causes, et la console de
    Mike n'en disait aucune : elle affichait `en echec : 3`. Onze d'entre eux
    etaient des `_exiftool_tmp` fantomes laisses par un ExifTool tue en cours
    de route, qui empechent DEFINITIVEMENT de reecrire la photo. Un compte
    sans cause ne se repare pas."""

    def __init__(self, echoue_sur=(), cause="Error: Temporary file already exists"):
        FauxExif.__init__(self, echoue_sur=echoue_sur)
        self.cause = cause

    def run(self, cmd, **kw):
        r = FauxExif.run(self, cmd, **kw)
        if r.returncode:
            r.stderr = self.cause
        return r


def _fonds_de_deux(tmp):
    tmp = Path(tmp)
    a, b = tmp / "a.jpg", tmp / "b.jpg"
    for f in (a, b):
        f.write_bytes(b"jpeg")
    par_chemin = {V._normalise(a): (a, {"Ellie"}),
                  V._normalise(b): (b, {"Ellie"})}
    return tmp, a, b, par_chemin


def _balaye(par_chemin, tmp, faits, faux):
    vrai_lire, vrai_run = V.lire_tags, A.subprocess.run
    V.lire_tags = lambda chemins, exe, **kw: {V._normalise(c): set()
                                              for c in chemins}
    A.subprocess.run = faux.run
    try:
        return A.balayer(par_chemin, "exiftool", tmp / "j.jsonl", faits,
                         serveur='', lot=10, appliquer_vrai=True,
                         ecrire=lambda *x: None)
    finally:
        V.lire_tags, A.subprocess.run = vrai_lire, vrai_run


def t_une_ecriture_QUI_ECHOUE_n_est_pas_notee_faite(tmp):
    """Regle 2, cote reprise : un nom qui n'a PAS atterri ne se note pas
    atterri. Le fichier de reprise etait ecrit pour toute photo VUE, echec
    compris — les 13 echecs du 24/08 sont ainsi marques faits, et aucune
    relance ne les reprendra jamais."""
    tmp, a, b, par_chemin = _fonds_de_deux(tmp)
    faits = tmp / "faits.txt"
    r = _balaye(par_chemin, tmp, faits, ExifQuiEchoue(echoue_sur={"a.jpg"}))
    deja = A.charger_faits(faits)
    verifie("l'echec n'est PAS note fait", V._normalise(a) not in deja,
            "reprise=%r" % sorted(deja))
    verifie("la reussite EST notee faite", V._normalise(b) in deja,
            "reprise=%r" % sorted(deja))
    verifie("l'echec est compte", r['rates'] == 1 and r['reecrites'] == 1,
            "r=%r" % r)


def t_l_echec_REPASSE_a_la_relance(tmp):
    """La consequence qui compte : relancer reprend la photo en echec, et
    seulement elle."""
    tmp, a, b, par_chemin = _fonds_de_deux(tmp)
    faits = tmp / "faits.txt"
    _balaye(par_chemin, tmp, faits, ExifQuiEchoue(echoue_sur={"a.jpg"}))
    faux2 = FauxExif()
    r2 = _balaye(par_chemin, tmp, faits, faux2)
    verifie("la relance ne reprend QUE l'echec", r2['total'] == 1,
            "total=%r" % r2['total'])
    verifie("la relance reprend la BONNE photo",
            len(faux2.appels) == 1 and "a.jpg" in faux2.appels[0][-1],
            "appels=%r" % faux2.appels)


def t_la_CAUSE_d_un_echec_est_dite_pas_seulement_son_compte(tmp):
    """`en echec : 3` ne se repare pas. `11 x Temporary file already exists`
    se repare : ce sont des fichiers fantomes a effacer."""
    tmp, a, b, par_chemin = _fonds_de_deux(tmp)
    faits = tmp / "faits.txt"
    r = _balaye(par_chemin, tmp, faits,
                ExifQuiEchoue(echoue_sur={"a.jpg"},
                              cause="Error: Temporary file already exists"))
    causes = r.get('causes') or {}
    verifie("le rapport porte les CAUSES d'echec", bool(causes),
            "causes=%r" % causes)
    verifie("la cause est nommee et comptee",
            sum(causes.values()) == 1
            and any("Temporary file" in c for c in causes),
            "causes=%r" % causes)



def t_le_mode_nom_DIT_AUSSI_la_cause(tmp):
    """`--nom Val` est le mode du rattrapage, celui qu'on lance a la main
    quand quelque chose a rate. S'il compte les echecs sans les nommer, on
    relance a l'aveugle."""
    tmp = Path(tmp)
    a = tmp / "a.jpg"
    a.write_bytes(b"jpeg")
    plan = [{'cle': str(a), 'chemin': str(a), 'ajoute': ['Val'],
             'retire': [], 'avant': []}]
    dit = []
    faux = ExifQuiEchoue(echoue_sur={"a.jpg"},
                         cause="Error: Temporary file already exists")
    vrai = A.subprocess.run
    A.subprocess.run = faux.run
    try:
        faits, rates = A.appliquer(plan, "exiftool", tmp / "j.jsonl",
                                   ecrire=dit.append)
    finally:
        A.subprocess.run = vrai
    verifie("--nom : l'echec est compte", rates == 1 and faits == 0,
            "faits=%r rates=%r" % (faits, rates))
    verifie("--nom : la cause est DITE",
            any("Temporary file" in l for l in dit), "dit=%r" % dit)



def _journal(tmp, lignes):
    j = Path(tmp) / "xmp_tous_20260101_000000.jsonl"
    import json as _j
    j.write_text('\n'.join(_j.dumps(l, ensure_ascii=False) for l in lignes)
                 + '\n', encoding='utf-8')
    return j


def t_echecs_des_journaux_ne_retient_que_ce_qui_a_RATE(tmp):
    """Les 13 echecs du 24/08 sont dans les journaux, avec leur cause et les
    noms qui n'ont pas atterri. Personne ne les relira a la main."""
    tmp = Path(tmp)
    a, b = tmp / "a.jpg", tmp / "b.jpg"
    for f in (a, b):
        f.write_bytes(b"jpeg")
    _journal(tmp, [
        {'chemin': str(a), 'ajoute': ['Val'], 'ok': False,
         'erreur': 'Error: Temporary file already exists'},
        {'chemin': str(a), 'ajoute': ['Zab'], 'ok': False, 'erreur': 'x'},
        {'chemin': str(b), 'ajoute': ['Mike'], 'ok': True, 'erreur': ''},
    ])
    par_chemin = A.echecs_des_journaux(tmp)
    verifie("les echecs : la photo qui a RATE est la",
            V._normalise(a) in par_chemin, "%r" % sorted(par_chemin))
    verifie("les echecs : celle qui a REUSSI n'y est pas",
            V._normalise(b) not in par_chemin, "%r" % sorted(par_chemin))
    verifie("les echecs : les noms d'une meme photo sont GROUPES",
            par_chemin.get(V._normalise(a), (None, set()))[1] == {'Val', 'Zab'},
            "%r" % (par_chemin.get(V._normalise(a)),))


def t_reprendre_les_echecs_NE_CROIT_PAS_le_journal(tmp):
    """Un journal est une liste de candidats, pas un ordre : entre l'echec et
    la reprise, la file du serveur a pu poser le nom. On relit les tags."""
    tmp = Path(tmp)
    a = tmp / "a.jpg"
    a.write_bytes(b"jpeg")
    par_chemin = {V._normalise(a): (a, {"Val"})}
    tags = {V._normalise(a): {"personne:val"}}
    verifie("les echecs : une photo devenue conforme ne se reecrit pas",
            A.a_faire_photo(par_chemin, tags)[0]['ajoute'] == [],
            "%r" % A.a_faire_photo(par_chemin, tags))


def t_reprendre_les_echecs_ne_se_melange_pas_aux_autres_modes(tmp):
    verifie("--reprendre-echecs refuse de se melanger a --tous",
            A.main(['--reprendre-echecs', '--tous']) == 2)
    verifie("--reprendre-echecs refuse de se melanger a --nom",
            A.main(['--reprendre-echecs', '--nom', 'Val']) == 2)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="test_appl_xmp_"))
    tests = [t_refus_si_la_file_tourne, t_refus_sans_verite_dindex,
             t_la_patience_par_defaut_est_une_CONSTANTE_lisible,
             t_a_faire_ne_reecrit_pas_le_conforme,
             t_une_seule_invocation_par_photo, t_journal_et_finally,
             t_journal_survit_a_une_interruption, t_candidats_depuis_un_rapport,
             t_tous_groupe_par_PHOTO, t_tous_ne_reecrit_pas_le_conforme,
             t_tous_ne_devine_pas_ce_qu_il_n_a_pas_lu,
             t_tous_REPREND_ou_il_s_est_arrete,
             t_tous_S_ARRETE_si_le_serveur_se_remet_a_ecrire,
             t_tous_a_blanc_n_ecrit_RIEN, t_tous_refuse_de_se_melanger_a_nom,
             t_une_requete_qui_lache_est_REESSAYEE,
             t_ce_qui_lache_TROIS_fois_leve,
             t_un_nom_saute_est_ECRIT_sur_disque_et_redit,
             t_attente_le_curateur_ne_tue_plus_la_passe,
             t_attente_BORNEE_un_script_qui_se_fige_est_pire,
             t_attente_ne_desserre_RIEN_on_n_ecrit_pas_pendant,
             t_attente_serveur_MUET_est_libre_mais_se_dit,
             t_demarrage_ATTEND_au_lieu_de_refuser_tout_de_suite,
             t_le_temps_attendu_est_DIT_dans_le_rapport,
             t_une_ecriture_QUI_ECHOUE_n_est_pas_notee_faite,
             t_l_echec_REPASSE_a_la_relance,
             t_la_CAUSE_d_un_echec_est_dite_pas_seulement_son_compte,
             t_le_mode_nom_DIT_AUSSI_la_cause,
             t_echecs_des_journaux_ne_retient_que_ce_qui_a_RATE,
             t_reprendre_les_echecs_NE_CROIT_PAS_le_journal,
             t_reprendre_les_echecs_ne_se_melange_pas_aux_autres_modes]
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
