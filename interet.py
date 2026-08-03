#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Signaux d'« interet » d'une photo — brique PURE du triage des rebuts (point 21).

POURQUOI CE MODULE EST SEPARE (comme renommage.py, fichiers.py)
    Il n'importe NI server.py, NI torch, NI un modele lourd au chargement.
    Il ne fait que de l'arithmetique et de la logique deterministe :
      - heuristique de NOM de fichier (Screenshot_, VideoCapture_, WhatsApp, ...) ;
      - score de FLOU = variance du Laplacien (cv2 en import PARESSEUX) ;
      - ASSEMBLAGE des signaux en une PROPOSITION (jamais un tag dur, jamais une
        suppression automatique) ;
      - METRIQUES d'evaluation (precision/rappel, balayage de seuil, cout des
        faux positifs) — pour mesurer AVANT de batir, discipline vision-eval.

    Consequence : tout ce qui est ici est testable dans un bac a sable sans NAS,
    sans GPU et sans base (voir test_interet.py). Le banc eval_interet.py, lui,
    touche le corpus (echantillon, SigLIP) et importe ce module pour la logique.

INVARIANT DE SECURITE
    Ce module ne SUPPRIME rien et n'ECRIT aucun tag. Il PROPOSE. La suppression
    reste le geste humain, reversible (quarantaine .corbeille-rangement/ via
    FileOps.delete, deja en place). Un faux positif ne doit jamais couter une
    bonne photo : c'est le cout mesure en priorite.
