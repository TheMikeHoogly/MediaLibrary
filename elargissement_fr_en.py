#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Élargir une requête FRANÇAISE vers l'ANGLAIS par les co-occurrences du tagueur
──────────────────────────────────────────────────────────────────────────────

POURQUOI (ROADMAP 1 nonies, mesuré dans la nuit du 29 au 30/08,
`mesure_requete_fr_en.py`) : SigLIP 2 a surtout lu de l'anglais. Sur 40
concepts, la requête française rappelle 0,583 (rappel@200), l'anglaise 0,683,
et la MOYENNE des deux vecteurs 0,663 — l'anglais bat le français sur 33
paires, fr+en bat fr sur 35. **Mike a tranché (30/08) : élargir FR→EN.**

D'OÙ VIENT LA TRADUCTION : de personne. Le tagueur écrit pour chaque photo
des mots-clés en français ET en anglais (`kw_fr`, `kw_en`) ; « ours en
peluche » et « teddy bear » se trouvent sur les mêmes photos. Un tag français
se traduit par le tag anglais qui l'accompagne le plus souvent, quand cette
compagnie est serrée (la paire couvre au moins la moitié des occurrences du
plus rare des deux) — la même règle que le banc, pour que la mesure et la
production disent la même chose.

DEUX NIVEAUX : la phrase entière d'abord (« ours en peluche » → « teddy
bear »), sinon mot à mot (« chat sur un canapé » → « cat sur un sofa » : les
mots inconnus restent, l'encodeur tolère le mélange). Rien de traduit → None,
et l'appelant encode la requête seule, comme avant.

Module PUR : ni store, ni base, ni modèle. Le serveur construit le
dictionnaire au démarrage sur l'index (secondes) ; le banc, sur une copie.
"""
import re
from collections import Counter, defaultdict

PREFIXES_NOMS = ('personne:', 'animal:', 'espece:')
MOT_RE = re.compile(r"[0-9a-zà-ÿ][0-9a-zà-ÿ'’-]*", re.I)
# Mots-outils : jamais traduits, jamais appris (ils ne portent pas de sens visuel).
OUTILS = frozenset('''le la les un une des du de d l au aux et ou en sur sous dans
avec sans pour par chez vers entre qui que quoi ce cet cette ces son sa ses mon ma
mes ton ta tes leur leurs a à y il elle ils elles on nous vous je tu est sont'''.split())


def _norm(t):
    return re.sub(r'\s+', ' ', str(t).strip().lower())


class Dictionnaire:
    """fr → en appris par co-occurrence. `serrage` : part minimale des
    occurrences du plus rare des deux tags que la paire doit couvrir."""

    def __init__(self, entrees=(), serrage=0.5, minimum=3):
        self.serrage, self.minimum = serrage, minimum
        self.fr_en = {}
        self.n_photos = 0
        if entrees:
            self.apprendre(entrees)

    def apprendre(self, entrees):
        """Co-occurrence par photo. Pour un tag francais `f`, on retient le
        tag anglais `g` qui maximise le DICE co(f,g)^2 / (n(f) * n(g)) — pas le
        plus frequent : « plage » voisine 123 fois « beach » (sur 141) mais
        aussi 75 fois « ocean », et « ocean » est 8 fois plus frequent que
        « beach » ; le Dice prefere le compagnon fidele au compagnon
        omnipresent. Et la paire doit COUVRIR au moins `serrage` des
        occurrences de `f` (la moitie) — sinon on n'apprend rien. Pas de
        reciprocite exigee : « beach » (949) a pour meilleur francais
        « piscine », ce qui n'empeche pas « plage » de se dire « beach ». A
        Dice egal, le tag de MEME RANG dans les deux listes l'emporte (le
        tagueur ecrit ses listes en parallele)."""
        co = defaultdict(Counter)
        pos = defaultdict(Counter)          # meme rang dans les deux listes
        nfr, nen = Counter(), Counter()
        vals = entrees.values() if isinstance(entrees, dict) else entrees
        for e in vals:
            if not isinstance(e, dict) or e.get('failed'):
                continue
            fr = list(dict.fromkeys(_norm(t) for t in (e.get('kw_fr') or [])
                                    if isinstance(t, str) and ':' not in t))
            en = list(dict.fromkeys(_norm(t) for t in (e.get('kw_en') or [])
                                    if isinstance(t, str) and ':' not in t))
            if not fr or not en:
                continue
            self.n_photos += 1
            for i, f in enumerate(fr):
                nfr[f] += 1
                for j, g in enumerate(en):
                    co[f][g] += 1
                    if i == j:
                        pos[f][g] += 1
            for g in en:
                nen[g] += 1
        fr_en = {}
        for f, c in co.items():
            if nfr[f] < self.minimum or f in OUTILS:
                continue
            # Un mot deja aussi frequent en anglais (« table », « orange »)
            # est bilingue : l'elargir n'apporterait rien.
            if nen.get(f, 0) >= self.serrage * nfr[f]:
                continue
            meilleur, score = None, (0.0, 0)
            for g, cg in c.items():
                if g == f or cg < self.serrage * nfr[f]:
                    continue
                d = ((cg * cg) / float(nfr[f] * nen[g]), pos[f][g])
                if d > score:
                    meilleur, score = g, d
            if meilleur is not None:
                fr_en[f] = meilleur
        self.fr_en = fr_en
        return self

    def __len__(self):
        return len(self.fr_en)

    def traduire(self, texte):
        """La forme anglaise de `texte`, ou None si rien n'est connu.
        Phrase entière d'abord, sinon mot à mot (les inconnus restent)."""
        t = _norm(texte)
        if not t:
            return None
        if t in self.fr_en:
            return self.fr_en[t]
        mots = MOT_RE.findall(t)
        if not mots:
            return None
        out, n = [], 0
        for m in mots:
            if m in OUTILS:
                out.append(m)
                continue
            g = self.fr_en.get(m)
            if g is None:
                out.append(m)
            else:
                out.append(g)
                n += 1
        if not n:
            return None
        en = ' '.join(out)
        return None if en == t else en


def formes(dico, texte):
    """Les textes à encoder pour une requête : [fr] ou [fr, en]. L'appelant
    moyenne les vecteurs (comme le banc : `fr+en`)."""
    en = dico.traduire(texte) if dico is not None else None
    return [texte] if not en else [texte, en]
