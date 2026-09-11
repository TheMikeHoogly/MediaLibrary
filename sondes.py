#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sondes — ce que le PROCESSUS fait payer a toutes les routes a la fois
──────────────────────────────────────────────────────────────────────────────
POURQUOI (11/09)
L'horloge de phases de `/api/maint/status` a montre, pendant la campagne, une
phase de TROIS `len()` a 51-101 ms, appel apres appel, et trois balayages de
44 600 entrees a 70-135 ms chacun — cinq a dix fois ce que ce code coute sur
une machine au repos. Le temps ne se perd pas DANS la route : quelque chose,
dans le processus, empeche le fil HTTP de tourner. Deux suspects, et aucun
instrument pour les departager :

  1. le RAMASSE-MIETTES — une collecte arrete TOUS les fils, et ce processus
     porte des millions d'objets (l'index, les visages, les faits) ;
  2. le GIL — un fil qui calcule en Python, ou qui tient le verrou dans un long
     appel C, fait attendre les autres ; le peage du 11/09 n'en a regle qu'une
     partie (`mesure_peage_gil.py`).

Deux sondes, une par suspect. Aucune ne change ce que fait le serveur.

  · `SondeGC`  : `gc.callbacks` — la duree de chaque collecte, par generation,
                 et un compteur cumule qu'une route lit avant et apres elle.
  · `SondeGIL` : un fil qui dort `periode` et mesure son RETARD au reveil.
                 Dormir relache le GIL ; le retard, c'est le temps qu'il a fallu
                 pour le reprendre (plus l'ordonnanceur de Windows, ~1 ms avec
                 le minuteur a 1 ms).

