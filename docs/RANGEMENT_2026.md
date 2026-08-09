# Rangement / dédoublonnage / renommage — état de référence

Photothèque familiale locale, serveur Python. Règle du projet : mesurer d'abord,
jamais de perte d'info. Le détail des travaux TERMINÉS est dans l'historique git
(recensement, plan, applicateur, purge, `rekey_everywhere`, cœur du renommage).

## Fait et appliqué (ne pas refaire)
- Dédoublonnage par contenu : 290 quarantaines, ~8,4 Go récupérés, index re-clé.
- Rangement par année : cœur en place. Renommage : cœur déterministe codé + testé.
- `rekey_everywhere`, purge de corbeille, orchestrateur de maintenance : livrés.

## Décisions d'architecture (toujours valables)
- Le démon d'analyse (lecture seule) PROPOSE un plan JSON à provenance ; le
  serveur, seul écrivain de l'index, l'APPLIQUE (rekey + undo).
- Doublon détecté sur le CONTENU (taille → sha256), jamais sur le nom.
- Tout déplacement/renommage passe par `rekey_everywhere(old, new)` : tags +
  FACE/PEOPLE/ANIMAL/PETS_STORE + `photo_vectors().rekey_prefix_all` (clé nue).
- Dossiers : année seule (`Photos/AAAA/`). Nom cible :
  `YYYYMMDD[-HHMMSS]_<lieu-ou-type>_<sujet>.ext`. Canonique : année > `_A TRIER`.
- Quarantaine réversible 30 j dans `.corbeille-rangement/` (manifeste + undo).

## Garde-fous (invariants — ne jamais casser)
- Jamais de `rm` direct ; retrait = quarantaine. dry-run par défaut sur tout mutant.
- Noms humains jamais perdus : fusionner les noms avant de retirer une copie.
- Tests destructifs sur COPIE /tmp de `photos.db`, jamais la vraie base.
- Purge : ne supprime un groupe que si sa canonique existe encore.

## Procédures encore relancées
- Purge : `python purger_corbeille.py --appliquer` (ou `.bat 24`), planifiable ;
  n'efface rien avant 30 j.
- Maintenance : thread de fond `maintenance.py run_cycle`, réglé par
  `MAINTENANCE_AUTO` / `MAINTENANCE_EVERY` et `INTERVALS`/`AUTONOMY`
  (auto/propose/off) en tête de `server.py` ; `.bat 25` pour forcer une passe.

## Reste à faire + dettes
- [ ] Rangement par année des `_A TRIER`/`_Uploads` : manque l'inventaire complet
      (chemin+date+zone). Enrichir `recensement_doublons.py` ou dériver de l'index
      (~2 600 fichiers non indexés).
- [ ] Application RÉELLE du renommage (mutant) : brancher `resolve_facts` sur GPS
      inversé + type SigLIP, provenance JSON+XMP, undo par lot. Session testée sur
      copie ; ne pas muter le NAS pendant un recensement.
- [ ] Détection de déplacement au scan (`server.py`, zone `scan_uploads`) : encore
      par nom+taille, rate un fichier renommé ET déplacé → migrer vers signature de contenu.
- [ ] Dette `lieux.txt` : `server.lieux_connus()` régénère la liste brute si le
      fichier est supprimé → brancher `nettoyer_lieux` ou ne pas le supprimer.
- [ ] Vérifier en réel : serveur démarre avec le thread de maintenance actif.

## Reprise
Lire ce fichier + `ROADMAP.md` (item renommage). Charger `monolith-surgery` avant
toute édition de `server.py`. Rien ne se supprime/déplace sans : plan relu,
`rekey_everywhere` couvrant le geste, quarantaine réversible en place.
