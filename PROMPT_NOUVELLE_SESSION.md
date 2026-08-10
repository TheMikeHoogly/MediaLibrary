# Amorce de reprise — MediaLibrary

> Colle ce bloc dans une nouvelle conversation Cowork, après avoir connecté le dossier
> `C:\Prog\Claude\MediaLibrary`. L'état vit dans les fichiers, pas dans l'historique.
> Les **règles** et le **protocole** sont dans `CLAUDE.md` (chargé automatiquement) —
> ce fichier ne les répète pas : il donne juste l'état et le prochain pas.

Tu reprends **MediaLibrary** — photothèque familiale locale à IA (~30 000 photos NAS,
serveur Python stdlib pur, pipelines Ollama/InsightFace/YOLO/DINOv2, RTX 3050 4 Go).

## Ordre de lecture

1. `CLAUDE.md` (auto) — règles absolues, protocole, architecture.
2. `ROADMAP.md` — état + priorités (détail chiffré de la session ci-dessous).
3. `eval/DECISIONS.md` — idées déjà rejetées/tranchées (ne rien reproposer).
4. Selon le sujet : `docs/RANGEMENT_2026.md`, `docs/AUDIT_EXTERNE_2026.md`, et les
   skills `.claude/skills/` (`monolith-surgery` avant tout edit de `server.py`,
   `photo-ui` dès qu'on touche une page/CSS/JS).

## Où on en est (10/08/2026, soir)

Grosse session « curation » + une nouvelle page + début de tokenisation UI. **Tout est
écrit sur le disque** (`server.py`, `ROADMAP.md`) et **l'essentiel a été vérifié en réel**
via Claude-in-Chrome (le serveur a été redémarré en cours de session). **PAS encore
git-commité** → lancer `27 - Commit de session.bat` (puis `28 - Fusionner…` / `git push`
= gestes Mike, cf. `docs/GIT_WORKFLOW.md`).

Fait ce soir (détail : `ROADMAP.md` + git) :

- **Faux positifs ENFIN appris** (le vrai sujet de la session). `exclude` (le rejet humain
  durable) fait désormais autorité PARTOUT : générateur de cartes « faux positif »
  (`build_suggestions` REMOVE) **+ auto-guérison** des tags resurgis, et `reimport_name_tags`.
  Réversibilité : une **attribution positive** lève l'exclusion (`_nommer_membres_visages`).
  Cause : un traitement de fond ressuscitait le tag pendant qu'`exclude` était ignoré là.
- **Nouvelle page `/sujets`** (onglet dans la nav des 7 pages) : vue unifiée LECTURE SEULE
  personnes+animaux (grille, filtre par nom, bascule Tous/Personnes/Animaux), API
  `/api/sujets/list`, cartes → fiches détail via **lien profond `?name=`** ajouté à `/people`
  et `/pets`. **Vérifié en réel** : 363 sujets (351 pers + 12 anim), filtres/bascule/état
  vide OK, deep-links OK dans les deux sens.
- **2 bugs de curation corrigés** :
  - Une **nouvelle personne** créée depuis le champ « c'est… » d'une carte faux positif
    n'apparaissait pas (manquait `loadPeople()` + invalidation du cache de noms dans
    `assigner()`). Corrigé, vérifié live (le code tourne).
  - **Caline (chatte) revenait sans cesse comme personne** — VRAIE cause : `reembed_one_batch()`
    faisait `e['faces'] = detect_faces(...)`, **écrasant les marquages humains** (pas_visage/
    non_group/…) sur les visages faibles (les découpes de chat sont faibles). Corrigé : le
    ré-embedding **saute** toute photo jugée par un humain ou dont un visage est assigné.
    ⚠ **Geste Mike** : re-rejeter le groupe visages Caline **une fois** après redémarrage
    (les marques déjà effacées ne se restaurent pas seules ; ensuite ça tient).
