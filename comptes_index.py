"""
Comptes de l'index en mémoire — qui retire des clés, et combien.
──────────────────────────────────────────────────────────────────────────────

POURQUOI
    Le 17/08/2026, l'index en mémoire est passé de 43 064 à 42 814 entrées
    pendant les lots de renommage, tandis que `photos.db` restait à 43 064 ;
    au redémarrage, 43 064. Rien n'était perdu, mais la mémoire a été FAUSSE
    pendant un quart d'heure et le mécanisme est resté introuvable — non par
    manque d'hypothèses (trois testées, trois tombées) mais parce que **rien ne
    comptait ce que le scan oublie**. `forget_everywhere()` renvoyait un nombre
    que personne n'enregistrait ; l'étape 4 de `_sync_dir` ne disait pas combien
    de clés elle retirait.

    Un travail de fond qui ne rend pas de comptes finit par ne plus travailler
    du tout. Ce module est le carnet de comptes.

CE QU'IL FAIT
    1. **Il compte au goulot, pas aux appelants.** Dans `store_sqlite.py`,
       TOUTE clé qui entre ou sort de l'index en mémoire passe par
       `TrackedDict` (`__setitem__`, `__delitem__`, `pop`, `popitem`, `clear`).
       Le registre s'y branche : aucun retrait ne peut lui échapper.
    2. **Il demande un MOTIF à l'appelant** (`with registre.motif('scan:disparus')`).
       Un retrait sans motif tombe dans le bucket « (non déclaré) » — et c'est
       ce bucket, pas les autres, qui est intéressant.
    3. **Il RÉCONCILIE chaque cycle de scan** :

           inexpliqué = (taille_fin − taille_début) − (ajouts − retraits)

       Zéro signifie que la variation de taille de l'index s'explique
       entièrement par des mutations passées par le goulot. Non nul signifie
       que l'index a changé de taille par un chemin que personne ne déclare —
       exactement le diagnostic qui manquait aux −250. Le nombre lui-même est
       la piste : il dit COMBIEN d'entrées se sont évaporées hors du goulot.

CE QU'IL NE FAIT PAS
    Il ne corrige rien, ne supprime rien, ne bloque rien. Il n'a pas d'opinion
    sur ce qui est légitime : « scan:disparus » qui retire 4 000 clés est normal
    au premier scan d'un dossier vidé. Il rend seulement les comptes lisibles
    pour que la PROCHAINE occurrence soit tranchable.

CONTRAINTES
    Module PUR : stdlib seule (`threading`, `time`), aucun import lourd, aucune
    E/S, aucun état global. Testable hors serveur (`test_comptes_index.py`).
    Coût : un `Lock` et quelques incréments par clé — négligé devant l'écriture
    SQLite qui suit. Toutes les listes exposées sont BORNÉES (le résumé part
    dans `/api/maint/status`, il ne doit pas grossir sans fin).
"""

import threading
import time

# Bucket des retraits dont personne n'a déclaré la raison. Sans accent : ce
# libellé voyage en JSON et s'affiche tel quel.
MOTIF_NON_DECLARE = "(non declare)"


class _Contexte:
    """Gestionnaire de contexte renvoyé par `RegistreOublis.motif()`."""

    __slots__ = ('_reg', 'motif', 'label', 'ajouts', 'retraits', 'exemples', 'at')

    def __init__(self, registre, motif, label=''):
        self._reg = registre
        self.motif = str(motif)
        self.label = str(label or '')
        self.ajouts = 0
        self.retraits = 0
        self.exemples = []
        self.at = 0.0

    def __enter__(self):
        self.at = time.time()
        self._reg._empiler(self)
        return self

    def __exit__(self, *exc):
        self._reg._depiler(self)
        return False


