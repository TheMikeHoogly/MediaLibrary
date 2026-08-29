#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les COMPTES — qui regarde, et comment on le prouve
───────────────────────────────────────────────────

Chantier 17, étape 4 (choix de Mike, 29/08/2026 : un mot de passe par compte).

LE FICHIER

`comptes.json`, à côté du serveur, HORS git (`.gitignore`) :

    { "secret": "<hex, 32 octets — signe les jetons>",
      "comptes": { "Mike": { "sel": "<hex>", "hache": "<hex>", "admin": true,
                             "cree_le": "2026-08-29 15:00:00" }, ... } }

Le NOM d'un compte est le nom de son dossier `Photos <Nom>` : c'est lui que
`auteurs.proprietaire_de` compare, lui que `visibilite.visible` compare. Un
compte « Flo » voit `Photos Flo\\PRIVE` ; un compte « Florine » ne le
verrait pas. L'admin est `auteurs.ADMIN` (Mike) — le drapeau `admin` du
fichier est là pour le jour où il y en a deux.

LE MOT DE PASSE

Jamais en clair, jamais réversible : PBKDF2-HMAC-SHA256, 300 000 tours, sel
de 16 octets par compte (bibliothèque standard, rien à installer). La
comparaison est à temps constant (`hmac.compare_digest`).

LA SESSION

Un jeton signé, pas une table de sessions : `<nom>|<expire>|<hmac>`, HMAC
du secret du fichier. Il survit au redémarrage du serveur (le secret est sur
disque), expire en 30 jours, et se révoque pour tout le monde en changeant le
secret. Un jeton n'est valable que si le compte existe encore.

LA PORTE

