#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
git_agent — livrer dans git par un FICHIER, et seulement si c'est prouvé
──────────────────────────────────────────────────────────────────────────────

POURQUOI

`pilotage.py` a ouvert à la sandbox le seul geste qu'elle ne pouvait pas faire :
redémarrer le serveur, donc OBSERVER ce qu'elle venait d'écrire. Restait le
dernier geste manuel de chaque livraison — commit, push, fusion — répété cinq
fois par session, toujours identique, et pourtant impossible depuis la VM :
`git` lancé sur le dossier MONTÉ laisse un `.git/index.lock` que la VM ne sait
pas supprimer (elle n'écrit, elle n'efface pas). Ce n'était donc pas un
principe, mais une impossibilité technique. Un agent qui tourne sous WINDOWS
lance le vrai `git`, et le verrou n'existe plus.

CE QUI CHANGE VRAIMENT — L'ORDRE

Jusqu'ici : commit → redémarrage → observation → fusion. Le commit précédait
la preuve, et c'est l'ordre que le bat 27 devait RAPPELER à chaque écran.
Ici l'agent inverse : **rien n'entre dans git avant d'avoir tourné**.

    éditer → écrire sur le disque → redémarrer → OBSERVER en réel
           → écrire « livrer » → l'agent contrôle, puis commit + push + fusion

L'agent n'est donc pas un bouton déporté : c'est la PORTE. Un commit refusé
parce que le serveur ne fait pas tourner le code qu'on veut graver vaut mieux
qu'un commit propre sur une observation fausse — « une observation fausse est
pire qu'une observation absente ».

LES CONTRÔLES, ET LEQUEL EST NÉGOCIABLE

  Jamais contournables — ils protègent le dépôt lui-même :
   1. aucun verrou `.git\\*.lock` (on ne le SUPPRIME pas : c'est peut-être un
      client git ouvert, et le bat 27 pose la question à un humain) ;
   2. `SESSION_COMMIT.txt` présent, lisible, branche de la forme
      `feat|fix|chore|docs|test/nom`, jamais `main` ;
   3. la branche visée est la courante, ou n'existe pas encore — on ne fait
      JAMAIS de `checkout` vers une branche existante : cela réécrirait le
      répertoire de travail sous le serveur qui tourne ;
   4. rien d'énorme ni de binaire dans ce qui serait commité — ceinture
      par-dessus les bretelles de `.gitignore` : `photos.db` fait 290 Mo.

  Contournables par `force=raison` dans `SESSION_COMMIT.txt` (tracé) :
   5. tout `.py` modifié (hors `test_` / `mesure_`, que le serveur n'importe
      jamais) est PLUS ANCIEN que le démarrage du serveur — donc le serveur
      fait tourner ce qu'on grave ;
   6. les `test_*.py` des modules touchés passent ;
   7. `verifier_bat.py` passe si un `.bat` a changé (règle absolue du projet) ;
   8. le lint des docs de suivi est propre.

La règle 5 est volontairement plus stricte que nécessaire : `git_agent.py`
lui-même n'est jamais importé par le serveur, et exiger un redémarrage pour le
commiter est un faux positif. C'est le prix d'une règle qu'on peut lire en une
ligne ; le redémarrage coûte douze secondes, et `force=` existe.

CE QUE L'AGENT NE SAIT PAS FAIRE

Ni `reset`, ni `rebase`, ni `--force`, ni `checkout` d'une branche existante,
ni supprimer une branche, ni toucher à `main` autrement qu'en fast-forward
(technique du bat 27 : `push origin HEAD:main`, sans jamais `checkout main`).
Il n'a aucun mot pour défaire : ce qui défait reste un geste de Mike.

LA VÉRIFICATION N'EST PAS SON RAPPORT

`_etat_git.json` dit ce que l'agent a TENTÉ. Ce qui s'est PASSÉ se lit dans
`.git/logs/HEAD` et `.git/logs/refs/heads/main`, que la sandbox lit déjà en
début de session. Un agent qui serait à la fois l'acteur et le juge ne
prouverait rien.

LE SIGNE DE VIE

`superviseur_git.bat` touche `_agent_git_vu.txt` à chaque tour de boucle, et la
commande `ping` fait répondre l'agent sans rien toucher. Les deux existent parce
que le 19/08 une fenêtre morte-née s'est révélée indiscernable d'une fenêtre en
écoute : rien ne se livrait, et rien ne le disait.

