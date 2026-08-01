#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nettoyage semantique de lieux.txt — ne garder que de VRAIS lieux.

PROBLEME. `lieux.txt` est auto-genere par server.lieux_connus() a partir des NOMS
DE DOSSIERS, via une heuristique (`_lieu_plausible`) qui retire chiffres/dates et
un peu de bruit. Sur un fonds reel, l'heuristique laisse passer quantite de NON-
lieux : evenements (Mariage, EVJF, Soiree), activites (Jujitsu, Plongee), marques
(NIKON, Nokia), fetes (Noel, Navidad, Weihnacht), et des NOMS DE PERSONNES
(Tagliani, Charlie, Yani...). Consequence : « _Uploads » etait pris pour un lieu,
et la recherche par lieu est polluee.

PRINCIPE. Distinguer « Riberalta » (vraie ville de Bolivie) de « Tagliani »
(patronyme) demande un SAVOIR geographique, pas une regle. On valide donc par une
LISTE BLANCHE (gazetteer) : seuls les jetons/expressions reconnus comme lieux sont
gardes ; tout le reste est rejete. Les entrees multi-mots sont DECOMPOSEES et on
n'en garde que le(s) lieu(x) (« Appart Bremblens » -> « Bremblens » ; « CoRo
Manifestation Birmanie Geneve » -> « Birmanie », « Geneve »).

Le gazetteer couvre les lieux presents dans CE corpus (Bolivie, Perou, Suisse
romande, France, voyages) plus quelques pays/regions evidents. Pour les candidats
INCONNUS (nouveaux dossiers), l'option --ollama demande au LLM local de trancher,
et les lieux confirmes peuvent etre ajoutes au gazetteer.

REVERSIBLE. L'ancien fichier est sauve en lieux.txt.bak, et les entrees rejetees
sont conservees EN COMMENTAIRE en bas du nouveau fichier : rien n'est perdu, tout
est relisable et re-activable a la main.

Usage :
    python nettoyer_lieux.py               # apercu (dry-run), n'ecrit rien
    python nettoyer_lieux.py --ecrire      # applique (backup + reecriture)
    python nettoyer_lieux.py --ollama[=modele] --ecrire   # valide les inconnus au LLM