LEUR DEVOIR
Ne jamais lever, ne jamais bloquer, couter moins que ce qu'elles mesurent :
le rappel du GC tourne a CHAQUE collecte (des centaines par seconde sous
allocation) — deux `perf_counter` et trois additions ; la sonde du GIL se
reveille 50 fois par seconde. Module PUR (stdlib), teste sans serveur.
"""

import gc
import threading
import time

__all__ = ['SondeGC', 'SondeGIL', 'SEAUX_GIL_MS']


class SondeGC:
    """Duree des collectes du ramasse-miettes, par generation.

    Une collecte tient le GIL du debut a la fin : aucun autre fil Python ne
    tourne pendant le rappel, les compteurs n'ont donc pas besoin de verrou.
    `etat()` en rend une COPIE."""

    def __init__(self, horloge=time.perf_counter):
        self._horloge = horloge
        self._t0 = None
        self.total_ms = 0.0            # cumul, toutes generations : lu par les routes
        self.par_gen = {g: {'n': 0, 'ms': 0.0, 'max': 0.0, 'collectes': 0}
                        for g in (0, 1, 2)}
        self.pire = {'ms': 0.0, 'gen': None, 'a': None}
        self.branchee = False

    def rappel(self, phase, info):
        try:
            if phase == 'start':
                self._t0 = self._horloge()
                return
            if phase != 'stop' or self._t0 is None:
                return
            ms = (self._horloge() - self._t0) * 1000.0
            self._t0 = None
            g = info.get('generation', 0) if isinstance(info, dict) else 0
            e = self.par_gen.get(g)
            if e is None:
                # CPython n'a que trois generations : une autre valeur est un
                # rappel abime, pas une generation nouvelle.
                return
            e['n'] += 1
            e['ms'] += ms
            if ms > e['max']:
                e['max'] = ms
            e['collectes'] += int(info.get('collected', 0) or 0) if isinstance(info, dict) else 0
            self.total_ms += ms
            if ms > self.pire['ms']:
                self.pire = {'ms': ms, 'gen': g, 'a': time.time()}
        except Exception:                                         # noqa: BLE001
            self._t0 = None

    def brancher(self):
        """Pose le rappel. Idempotent ; ne leve jamais."""
        try:
            if self.rappel not in gc.callbacks:
                gc.callbacks.append(self.rappel)
            self.branchee = True
        except Exception:                                         # noqa: BLE001
            self.branchee = False
        return self.branchee

    def debrancher(self):
        try:
            while self.rappel in gc.callbacks:
                gc.callbacks.remove(self.rappel)
        except Exception:                                         # noqa: BLE001
            pass
        self.branchee = False

    def etat(self):
        try:
            seuils = gc.get_threshold()
            comptes = gc.get_count()
        except Exception:                                         # noqa: BLE001
            seuils = comptes = None
        return {
            'branchee': self.branchee,
            'total_ms': round(self.total_ms, 1),
            'par_gen': {str(g): {'n': e['n'], 'ms': round(e['ms'], 1),
                                 'max': round(e['max'], 1),
                                 'moy': round(e['ms'] / e['n'], 2) if e['n'] else None,
                                 'collectes': e['collectes']}
                        for g, e in sorted(self.par_gen.items(), key=lambda ge: str(ge[0]))},
            'pire': {'ms': round(self.pire['ms'], 1), 'gen': self.pire['gen'],
                     'a': self.pire['a']},
            'seuils': seuils, 'comptes': comptes,
        }


# Retard au reveil, en ms. Le premier seau est le bruit de l'ordonnanceur ; au
# dela de 5 ms, le fil a ATTENDU quelque chose.
SEAUX_GIL_MS = (2, 5, 15, 50, 150)


class SondeGIL:
    """Un fil qui dort `periode` secondes et note son retard au reveil.

    `tour()` fait UNE mesure (c'est ce que le banc appelle) ; `demarrer()` lance
    le fil qui boucle. Les chiffres : un cumul depuis le demarrage, et la
    FENETRE des `fenetre_s` dernieres secondes, remise a zero par tranche —
    un cumul seul noierait l'instant ou quelqu'un attendait."""

    def __init__(self, periode=0.02, fenetre_s=60.0,
                 horloge=time.perf_counter, dormir=time.sleep, mur=time.time):
        self.periode = float(periode)
        self.fenetre_s = float(fenetre_s)
        self._horloge = horloge
        self._dormir = dormir
        self._mur = mur
        self._lock = threading.Lock()
        self.cumul = self._vide()
        self.fenetre = self._vide()
        self.fenetre_precedente = None
        self._fenetre_debut = mur()
        self.vivante = False
        self.erreur = None

    @staticmethod
    def _vide():
        return {'n': 0, 'ms': 0.0, 'max': 0.0, 'seaux': [0] * (len(SEAUX_GIL_MS) + 1)}

    @staticmethod
    def _ranger(agr, ms):
        agr['n'] += 1
        agr['ms'] += ms
        if ms > agr['max']:
            agr['max'] = ms
        i = 0
        while i < len(SEAUX_GIL_MS) and ms >= SEAUX_GIL_MS[i]:
            i += 1
        agr['seaux'][i] += 1

    def tour(self):
        """Une mesure. Rend le retard en ms (jamais negatif)."""
        t0 = self._horloge()
        self._dormir(self.periode)
        retard = max(0.0, (self._horloge() - t0 - self.periode) * 1000.0)
        with self._lock:
            maintenant = self._mur()
            if maintenant - self._fenetre_debut >= self.fenetre_s:
                self.fenetre_precedente = self._fige(self.fenetre, self._fenetre_debut,
                                                     maintenant)
                self.fenetre = self._vide()
                self._fenetre_debut = maintenant
            self._ranger(self.cumul, retard)
            self._ranger(self.fenetre, retard)
        return retard

    @staticmethod
    def _fige(agr, debut, fin):
        return {'n': agr['n'], 'moy_ms': round(agr['ms'] / agr['n'], 2) if agr['n'] else None,
                'max_ms': round(agr['max'], 1), 'seaux': list(agr['seaux']),
                'de': round(debut, 1), 'a': round(fin, 1)}

    def boucle(self, continuer=lambda: True):
        self.vivante = True
        try:
            while continuer():
                self.tour()
        except Exception as e:                                    # noqa: BLE001
            self.erreur = str(e)[:200]
        finally:
            self.vivante = False

    def demarrer(self):
        try:
            t = threading.Thread(target=self.boucle, name='sonde_gil', daemon=True)
            t.start()
            return t
        except Exception as e:                                    # noqa: BLE001
            self.erreur = str(e)[:200]
            return None

    def etat(self):
        with self._lock:
            return {
                'vivante': self.vivante, 'erreur': self.erreur,
                'periode_ms': round(self.periode * 1000.0, 1),
                'seaux_ms': list(SEAUX_GIL_MS),
                'cumul': self._fige(self.cumul, 0.0, 0.0),
                'fenetre': self._fige(self.fenetre, self._fenetre_debut, self._mur()),
                'fenetre_precedente': self.fenetre_precedente,
            }