USAGE
    python git_agent.py --executer     (boucle du superviseur : agit si demandé)
    python git_agent.py --etat         (affiche le dernier rapport)
    python git_agent.py --controle     (contrôles seuls, ne touche pas au dépôt)
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import canal

__all__ = ['FICHIER_COMMANDE', 'FICHIER_ETAT', 'COMMANDES', 'DEFAUT',
           'PERIODE_S', 'lire_commande', 'ecrire_commande',
           'lire_session_commit', 'motif_branche', 'motif_fichiers',
           'py_a_observer', 'tests_pour', 'porcelain']

FICHIER_COMMANDE = '_commande_git.txt'
FICHIER_ETAT = '_etat_git.json'
FICHIER_VU = '_agent_git_vu.txt'      # touché à chaque tour de boucle
SESSION_COMMIT = 'SESSION_COMMIT.txt'

# `commit` = branche + push, `main` INTACTE (traite autonome : la fusion
# attend le retour de Mike). `livrer` ajoute le fast-forward de `main`. Les
# deux POUSSENT : un commit qui ne vit que sur un disque n'est pas livré.
RIEN, PING, COMMIT, LIVRER = 'rien', 'ping', 'commit', 'livrer'
# `ping` ne touche à RIEN : il consomme la commande et écrit un rapport.
# Sans lui, la seule façon de savoir si l'agent écoute était de lui
# demander une livraison — un test qui modifie le dépôt n'est pas un test.
COMMANDES = (RIEN, PING, COMMIT, LIVRER)
DEFAUT = RIEN

# Le superviseur relit le fichier toutes les PERIODE_S secondes. Trois : un
# `stat` local, jamais le NAS — et personne n'attend un commit à la seconde.
PERIODE_S = 3.0

# Préfixes de branche autorisés. La liste est courte à dessein : une branche
# hors convention est plus probablement une faute de frappe qu'un chantier.
BRANCHE_OK = re.compile(r'^(feat|fix|chore|docs|test)/[a-z0-9][a-z0-9._-]*$')

# Ce qui ne doit JAMAIS entrer dans un dépôt de 12 000 lignes de Python : bases,
# poids de modèles, archives, exécutables, vidéos. `.gitignore` les écarte déjà
# — ceci est la ceinture, pas les bretelles, et une ceinture ne coûte rien.
EXT_INTERDITES = {
    '.db', '.db-wal', '.db-shm', '.sqlite', '.sqlite3', '.wal', '.shm',
    '.pt', '.pth', '.onnx', '.safetensors', '.bin', '.ckpt',
    '.zip', '.7z', '.rar', '.tar', '.gz', '.exe', '.dll', '.msi',
    '.mp4', '.mov', '.avi', '.mkv', '.pyc',
}
TAILLE_MAX = 5 * 1024 * 1024        # 5 Mo : au-delà, on veut une phrase humaine

# Modules que le serveur n'importe jamais : les faire compter dans le contrôle
# « le serveur tourne-t-il ce code » ferait sonner l'alarme pour rien, et une
# alarme qui sonne pour rien s'ignore. Même raison que le rappel du bat 27.
HORS_SERVEUR = re.compile(r'^(test_|mesure_)')

API_SERVEUR = 'http://127.0.0.1:8080/api/serveur'


# ─────────────────────── le canal (miroir de pilotage) ───────────────────────

def lire_commande(chemin):
    """Commande courante, normalisée — toujours l'une de `COMMANDES`.

    Les octets sont l'affaire de `canal`, partagé avec `pilotage` et
    `banc_agent` : absent, vide, illisible ou inconnu → `rien`, l'état qui
    n'agit pas. Le doute penche du côté qui NE TOUCHE PAS au dépôt."""
    mot = canal.lire_ligne(chemin, DEFAUT).lower()
    return mot if mot in COMMANDES else DEFAUT


def ecrire_commande(chemin, commande):
    """Écrit la commande, atomiquement, en CRLF explicite.

    Atomique parce que l'agent relit ce fichier toutes les trois secondes : un
    fichier à moitié écrit se lirait `rien`, donc une livraison silencieusement
    perdue. Le détail des octets vit dans `canal`."""
    commande = str(commande).strip().lower()
    if commande not in COMMANDES:
        raise ValueError(f"commande inconnue : {commande!r} "
                         f"(attendu : {', '.join(COMMANDES)})")
    return canal.ecrire_ligne(chemin, commande)