- **Tokenisation UI (chantier #8) — value-preserving TERMINÉ sur les 7 pages.** `/browse` (plus
  tôt), puis GALLERY/MAP/PEOPLE/PETS/REGLAGES/HTML (suite 10/08). Les espacements/rayons/tailles
  qui **égalent déjà un token** pointent vers lui (rendu **identique**, prouvé : résolution des
  tokens + diff = zéro écart ; `getComputedStyle` sur serveur en marche). Divergences design
  nommées tranchées : GALLERY `.pchip`/`.chip` **fusionnés** ; PEOPLE `#222`→`var(--salle-3)`,
  `#f0a35b`→`var(--veilleuse)`. `verifier_ui_tokens.py` = 0 interdit dur ; `py_compile` OK.
  Livré sur disque, **pas commité**, **à activer par redémarrage** + **vérif visuelle** (les 2
  couleurs /people + la fusion sont à confirmer en réel). `#4A8C7B` Leaflet restent en dur.

**Restart** : le serveur ne recharge pas à chaud. Le tout dernier changement (tokenisation
`/browse`) s'active au prochain `0 - Démarrer le serveur.bat` — mais il est **visuellement
identique**, donc sans risque.

**Ouvert (gestes Mike)** :
- **Redémarrer le serveur** (`0 - …bat`) pour activer le nouveau `server.py` (tokenisation #8),
  puis laisser un onglet `192.168.0.13:8080/files` au premier plan pour la vérif visuelle.
- **git-commit de la session** (`27 - …bat`).
- **Fiche animal Caline POLLUÉE par des photos de chien** (cocker, scores négatifs en tête de
  sa fiche `/pets`) — repéré en réel. Nettoyer via « Corriger » sur sa fiche. (≠ le bug visages.)
- **Re-rejeter le groupe visages Caline** une fois (cf. ci-dessus).
- **Nettoyer Flo** (Corriger seuil ~0.2 / Nettoyer référence).
- Lots de renommage + `gps_place` (bat 18 → `enrichir_lieux.py` → `--ecrire` → redémarrer).

## Prochain chantier

0. **Finir la vérif visuelle de la tokenisation #8** (dès le redémarrage) : tour des 6 pages en
   Claude-in-Chrome, attention particulière à `/people` (2 couleurs changées : fond de vignette
   `#222`→`--salle-3`, « hésite » `#f0a35b`→`--veilleuse`) et aux chips GALLERY (fusion
   `.pchip`/`.chip`). Le value-preserving est déjà prouvé identique hors-ligne ; ici on confirme
   juste que rien n'a cassé et que les 2 couleurs /people plaisent.
1. **Passe DESIGN ciblée (optionnelle, hors value-preserving — CHANGE le rendu)** : caler les
   valeurs **hors échelle 4px** (0.8rem, radius 8/10px, px de PETS, etc.) sur l'échelle, page par
   page, AVEC vérif visuelle. Harmoniser les fonds photo (#000 vs `--salle-3`) entre PEOPLE/PETS
   si voulu. À faire seulement si Mike veut pousser la cohérence ; le gain est esthétique, le
   risque = beaucoup de petits décalages → vérifier chaque page.
2. **Vérité terrain (priorité n°1 hors tokenisation)** : confirmer ~100 propositions dans
   `/people` (page réorganisée + filtrable, tri clavier Espace/X/Z).
3. **`/sujets`** : ajouter **Lieux** (3ᵉ entité, dépend de `gps_place`) puis **fusion**
   (`/sujets` = entrée unique, `/people`+`/pets` en vues spécialisées).
4. Lots de renommage + `gps_place` (gestes Mike) ; recherche en langue naturelle (SigLIP 2).

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080**, via Claude-in-Chrome. Le serveur **ne recharge
  pas à chaud** → redémarrer (`0 - Démarrer le serveur.bat`) pour activer une modif de
  `server.py`. ⚠ Les clics/captures Claude-in-Chrome ne marchent que si l'onglet est **au
  premier plan** ; vérifs d'état par `fetch` GET (marche même onglet caché).
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files` (le pont device
  peut se déconnecter — `RefreshMcpTools` le relance). Git = gestes Mike.
- Garde-fous détaillés dans `CLAUDE.md` (noms humains sacrés, `.bat` ASCII, zéro dépendance,
  SQLite local). Mutations = vrais clics UI ; ne pas ouvrir `photos.db` depuis le sandbox.

Une phrase suffit pour démarrer : « Lis ROADMAP.md et DECISIONS.md, puis termine la
tokenisation UI (chantier #8) page par page, passe combinée + vérif visuelle. »
