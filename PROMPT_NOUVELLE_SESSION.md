# Amorce de reprise — MediaLibrary

> Colle ce bloc dans une nouvelle conversation Cowork, après avoir connecté
> `C:\Prog\Claude\MediaLibrary`. L'état vit dans les fichiers, pas dans l'historique.
> Règles + protocole = `CLAUDE.md` (chargé auto). Ici : juste l'état et le prochain pas.

Tu reprends **MediaLibrary** — photothèque familiale locale à IA (~30 000 photos NAS,
serveur Python stdlib pur, pipelines Ollama/InsightFace/YOLO/DINOv2, RTX 3050 4 Go).

## Ordre de lecture

1. `CLAUDE.md` (auto) — règles absolues, protocole, architecture.
2. `ROADMAP.md` — état détaillé + priorités par valeur.
3. `eval/DECISIONS.md` — pistes déjà tranchées (ne rien reproposer).
4. Selon le sujet : `docs/RANGEMENT_2026.md`, `docs/AUDIT_EXTERNE_2026.md` ; skills
   `monolith-surgery` (avant tout edit de `server.py`), `photo-ui` (dès qu'on touche l'UI).

## Où on en est (10/08/2026)

Tout est **git-commité** et validé en réel. Derniers chantiers : curation (faux positifs
enfin *appris* — `exclude` fait autorité partout), page `/sujets` (lecture seule), et
**tokenisation UI #8 value-preserving terminée sur les 7 pages** (`.pchip`/`.chip` fusionnés,
`#222`→`--salle-3` et `#f0a35b`→`--veilleuse` dans `/people`). Détail : `ROADMAP.md` + git.

## Prochain pas — par valeur

1. **Vérité terrain (priorité n°1)** : confirmer ~100 propositions dans `/people`
   (page filtrable, tri clavier Espace=oui / X=non / Z=annuler).
2. **Passe DESIGN ciblée (optionnelle)** : caler les valeurs *hors échelle 4px* (0.8rem,
   radius 8/10px, px de PETS) — **CHANGE le rendu**, page par page + vérif visuelle.
3. **`/sujets`** : ajouter **Lieux** (dépend de `gps_place`) puis fusion (`/sujets` = entrée
   unique, `/people`+`/pets` en vues spécialisées).
4. Gestes Mike : lots de renommage + activer `gps_place` ; nettoyer Flo/Caline.

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché).
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git + redémarrage
  = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur est l'écrivain unique).