# ────────────────────────── lectures pures (testables) ──────────────────────

def lire_session_commit(texte):
    """`SESSION_COMMIT.txt` → {'branche', 'titre', 'force'}.

    Format déjà en service (lu par `27 - Git.bat`, choix 1) : `cle=valeur`, une
    par ligne, `#` en commentaire. `force=raison` est la seule nouveauté — elle
    lève les contrôles NÉGOCIABLES et sa raison part dans le journal. Une
    livraison forcée doit rester lisible six mois plus tard."""
    out = {'branche': '', 'titre': '', 'force': ''}
    for ligne in (texte or '').splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#') or '=' not in ligne:
            continue
        cle, _, val = ligne.partition('=')
        cle = cle.strip().lower()
        if cle in out:
            out[cle] = val.strip()
    return out


def motif_branche(nom):
    """Motif de refus d'un nom de branche, ou None s'il est acceptable."""
    if not nom:
        return "SESSION_COMMIT.txt ne donne pas de branche"
    if nom == 'main':
        return "livrer directement sur main n'est pas un geste de l'agent"
    if not BRANCHE_OK.match(nom):
        return (f"nom de branche hors convention : {nom!r} "
                "(attendu feat|fix|chore|docs|test/nom-en-minuscules)")
    return None


def porcelain(sortie):
    """`git status --porcelain` → liste de chemins concernés.

    Gère les renommages (`R  ancien -> nouveau` : les DEUX comptent) et les
    chemins entre guillemets que git produit dès qu'un nom sort de l'ASCII —
    et ce dépôt en a (`0 - Démarrer le serveur.bat`)."""
    chemins = []
    for ligne in (sortie or '').splitlines():
        if len(ligne) < 4:
            continue
        reste = ligne[3:]
        for part in (reste.split(' -> ') if ' -> ' in reste else [reste]):
            part = part.strip()
            if part.startswith('"') and part.endswith('"'):
                try:
                    part = part[1:-1].encode().decode('unicode_escape')
                    part = part.encode('latin-1').decode('utf-8', 'replace')
                except (UnicodeDecodeError, ValueError):
                    part = part.strip('"')
            if part:
                chemins.append(part)
    return chemins


def motif_fichiers(chemins, taille_de):
    """Motif de refus portant sur CE QUI SERAIT COMMITÉ, ou None.

    `taille_de(chemin)` rend une taille en octets (0 si le fichier a été
    supprimé — un effacement n'a pas de poids et ne doit pas être refusé)."""
    for c in chemins:
        ext = Path(c).suffix.lower()
        if ext in EXT_INTERDITES:
            return (f"{c} : extension {ext} interdite dans le dépôt "
                    "(base, poids de modèle, archive ou binaire)")
        try:
            taille = taille_de(c)
        except OSError:
            taille = 0
        if taille > TAILLE_MAX:
            return (f"{c} : {taille // 1024} Ko > {TAILLE_MAX // 1024} Ko — "
                    "un gros fichier se commite à la main, avec une phrase")
    return None


def py_a_observer(chemins):
    """Les `.py` modifiés que le SERVEUR importe — ceux dont il faut prouver
    qu'il les fait tourner. `test_*` et `mesure_*` en sont exclus : le serveur
    ne les importe jamais."""
    out = []
    for c in chemins:
        p = Path(c)
        if p.suffix.lower() == '.py' and not HORS_SERVEUR.match(p.name):
            out.append(c)
    return out


def tests_pour(chemins, existe):
    """Fichiers de test à lancer : ceux des modules touchés, plus les fichiers
    de test modifiés eux-mêmes. `existe(nom)` dit si le fichier est là.

    Un module sans test n'est pas un refus — la moitié du dépôt est ancienne.
    C'est un fait à journaliser, pas une porte à fermer."""
    out = []
    for c in chemins:
        p = Path(c)
        if p.suffix.lower() != '.py':
            continue
        if p.name.startswith('test_'):
            cible = p.name
        else:
            cible = 'test_' + p.name
        if existe(cible) and cible not in out:
            out.append(cible)
    return sorted(out)


# ───────────────────────────── le monde extérieur ────────────────────────────

def _git(projet, *args, **kw):
    """Un appel git, sortie capturée. Aucun shell : les arguments passent tels
    quels, donc un nom de branche exotique ne peut pas devenir une commande."""
    r = subprocess.run(('git',) + args, cwd=str(projet), capture_output=True,
                       text=True, encoding='utf-8', errors='replace',
                       timeout=kw.get('timeout', 180))
    return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()


