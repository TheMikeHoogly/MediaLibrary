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

## Où on en est (11/08/2026)

Lieux (3ᵉ type de sujet) **commité** (`fd1f805`) et **vérifié en réel** ce jour : `/api/sujets/list`
renvoie 25 lieux, cartes 📍 → `/files?q=`. Session du 11/08 (dans `server.py`, **modifié, PAS
encore commité** au moment d'écrire — un `git commit` de session est en cours) :
- **Uniformisation clusters Personnes/Animaux** : bug d'affichage « Rejeter le groupe » corrigé
  (débordement grille → `flex-wrap` + `min-width:0` + cibles 44px, miroir de `.cl .row`) ; bouton
  **« Archiver (inconnu) »** ajouté côté Animaux (parité). Vérifié en réel.
- **Perf `/sujets`** : `/api/sujets/list` passait de **>45 s (bloqué) à ~0,8 s** — `places_list`
  refaisait `media_roots()` (lectures config + **stats SMB**) par clé sur 64k. Fix : `_chemin_relatif(k, roots)`
  reçoit `roots` précalculé (idem `_cles_du_lieu`, `lieux_connus`). Vérifié en réel.
- **Page de résultats globale `/files?q=`** : sans `dir`, la galerie ne chargeait que `uploads/` (vide)
  → clic sur un Lieu ouvrait une galerie vide. Désormais le serveur remplit la grille avec
  `semantic_search(q)` (≤1500, pertinence) + mode IA côté client. Vérifié en réel (Bremblens 1141).
- **Fix racine faux positifs (curation)** : corriger un faux positif vers un nom que la photo
  **porte déjà** (ex. photo taguée Mike *et* Zab) ne retirait PAS le tag erroné (branche « déjà
  tagué » de `attribuer_visage`) → il revenait à chaque passe. Corrigé (retrait + exclusion,
  réversible). **À vérifier en réel après redémarrage.** File « À vérifier » nettoyée en direct
  (5 FP corrigés : Flo→Mathilde, Phéno→Dévi ×2, Zab→Mike ×2).

## Prochain pas — par valeur

0. **Vérifier le fix faux positifs en réel** (après redémarrage) : dans `/people` → « À vérifier »,
   corriger un FP vers un nom déjà présent et confirmer qu'il ne revient plus après rebuild.
1. **Vérité terrain (priorité n°1)** : confirmer ~100 propositions dans `/people`
   (page filtrable, tri clavier Espace=oui / X=non / Z=annuler).
2. **`/sujets` — fusion** : faire de `/sujets` l'entrée unique, `/people`+`/pets` en vues
   spécialisées (Lieux déjà livrés ; page résultats `/files?q=` déjà en place).
3. **Passe DESIGN ciblée (optionnelle)** : caler les valeurs *hors échelle 4px* (0.8rem,
   radius 8/10px, px de PETS) — **CHANGE le rendu**, page par page + vérif visuelle.
4. Gestes Mike : lots de renommage + activer `gps_place` (enrichit les Lieux) ; nettoyer Flo/Caline.

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché).
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git + redémarrage
  = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur est l'écrivain unique).
