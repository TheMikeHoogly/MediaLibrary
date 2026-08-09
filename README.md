# MediaLibrary

Photothèque familiale locale à IA — serveur photo domestique en
**Python stdlib pure** (`http.server`), servi au
téléphone sur le réseau local. Il indexe un fonds familial d'environ
30 000 photos stocké sur un NAS SMB, et y applique cinq pipelines d'IA locale.

Aucune donnée ne sort de la maison.

## Ce que fait le système

| Pipeline | Modèle | Sortie |
|---|---|---|
| Tagging | `qwen3-vl:2b` via Ollama | mots-clés FR/EN + description |
| Recherche sémantique | SigLIP 2 ViT-B/16-256 | recherche en langue naturelle |
| Visages | InsightFace `buffalo_l` (ArcFace) | détection + empreintes 512-d |
| Animaux | YOLO11s + vérification SigLIP | détection d'espèce |
| Individus animaux | DINOv2 base | empreintes 768-d + regroupement |

La recherche combine trois dimensions : **qui** (noms attribués par un humain),
**où** (arborescence des dossiers), **quoi** (sens de l'image).
`Luna à Bremblens en hiver` fonctionne.

Les noms attribués (`personne:Nom`, `animal:Nom`) sont écrits dans les
**métadonnées XMP des fichiers** via exiftool : le travail survit à
l'application.

## Contrainte matérielle

**RTX 3050 Laptop, 4 Go de VRAM.** C'est elle qui filtre toutes les décisions
techniques. Un ordonnanceur à tour de rôle et un arbitre de VRAM répartissent
la carte entre Ollama, InsightFace, YOLO, DINOv2 et SigLIP.

## Démarrer

```
Demarrer le serveur.bat
```

Les scripts numérotés s'exécutent dans l'ordre pour installer chaque brique.
Ils sont en **ASCII pur** : `cmd.exe` relit les fichiers de commandes par
décalage d'octets, et un caractère accentué lui fait exécuter des fragments de
lignes. `python verifier_bat.py` le contrôle.

## Documents à lire avant de contribuer

| Fichier | Rôle |
|---|---|
| `CLAUDE.md` | Brief du projet, règles absolues — lu automatiquement par Claude Code |
| `ROADMAP.md` | Où en est le projet, ce qui reste |
| `eval/DECISIONS.md` | Journal des évaluations : ce qui a été adopté **et rejeté sur mesure** |
| `docs/AUDIT_EXTERNE_2026.md` | État de l'art, dette technique |
| `.claude/skills/` | Trois skills : design system, protocole d'évaluation, chirurgie du monolithe |

## Une règle de méthode

Toute évaluation aboutit à une entrée écrite dans `eval/DECISIONS.md`, y
compris — surtout — quand elle conduit à **rejeter** une idée. Cinq y figurent
déjà, dont deux recommandations de l'audit initial réfutées par la mesure.

Le journal documente aussi deux bancs d'essai qui ne mesuraient pas ce qu'ils
prétendaient : l'un circulaire, l'autre inéquitable. Un score parfait est un
signal d'alarme, pas un succès.

## Ce qui n'est pas versionné

La base `photos.db`, les vignettes, les images récupérées et les jeux
d'évaluation restent locaux : ce sont des photos de famille et des chemins
privés. Voir `.gitignore`.