def _python():
    """L'interpréteur du venv s'il existe, sinon celui qui nous exécute."""
    venv = Path(sys.argv[0]).resolve().parent / '.venv' / 'Scripts' / 'python.exe'
    return str(venv) if venv.exists() else sys.executable


def _serveur_demarre_a(url=API_SERVEUR):
    """`demarre_a` du serveur, ou None s'il ne répond pas. Localhost, stdlib,
    aucune dépendance — comme tout le reste du projet."""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=3) as r:
            return float(json.loads(r.read().decode('utf-8'))['demarre_a'])
    except Exception:                                   # noqa: BLE001
        return None


def _verrous(projet):
    g = Path(projet) / '.git'
    return [str(p.name) for p in (g / 'index.lock', g / 'HEAD.lock') if p.exists()]


# ─────────────────────────────── les contrôles ───────────────────────────────

def controler(projet, sc, chemins):
    """Rend (refus, notes). `refus` est None si la porte s'ouvre.

    L'ordre compte : les contrôles NON contournables d'abord, pour qu'un
    `force=` ne puisse jamais faire passer un verrou ou un `photos.db`."""
    projet = Path(projet)
    notes = []

    verrous = _verrous(projet)
    if verrous:
        return ("verrou git présent (%s) — un client git est peut-être ouvert. "
                "L'agent ne le supprime pas : c'est la question que « 27 - "
                "Git.bat » pose à un humain." % ', '.join(verrous), notes)

    m = motif_branche(sc['branche'])
    if m:
        return m, notes

    if not chemins:
        return "rien à commiter : le répertoire de travail est propre", notes

    m = motif_fichiers(chemins, lambda c: (projet / c).stat().st_size
                       if (projet / c).exists() else 0)
    if m:
        return m, notes

    # La branche visée : courante, ou inexistante. Jamais un `checkout` vers une
    # branche qui existe — il réécrirait server.py sous le serveur qui tourne.
    code, actuelle, _ = _git(projet, 'rev-parse', '--abbrev-ref', 'HEAD')
    actuelle = actuelle if code == 0 else ''
    if actuelle != sc['branche']:
        code, _, _ = _git(projet, 'rev-parse', '--verify', '--quiet',
                          'refs/heads/' + sc['branche'])
        if code == 0:
            return (f"la branche {sc['branche']} existe déjà et n'est pas la "
                    f"courante ({actuelle}) : y basculer réécrirait le "
                    "répertoire de travail sous le serveur. Geste de Mike.",
                    notes)
        notes.append(f"branche {sc['branche']} à créer depuis {actuelle}")

    if sc['force']:
        notes.append("FORCE : " + sc['force'])
        return None, notes

    # ── contrôle 5 : le serveur fait-il tourner ce qu'on grave ? ──
    py = py_a_observer(chemins)
    if py:
        demarre_a = _serveur_demarre_a()
        if demarre_a is None:
            return ("du code Python change, mais le serveur ne répond pas : "
                    "impossible de prouver qu'il fait tourner ce qu'on grave. "
                    "Démarrer le serveur, ou `force=`.", notes)
        en_retard = [c for c in py
                     if (projet / c).exists()
                     and (projet / c).stat().st_mtime > demarre_a]
        if en_retard:
            return ("le serveur a démarré AVANT " + ', '.join(en_retard) +
                    " : il fait tourner l'ancien code. Redémarrer "
                    "(_commande_serveur.txt), observer, puis relivrer.", notes)
        notes.append("serveur à jour sur %d module(s)" % len(py))

    # ── contrôle 6 : les tests des modules touchés ──
    tests = tests_pour(chemins, lambda n: (projet / n).exists())
    for t in tests:
        r = subprocess.run([_python(), t], cwd=str(projet), capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=600)
        if r.returncode != 0:
            queue = (r.stderr or r.stdout or '').strip().splitlines()[-3:]
            return f"{t} ne passe pas : " + ' / '.join(queue), notes
    notes.append("tests verts : " + (', '.join(tests) if tests else "aucun visé"))

    # ── contrôle 7 : les .bat en ASCII pur (règle absolue du projet) ──
    if any(Path(c).suffix.lower() == '.bat' for c in chemins):
        r = subprocess.run([_python(), 'verifier_bat.py'], cwd=str(projet),
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=120)
        if r.returncode != 0:
            return "verifier_bat.py refuse un .bat : " + (
                r.stdout or r.stderr or '').strip()[-300:], notes
        notes.append("bats ASCII purs")

    # ── contrôle 8 : le lint des docs de suivi ──
    r = subprocess.run([_python(), 'nettoyer_session.py', '--lint-only'],
                       cwd=str(projet), capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=120)
    if 'docs de suivi coherents' not in (r.stdout or ''):
        return "lint des docs de suivi : " + (
            r.stdout or '').strip().splitlines()[-1][:300], notes
    notes.append("lint des docs propre")

    return None, notes


