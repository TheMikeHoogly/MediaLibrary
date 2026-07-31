"""
Ordonnancement des travaux de fond et arbitrage de la VRAM.
──────────────────────────────────────────────────────────────────────────────

LE PROBLEME MESURE
    Chaque boucle de fond decidait seule, par « if system_busy(): dors ».
    Or system_busy() est vrai des que le CPU depasse 70 %, et le balayage des
    visages l'y maintient en permanence. Resultat : l'encodage semantique est
    reste bloque a 5 % du corpus (1 447 photos sur 30 682) — il n'attendait
    pas son tour, il renoncait.

    Cote GPU, quatre politiques independantes (FACE_GPU_MIN_FREE_MB,
    ANIMAL_GPU_MIN_FREE_MB, PET_GPU_MIN_FREE_MB, plus Ollama qui garde son
    modele 30 minutes) se partagent 4 096 Mo au premier arrive, premier servi.

DEUX MECANISMES
    Ordonnanceur — un seul travail lourd a la fois, choisi par TOUR DE ROLE A
    DEFICIT. Chaque travail porte une dette qui augmente de 1/poids a chaque
    passage ; c'est toujours le plus endette qui passe. Un travail lent ou
    peu prioritaire finit donc TOUJOURS par passer : la famine devient
    structurellement impossible, ce qu'un seuil ne garantit jamais.

    ArbitreGPU — des baux explicites sur la VRAM, avec priorites. Un seul
    point de verite sur ce qui est reserve, au lieu de N sondes concurrentes
    qui voient toutes la meme memoire libre et se croient seules.

Aucune dependance : threading et time.
"""

import threading
import time
from contextlib import contextmanager


class Ordonnanceur:
    """Tour de role a deficit entre les travaux de fond."""

    def __init__(self, poids):
        # poids eleve = passe plus souvent. Ce n'est PAS une priorite stricte :
        # une priorite stricte affame les derniers, c'est le defaut qu'on corrige.
        self.poids = dict(poids)
        self.dette = {n: 0.0 for n in poids}
        self.attente = set()
        self.actif = None
        self.depuis = 0.0
        self.tours = {n: 0 for n in poids}
        self.temps = {n: 0.0 for n in poids}
        self.cv = threading.Condition()

    def inscrire(self, nom, poids=1.0):
        with self.cv:
            self.poids.setdefault(nom, poids)
            self.dette.setdefault(nom, 0.0)
            self.tours.setdefault(nom, 0)
            self.temps.setdefault(nom, 0.0)

    def _elu(self):
        """Le plus endette parmi ceux qui attendent."""
        if not self.attente:
            return None
        return min(sorted(self.attente), key=lambda n: self.dette.get(n, 0.0))

    def tour(self, nom, timeout=120.0, duree_max=None):
        """Bloque jusqu'au tour de `nom`. False si le delai expire."""
        self.inscrire(nom)
        fin = time.time() + timeout
        with self.cv:
            self.attente.add(nom)
            try:
                while True:
                    if self.actif is None and self._elu() == nom:
                        self.actif = nom
                        self.depuis = time.time()
                        self.attente.discard(nom)
                        self.dette[nom] += 1.0 / max(self.poids.get(nom, 1.0), 1e-6)
                        self.tours[nom] += 1
                        return True
                    # Un travail qui depasse sa duree max est considere comme
                    # ayant rendu la main : sinon un blocage le fige pour tous.
                    if (self.actif and duree_max
                            and time.time() - self.depuis > duree_max):
                        self.actif = None
                        self.cv.notify_all()
                        continue
                    restant = fin - time.time()
                    if restant <= 0:
                        self.attente.discard(nom)
                        return False
                    self.cv.wait(min(restant, 0.5))
            except BaseException:
                self.attente.discard(nom)
                raise

    def fin(self, nom):
        with self.cv:
            if self.actif == nom:
                self.temps[nom] = self.temps.get(nom, 0.0) + (time.time() - self.depuis)
                self.actif = None
            self.cv.notify_all()

    @contextmanager
    def creneau(self, nom, timeout=120.0, duree_max=None):
        ok = self.tour(nom, timeout, duree_max)
        try:
            yield ok
        finally:
            if ok:
                self.fin(nom)

    def etat(self):
        with self.cv:
            return {"actif": self.actif, "attente": sorted(self.attente),
                    "tours": dict(self.tours),
                    "temps": {k: round(v, 1) for k, v in self.temps.items()}}


class ArbitreGPU:
    """Baux de VRAM : un seul point de verite sur ce qui est reserve."""

    def __init__(self, sonde_libre_mb, total_mb=4096, reserve_mb=192):
        self.sonde = sonde_libre_mb       # callable -> Mo reellement libres
        self.total_mb = total_mb
        self.reserve_mb = reserve_mb      # marge jamais allouee
        self.baux = {}                    # nom -> Mo
        self.lock = threading.RLock()
        self.refus = {}

    def libre_mb(self):
        """Mo disponibles : mesure reelle MOINS ce que nos baux ont promis.

        Sans cette soustraction, deux pipelines sondant en meme temps voient
        tous deux la memoire libre et s'accordent chacun un bail : c'est le
        scenario de debordement.
        """
        with self.lock:
            promis = sum(self.baux.values())
        try:
            mesure = float(self.sonde() or 0)
        except Exception:                                     # noqa: BLE001
            return 0.0
        return max(0.0, mesure - promis - self.reserve_mb)

    def demander(self, nom, besoin_mb):
        with self.lock:
            if nom in self.baux:
                return True
            if self.libre_mb() >= besoin_mb:
                self.baux[nom] = besoin_mb
                return True
            self.refus[nom] = self.refus.get(nom, 0) + 1
            return False

    def rendre(self, nom):
        with self.lock:
            self.baux.pop(nom, None)

    @contextmanager
    def bail(self, nom, besoin_mb):
        ok = self.demander(nom, besoin_mb)
        try:
            yield ok
        finally:
            if ok:
                self.rendre(nom)

    def etat(self):
        with self.lock:
            return {"baux": dict(self.baux), "libre_mb": round(self.libre_mb()),
                    "refus": dict(self.refus)}
