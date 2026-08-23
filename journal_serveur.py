#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le journal du serveur — ce que la console disait, mais qui SURVIT
──────────────────────────────────────────────────────────────────────────────

POURQUOI CE MODULE EXISTE

Tout ce que `server.py` raconte va dans une fenêtre `cmd.exe` : les tracebacks
des threads qui meurent, les refus d'ExifTool, les avertissements d'un backfill
qui n'a rien trouvé. Cette fenêtre est chez Mike, et le sandbox ne la voit pas.
Le 22/08, une erreur affichée là a expliqué un défaut en une ligne — encore
a-t-il fallu que quelqu'un la lise et la recopie. Tant qu'elle n'existe QUE là,
diagnostiquer coûte un aller-retour humain, et un thread qui meurt en silence
pendant la nuit ne laisse rien du tout.

Ce module met un MIROIR sur `stdout` et `stderr` : la console garde exactement
ce qu'elle avait, et un fichier daté garde la même chose, lisible à distance
(`_journal_serveur.log`). Il ajoute ce qu'un `print` ne donne pas :

  · **l'heure** sur chaque ligne — sans elle, « ça a planté » ne se recoupe
    avec rien : ni avec un clic, ni avec un redémarrage, ni avec un banc ;
  · une **bannière de démarrage**, pour que « depuis le dernier démarrage » soit
    une question qui se réponde d'un `sed` ;
  · les **exceptions non rattrapées**, du fil principal ET des threads — c'est
    le cas qui n'apparaît nulle part ailleurs : un worker meurt, sa file se
    remplit, et le serveur a l'air vivant ;
  · les **plantages durs** (segfault d'une lib native) dans un fichier à part,
    via `faulthandler` — torch et insightface tournent dans ce processus.

CE QU'IL NE FAIT PAS

Il ne remplace pas la console : Mike voit toujours tout. Il ne parle à
personne : ni réseau, ni serveur — un journal qui a besoin du serveur vivant
est inutile le jour où le serveur meurt. Il n'échoue jamais bruyamment : un
disque plein ne doit pas tuer la photothèque, donc toute écriture ratée est
avalée, et seule la console reste.

ET IL RÉPARE UN VIEUX DÉFAUT AU PASSAGE

Une console `cp1252` lève `UnicodeEncodeError` sur un « ↻ » — c'est ce qui
avait fait tomber 11 tests le 22/08. Le miroir écrit le VRAI texte dans le
fichier et une version dégradée dans la console : le caractère ne peut plus
faire tomber ce qui l'entoure.

USAGE
    import journal_serveur
    journal_serveur.installer(SCRIPT_DIR / '_journal_serveur.log')
"""

import datetime
import faulthandler
import io
import os
import sys
import threading
import traceback
from pathlib import Path

TAILLE_MAX = 4 * 1024 * 1024      # au-delà, on tourne (une seule archive)
BANNIERE = "===== DEMARRAGE"      # ancre de « depuis le dernier demarrage »

_ETAT = {'journal': None, 'crash': None, 'installe': False}


class Journal:
    """Un fichier de lignes datées, borné, qui n'échoue jamais bruyamment."""

    def __init__(self, chemin, taille_max=TAILLE_MAX):
        self.chemin = Path(chemin)
        self.taille_max = int(taille_max)
        self.verrou = threading.RLock()
        self._f = None
        self._ouvrir()

    # — la mécanique —
    def _ouvrir(self):
        try:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            self._f = open(self.chemin, 'a', encoding='utf-8',
                           errors='replace', newline='\n')
        except OSError:
            self._f = None

    def _tourner_si_besoin(self):
        """Une seule archive : `.1`. Deux fichiers se lisent, dix se cherchent."""
        try:
            if self._f is None or self._f.tell() < self.taille_max:
                return
            self._f.close()
        except (OSError, ValueError):
            self._f = None
        try:
            os.replace(self.chemin, self.chemin.with_suffix(
                self.chemin.suffix + '.1'))
        except OSError:
            pass
        self._ouvrir()

    def ecrire(self, texte, horodater=True):
        """Une ou plusieurs lignes. Ne lève JAMAIS."""
        if not texte:
            return
        with self.verrou:
            if self._f is None:
                self._ouvrir()
            if self._f is None:
                return
            try:
                self._tourner_si_besoin()
                if self._f is None:
                    return
                if horodater:
                    h = datetime.datetime.now().strftime('%H:%M:%S')
                    texte = '\n'.join(f'{h} {l}' for l in texte.split('\n'))
                self._f.write(texte + '\n')
                self._f.flush()
            except (OSError, ValueError, UnicodeError):
                pass

    def fermer(self):
        with self.verrou:
            try:
                if self._f is not None:
                    self._f.close()
            except (OSError, ValueError):
                pass
            self._f = None


class Miroir(io.TextIOBase):
    """Ce qu'on écrit passe par la console ET par le journal.

    Le découpage se fait sur les LIGNES : `print` écrit le texte puis le saut
    de ligne en deux appels, et dater un fragment produirait un journal
    illisible. Ce qui n'est pas terminé attend sa fin de ligne."""

    def __init__(self, flux, journal):
        self.flux = flux
        self.journal = journal
        self._reste = ''
        self._verrou = threading.RLock()

    # — ce que le reste du monde attend d'un flux —
    def isatty(self):
        try:
            return self.flux.isatty()
        except (OSError, ValueError, AttributeError):
            return False

    def fileno(self):
        return self.flux.fileno()

    @property
    def encoding(self):
        return getattr(self.flux, 'encoding', 'utf-8')

    def writable(self):
        return True

    def flush(self):
        try:
            self.flux.flush()
        except (OSError, ValueError):
            pass

    def write(self, texte):
        if not isinstance(texte, str):
            texte = str(texte)
        with self._verrou:
            self._vers_console(texte)
            self._reste += texte
            if '\n' in self._reste:
                *lignes, self._reste = self._reste.split('\n')
                for ligne in lignes:
                    self.journal.ecrire(ligne.rstrip('\r'))
        return len(texte)

    def _vers_console(self, texte):
        """La console d'abord, et une console qui refuse un caractère ne fait
        plus tomber ce qui l'entoure : c'est le defaut du 22/08 (un « ↻ » sur
        cp1252 a fait tomber 11 tests). Le journal, lui, garde le vrai texte."""
        try:
            self.flux.write(texte)
            return
        except UnicodeEncodeError:
            pass
        except (OSError, ValueError):
            return
        try:
            cod = getattr(self.flux, 'encoding', None) or 'ascii'
            self.flux.write(texte.encode(cod, 'replace').decode(cod, 'replace'))
        except (OSError, ValueError, UnicodeError, LookupError):
            pass


# ────────────────────────────── L'installation ───────────────────────────────

def _banniere(source=None):
    maintenant = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    bout = f"{BANNIERE} {maintenant} pid {os.getpid()}"
    if source:
        try:
            mtime = datetime.datetime.fromtimestamp(
                Path(source).stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            bout += f" — {Path(source).name} du {mtime}"
        except OSError:
            pass
    return bout + " " + "=" * 5


def installer(chemin, source=None, taille_max=TAILLE_MAX):
    """Branche le miroir, les crochets d'exception et `faulthandler`.

    Rend le `Journal`. Deux appels ne branchent qu'une fois : le serveur peut
    être importé par mégarde sans empiler des miroirs sur des miroirs."""
    if _ETAT['installe']:
        return _ETAT['journal']

    journal = Journal(chemin, taille_max)
    _ETAT['journal'] = journal
    _ETAT['installe'] = True
    journal.ecrire(_banniere(source), horodater=False)

    sys.stdout = Miroir(sys.stdout, journal)
    sys.stderr = Miroir(sys.stderr, journal)

    # Une exception non rattrapee du fil principal : le serveur s'arrete, et
    # sans ca la raison ne survit pas a la fermeture de la fenetre.
    precedent = sys.excepthook

    def _crochet(genre, valeur, trace):
        # Une MARQUE, pas la trace : le crochet par défaut va l'imprimer sur
        # `stderr` juste après, et `stderr` est miré — l'écrire ici aussi
        # doublerait chaque traceback dans le journal. La marque, elle, est ce
        # qui se `grep`, et elle porte de quoi comprendre même si la trace
        # manquait.
        journal.ecrire(f"EXCEPTION NON RATTRAPEE (fil principal) : "
                       f"{getattr(genre, '__name__', genre)}: {valeur}")
        precedent(genre, valeur, trace)

    sys.excepthook = _crochet

    # Le cas qui n'apparait NULLE PART ailleurs : un thread de travail meurt,
    # sa file se remplit, et le serveur a l'air parfaitement vivant.
    if hasattr(threading, 'excepthook'):
        precedent_fil = threading.excepthook

        def _crochet_fil(args):
            nom = getattr(args.thread, 'name', '?')
            journal.ecrire(f"THREAD MORT : {nom} : "
                           f"{getattr(args.exc_type, '__name__', args.exc_type)}"
                           f": {args.exc_value}")
            precedent_fil(args)      # la trace complète arrive par `stderr`

        threading.excepthook = _crochet_fil

    # Plantage dur d'une lib native (torch, insightface) : il n'y a plus de
    # Python pour ecrire quoi que ce soit, seul faulthandler passe encore.
    try:
        crash = open(Path(chemin).with_name(Path(chemin).stem + '_crash.log'),
                     'a', encoding='utf-8')
        _ETAT['crash'] = crash
        faulthandler.enable(file=crash, all_threads=True)
    except (OSError, ValueError, RuntimeError):
        pass

    return journal


def dire(*morceaux):
    """Écrire dans le journal SANS passer par la console — pour ce qui aiderait
    un diagnostic mais encombrerait l'écran de Mike."""
    j = _ETAT.get('journal')
    if j is not None:
        j.ecrire(' '.join(str(m) for m in morceaux))


def depuis_le_dernier_demarrage(chemin):
    """Le journal depuis la dernière bannière — « qu'est-ce qui a plante depuis
    que ce serveur tourne ? » doit se répondre sans lire six heures de log."""
    try:
        texte = Path(chemin).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''
    i = texte.rfind(BANNIERE)
    return texte if i < 0 else texte[i:]