# ─────────────────────────────── l'exécution ────────────────────────────────

def livrer(projet, commande):
    """Contrôle puis, si la porte s'ouvre, commit + push — et la fusion de
    `main` en plus pour `livrer`. Rend le dict de rapport écrit dans
    `_etat_git.json`."""
    projet = Path(projet)
    rap = {'quand': time.time(), 'commande': commande, 'ok': False,
           'refus': None, 'notes': [], 'etapes': [], 'branche': '',
           'titre': '', 'commit': ''}

    texte = ''
    p = projet / SESSION_COMMIT
    if p.exists():
        texte = p.read_text(encoding='utf-8-sig', errors='replace')
    sc = lire_session_commit(texte)
    rap['branche'], rap['titre'] = sc['branche'], sc['titre']
    if not sc['titre']:
        rap['refus'] = "SESSION_COMMIT.txt ne donne pas de titre"
        return rap

    code, sortie, _ = _git(projet, 'status', '--porcelain')
    if code != 0:
        rap['refus'] = "git status a échoué — ce dossier est-il un dépôt ?"
        return rap
    chemins = porcelain(sortie)

    refus, notes = controler(projet, sc, chemins)
    rap['notes'] = notes
    if refus:
        rap['refus'] = refus
        return rap

    def etape(libelle, *args):
        c, o, e = _git(projet, *args)
        rap['etapes'].append({'quoi': libelle, 'code': c,
                              'dit': (o or e).strip()[-400:]})
        return c == 0

    code, actuelle, _ = _git(projet, 'rev-parse', '--abbrev-ref', 'HEAD')
    if actuelle != sc['branche'] and not etape(
            'branche', 'checkout', '-b', sc['branche']):
        rap['refus'] = "création de la branche impossible"
        return rap

    if not etape('add', 'add', '-A'):
        rap['refus'] = "git add a échoué"
        return rap
    if not etape('commit', 'commit', '-m', sc['titre']):
        rap['refus'] = "git commit a échoué"
        return rap

    # La proposition est CONSOMMÉE — sinon la prochaine livraison reprendrait
    # un titre périmé, exactement comme le bat 27 la supprime au choix 1.
    try:
        p.unlink()
    except OSError:
        pass

    _, sha, _ = _git(projet, 'rev-parse', '--short', 'HEAD')
    rap['commit'] = sha

    # Le push vaut pour les DEUX modes, et c'est la correction du 20/08 : le
    # mode `commit` s'arrêtait ici, alors que la convention de la traite
    # autonome (`CLAUDE.md`) annonçait « branche + push ». Une nuit de travail
    # ne vivait donc que sur le disque de Mike — exactement le scénario que le
    # chantier 12 (« PC mort lundi, tout revit vendredi ») cherche à couvrir.
    # Ce que `commit` protège, c'est `main` ; ce n'est pas l'absence de copie.
    # Une branche de trop sur GitHub se jette en une commande ; une traite
    # perdue ne se rejoue pas.
    if not etape('push branche', 'push', '-u', 'origin', 'HEAD'):
        rap['refus'] = ("commit fait, push refusé — le commit est en local, "
                        "rien n'est perdu. Réseau ou identifiants GitHub ?")
        return rap

    if commande == COMMIT:
        rap['ok'] = True
        return rap

    # Fusion : la technique éprouvée du bat 27 — on ne fait JAMAIS
    # `checkout main`, donc le répertoire de travail n'est pas réécrit et le
    # verrou de server.py tenu par le serveur ne gêne pas.
    if not etape('fetch', 'fetch', 'origin'):
        rap['refus'] = "commit et push faits, fetch refusé"
        return rap
    code, _, _ = _git(projet, 'merge-base', '--is-ancestor', 'origin/main', 'HEAD')
    if code != 0:
        rap['refus'] = ("commit et push faits, mais main a DIVERGÉ : le "
                        "fast-forward est impossible. Une vraie fusion réécrit "
                        "le répertoire de travail — geste de Mike, serveur "
                        "arrêté (« 27 - Git.bat », choix 2 explique la suite).")
        return rap
    if not etape('fusion main', 'push', 'origin', 'HEAD:main'):
        rap['refus'] = "commit et push faits, fast-forward de main refusé"
        return rap
    etape('ref locale main', 'fetch', 'origin', 'main:main')

    rap['ok'] = True
    return rap