"""

import re
import sys
import unicodedata
from pathlib import Path

FICHIER = Path(__file__).resolve().parent / "lieux.txt"

# ── Gazetteer : liste blanche des lieux (forme normalisee -> libelle affiche) ──
# Jetons SIMPLES.
PLACE_TOKENS = {
    # Suisse romande / Alpes
    'bremblens': 'Bremblens', 'lausanne': 'Lausanne', 'geneve': 'Genève',
    'verbier': 'Verbier', 'sanetsch': 'Sanetsch', 'plannaz': 'Plannaz',
    'suisse': 'Suisse', 'suiza': 'Suiza', 'valais': 'Valais', 'vaud': 'Vaud',
    # France
    'france': 'France', 'luzarches': 'Luzarches', 'paris': 'Paris',
    # Bolivie / Perou (voyages)
    'bolivie': 'Bolivie', 'bolivia': 'Bolivie', 'achumani': 'Achumani',
    'irpavi': 'Irpavi', 'riberalta': 'Riberalta', 'rurre': 'Rurre',
    'copacabana': 'Copacabana', 'cuzco': 'Cuzco', 'cusco': 'Cuzco',
    'yucay': 'Yucay', 'trinidad': 'Trinidad', 'perou': 'Pérou', 'peru': 'Pérou',
    # Autres pays / regions du corpus
    'belgique': 'Belgique', 'birmanie': 'Birmanie', 'myanmar': 'Birmanie',
    'danemark': 'Danemark', 'indonesie': 'Indonésie', 'bali': 'Bali',
    'seychelles': 'Seychelles',
}

# Jetons AMBIGUS ou abreviations qu'on mappe explicitement (savoir local).
ALIASES = {
    'trini': 'Trinidad',      # Trinidad (Beni, Bolivie)
    'srz': 'Santa Cruz',      # Santa Cruz de la Sierra
}

# EXPRESSIONS multi-jetons (verifiees comme sous-sequence consecutive).
PLACE_PHRASES = {
    ('san', 'borja'): 'San Borja',
    ('santa', 'cruz'): 'Santa Cruz',
    ('chateau', 'd', 'oex'): "Château-d'Œx",
    ('vallee', 'd', 'aoste'): "Vallée d'Aoste",
    ('sud', 'france'): 'Sud France',
}


def _sans_accents(s):
    s = unicodedata.normalize('NFD', str(s).lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def tokenize(texte):
    """Jetons normalises : coupe le camelCase (« SanBorja » -> san, borja) puis
    sur tout non-alphanumerique. « StaRita » -> [sta, rita]."""
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(texte))     # camelCase -> espace
    s = _sans_accents(s)
    return [t for t in re.split(r'[^a-z0-9]+', s) if t]


def extract_places(ligne):
    """Lieux reconnus dans une entree (liste blanche). Renvoie la liste des
    libelles (ordre d'apparition, dedupe). Vide si l'entree n'est pas un lieu."""
    toks = tokenize(ligne)
    n = len(toks)
    couverts = [False] * n
    trouves = []

    # 1) expressions multi-jetons d'abord (les plus specifiques)
    for phrase, label in PLACE_PHRASES.items():
        L = len(phrase)
        for i in range(n - L + 1):
            if tuple(toks[i:i + L]) == phrase and not any(couverts[i:i + L]):
                trouves.append(label)
                for j in range(i, i + L):
                    couverts[j] = True

    # 2) jetons simples + alias, sur les positions non couvertes
    for i, t in enumerate(toks):
        if couverts[i]:
            continue
        label = PLACE_TOKENS.get(t) or ALIASES.get(t)
        if label:
            trouves.append(label)
            couverts[i] = True

    # dedupe en gardant l'ordre
    vus, out = set(), []
    for l in trouves:
        if l not in vus:
            vus.add(l)
            out.append(l)
    return out


# ── Validation LLM optionnelle (lieux inconnus) ──────────────────────────────

def valider_ollama(candidat, modele='qwen3-vl:2b', hote='http://localhost:11434'):
    """Demande au LLM local si `candidat` est un vrai lieu geographique. Renvoie
    le libelle (str) si oui, None sinon. N'est appelee que sous --ollama."""
    import json
    import urllib.request
    prompt = (
        "Tu valides des noms de LIEUX geographiques (ville, village, region, "
        "pays, ile, quartier, site naturel). Reponds STRICTEMENT en JSON.\n"
        f"Le terme suivant est-il un vrai lieu geographique reel ? « {candidat} »\n"
        "Ce n'est PAS un lieu si c'est un prenom/patronyme, un evenement "
        "(mariage, soiree), une activite, une marque, une fete, un objet.\n"
        'Repond : {"lieu": true/false, "nom": "<nom propre du lieu ou vide>"}')
    data = json.dumps({"model": modele, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    try:
        req = urllib.request.Request(hote + "/api/generate", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            rep = json.loads(r.read().decode()).get("response", "")
        m = re.search(r'\{.*\}', rep, re.S)
        if not m:
            return None
        j = json.loads(m.group(0))
        if j.get("lieu") is True:
            return (j.get("nom") or candidat).strip() or candidat
    except Exception as e:
        print(f"  (ollama indisponible pour « {candidat} » : {e})")
    return None


# ── Programme ────────────────────────────────────────────────────────────────

def main():
    ecrire = '--ecrire' in sys.argv
    ollama = None
    for a in sys.argv[1:]:
        if a.startswith('--ollama'):
            ollama = a.split('=', 1)[1] if '=' in a else 'qwen3-vl:2b'

    if not FICHIER.exists():
        print(f"{FICHIER} introuvable.")
        return 2

    lignes = FICHIER.read_text(encoding='utf-8').splitlines()
    entrees = [l.strip() for l in lignes
               if l.strip() and not l.lstrip().startswith('#')]

    gardes = {}          # libelle -> None (set ordonne)
    rejetes = []         # (entree, raison)
    for e in entrees:
        lieux = extract_places(e)
        if lieux:
            for l in lieux:
                gardes.setdefault(l, None)
        else:
            verdict = valider_ollama(e, ollama) if ollama else None
            if verdict:
                gardes.setdefault(verdict, None)
                print(f"  + LLM valide « {e} » -> {verdict}")
            else:
                rejetes.append(e)

    kept = sorted(gardes, key=_sans_accents)
    print(f"=== {len(entrees)} entrees -> {len(kept)} lieux gardes, "
          f"{len(rejetes)} rejetes ===")
    print("\nLIEUX GARDES :")
    print("  " + ", ".join(kept))
    print("\nREJETES (non-lieux) :")
    print("  " + ", ".join(rejetes))

    if not ecrire:
        print("\n(dry-run — rien ecrit. Relance avec --ecrire pour appliquer.)")
        return 0

    bak = FICHIER.with_suffix('.txt.bak')
    bak.write_text("\n".join(lignes) + "\n", encoding='utf-8')
    corps = [
        "# Lieux reconnus par la recherche (un par ligne).",
        "# Nettoye par nettoyer_lieux.py : seuls de vrais lieux sont gardes.",
        "# Les entrees rejetees (non-lieux) sont conservees en commentaire plus",
        "# bas — decommente pour en reactiver une. Sauvegarde : lieux.txt.bak.",
        "#",
    ]
    corps += kept
    corps += ["#", "# --- Rejetes (non-lieux), conserves pour reference ---"]
    corps += [f"# {r}" for r in rejetes]
    FICHIER.write_text("\n".join(corps) + "\n", encoding='utf-8')
    print(f"\nEcrit {FICHIER} ({len(kept)} lieux). Backup : {bak.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
