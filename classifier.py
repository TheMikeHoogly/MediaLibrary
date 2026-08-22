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

LA CORRECTION RETENUE — PROTOTYPES MULTIPLES
    Les references sont regroupees en k paquets (k-moyennes, k choisi selon
    leur nombre) et l'on garde un vecteur par paquet. Le score devient le
    MAXIMUM sur les prototypes : « ressemble a l'une des facettes connues »
    plutot que « ressemble a la moyenne ». C'est ce que `server.py` importe,
    et la seule chose que ce module expose.

CE QUI A ETE REJETE, ET QUI N'EST PLUS ICI — LES CONTRE-EXEMPLES
    Une seconde correction avait ete ecrite : exiger d'un candidat qu'il soit
    plus proche d'un prototype positif que de tout contre-exemple humain
    (classes `Modele` / `Banque`, constante `MARGE_NEGATIVE`). Elle a ete
    REJETEE les 30-31/07 et n'a jamais eu d'appelant. Elle est restee 22 jours
    dans le fichier avec un en-tete qui la presentait comme acquise —
    c'est-a-dire une documentation qui decrivait un comportement que le
    logiciel n'avait pas (audit interne I4). Retiree le 22/08 : le code vit
    dans git, ou il se relit tel qu'il etait le jour du rejet.

Le module ne depend que de numpy et sert INDIFFEREMMENT aux personnes et aux
animaux : c'est le meme probleme.
"""

MAX_PROTOTYPES = 4       # au-dela, on decoupe un nuage qui n'a plus de sens
MIN_PAR_PROTOTYPE = 12   # references minimales pour justifier un prototype


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