class RegistreOublis:
    """Carnet de comptes des ajouts/retraits de clés de l'index en mémoire.

    Thread-safe. Aucune méthode ne lève : un instrument qui casse le programme
    qu'il observe est pire que pas d'instrument.
    """

    actif = True        # cf. `_RegistreInerte` côté serveur (repli JSON)

    def __init__(self, max_evenements=25, max_exemples=3, max_non_declares=20,
                 max_cycles=10):
        self._lock = threading.Lock()
        self._tl = threading.local()
        self.max_evenements = int(max_evenements)
        self.max_exemples = int(max_exemples)
        self.max_non_declares = int(max_non_declares)
        self.max_cycles = int(max_cycles)

        self.ajouts = 0                 # cumul depuis le démarrage
        self.retraits = 0
        self.par_motif = {}             # motif -> {'ajouts': n, 'retraits': n}
        self.evenements = []            # blocs clos, plus récent en tête
        self.non_declares = []          # exemples de retraits sans motif
        self.cycles = []                # réconciliations, plus récente en tête
        self.anomalies = []             # cycles à écart non nul
        self.inexplique_cumul = 0       # somme SIGNÉE des écarts
        self.cycles_inexpliques = 0
        self._cycle = None

    # ─────────────────────────── motifs ───────────────────────────

    def motif(self, motif, label=''):
        """`with registre.motif('scan:disparus', label='D:/Photos'):` — tout
        retrait effectué dans le bloc (par ce thread) est attribué à ce motif."""
        return _Contexte(self, motif, label)

    def motif_du_thread(self, motif, label=''):
        """Motif PERMANENT du thread courant — pour un worker dédié (tagging,
        visages…) dont toute l'activité relève du même motif.

        Empilé une fois, jamais dépilé : ce bloc ne produit donc AUCUN
        événement (il ne se clôt jamais), seulement des compteurs. Un
        `with registre.motif(...)` ouvert par-dessus l'emporte, comme toute
        imbrication. Idempotent : deux appels dans le même thread ne créent
        qu'un bloc.
        """
        p = self._pile()
        if p and p[0].motif == str(motif):
            return p[0]
        bloc = _Contexte(self, motif, label)
        bloc.at = time.time()
        p.insert(0, bloc)
        return bloc

    def _pile(self):
        p = getattr(self._tl, 'pile', None)
        if p is None:
            p = []
            self._tl.pile = p
        return p

    def _empiler(self, bloc):
        self._pile().append(bloc)

    def _depiler(self, bloc):
        p = self._pile()
        # Retrait tolérant : un `with` mal imbriqué ne doit pas faire dérailler
        # le programme observé.
        if bloc in p:
            p.remove(bloc)
        if not (bloc.ajouts or bloc.retraits):
            return
        maintenant = time.time()
        with self._lock:
            # COALESCENCE. Un lot de renommage ouvre un bloc `rekey` PAR
            # FICHIER : 200 fichiers chassaient les 25 derniers evenements de
            # l'anneau, effacant precisement les traces (scan, purges) qu'on
            # voulait lire. On fusionne donc les blocs CONSECUTIFS de meme
            # motif et meme libelle, en gardant le compte d'operations (`n`) :
            # « rekey x200 » dit plus que 25 lignes identiques, et laisse la
            # place aux autres motifs.
            tete = self.evenements[0] if self.evenements else None
            if tete is not None and tete['motif'] == bloc.motif \
                    and tete['label'] == bloc.label:
                tete['n'] += 1
                tete['ajouts'] += bloc.ajouts
                tete['retraits'] += bloc.retraits
                tete['at'] = maintenant
                for x in bloc.exemples:
                    if len(tete['exemples']) < self.max_exemples:
                        tete['exemples'].append(x)
                return
            self.evenements.insert(0, {
                'at': maintenant, 'n': 1,
                'duree_s': round(max(0.0, maintenant - (bloc.at or maintenant)), 1),
                'motif': bloc.motif, 'label': bloc.label,
                'ajouts': bloc.ajouts, 'retraits': bloc.retraits,
                'exemples': list(bloc.exemples)})
            del self.evenements[self.max_evenements:]

    # ──────────────────── notifications du store ────────────────────

    def cle_ajoutee(self, cle):
        """Une clé ABSENTE vient d'entrer dans l'index en mémoire."""
        pile = self._pile()
        with self._lock:
            self.ajouts += 1
            m = pile[-1].motif if pile else MOTIF_NON_DECLARE
            self.par_motif.setdefault(m, {'ajouts': 0, 'retraits': 0})['ajouts'] += 1
        for b in pile:
            b.ajouts += 1

    def cle_retiree(self, cle):
        """Une clé PRÉSENTE vient de sortir de l'index en mémoire."""
        pile = self._pile()
        with self._lock:
            self.retraits += 1
            m = pile[-1].motif if pile else MOTIF_NON_DECLARE
            self.par_motif.setdefault(m, {'ajouts': 0, 'retraits': 0})['retraits'] += 1
            if not pile and len(self.non_declares) < self.max_non_declares:
                self.non_declares.append({'at': time.time(),
                                          'cle': str(cle)[:160]})
        for b in pile:
            b.retraits += 1
            if len(b.exemples) < self.max_exemples:
                b.exemples.append(str(cle)[:160])

    def cles_retirees(self, cles):
        """Repli pour les chemins qui court-circuitent le goulot (ex. le
        remplacement global `store.data = {}`, qui vide le dict par en dessous).
        À déclarer explicitement, sinon la réconciliation les compte comme
        inexpliquées — ce qui serait un faux positif."""
        for k in cles:
            self.cle_retiree(k)

    # ────────────────────── réconciliation ──────────────────────

    def debut_cycle(self, taille_index):
        """À appeler juste AVANT un cycle de scan, avec `len(STORE.data)`."""
        with self._lock:
            self._cycle = {'debut': int(taille_index), 'at': time.time(),
                           'a0': self.ajouts, 'r0': self.retraits}

    def fin_cycle(self, taille_index):
        """À appeler juste APRÈS, avec `len(STORE.data)`. Renvoie la
        réconciliation, ou None si aucun cycle n'était ouvert.

        `inexplique` non nul = l'index a changé de taille par un chemin qui ne
        passe pas par le goulot. C'est le signal ; le reste est du contexte.
        """
        with self._lock:
            c = self._cycle
            self._cycle = None
            if c is None:
                return None
            a = self.ajouts - c['a0']
            r = self.retraits - c['r0']
            fin = int(taille_index)
            attendu = c['debut'] + a - r
            res = {'at': c['at'],
                   'duree_s': round(max(0.0, time.time() - c['at']), 1),
                   'debut': c['debut'], 'fin': fin,
                   'ajouts': a, 'retraits': r,
                   'attendu': attendu, 'inexplique': fin - attendu}
            self.cycles.insert(0, res)
            del self.cycles[self.max_cycles:]
            if res['inexplique']:
                self.inexplique_cumul += res['inexplique']
                self.cycles_inexpliques += 1
                self.anomalies.insert(0, res)
                del self.anomalies[self.max_cycles:]
            return res

    # ───────────────────────── lecture ─────────────────────────

    def resume(self):
        """Vue JSON-able et BORNÉE, pour `/api/maint/status`."""
        with self._lock:
            return {
                'actif': True,
                'ajouts': self.ajouts,
                # Le COMPTE vient de `par_motif` (exact) ; `non_declares` n'est
                # qu'une liste d'EXEMPLES, bornee. Les confondre affichait « 20 »
                # la ou 250 cles etaient parties -- l'instrument aurait
                # sous-declare le chiffre meme pour lequel il existe.
                'retraits': self.retraits,
                'par_motif': {m: dict(v) for m, v in sorted(self.par_motif.items())},
                'non_declares':
                    self.par_motif.get(MOTIF_NON_DECLARE, {}).get('retraits', 0),
                'non_declares_exemples': list(self.non_declares),
                'evenements': list(self.evenements),
                'cycles': list(self.cycles),
                'anomalies': list(self.anomalies),
                'inexplique_cumul': self.inexplique_cumul,
                'cycles_inexpliques': self.cycles_inexpliques,
                'cycles_vus': len(self.cycles),
            }

    def ligne_cycle(self, res):
        """Une ligne lisible pour le résumé de scan. `res` = retour de
        `fin_cycle()`. Renvoie '' si le cycle n'a rien à dire (index stable et
        aucun écart) : un instrument bavard finit ignoré."""
        if not res:
            return ''
        if not res['ajouts'] and not res['retraits'] and not res['inexplique']:
            return ''
        s = (f"index {res['debut']} -> {res['fin']} "
             f"(+{res['ajouts']} / -{res['retraits']})")
        if res['inexplique']:
            s += (f"  ⚠ ECART INEXPLIQUE {res['inexplique']:+d} "
                  f"— {abs(res['inexplique'])} entree(s) hors du goulot")
        return s

    def ligne_motifs(self):
        """Une ligne récapitulant les retraits par motif depuis le démarrage."""
        with self._lock:
            parts = [f"{m} {v['retraits']}"
                     for m, v in sorted(self.par_motif.items())
                     if v['retraits']]
        return ', '.join(parts)