`porte(chemin, nom)` dit ce que fait le serveur pour une requête :
  - 'ouvert' : rien à vérifier (page de connexion, `/api/serveur` pour les
    agents locaux, les fichiers statiques de l'UI) ;
  - 'ok' : un compte est là ;
  - 'connexion' : une PAGE sans compte -> rediriger vers /connexion ;
  - 'refus' : une API sans compte -> 401.
TANT QU'AUCUN COMPTE N'EXISTE, tout est 'ouvert' : le serveur d'aujourd'hui,
Mike seul, sans mot de passe, ne change pas d'un iota — la porte se ferme au
premier compte créé (`creer_compte.py`, à faire par Mike sur le PC) — le
serveur relit le fichier dès qu'il change, sans redémarrage.

LE FREIN

Cinq échecs en cinq minutes sur un même nom -> une minute d'attente, en
mémoire. Pas une forteresse (le LAN et Tailscale sont le périmètre), un
frein contre l'essai bête depuis un téléphone de la maison.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

from auteurs import ADMIN

TOURS = 300_000
DUREE_SESSION = 30 * 24 * 3600
COOKIE = 'session'
ECHECS_MAX, FENETRE_ECHECS, ATTENTE = 5, 300, 60

OUVERTS = ('/connexion', '/api/connexion', '/api/serveur', '/favicon.ico')
PREFIXES_OUVERTS = ('/ui/', '/static/')


def _hacher(mdp, sel_hex):
    return hashlib.pbkdf2_hmac('sha256', mdp.encode('utf-8'), bytes.fromhex(sel_hex), TOURS).hex()


def nom_valide(nom):
    """Le nom d'un compte = le nom d'un dossier `Photos <Nom>` : pas vide,
    pas de séparateur, pas de deux-points ni de barre (le jeton les emploie)."""
    n = (nom or '').strip()
    return bool(n) and len(n) <= 40 and not any(c in n for c in '\\/|:\n\r\t')


class Comptes:
    def __init__(self, chemin):
        self.chemin = Path(chemin)
        self.lock = threading.Lock()
        self._echecs = {}       # nom -> [instants]
        self._d = {'secret': None, 'comptes': {}}
        self._charger()

    # ─── fichier ────────────────────────────────────────────────────────
    def _mtime(self):
        try:
            return self.chemin.stat().st_mtime
        except OSError:
            return 0.0

    def _charger(self):
        self._vu = self._mtime()
        try:
            d = json.loads(self.chemin.read_text(encoding='utf-8'))
            if isinstance(d, dict) and isinstance(d.get('comptes'), dict):
                self._d = d
        except (OSError, ValueError):
            pass
        if not self._d.get('secret'):
            self._d['secret'] = secrets.token_hex(32)
            if self._d['comptes']:
                self._sauver()

    def _sauver(self):
        tmp = self.chemin.with_name(self.chemin.name + '.tmp')
        tmp.write_text(json.dumps(self._d, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, self.chemin)
        self._vu = self._mtime()

    def recharger_si_change(self):
        """Relit le fichier s'il a bougé (un `stat` local) : un compte créé par
        `creer_compte.py` pendant que le serveur tourne est vu sans redémarrage."""
        if self._mtime() != self._vu:
            with self.lock:
                if self._mtime() != self._vu:
                    self._charger()
                    return True
        return False

    # ─── comptes ────────────────────────────────────────────────────────
    def noms(self):
        return sorted(self._d['comptes'])

    def existe(self, nom):
        return nom in self._d['comptes']

    def actifs(self):
        """La porte est fermée dès qu'un compte existe."""
        return bool(self._d['comptes'])

    def est_admin(self, nom):
        c = self._d['comptes'].get(nom)
        return bool(c and (c.get('admin') or nom == ADMIN))

    def creer(self, nom, mdp, admin=False):
        nom = (nom or '').strip()
        if not nom_valide(nom):
            raise ValueError('nom invalide')
        if len(mdp or '') < 8:
            raise ValueError('mot de passe trop court (8 caractères au moins)')
        with self.lock:
            if nom in self._d['comptes']:
                raise ValueError('ce compte existe déjà')
            sel = secrets.token_hex(16)
            self._d['comptes'][nom] = {
                'sel': sel, 'hache': _hacher(mdp, sel),
                'admin': bool(admin or nom == ADMIN),
                'cree_le': time.strftime('%Y-%m-%d %H:%M:%S')}
            self._sauver()
        return nom

    def changer_mdp(self, nom, mdp):
        if len(mdp or '') < 8:
            raise ValueError('mot de passe trop court (8 caractères au moins)')
        with self.lock:
            c = self._d['comptes'].get(nom)
            if not c:
                raise ValueError('compte inconnu')
            c['sel'] = secrets.token_hex(16)
            c['hache'] = _hacher(mdp, c['sel'])
            self._sauver()

    def supprimer(self, nom):
        with self.lock:
            if nom == ADMIN:
                raise ValueError("l'admin ne se supprime pas")
            if self._d['comptes'].pop(nom, None) is None:
                raise ValueError('compte inconnu')
            self._sauver()

    # ─── mot de passe ───────────────────────────────────────────────────
    def freine(self, nom, maintenant=None):
        """Secondes d'attente imposées à ce nom, 0 si aucune."""
        t = maintenant if maintenant is not None else time.time()
        L = [x for x in self._echecs.get(nom, []) if t - x < FENETRE_ECHECS]
        self._echecs[nom] = L
        if len(L) >= ECHECS_MAX:
            return max(0, int(ATTENTE - (t - L[-1])))
        return 0

    def verifier(self, nom, mdp, maintenant=None):
        """Le nom si le mot de passe est bon, None sinon (freiné compris).
        Un nom inconnu coûte le même calcul qu'un mauvais mot de passe : on ne
        dit pas par le TEMPS quels comptes existent."""
        nom = (nom or '').strip()
        t = maintenant if maintenant is not None else time.time()
        if self.freine(nom, t):
            return None
        c = self._d['comptes'].get(nom)
        sel = c['sel'] if c else '00' * 16
        attendu = c['hache'] if c else '00' * 32
        ok = hmac.compare_digest(_hacher(mdp or '', sel), attendu)
        if ok and c:
            self._echecs.pop(nom, None)
            return nom
        self._echecs.setdefault(nom, []).append(t)
        return None

    # ─── jeton de session ───────────────────────────────────────────────
    def _signer(self, corps):
        return hmac.new(self._d['secret'].encode(), corps.encode('utf-8'), hashlib.sha256).hexdigest()

    def jeton(self, nom, maintenant=None):
        t = maintenant if maintenant is not None else time.time()
        corps = f"{nom}|{int(t) + DUREE_SESSION}"
        return corps + '|' + self._signer(corps)

    def lire_jeton(self, jeton, maintenant=None):
        """Le nom du compte porté par un jeton valide, sinon None."""
        t = maintenant if maintenant is not None else time.time()
        try:
            nom, expire, sig = (jeton or '').split('|')
            if not hmac.compare_digest(sig, self._signer(f"{nom}|{expire}")):
                return None
            if int(expire) < t:
                return None
        except (ValueError, AttributeError):
            return None
        return nom if nom in self._d['comptes'] else None

    def revoquer_tout(self):
        """Change le secret : tous les jetons meurent."""
        with self.lock:
            self._d['secret'] = secrets.token_hex(32)
            self._sauver()

    # ─── la porte ───────────────────────────────────────────────────────
    def porte(self, chemin, nom):
        chemin = chemin or '/'
        if not self.actifs():
            return 'ouvert'
        if chemin in OUVERTS or chemin.startswith(PREFIXES_OUVERTS):
            return 'ouvert'
        if nom:
            return 'ok'
        return 'refus' if chemin.startswith('/api/') else 'connexion'


def cookie_session(en_tete):
    """La valeur du cookie `session` dans un en-tête Cookie, ou None."""
    for part in (en_tete or '').split(';'):
        k, _, v = part.strip().partition('=')
        if k == COOKIE and v:
            return v
    return None
