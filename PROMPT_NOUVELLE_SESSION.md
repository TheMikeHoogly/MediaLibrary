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
- **Tokenisation UI (chantier #8), début** : page `/browse` — les espacements/rayons/tailles
  qui **égalent déjà un token** pointent vers lui (rendu **identique**, vérifié sur le serveur
  en marche : `--e-3`=12px, `--r-pill`=999px, etc.). 2 `#4a8c7b` en dur (contour de sélection)
  → `var(--fixateur)`. Discipline skill respectée : « identique d'abord, redesign séparé ».

**Restart** : le serveur ne recharge pas à chaud. Le tout dernier changement (tokenisation
`/browse`) s'active au prochain `0 - Démarrer le serveur.bat` — mais il est **visuellement
identique**, donc sans risque.

**Ouvert (gestes Mike)** :
- **git-commit de la session** (`27 - …bat`).
- **Fiche animal Caline POLLUÉE par des photos de chien** (cocker, scores négatifs en tête de
  sa fiche `/pets`) — repéré en réel. Nettoyer via « Corriger » sur sa fiche. (≠ le bug visages.)
- **Re-rejeter le groupe visages Caline** une fois (cf. ci-dessus).
- **Nettoyer Flo** (Corriger seuil ~0.2 / Nettoyer référence).
- Lots de renommage + `gps_place` (bat 18 → `enrichir_lieux.py` → `--ecrire` → redémarrer).

## Prochain chantier — les 2 tranches de tokenisation sont approuvées

1. **Tokenisation UI — terminer le chantier #8 (approuvé « les deux »)** :
   - **(a) Value-preserving** sur les pages restantes (GALLERY, MAP, PEOPLE, PETS, REGLAGES,
     HTML) : remplacer les valeurs en dur qui **égalent déjà un token** (12px→`--e-3`, 8px→
     `--e-2`, 16px→`--e-4`, 0.75rem→`--t-xs`, 0.85rem→`--t-sm`, 999px→`--r-pill`, `#4a8c7b`→
     `var(--fixateur)` SAUF dans Leaflet qui n'accepte pas `var()`). Mécanique, **rendu identique**
     (vérifiable hors ligne + `getComputedStyle`). Modèle : voir ce qui a été fait sur `/browse`.
   - **(b) Passe DESIGN** : caler les valeurs **hors échelle 4px** sur l'échelle, trancher les
     divergences couleur repérées (**`#222`** gris froid sous-AA et **`#f0a35b`** orange « hésite »
     dans `/people` → tokeniser, candidat variante `--veilleuse`), et **unifier `.pchip` vs `.chip`**
     (divergence connue, GALLERY). **Change le rendu → VÉRIFIER VISUELLEMENT** via Claude-in-Chrome
     (serveur en marche, onglet au premier plan).
   - ⚠ **Recommandation d'efficacité** : pour chaque page restante, faire **UNE passe combinée**
     (tokeniser + caler + divergences) AVEC vérification visuelle, plutôt que deux passes sur les
     mêmes déclarations. La liste des divergences `/browse` + `/people` est dans **ROADMAP #8**.
   - Outils : `python verifier_ui_tokens.py` (0 interdit dur attendu) ; `getComputedStyle` sur
     `:root` pour prouver l'équivalence des valeurs.
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
