"""
Modele de reconnaissance : prototypes multiples + contre-exemples.
──────────────────────────────────────────────────────────────────────────────

CE QUI NE VA PAS AVEC UN CENTROIDE UNIQUE
    Une personne photographiee sur vingt ans — enfant puis adulte, de face puis
    de profil, avec et sans lunettes — n'est PAS un point dans l'espace des
    empreintes. C'est un nuage, souvent en plusieurs paquets. En faire la
    moyenne produit un vecteur qui ne ressemble a aucune des photos reelles :
    il tombe entre les modes, et se rapproche mecaniquement des autres fiches.

    Mesure sur le corpus : Florine et Flo obtiennent des scores separes de
    0,03 sur les memes visages. Ce n'est pas un probleme de seuil, c'est un
    probleme de MODELE.

DEUX CORRECTIONS
    1. PROTOTYPES MULTIPLES — les references sont regroupees en k paquets
       (k-moyennes, k choisi selon leur nombre) et l'on garde un vecteur par
       paquet. Le score devient le MAXIMUM sur les prototypes : « ressemble a
       l'une des facettes connues » plutot que « ressemble a la moyenne ».

    2. CONTRE-EXEMPLES — les exclusions posees a la main (« non, ce n'est pas
       Florine ») ne servaient qu'a ne plus reproposer la photo. Elles portent
       pourtant l'information la plus precieuse du corpus : ce que cette
       personne N'EST PAS. On exige desormais qu'un candidat soit plus proche
       d'un prototype positif que de tout contre-exemple.

Le module ne depend que de numpy et sert INDIFFEREMMENT aux personnes et aux
animaux : c'est le meme probleme.
"""

MAX_PROTOTYPES = 4       # au-dela, on decoupe un nuage qui n'a plus de sens
MIN_PAR_PROTOTYPE = 12   # references minimales pour justifier un prototype
MARGE_NEGATIVE = 0.02    # avance requise du meilleur positif sur le negatif


def _kmoyennes(X, k, iterations=12, graine=0):
    """k-moyennes spherique (cosinus) — court, deterministe, sans dependance."""
    import numpy as np
    n = X.shape[0]
    if k <= 1 or n <= k:
        return None
    rng = np.random.default_rng(graine)
    # k-means++ : premier centre au hasard, suivants loin des precedents
    centres = [X[rng.integers(n)]]
    for _ in range(k - 1):
        d = 1.0 - np.max(X @ np.stack(centres).T, axis=1)
        d = np.maximum(d, 0)
        if d.sum() <= 0:
            centres.append(X[rng.integers(n)])
        else:
            centres.append(X[int(rng.choice(n, p=d / d.sum()))])
    C = np.stack(centres)
    for _ in range(iterations):
        appart = np.argmax(X @ C.T, axis=1)
        neuf = []
        for j in range(k):
            membres = X[appart == j]
            if len(membres) == 0:
                neuf.append(C[j])
                continue
            c = membres.mean(axis=0)
            nrm = np.linalg.norm(c)
            neuf.append(c / nrm if nrm else C[j])
        neufC = np.stack(neuf)
        if np.allclose(neufC, C, atol=1e-5):
            C = neufC
            break
        C = neufC
    return C, np.argmax(X @ C.T, axis=1)


def prototypes(vecteurs, max_proto=None, min_par=None):
    """Liste de prototypes normalises representant un nuage de references.

    Les valeurs par defaut sont lues A L'APPEL, pas a la definition : sinon
    modifier MAX_PROTOTYPES n'a aucun effet et un banc d'essai qui balaie ce
    parametre mesure quatre fois la meme chose.
    """
    import numpy as np
    if max_proto is None:
        max_proto = MAX_PROTOTYPES
    if min_par is None:
        min_par = MIN_PAR_PROTOTYPE
    if not len(vecteurs):
        return None
    X = np.stack([v for v in vecteurs]).astype(np.float32)
    n = np.linalg.norm(X, axis=1, keepdims=True)
    n[n == 0] = 1.0
    X = X / n
    k = min(max_proto, max(1, X.shape[0] // min_par))
    if k <= 1:
        c = X.mean(axis=0)
        nrm = np.linalg.norm(c)
        return (c / nrm if nrm else c).reshape(1, -1)
    res = _kmoyennes(X, k)
    if res is None:
        c = X.mean(axis=0)
        nrm = np.linalg.norm(c)
        return (c / nrm if nrm else c).reshape(1, -1)
    C, appart = res
    # On abandonne les prototypes trop maigres : un paquet de 2 references
    # decrit du bruit, pas une facette.
    garde = [j for j in range(C.shape[0])
             if int((appart == j).sum()) >= max(3, min_par // 3)]
    if not garde:
        return C
    return C[garde]


class Modele:
    """Un sujet (personne ou animal) : ses facettes et ses contre-exemples."""

    __slots__ = ('nom', 'P', 'N')

    def __init__(self, nom, positifs, negatifs=None):
        self.nom = nom
        self.P = prototypes(positifs) if len(positifs) else None
        self.N = None
        if negatifs is not None and len(negatifs):
            import numpy as np
            X = np.stack(negatifs).astype(np.float32)
            nn = np.linalg.norm(X, axis=1, keepdims=True)
            nn[nn == 0] = 1.0
            self.N = X / nn

    def valide(self):
        return self.P is not None and self.P.shape[0] > 0

    def score(self, v):
        """(meilleur score positif, meilleur score negatif)."""
        import numpy as np
        pos = float(np.max(self.P @ v))
        neg = float(np.max(self.N @ v)) if self.N is not None else -1.0
        return pos, neg


class Banque:
    """Ensemble de modeles : classe un vecteur parmi tous les sujets connus."""

    def __init__(self, modeles):
        self.modeles = [m for m in modeles if m.valide()]

    def classer(self, v, marge_negative=MARGE_NEGATIVE):
        """[(nom, score)] decroissant, contre-exemples deja appliques."""
        import numpy as np
        v = np.asarray(v, dtype=np.float32).ravel()
        nrm = np.linalg.norm(v)
        if nrm:
            v = v / nrm
        out = []
        for m in self.modeles:
            if m.P.shape[1] != v.shape[0]:
                continue
            pos, neg = m.score(v)
            # Un contre-exemple plus proche que la meilleure facette connue
            # DISQUALIFIE le sujet : c'est un « non » humain, il prime.
            if neg > pos - marge_negative:
                continue
            out.append((m.nom, pos))
        out.sort(key=lambda t: -t[1])
        return out

    def meilleur(self, v, **kw):
        r = self.classer(v, **kw)
        if not r:
            return None, -1.0, -1.0
        second = r[1][1] if len(r) > 1 else -1.0
        return r[0][0], r[0][1], r[0][1] - second
