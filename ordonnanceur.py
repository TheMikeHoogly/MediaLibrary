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
    """Baux de VRAM avec priorites et eviction : un seul point de verite.

    Un bail couvre la RESIDENCE d'un modele sur le GPU, pas une inference :
    c'est la residence qui consomme la VRAM. Cycle de vie :

        demander(nom, mb)   -> bail promis (soustrait de la mesure)
        <monter le modele>
        confirmer(nom)      -> la sonde voit desormais l'usage reel ; on
                               cesse de soustraire (sinon compte double)
        <... le modele vit sur le GPU ...>
        rendre(nom)         -> le modele est redescendu (ou dechu)

    Priorites : une demande refusee EVINCE les baux strictement moins
    prioritaires (leur `liberer()` descend le modele sur CPU et renvoie
    True ; False = inference en vol, on ne l'interrompt jamais).

    `menage()` est le garde-fou du pire echec (debordement silencieux en
    RAM, vitesse divisee par 3 sans erreur) : si la VRAM reellement libre
    passe sous un plancher — typiquement Ollama qui vient de monter — on
    evince le bail materialise le moins prioritaire.
    """

    def __init__(self, sonde_libre_mb, total_mb=4096, reserve_mb=192,
                 sonde_fraiche=None):
        self.sonde = sonde_libre_mb       # callable -> Mo reellement libres
        self.sonde_f = sonde_fraiche or sonde_libre_mb   # variante sans cache
        self.total_mb = total_mb
        self.reserve_mb = reserve_mb      # marge jamais allouee
        self.baux = {}                    # nom -> {"mb": x, "materialise": bool}
        self.prios = {}                   # nom -> int (plus grand = prioritaire)
        self.liberateurs = {}             # nom -> callable() -> bool
        self.lock = threading.RLock()
        self.refus = {}
        self.evictions = {}

    def enregistrer(self, nom, prio=None, liberer=None):
        """Declare la priorite et/ou le liberateur d'un pipeline. Idempotent ;
        un argument None laisse la valeur existante intacte."""
        with self.lock:
            if prio is not None:
                self.prios[nom] = prio
            if liberer is not None:
                self.liberateurs[nom] = liberer

    def _libre_mb(self, frais=False):
        """Mo disponibles : mesure reelle MOINS les baux promis non encore
        materialises (un bail materialise est deja visible dans la mesure —
        le soustraire encore le compterait deux fois).

        Sans cette soustraction, deux pipelines sondant en meme temps voient
        tous deux la memoire libre et s'accordent chacun un bail : c'est le
        scenario de debordement.
        """
        with self.lock:
            promis = sum(b["mb"] for b in self.baux.values()
                         if not b["materialise"])
        try:
            mesure = float((self.sonde_f if frais else self.sonde)() or 0)
        except Exception:                                     # noqa: BLE001
            return 0.0
        return max(0.0, mesure - promis - self.reserve_mb)

    def libre_mb(self):
        return self._libre_mb()

    def demander(self, nom, besoin_mb):
        with self.lock:
            if nom in self.baux:
                return True
            if self._libre_mb() >= besoin_mb:
                self.baux[nom] = {"mb": besoin_mb, "materialise": False}
                return True
            # Eviction : baux strictement moins prioritaires, en commencant
            # par le moins prioritaire. La sonde fraiche est necessaire apres
            # une descente CPU (la mesure en cache ne la voit pas encore).
            ma_prio = self.prios.get(nom, 0)
            victimes = sorted(
                [v for v in self.baux
                 if self.prios.get(v, 0) < ma_prio and v in self.liberateurs],
                key=lambda v: self.prios.get(v, 0))
            for v in victimes:
                try:
                    if not self.liberateurs[v]():
                        continue          # en vol : on n'interrompt pas
                except Exception:                             # noqa: BLE001
                    continue
                self.baux.pop(v, None)
                self.evictions[v] = self.evictions.get(v, 0) + 1
                if self._libre_mb(frais=True) >= besoin_mb:
                    self.baux[nom] = {"mb": besoin_mb, "materialise": False}
                    return True
            self.refus[nom] = self.refus.get(nom, 0) + 1
            return False

    def confirmer(self, nom):
        """A appeler une fois le modele monte : son usage est desormais dans
        la mesure de la sonde, on cesse de le soustraire. La sonde FRAICHE est
        rafraichie d'abord — sinon, pendant la duree du cache (~8 s), la
        mesure perimee d'avant montage + bail non soustrait = fenetre de
        double allocation, precisement le debordement qu'on veut empecher."""
        with self.lock:
            if nom not in self.baux or self.baux[nom]["materialise"]:
                return                  # deja materialise : ne pas re-sonder
            try:
                self.sonde_f()          # un nvidia-smi par montage : negligeable
            except Exception:                                 # noqa: BLE001
                pass
            self.baux[nom]["materialise"] = True

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

    def menage(self, plancher_mb=256, sauf=None):
        """Evince le bail materialise le moins prioritaire si la VRAM
        reellement libre est sous le plancher (voir docstring de classe).
        `sauf` : bail de l'appelant, jamais choisi comme victime (son propre
        verrou pipeline est tenu — un try-lock echouerait et l'eviction
        glisserait vers un bail PLUS prioritaire, inversion indesirable).
        Pre-filtre sur la mesure en cache (menage est appele a chaque photo),
        confirmation sur mesure fraiche avant d'agir — sinon une pression
        transitoire evince tous les baux en cascade pendant les ~8 s du cache."""
        with self.lock:
            try:
                mesure = float(self.sonde() or 0)
            except Exception:                                 # noqa: BLE001
                return
            if mesure >= plancher_mb:
                return
            try:
                mesure = float(self.sonde_f() or 0)
            except Exception:                                 # noqa: BLE001
                return
            if mesure >= plancher_mb:
                return
            victimes = sorted(
                [v for v, b in self.baux.items()
                 if b["materialise"] and v in self.liberateurs and v != sauf],
                key=lambda v: self.prios.get(v, 0))
            for v in victimes:
                try:
                    if self.liberateurs[v]():
                        self.baux.pop(v, None)
                        self.evictions[v] = self.evictions.get(v, 0) + 1
                        return
                except Exception:                             # noqa: BLE001
                    continue

    def etat(self):
        with self.lock:
            return {"baux": {n: dict(b) for n, b in self.baux.items()},
                    "prios": dict(self.prios),
                    "libre_mb": round(self._libre_mb()),
                    "refus": dict(self.refus),
                    "evictions": dict(self.evictions)}