"""
from __future__ import annotations

import re
from pathlib import Path

# ── Categories de rebut (vocabulaire de TRIAGE, distinct du vocab de tagging) ──
# On ne touche PAS vocabulaire_tags.txt : ces libelles servent la MESURE. Leur
# adoption eventuelle dans le vocab de production vient APRES la decision ecrite.
CATEGORIES = ("document", "capture", "facture", "flou", "errone")
GARDER = "garder"          # la classe « bonne photo, ne pas proposer »

# Libelles francais pour le zero-shot SigLIP, par categorie. Plusieurs libelles
# par categorie : on prend le meilleur score de la categorie (max), ce qui donne
# plus de prise qu'un libelle unique. Le gabarit de prompt est applique par le
# banc (semantic.GABARIT = « une photo de {} »).
LIBELLES_SIGLIP = {
    "document": ["un document scanne", "une page de texte", "un document"],
    "capture":  ["une capture d ecran", "une interface de telephone",
                 "une capture d ecran de messagerie"],
    "facture":  ["un recu ou une facture", "un ticket de caisse", "une facture"],
    # « flou » et « errone » ne se lisent pas au zero-shot : ce sont des defauts
    # de RENDU, pas des sujets. Ils viennent du score de flou et du pipeline de
    # recuperation d'images (illisibles.json). SigLIP a tout de meme « photo
    # ratee » dans le vocab existant, utilisable comme signal faible.
    "flou":     ["une photo floue et ratee", "une photo ratee"],
}


# ─────────────────────────── Heuristique de nom ───────────────────────────────
# Signal FORT et GRATUIT : le nom porte souvent l'origine. On matche sur le nom
# de fichier seul (pas le chemin), insensible a la casse. Chaque motif renvoie
# une categorie proposee et le motif reconnu (provenance, pour l'affichage).

_MOTIFS_NOM = [
    # (categorie, regex compilee, etiquette lisible du motif)
    ("capture", re.compile(r"(?:^|[^a-z])screenshot", re.I),        "Screenshot_"),
    ("capture", re.compile(r"screen[\s._-]?shot", re.I),            "screen shot"),
    ("capture", re.compile(r"capture[\s._'-]*d?[\s._'-]*ecran", re.I),"capture d'ecran"),
    ("capture", re.compile(r"\bscr[\s._-]?\d", re.I),               "Scr_"),
    ("capture", re.compile(r"videocapture", re.I),                  "VideoCapture_"),
    ("capture", re.compile(r"\bstory[\s._-]?save", re.I),           "StorySaver"),
    ("capture", re.compile(r"whats?app", re.I),                     "WhatsApp"),
    ("capture", re.compile(r"[\s._-]wa\d{3,}", re.I),               "-WA#### (WhatsApp)"),
    ("capture", re.compile(r"\bfb[\s._-]?img", re.I),               "FB_IMG"),
    ("capture", re.compile(r"\bsnapchat|\bsnap[\s._-]?\d", re.I),   "Snapchat"),
    ("capture", re.compile(r"\bscreen[\s._-]?record", re.I),        "screen record"),
    ("document", re.compile(r"\bscan[\s._-]?\d|\bnumerisation|\bscanned", re.I),
                                                                    "Scan_"),
    ("document", re.compile(r"\bdoc[\s._-]?\d", re.I),              "Doc_"),
    ("facture", re.compile(r"facture|invoice|\brecu\b|receipt|ticket", re.I),
                                                                    "facture/recu"),
]


def indice_nom(nom_ou_chemin) -> tuple[str | None, str | None]:
    """Devine une categorie de rebut d'apres le seul NOM de fichier.

    Renvoie (categorie, motif_lisible) ou (None, None) si rien ne matche.
    Ne lit AUCUN octet du fichier. Deterministe.
    """
    nom = Path(str(nom_ou_chemin)).name
    for cat, rx, motif in _MOTIFS_NOM:
        if rx.search(nom):
            return cat, motif
    return None, None


# Dossiers dont le NOM identifie deja un rebut (capture/scan). Un rebut « pris par
# regle » ne demande aucun detecteur : c'est une regle + une politique (garder ou
# non), pas un probleme de classification.
_DOSSIER_REGLE = re.compile(r'screenshots?|captures?[ _]?d.?ecran|scans?', re.I)


def classer_regle(key) -> tuple[str | None, str | None]:
    """(categorie, motif) si `key` est un rebut attrapable par REGLE — nom de
    fichier OU dossier du chemin (`\\Screenshots\\`, `\\Scans\\`...). Sinon
    (None, None). Les cles du projet sont des chemins Windows : on decoupe avec
    PureWindowsPath pour rester correct meme execute sous Linux (tests)."""
    from pathlib import PureWindowsPath
    cat, motif = indice_nom(key)
    if cat:
        return cat, motif
    for p in PureWindowsPath(str(key)).parts[:-1]:
        if _DOSSIER_REGLE.search(str(p)):
            return ("document" if "scan" in str(p).lower() else "capture",
                    f"dossier {p}")
    return None, None


# ─────────────────────────── Score de flou ────────────────────────────────────
# Variance du Laplacien : mesure classique de nettete (CPU, aucun modele). Une
# image nette a beaucoup de hautes frequences -> forte variance ; une image floue
# les perd -> faible variance. Le SEUIL depend du corpus et se MESURE (ne jamais
# le coder en dur avant la courbe precision/rappel sur les vraies photos).

def variance_laplacien(gris) -> float:
    """Variance du Laplacien d'une image en niveaux de gris (numpy 2D).

    Fonction PURE et testable : accepte un tableau numpy, pas un chemin. cv2 est
    importe paresseusement ; en son absence on retombe sur un Laplacien numpy.
    """
    import numpy as np
    a = np.asarray(gris)
    if a.ndim == 3:                      # au cas ou : moyenne des canaux
        a = a.mean(axis=2)
    a = a.astype("float64")
    try:
        import cv2
        lap = cv2.Laplacian(a, cv2.CV_64F)
    except Exception:                    # noqa: BLE001 — repli pur numpy
        noyau = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype="float64")
        # convolution 2D « valide » via decoupage (petit noyau, corpus modeste)
        from numpy.lib.stride_tricks import sliding_window_view as _swv
        if a.shape[0] < 3 or a.shape[1] < 3:
            return 0.0
        fen = _swv(a, (3, 3))
        lap = (fen * noyau).sum(axis=(-1, -2))
    return float(lap.var())


def score_flou(chemin, max_cote: int = 1024) -> float | None:
    """Variance du Laplacien d'un FICHIER image. None si illisible.

    Reduit l'image a `max_cote` px de cote max avant mesure : la variance depend
    de la resolution, donc on normalise la taille pour que le seuil soit
    comparable d'une photo a l'autre.
    """
    try:
        import cv2
        import numpy as np
        data = np.fromfile(str(chemin), dtype=np.uint8)   # gere les chemins SMB/unicode
        img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        h, w = img.shape[:2]
        cote = max(h, w)
        if cote > max_cote:
            f = max_cote / cote
            img = cv2.resize(img, (max(1, int(w * f)), max(1, int(h * f))),
                             interpolation=cv2.INTER_AREA)
        return variance_laplacien(img)
    except Exception:                    # noqa: BLE001
        return None


# ─────────────────────── Assemblage des signaux ───────────────────────────────
# On combine les signaux en une PROPOSITION. Regle de prudence : le nom et la
# facture/document sont des signaux nets ; le flou est un signal a seuil ; le
# zero-shot SigLIP tranche le reste. Rien n'est un verdict — tout est propose.

def proposer(*, indice_nom_cat=None, siglip_cat=None, siglip_score=None,
             flou=None, seuil_flou=None, seuil_siglip=0.0) -> dict:
    """Assemble une proposition a partir des signaux disponibles.

    Renvoie {rebut: bool, categorie: str|None, motif: str, sources: [...]}.
    Aucun effet de bord. `seuil_*` sont fournis par la MESURE, pas devines ici.
    """
    sources = []
    # 1) Nom de fichier : signal fort.
    if indice_nom_cat:
        sources.append(("nom", indice_nom_cat))
    # 2) Flou : seulement si un seuil mesure est fourni ET franchi.
    est_flou = (flou is not None and seuil_flou is not None and flou < seuil_flou)
    if est_flou:
        sources.append(("flou", "flou"))
    # 3) Zero-shot : seulement si le score depasse le seuil mesure.
    if (siglip_cat in CATEGORIES and siglip_score is not None
            and siglip_score >= seuil_siglip):
        sources.append(("siglip", siglip_cat))

    if not sources:
        return {"rebut": False, "categorie": None, "motif": "", "sources": []}

    # Categorie retenue : priorite au nom, puis facture/document/capture SigLIP,
    # puis flou. (Un ticket photographie net doit sortir « facture », pas « flou ».)
    ordre = {"nom": 0, "siglip": 1, "flou": 2}
    src, cat = sorted(sources, key=lambda s: ordre[s[0]])[0]
    motif = "+".join(f"{s}:{c}" for s, c in sources)
    return {"rebut": True, "categorie": cat, "motif": motif, "sources": sources}


# ─────────────────────────── Metriques d'evaluation ───────────────────────────
# Pures : listes de verites et de predictions -> chiffres. Le CRITERE central du
# point 21 est le COUT DES FAUX POSITIFS : une bonne photo proposee a la
# suppression. On le rapporte explicitement, pas seulement la precision moyenne.

def _pr(vp, fp, fn):
    prec = vp / (vp + fp) if (vp + fp) else 0.0
    rapp = vp / (vp + fn) if (vp + fn) else 0.0
    f1 = 2 * prec * rapp / (prec + rapp) if (prec + rapp) else 0.0
    return prec, rapp, f1


def metriques_binaire(verites, predictions) -> dict:
    """verites/predictions : listes booleennes alignees (True = rebut).

    Renvoie precision, rappel, F1, et le detail vp/fp/fn/vn. `fp` = faux positifs
    = BONNES photos signalees a tort : le chiffre a surveiller.
    """
    if len(verites) != len(predictions):
        raise ValueError("listes de longueurs differentes")
    vp = fp = fn = vn = 0
    for y, p in zip(verites, predictions):
        if p and y:
            vp += 1
        elif p and not y:
            fp += 1
        elif (not p) and y:
            fn += 1
        else:
            vn += 1
    prec, rapp, f1 = _pr(vp, fp, fn)
    return {"precision": prec, "rappel": rapp, "f1": f1,
            "vp": vp, "fp": fp, "fn": fn, "vn": vn, "n": len(verites)}


def balayage_seuil(scores, verites, seuils, *, sens="sup") -> list[dict]:
    """Precision/rappel a chaque seuil pour un score scalaire.

    scores/verites : listes alignees. `sens='sup'` -> predit rebut si
    score >= seuil (cas SigLIP) ; `sens='inf'` -> rebut si score < seuil (cas
    flou : faible variance = flou). Renvoie une ligne par seuil.
    """
    if sens not in ("sup", "inf"):
        raise ValueError("sens doit etre 'sup' ou 'inf'")
    lignes = []
    for s in seuils:
        if sens == "sup":
            preds = [sc is not None and sc >= s for sc in scores]
        else:
            preds = [sc is not None and sc < s for sc in scores]
        m = metriques_binaire(verites, preds)
        m["seuil"] = s
        lignes.append(m)
    return lignes


def meilleur_seuil(balayage, *, fp_max=None) -> dict | None:
    """Choisit le seuil de meilleur F1 parmi ceux dont fp <= fp_max.

    fp_max borne le cout des faux positifs (bonnes photos signalees). Si aucun
    seuil ne respecte la borne, renvoie None : signal a ne PAS activer seul.
    """
    cand = [l for l in balayage if (fp_max is None or l["fp"] <= fp_max)]
    if not cand:
        return None
    return max(cand, key=lambda l: (l["f1"], l["rappel"]))
