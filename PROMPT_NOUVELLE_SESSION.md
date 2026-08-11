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

## Où on en est (11/08/2026, soir)

Matin + après-midi du 11/08 : **commités et fusionnés** (fixes clusters/perf/FP, fusion
`/sujets`, design PEOPLE+PETS, fix bandeau timm `/pets`) — détail dans git.

**Session du soir — livrée sur disque, PAS vérifiée en réel, PAS commitée** (le serveur
n'avait pas été redémarré) :
- **Recherche sur la Carte** : champ « noms, lieux, sens » sur `/map` (vocabulaire
  `/api/search` partagé, plafond `n` 1500) ; filtre composable avec zone/diaporama.
- **Passe DESIGN terminée sur les 5 pages restantes** (MAP/GALLERY/HTML/BROWSE/FACES)
  + `outline:none` purgés partout. Lint tokens : 0 interdit, 0 avertissement.
- **Éval INT8 : REJETÉ** (consigné `eval/DECISIONS.md`, script `eval/eval_int8_vectors.py`).

## Prochain pas — par valeur

1. **Redémarrer puis VÉRIFIER en réel** la fournée du soir : `/map` (recherche « Luna »,
   « Bremblens », composition avec zone/diaporama), `/files`, `/`, `/browse`, `/faces`
   (rendu tokens), bandeau `/pets` (mention neutre « en veille », pas d'alerte rouge).
   Puis commiter (`27 - Commit de session.bat`).
2. **Vérité terrain (priorité n°1)** : confirmer ~100 propositions dans `/people`
   (page filtrable, tri clavier Espace=oui / X=non / Z=annuler).
3. Gestes Mike : lots de renommage + activer `gps_place` ; nettoyer Flo/Caline.
   Ensuite : extraction physique `ui/` (`bundle.py`) ; `GpuArbiter` (session dédiée).

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché).
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git + redémarrage
  = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur est l'écrivain unique).