def ecrire_etat(chemin, rapport, garde=10):
    """Écrit le rapport, en gardant les `garde` derniers. Atomique, comme tout
    ce que ce projet écrit : le fichier est lu par la sandbox et par le bat."""
    chemin = Path(chemin)
    hist = []
    try:
        vieux = json.loads(chemin.read_text(encoding='utf-8'))
        hist = vieux.get('historique') or []
        if vieux.get('dernier'):
            hist = [vieux['dernier']] + hist
    except (OSError, ValueError, TypeError):
        hist = []
    data = {'dernier': rapport, 'historique': hist[:garde]}
    tmp = chemin.with_suffix(chemin.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    os.replace(tmp, chemin)
    return data


def _resume(rap):
    q = time.strftime('%H:%M:%S', time.localtime(rap.get('quand') or 0))
    if rap.get('ok'):
        return f"[{q}] OK {rap.get('commande')} {rap.get('commit')} " \
               f"sur {rap.get('branche')} — {rap.get('titre')}"
    return f"[{q}] REFUS ({rap.get('commande')}) : {rap.get('refus')}"


def main(argv):
    projet = Path(__file__).resolve().parent
    fcmd, fetat = projet / FICHIER_COMMANDE, projet / FICHIER_ETAT

    if '--etat' in argv:
        # Le signe de vie AVANT le rapport : un rapport vieux de trois heures
        # ne dit pas si l'agent écoute encore, et c'est la première question.
        vu = projet / FICHIER_VU
        try:
            age = int(time.time() - vu.stat().st_mtime)
            if age <= 30:
                print("  Agent : EN ECOUTE (vu il y a %d s)." % age)
            else:
                print("  Agent : SILENCIEUX depuis %d s — sa fenetre "
                      "\u00ab MediaLibrary - Git \u00bb est-elle ouverte ?" % age)
        except OSError:
            print("  Agent : AUCUN signe de vie — fenetre jamais lancee, ou "
                  "fermee depuis un redemarrage.")
        print()
        try:
            d = json.loads(fetat.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            print("  Aucun rapport : l'agent n'a encore rien tenté.")
            return 0
        print(" ", _resume(d.get('dernier') or {}))
        for n in (d.get('dernier') or {}).get('notes') or []:
            print("    -", n)
        for vieux in (d.get('historique') or [])[:5]:
            print("  ", _resume(vieux))
        return 0

    if '--controle' in argv:
        texte = ''
        p = projet / SESSION_COMMIT
        if p.exists():
            texte = p.read_text(encoding='utf-8-sig', errors='replace')
        sc = lire_session_commit(texte)
        _, sortie, _ = _git(projet, 'status', '--porcelain')
        refus, notes = controler(projet, sc, porcelain(sortie))
        for n in notes:
            print("  -", n)
        print("  REFUS :", refus) if refus else print("  La porte s'ouvre.")
        return 1 if refus else 0

    commande = lire_commande(fcmd)
    if commande == RIEN:
        return 0
    if commande == PING:
        ecrire_commande(fcmd, RIEN)
        ecrire_etat(fetat, {'quand': time.time(), 'commande': PING, 'ok': True,
                            'refus': None, 'notes': ["en écoute, rien tenté"],
                            'etapes': [], 'branche': '', 'titre': '',
                            'commit': ''})
        print("[agent git] ping — en écoute.")
        return 0
    # Consommée AVANT d'agir : si l'agent meurt en route, il ne recommencera
    # pas tout seul au tour suivant. Une livraison ne se rejoue pas à l'aveugle.
    ecrire_commande(fcmd, RIEN)
    rap = livrer(projet, commande)
    ecrire_etat(fetat, rap)
    print(_resume(rap))
    for n in rap.get('notes') or []:
        print("   -", n)
    return 0 if rap.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
