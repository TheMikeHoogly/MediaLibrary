# Feuille de route

Ce fichier survit aux sessions, contrairement à une liste de tâches en mémoire.
Il est référencé par `CLAUDE.md`, donc relu au début de chaque session.

Dernière mise à jour : 2 août 2026.

---

## Fait, et vérifié

| # | Chantier | Preuve |
|---|---|---|
| 1 | **Migration SQLite** — `TagStore` → `SqliteStore`, écriture incrémentale | 64 676 entrées migrées et vérifiées, 42/42 tests. 48,8 Mo réécrits par `set()` → une ligne |
| 2 | **Embeddings hors JSON** — table BLOB, octets float16 préservés | 19 309 vecteurs sortis, base 58,8 → 47,2 Mo, `people` 11,5 Mo → 147 Ko |
| 3 | **Réparation GPU** — build CPU + orphelin `~orch` | `torch 2.13.0+cu130`, InsightFace sur CUDA |
| 4 | **Recherche sémantique SigLIP 2** — encodeur, index vectoriel, route, UI | 90 % de justesse au rang 1 ; recherche en 0,7 ms sur 8 730 vecteurs |
| 5 | **Recherche hybride** — noms humains + sens de l'image | 326 noms reconnus, y compris composés |
| 6 | **Vérification d'espèce** — SigLIP contre les classes COCO | 23 rejets justifiés sur 24 relus un par un |
| 7 | **Nommage généralisé** — chats → tous animaux, par espèce | `ANIMAL_NAMEABLE`, espèce déduite du groupe |
| 8 | **Attribution unifiée** — une action au lieu de boutons binaires | Sous-ensembles, noms multiples, annulation 10 s |
| 9 | **Prototypes multiples** (personnes) | 97,4 % contre 96,7 %, 0 régression |
| 10 | **Ordonnanceur + arbitre VRAM** | Tour de rôle à déficit, 16/16 tests |
| 11 | **Garde-fous de méthode** — `verifier_bat.py`, hook, journal de décisions | Règle ASCII bloquée à l'écriture |
| 12 | **MegaDescriptor rejeté, mesure valide** | À armes égales : DINOv2 97,4 % contre 94,0 %. Banc validé contre la production (97,4 % / 85,6 % vs 85,5 %) |
| 13 | **Résolution des découpes : sans effet** | 256 px 97,8 %, pleine résolution 97,4 %, 512 px 97,0 % — deux photos d'écart, du bruit |
| 14 | **Circularité du banc détectée et corrigée** | 100 % de justesse = alarme, pas succès : la vérité terrain était auto-générée |
| 15 | **Récupération d'images corrompues** | 987 fichiers inventoriés, orientation et analyse profonde corrigées |
| 16 | **Recherche à trois dimensions** — qui / où / quoi | `Luna à Bremblens en hiver` : tag humain + dossier + sens. `lieux.txt` déduit des chemins, 120 lieux |
| 17 | **`/people` : rangée responsive (12a) + gestion des groupes (12b)** | Attribution par sous-ensemble portée sur les visages (`attribuer_visages`), rejet de groupe / « pas un visage » réversibles, cibles 44 px, plus de scroll horizontal. Validé en réel |
| 18 | **Fondations design system « chambre noire »** | `ui/tokens.css`+`base.css`+`components.css`, injection partagée via `_send_html`, `bundle.py` mono-fichier, `test_ui_bundle.py` 4/4. Plancher a11y (focus-visible, reduced-motion) actif sur les 7 pages — anneau orange confirmé en réel |
| 19 | **Régression `/people` corrigée** — tempête de `/api/names` | Autocomplétion à la demande + cache/déduplication + erreurs visibles. Vérifié navigateur : 1 appel `/api/names` 200 à la frappe, tous `facecrop` 200 |

## Prochaine étape décidée

> **⚑ SESSION 02/08 — tout le neuf est sur la branche `integration`** (= `main`
> + file-ops + control-center), que Mike fait tourner. **Prochaine étape n°0 :
> valider en réel puis `git merge integration` dans `main` + push.** Détail
> complet et roadmap de la suite dans `PROMPT_NOUVELLE_SESSION.md` (§ « État au 2
> août »). Livré : redesign étape A (7 pages tokenisées) + étape B (planche
> contact, View Transitions, modale papier, **tri au clavier du curateur**),
> correctifs tagging (Mathilde `/api/names[:40]→[:2000]`, ARZOPA scan récursif
> d'Uploads), **gestion de fichiers `/browse`** (`fichiers.py`, 23/23),
> **centre de contrôle `/reglages`** (hub + monitoring + maintenance),
> **plan de rangement par année** (`rangement_annee.py`, lecture seule, 10/10).

**CAP ACTUEL = redesign UI/UX « chambre noire » (décidé avec Mike, 01/08).**

**◐ ÉTAPE A (TOKENISATION) FAITE SUR LES 7 PAGES + LA BARRE (01/08) — à valider
en réel.** Toutes les couleurs/polices en dur des pages ont été remplacées par
les tokens `ui/tokens.css` (`--salle`/`-2`/`-3`, `--texte`/`--graphite`,
`--papier`/`--texte-papier`, `--trait`, `--f-texte`/`--f-donnees`, accents
`--veilleuse`/`--fixateur`/`--encre`). Sémantique appliquée partout : **fixateur**
= filtre/onglet actif, zone géo, sélection de vignettes ; **veilleuse** = bandeau
IA `#pending`, barres de progression, focus ; **encre** = destructif (« Tout
effacer », retrait d'intrus) ; **papier** = bouton principal + onglet nav actif.
Bleu iOS (`#0a84ff`/`#5b9dff`/`#2a6df0`/`#7db4ff`) et violets éliminés ; gris
neutres froids → noir chaud. Ordre traité : `BROWSE`, `APP_NAV_CSS`, `HTML_PAGE`
(upload), `MAP`, `FACES`, `PETS`, `PEOPLE`, `GALLERY`. Structure/espacements/rayons
**inchangés** (redesign structurel = étape B). Chaque page : `py_compile` OK.

**Garde-fou de méthode ajouté : `verifier_ui_tokens.py`** (scanne les constantes
de page, signale les interdits `photo-ui`, code sortie 1 si interdit dur). État
final : **0 interdit dur sur les 9 constantes** (aperçus nav + galerie rendus et
vérifiés visuellement).

**RESTE :**
1. **Valider en réel au navigateur** les 7 pages (Mike). Points d'attention :
   contraste des `--graphite` hérités, lisibilité des popups papier (carte),
   états actifs teal.

**◐ ÉTAPE B (redesign structurel) — EN COURS (01/08), jamais mélangée à A :**
- ✓ **Planche contact** — `GALLERY .grid` en `repeat(auto-fill, minmax(clamp(96px,
  18vw,168px),1fr))`, gouttière `--e-1`, `content-visibility:auto` sur les cellules.
  Retire le dernier interdit structurel `photo-ui` (colonnes en dur) + la media
  query. Aperçu vérifié.
- ✓ **View Transitions** — `@view-transition{navigation:auto}` dans `base.css` :
  transition native multi-document, progressive, respecte reduced-motion.
- ✓ **Fix `__EXTRA__`** de `_serve_health` (bug préexistant, littéral affiché).
- ✓ **Deux registres — 1re surface** : la modale « nommer rapidement » (`.qn-card`)
  passe sur **papier** (posée sur scrim sombre), champ clair, boutons adaptés,
  primaire = `fixateur`. Aperçu vérifié. **RESTE** : propager le registre papier aux
  cartes de clusters toujours visibles (`.cl` sur `PEOPLE`, `.group` sur `PETS`) —
  plus gros changement du flux principal, **à valider en réel d'abord**.
- **RESTE** : **centre de tâches** remplaçant `#pending` (tâche/restant/CPU-GPU/
  Pause, données via `hw_state()`/`system_busy()`/tailles de files) ; **numéro de
  vue** en marge des cellules (`.vue__num`), signature planche contact.
2. Bibliothèque Figma (`figma-generate-library`) comme source des composants.

Voir la section « Interface » plus bas (points 9-12 + composants signature) pour
le détail. **Une phrase pour démarrer** : « Lis ROADMAP.md, charge `photo-ui` et
`monolith-surgery`, et tokenise `BROWSE_PAGE`. »

### En réserve (parké, non prioritaire)

- **Garde amont de 12b (`vision-eval`)** — `verifier_visages.py` (SigLIP humain vs
  animal/objet) + plancher `det_score`, décision écrite avant activation. Voir
  point 12b. Le marquage humain réversible tient l'usage en attendant.
- **Page Animaux** — `carteGroupe` a le même `listeProps()` eager que la
  régression corrigée sur `/people` ; à porter par cohérence (sans urgence, peu
  de groupes).
- **Éval tagging — assertions vs pixels (parké).** Ci-dessous, conservé pour ne
  pas reperdre le fil :

**Assertions vs pixels : mesuré, noté à l'aveugle et tranché (31/07, voir
`eval/DECISIONS.md`).** Verdict en deux temps. Proxies automatiques : V1 (pixels
jetés) disqualifié (33 % de descriptions « méta ») ; l'impératif de noms au prompt
est inefficace (16 % d'ancrage) et coûteux (× 2,6, VRAM 3 950 Mo au ras du
plafond). **Notation humaine (40 cartes) : l'hybride V2 gagne — meilleure
description dans 60 % des cas contre 30 % pour l'image seule**, hallucination à
peine plus haute (8 % vs 5 %), et il gagne dans les trois catégories. Les
assertions **améliorent** donc la description ; c'est la mesure automatique seule
(« V2 ≈ V0 ») qui l'avait manqué.

**Cap retenu :** garder **l'hybride assertions + image** (apport confirmé par
l'humain), mais **sans l'impératif de noms** (c'est lui le surcoût, pas les
assertions), et **attacher les noms/date/lieu par fusion programmatique** plutôt
que de les quémander au LLM (16 % d'obéissance). Le LLM reçoit les faits *en
contexte* pour mieux décrire ; la couche d'assertions à provenance garantit le
fait exact — ce qui débloque aussi la priorité n°1 (protéger les confirmations
humaines), puis cache de raisonnement et mémoire globale.

**Prochain pas éval, ciblé (mesurer avant de bâtir) :** noter/mesurer un V2
« assertions en contexte, **sans** impératif » (version à 4,3 s, jamais notée car
écrasée). Si elle garde l'avantage de qualité sans le surcoût, c'est le prompt de
production, doublé de la fusion programmatique.

**Assertions vs pixels : mesuré, noté à l'aveugle et tranché (31/07, voir
`eval/DECISIONS.md`).** Verdict en deux temps. Proxies automatiques : V1 (pixels
jetés) disqualifié (33 % de descriptions « méta ») ; l'impératif de noms au prompt
est inefficace (16 % d'ancrage) et coûteux (× 2,6, VRAM 3 950 Mo au ras du
plafond). **Notation humaine (40 cartes) : l'hybride V2 gagne — meilleure
description dans 60 % des cas contre 30 % pour l'image seule**, hallucination à
peine plus haute (8 % vs 5 %), et il gagne dans les trois catégories. Les
assertions **améliorent** donc la description ; c'est la mesure automatique seule
(« V2 ≈ V0 ») qui l'avait manqué.

**Cap retenu :** garder **l'hybride assertions + image** (apport confirmé par
l'humain), mais **sans l'impératif de noms** (c'est lui le surcoût, pas les
assertions), et **attacher les noms/date/lieu par fusion programmatique** plutôt
que de les quémander au LLM (16 % d'obéissance). Le LLM reçoit les faits *en
contexte* pour mieux décrire ; la couche d'assertions à provenance garantit le
fait exact — ce qui débloque aussi la priorité n°1 (protéger les confirmations
humaines), puis cache de raisonnement et mémoire globale.

**Prochain pas éval, ciblé (mesurer avant de bâtir) :** noter/mesurer un V2
« assertions en contexte, **sans** impératif » (version à 4,3 s, jamais notée car
écrasée). Si elle garde l'avantage de qualité sans le surcoût, c'est le prompt de
production, doublé de la fusion programmatique.

**Veille modèles (état de l'art, juillet 2026).** Le titulaire `qwen3-vl:2b`
reste **aligné SOTA** — Qwen3-VL est « le modèle de vision à battre en 2026 », et
le 2B (~1,9 Go) en est le plancher compact ; le 4B (~6 Go) déborderait les 4 Go
partagés, ce qui confirme le rejet passé du `qwen3-vl:4b`. **Nouveau challenger à
tester : `gemma4:e2b`** (Google, avril 2026, Apache 2.0) — ~2,3 Md effectifs
pensés pour l'edge (donc *a priori* dans 4 Go), **vision native + 140 langues
dont le français** (atout sur nos descriptions FR), présent sur Ollama
(`gemma4:e2b-it-q4_K_M`). Plans B : `ministral-3-3b` (Mistral, français natif),
`moondream3` (excellent en sortie structurée/étiquetage mais orienté anglais).
À écarter : 4B+/MoE trop gros pour 4 Go, Marlin-2B (vidéo), SmolLM3 (texte).

Le banc est prêt pour ce comparatif : `eval_tagging.py` porte `--modele` et
`--variantes`. Protocole (l'« option modèle » du plan, jamais lancée) :

```
python eval_tagging.py --modele qwen3-vl:2b --variantes V0
python eval_tagging.py --modele gemma4:e2b  --variantes V0
```

Chaque run écrit `tagging_results__<modele>.json` (fichiers non écrasés) avec le
**pic VRAM** ; on rejette tout modèle qui frôle les 4 Go pendant qu'Ollama est
résident (`keep_alive 30m`), puis on tranche la qualité entre les deux fichiers
(mêmes 150 photos figées). Sources archivées dans la discussion du 31/07.

Le point 7 (magasin de sujets commun) est **fait et vérifié**. La page
« Sujets » unifiée (point 8) et le plancher d'accessibilité restent en attente.

## Outillage et connecteurs

Les connecteurs s'autorisent dans les réglages de claude.ai (section
Connecteurs), par OAuth — jamais depuis une session Claude Code. Trois servent
directement les chantiers en cours ; les intégrer au flux de travail est un
objectif à part entière, pas un accessoire.

- **GitHub** (dépôt privé `TheMikeHoogly/MediaLibrary`). Dépôt local créé par
  `20 - Preparer le depot git.bat`, publié par `21 - Publier sur GitHub.bat`.
  Connecteur actif → trois usages concrets : (1) **revue de code sur diff/PR**
  (skill `engineering:code-review`) **avant** toute modification du monolithe —
  `server.py` fait 8 500 lignes sans filet ; (2) les chantiers de cette ROADMAP
  deviennent des **issues** suivies ; (3) un **historique** enfin présent. Règle :
  toute modif risquée de `server.py` passe par une branche + revue, pas par un
  edit direct sur `main`.
  > **Réglé (31/07) :** le dossier est un vrai dépôt git (`origin =
  > TheMikeHoogly/MediaLibrary`) et `git` est accessible **en local** depuis la
  > session (diff, log, branches, commit). La revue de diff avant de toucher
  > `server.py` ne dépend donc **pas** du connecteur GitHub MCP (dont l'OAuth
  > n'est pas activable depuis une session). Le connecteur distant reste utile
  > pour les issues/PR en ligne, mais n'est plus bloquant pour le cœur du travail.
- **Compétences utiles au projet** (récap 31/07, à charger selon la tâche) :
  `engineering:code-review` (revue de diff avant `server.py`, faisable en git
  local), `engineering:testing-strategy`/`debug`/`architecture`,
  `design:accessibility-review` (sert directement le plancher d'accessibilité,
  point 10), `design:design-critique`/`design-system`/`ux-copy` (redesign
  « chambre noire »), `data:*` + `graphing`/`create-viz` (interroger `photos.db`,
  visualiser le recensement, valider les bancs — cohérent avec « un proxy n'est
  pas le juge »), `mcp-builder` (exposer la recherche du serveur comme MCP — cap
  recherche AI ci-dessous). Hors sujet : les compétences banque/RH/support/ops.
- **Compression de prompts/contexte — à garder pour la phase recherche AI, pas
  maintenant.** Les outils type LLMLingua / LLMLingua-2 élaguent les tokens à
  faible information (2× à 5× de compression) via un petit modèle de scoring.
  Pertinent le jour où la recherche AI assemblera **beaucoup** de descriptions
  dans une seule requête LLM. Aujourd'hui non : nos prompts de tagging sont
  courts, le LLM est **local** (le coût n'est pas le token mais la **VRAM/temps**
  sur 4 Go), et ajouter un modèle de compression contredirait « zéro dépendance
  au démarrage » et la VRAM déjà au plafond. Le levier tokens **côté sessions
  Claude** est déjà en place : l'état vit dans les fichiers, on ouvre des sessions
  fraîches. Mesurer avant d'implémenter, comme toujours.
- **Figma** — moteur du redesign UI (section Interface ci-dessous). Le design
  system « chambre noire » existe en prototype (`ui/prototype.html`) ; les skills
  Figma (`figma-generate-library`, `figma-design-to-code`) le poussent en
  **bibliothèque de composants** versionnée, source de vérité du design, puis
  regénèrent le CSS/HTML **natif** des pages depuis ces composants — sans jamais
  introduire de build step ni de dépendance npm.
- **Registre MCP** — pour tout besoin ponctuel d'un service externe (ex. le
  géocodage inverse des 684 photos GPS du point 14), chercher d'abord un
  connecteur au registre avant d'écrire du code jetable.

## En cours

- **Correctif Errno 22 SMB (branche `fix/smb-errno22-retry`, commit `2d7ad19`,
  revue de code passée — à vérifier en réel puis merger).** Symptôme :
  `⚠ Visages/Animaux … : [Errno 22] Invalid
  argument` sur des fichiers `_Uploads/ARZOPA`. Diagnostic (sonde
  `diag_errno22.py`) : **le fichier n'est pas corrompu** — il se décode
  parfaitement, en local comme via SMB en isolation ; l'Errno 22 est un défaut
  de lecture SMB **transitoire sous charge concurrente** (recensement des
  doublons + workers). Le bug réel : un hoquet transitoire était écrit comme
  `failed` **permanent**, et le scan saute ensuite toute clé déjà dans le store
  → une photo saine exclue à jamais. Correctif : `_load_bgr` lit les octets avec
  retry (`_read_bytes_retry`) puis décode en mémoire (`io.BytesIO`) ;
  `face_worker`/`animal_worker` retentent `ImageReadError` 3× sans poisonner ;
  les scans re-enqueuent les `failed` transitoires (`_is_transient_io_fail`), donc
  les entrées déjà poisonnées repassent seules. Testé en isolation
  (`test_errno22_fix.py`, tout vert). **Reste : observer l'effet réel** — relancer
  le serveur, vérifier que ces fichiers repassent et réussissent, puis merger.
- **Encodage sémantique du fonds** — 29 549 photos encodées sur 30 682
  (96 %). Terminé pour l'essentiel.
- **Seconde passe de récupération** — les 945 fichiers à en-tête détruit n'ont
  jamais reçu la recherche de flux JPEG. Relancer
  `17 - Recuperer les images illisibles.bat`.
- **Remettre `recuperees/` sur le NAS** — ces images sont hors photothèque,
  donc ni taguées ni analysées.

## À faire, par ordre de valeur

### Reconnaissance

1. **Étoffer la vérité terrain humaine** — 91 photos confirmées sur 12 072
   taguées (0,8 %). Le banc de classification rejoué à l'échelle réelle a
   rendu 100 % : la mesure était devenue circulaire, l'auto-attribution ayant
   posé presque tous les tags. Corrigé (le jeu se limite aux confirmations
   humaines), mais 23 visages ne permettent pas de trancher. **Confirmer une
   centaine de propositions dans l'interface vaudrait plus que n'importe quel
   changement d'algorithme.**
2. **Regroupement par densité** (HDBSCAN, Chinese Whispers) à la place du
   seuil global unique. Un seuil ne peut pas servir à la fois des portraits
   nets et des profils de 90 px.
3. **AdaFace** sur le chemin de ré-embedding des visages faibles.
4. **Écrire les tags SigLIP** — aujourd'hui seulement proposés
   (`semantic.py --tags`). Décision à prendre : ils modifieraient les XMP.
5. **Comparer `qwen3-vl:2b` à SigLIP** sur le même échantillon annoté.
6. *(facultatif)* `MegaDescriptor-DINOv2-518` — dernière variante non testée.
   Peu d'espoir vu l'écart, mais `--equitable --modeles DINOv2-518` suffit.

> **La reconnaissance animale est à un bon point d'arrêt.** 97,4 % de rang-1,
> sept erreurs dont six sur la seule paire Inti/Luna — deux chats qui se
> ressemblent vraiment. Ni le modèle ni la résolution n'y changent rien : le
> gain restant est dans la donnée, pas dans l'algorithme.

### Harmonisation personnes / animaux / lieux

Le principe : **tout outil créé d'un côté doit servir de l'autre.** Les deux
pipelines résolvent le même problème — regrouper, nommer, corriger — et n'ont
divergé que par accident d'écriture.

| Capacité | Animaux | Personnes | À faire |
|---|---|---|---|
| Attribution unifiée (sous-ensemble, noms multiples, annulation) | oui | ✓ oui (01/08) | `attribuer_visages` + `carteGroupeP` : sélection par vignette, noms multiples, annulation — porté depuis les animaux |
| Vérification par SigLIP (« ce n'est pas un chat ») | oui | partiel | rejet **manuel** d'un non-visage fait (`__pas_visage__`/`__non_group__`) ; reste la vérification **automatique** SigLIP amont, à mesurer (`vision-eval`) |
| Curateur avec suggestions et auto-attribution | non | oui | porter côté animaux : proposer des rattachements au lieu d'attendre un regroupement |
| « Trouver d'autres photos de X » | oui | oui | unifier le code, aujourd'hui dupliqué |
| Prototypes multiples | non (mesuré défavorable) | oui | rien à faire, décidé sur mesure |
| Fiche avec avatar, exclusions, confirmations | partiel | oui | même structure des deux côtés |

7. ✓ **FAIT (31/07)** — **Un magasin de sujets commun** (`SubjectStore`).
   `PEOPLE_STORE` et `PETS_STORE` unifiés derrière une seule abstraction ;
   14 fonctions devenues des wrappers. Vérifié contre la base réelle : aucune
   régression, aucun nom perdu. `find_more` applique désormais `exclude` aussi
   aux animaux.
8. **Une seule page « Sujets »** au lieu de Personnes et Animaux séparées :
   même gestes, filtre par type. Le lieu devient une troisième facette.

### Interface — redesign UI/UX « chambre noire »

Chantier à part entière : rendre l'application **belle, utile et agréable**, pas
seulement fonctionnelle. Aujourd'hui les 7 pages sont des chaînes littérales
dans `server.py`, antérieures au design system — la page d'upload emploie encore
le bleu iOS `#0a84ff` et des gris neutres, précisément les interdits de la skill
`photo-ui`. Le redesign applique la direction « chambre noire » partout, en
gardant le serveur stdlib **zéro build, zéro dépendance npm**. Ancrages : skill
`photo-ui` (tokens, composants, plancher d'accessibilité), `ui/prototype.html`,
et le **connecteur Figma** comme source de vérité des composants.

Méthode (règle `monolith-surgery`, non négociable) : **une page à la fois**,
d'abord extraite à l'identique vers `ui/`, ensuite redessinée — jamais les deux
mélangés. Un `bundle.py` réinjecte les assets pour conserver le livrable
mono-fichier. La bibliothèque Figma est le contrat ; `figma-design-to-code`
regénère le CSS/HTML natif. La page « Sujets » (point 8) et le garde-fou
d'upload (point 17) adoptent le nouveau système en premier — deux occasions de
valider les composants Figma sur du réel avant de propager aux pages historiques.

9. **Fondations — ◐ EN COURS (01/08).** Socle posé et testé ; extraction
   page-par-page à suivre.
   - ✓ **FAIT** : `ui/tokens.css` (tokens « chambre noire », source unique),
     `ui/base.css` (plancher a11y global), `ui/components.css` (btn/chip/feuille/
     planche/toast, **opt-in** — pas injecté globalement pour ne pas écraser les
     pages historiques). Chargeur `ui_shared_css()` dans `server.py` (cache,
     relecture `mtime`, **dégradation propre si `ui/` absent** → invariant
     zéro-dép), injecté sur chaque page via le hook `_send_html` existant (après
     `APP_NAV_CSS`, marqueur `ui-shared` anti-double-injection). `bundle.py` cuit
     les assets dans `dist/server.py` (mono-fichier, marche avec **ou sans**
     `ui/`). Tests : `test_ui_bundle.py` (4 verts, dont **accord server↔bundle**
     sur le CSS réel). `py_compile` OK. `dist/` git-ignoré.
   - **RESTE** : (a) tokeniser les 7 pages une par une (remplacer les valeurs en
     dur par `var(--…)`, adopter `components.css`), en commençant par la plus
     simple (`BROWSE_PAGE`) — **extraction identique d'abord, redesign ensuite**,
     jamais mélangés ; (b) corriger les divergences (`.pchip` vs `.chip`,
     `#0a84ff`, gris neutres, `:root` d'`APP_NAV_CSS` à migrer sur les tokens) ;
     (c) bibliothèque Figma (`figma-generate-library`) comme source des composants.
     **NB** : `APP_NAV_CSS` définit encore son propre `:root` (bleu iOS `#5b9dff`) —
     à réconcilier avec les tokens lors de la migration des pages.
10. **Plancher d'accessibilité (bloquant) — ◐ EN COURS.** ✓ **Global (01/08)** :
    `:focus-visible` (anneau `--veilleuse`, rétabli même là où une page posait
    `outline:none`) et `prefers-reduced-motion` sont désormais injectés sur les
    **7 pages** via `ui/base.css`. **RESTE** : contraste AA (audit des couleurs
    héritées), cibles 44 px généralisées, `<button>`/`<a>` sémantiques partout,
    `alt` rédigés, navigation clavier de tri — à traiter page par page comme des
    tests. (12a a déjà réglé le scroll horizontal + cibles 44 px sur `/people`.)
11. **Planche contact justifiée** — densité par `auto-fill` + `clamp()`, liseré
    `--veilleuse` par photo pour l'état pipeline, numéro de vue en marge ;
    `content-visibility` puis **virtual scroll** au-delà de ~2 000 vignettes.
    C'est la signature visuelle de l'app.
12. ◐ **Raccourcis clavier de tri — FAIT pour le curateur « À vérifier »
    (02/08, branche `integration`, à valider en réel).** La carte active porte
    l'anneau veilleuse ; hors champ de saisie : `Espace`/`Entrée`/`O` = oui,
    `X`/`Suppr` = non, `Z` = annuler, une lettre = focus le champ nom + amorce
    l'autocomplétion. Rappel affiché sous le titre. **Sert directement la
    priorité n°1** (confirmer vite ~100 propositions). RESTE (optionnel) : `1`–`9`
    pour assigner à une personne connue, `Maj+clic` pour une plage.

**Bugs et manques observés le 01/08 (page `/people`, `PEOPLE_PAGE`) — à traiter
en priorité au redesign :**

12a. ✓ **FAIT (01/08)** — **Débordement horizontal des contrôles « À vérifier ».**
     La rangée `.cl .row` (partagée par « À vérifier » et « Groupes à nommer »)
     avait `flex-wrap` mais ses enfants ne pouvaient pas rétrécir (`min-width:auto`)
     et le champ « ou : c'est… » avait une largeur fixe inline de 150 px. Fix
     (`PEOPLE_PAGE`, `<style>`) : `.cl .row > * { min-width:0 }`, libellé
     `flex:1 1 12rem` + `overflow-wrap:anywhere`, champ `.qui`/inputs élastiques,
     **repli vertical pleine largeur sous 900 px**, cibles **44 px** sur boutons et
     champs ; largeur inline retirée. Plus de scroll horizontal. **Validé en réel par
     Mike (01/08)** ; `py_compile` OK.

12b. **Groupes de personnes non supprimables + pollués par des non-visages.** Un
     groupe proposé mélangeait des visages peu reconnaissables (nuques, profils
     détournés) et **2 découpes de chat** (Caline), sans aucun moyen de le rejeter
     ni d'en retirer des vignettes. Correction en deux temps :

     - ✓ **FAIT (01/08) — UI + backend réversible (port depuis les animaux).**
       Le pipeline visages a désormais l'**attribution unifiée par sous-ensemble**
       déjà éprouvée côté chats : `attribuer_visages(membres, cible)` (miroir de
       `attribuer_animaux`) + `_nommer_membres_visages` + `_marquer_visages`, route
       `/api/assign` `genre:'visage'` avec `membres`. Cibles spéciales
       `__pas_visage__` (découpe de chat/objet → flag `pas_visage`, sortie du
       pipeline) et `__non_group__` (« Rejeter le groupe » → flag `non_group`).
       `_gather_faces` **saute** ces deux flags (jamais de re-formation), le
       curateur ne suggère plus une `pas_visage` à une personne. UI `PEOPLE_PAGE`
       (`carteGroupeP`) : **vignettes sélectionnables** (`<button aria-pressed>`,
       vignette entière cliquable), **Attribuer N** (sous-ensemble), **Rejeter le
       groupe**, proposition **« Ce n'est pas un visage »**, **toast d'annulation
       10 s** (`role=status`, rappel de rafraîchissement). Tout réversible via la
       pile d'annulation existante. Les groupes exposent `membres`. `py_compile` OK,
       **validé en réel par Mike (01/08)**. Ferme deux lignes du tableau d'harmonisation
       (sélection par vignette côté visages + rejet d'un non-visage).
     - **RESTE — en amont (la vraie cause), à MESURER avant de câbler
       (`vision-eval`).** Empêcher qu'un tel groupe se forme est un changement de
       modèle/seuil : il ne s'adopte pas sans jeu de validation issu du corpus réel,
       mesure de VRAM (4 Go partagés) et décision écrite. Plan : (1) **Garde de
       validité de visage** — vérification type SigLIP « visage humain vs
       animal/objet » sur les découpes (miroir de `verifier_especes.py`, en **passe
       séparée** hors serveur, pas inline dans le worker) + plancher `det_score`
       InsightFace ; (2) **Plancher de reconnaissabilité** — écarter les empreintes
       de faible qualité (nuque/profil) du statut *nommable* via `det_score`/pose.
       Livrable attendu : `verifier_visages.py` + entrée `eval/DECISIONS.md`
       (précision, faux rejets, pic VRAM) avant toute activation. Le marquage humain
       réversible ci-dessus tient déjà l'usage en attendant.

Composants et gestes signature à intégrer au fil des pages (non numérotés, ils
traversent le chantier) :

- **Deux registres** — salle sombre pour *regarder* (`--salle`, planche contact),
  papier pour *décider* (`--feuille`, panneaux de nommage). Accents à sens
  unique : `--veilleuse` = IA en cours, `--fixateur` = confirmé humain,
  `--encre` = destructif. Jamais un accent « décoratif ».
- **Centre de tâches** — remplace le bandeau `#pending` : tâche en cours, restant
  à faire, appareil (`CPU`/`GPU`), bouton **Pause**. Données déjà disponibles
  (`hw_state()`, `system_busy()`, tailles des files).
- **View Transitions** (multi-document, sans SPA) sur galerie → photo → personne
  via `view-transition-name` — la seule animation qui mérite d'exister ici.
- **Toast d'annulation 10 s** pour toute action destructive (`role="status"`,
  `aria-live="polite"`), cohérent avec l'invariant « geste destructif différé et
  annulable ».

### Recherche

13. **Adapter l'encodage au matériel en temps réel** — `_device_cible()` décide
    déjà GPU/CPU selon la VRAM libre, mais la taille de lot, la précision et
    la résolution d'entrée restent fixes. Les rendre fonction de
    `hw_state()` : gros lots quand la carte est libre, repli progressif sinon.
14. **Carte et lieux dans la recherche** — les 684 photos géolocalisées
    devraient enrichir `lieux.txt` par géocodage inverse, et la page Carte
    partager le même vocabulaire que la barre de recherche.

### Données

15. **Fiche « Flo »** — 3 478 photos, 80 références, 17 exclusions. Fiche
    probablement mal constituée : c'est elle qui rend Florine ambiguë.
16. **Doublons de fiches** entre personnes et animaux.

### Ingestion et organisation des fichiers

17. ✓ **FAIT (31/07)** — **Upload de répertoires entiers depuis le téléphone.**
    La page d'upload (`HTML_PAGE`) a un second bouton « Choisir un dossier »
    (`<input webkitdirectory multiple>`, pris en charge par Chrome Android ; iOS
    Safari ne le gère pas). Le client envoie le `webkitRelativePath` de chaque
    fichier dans un champ `relpath` ; le serveur l'assainit via
    `_safe_upload_rel` (composants nettoyés comme un nom de fichier, `..` et
    racine absolue neutralisés, sous-dossiers préservés) et écrit sous
    `UPLOAD_DIR` en **préservant l'arborescence**. Les doublons sont sautés par
    **contenu, pas par nom** (`_upload_content_dup` : même taille d'abord, puis
    même sha256, réponse `SKIP`) — la même image revenant sous un autre nom ou
    dans un autre album est reconnue, et la page ne fabrique plus de doublons.
    Progression = compteurs envoyées / ignorées / erreurs. Invariant UI > NAS
    respecté : `note_heavy_activity()` est appelé en tête de chaque POST, donc
    chaque upload fait céder le travail de fond.

    > Deux modes cohabitent sans risque : un `relpath` avec sous-dossier =
    > mode DOSSIER (structure + dedup) ; un nom simple = mode PLAT (horodaté,
    > comportement historique inchangé). Les photos de sous-dossier sont
    > **taguées à l'upload** via `enqueue(clé_relative)` — indépendant du scan
    > racine, qui reste plat. Leur clé contient `/`, donc elles sont hors du
    > périmètre de purge du scan Uploads (`own = clés sans /`) : jamais
    > supprimées par mégarde. Reste à surveiller : une suppression manuelle sur
    > le NAS ne sera pas répercutée dans l'index (staleness mineure, comme pour
    > un dossier non configuré en `dossiers_a_taguer`).
18. ✓ **FAIT sur branche `feat/file-ops` (02/08, à valider en réel puis merger).**
    **Réorganiser le système de fichiers depuis la vue « Dossiers ».** `/browse`
    n'est plus en lecture seule : renommer, déplacer (couper/coller via
    `sessionStorage`, survit à la navigation), créer un dossier, supprimer
    (**quarantaine réversible `.corbeille-rangement/`, jamais `rm`**), annuler
    (journal undo serveur). Photos **et vidéos**. Architecture : module pur
    `fichiers.py` (confinement, dérivation de clé selon la convention `scan`,
    re-clé) + `test_fichiers.py` **23/23** (dont « aucun nom humain perdu ») ;
    routes `/api/files/*` dans `server.py` (`_do_files_post`, singleton
    `file_ops()`) ; chaque déplacement passe par **`rekey_everywhere`** (tags +
    visages/personnes/animaux + vecteur sémantique). UI : barre d'actions sur
    **papier** (registre « décider »), rangées sélectionnables (cible 22 px),
    toast d'annulation. **RESTE** : valider en réel (déplacer/renommer/supprimer/
    annuler sur le NAS), puis merger dans `main`. Renommage/déplacement de
    **dossiers** entiers gérés (re-clé de l'arbre). Optionnel ensuite : rangement
    par année automatisé (point 19, `_best_time`).

19. **Dédoublonnage et rangement automatique par année.** Chantier à part entière,
    spécifié en détail dans **`docs/RANGEMENT_2026.md`** (problème mesuré,
    architecture, spec Phase 0, prérequis, décisions ouvertes, procédure de
    reprise). **Pour démarrer une nouvelle session** : « Lis
    `docs/RANGEMENT_2026.md`, charge `monolith-surgery`, et attaque la Phase 0. »

    Contexte mesuré : 37 % du fonds (10 882 photos) dort sous `_A TRIER`, mais le
    proxy nom+taille ne trouve que 133 doublons — le vrai volume ne se connaît
    qu'en **hashant les fichiers**, car des images identiques ont des noms
    différents. Principe retenu : un **démon d'analyse séparé** (lecture seule,
    hors serveur) produit un **plan à provenance** que le **serveur applique**
    (source unique de vérité pour l'index, `rekey` + undo). Dédoublonnage **sans
    perte** = détection par **contenu** (taille puis sha256, jamais le nom),
    fusion de l'union des tags/noms dans la copie canonique, puis **quarantaine
    réversible** (jamais de `rm`). Rangement par année via `_best_time`, le geste
    « `_A TRIER` → année » automatisé. Vidéos incluses.

    Séquencement, ordre non négociable (garantie « aucune info perdue ») :

    - **Phase 0 — recensement lecture seule — ✓ FAIT, RÉSULTATS CAPTURÉS
      (01/08).** `recensement_doublons.py` a tourné complet (16 658 s ≈ 4 h 37) et
      écrit `docs/recensement.{md,json}` + `docs/recensement_console.log`.
      **Chiffres réels (34 305 fichiers) :** 261 groupes de doublons par
      **contenu**, 291 copies retirables, **8,4 Go récupérables**, **12 714 sous
      `_A TRIER`** (37 %), 991 sans date fiable. Ces chiffres tranchent les
      décisions ouvertes : le dédoublonnage vaut l'effort (8,4 Go), et le gros du
      travail est le rangement de `_A TRIER`. **Prochain pas Phase 2/3** : relire
      `docs/recensement.md`, puis bâtir le démon d'analyse (plan JSON à provenance)
      et le worker serveur d'application (déplacement/quarantaine via
      `rekey_everywhere`, déjà prêt). NB : le NAS n'est plus parcouru, la
      contrainte « ne pas muter pendant le recensement » est levée.
    - **Phase 1 — prérequis serveur, bloquant** : `vectors.rekey_prefix(old, new)`
      — ✓ **FAIT ET TESTÉ (31/07)** (`test_rekey_vectors.py` 12/12, `test_vectors`
      29/29). Octets préservés, borne `\x1f`, idempotent, collision bruyante.
      **Carte des empreintes corrigée** (voir `docs/RANGEMENT_2026.md`,
      « Avancement 31/07 ») : les stores faces/animaux transportent déjà leurs
      vecteurs via `rekey`+`save` ; les vrais trous sont le sémantique `PHOTO_VEC`
      (couvert par `rekey_prefix`) et le fait que le scan (~l. 1715) ne re-clé
      **que** le store `tags`. **Point de re-clé unique : ✓ FAIT ET TESTÉ
      (01/08).** `rekey_everywhere(old, new, save=True)` dans `server.py`
      (tags + FACE/PEOPLE/ANIMAL/PETS + `photo_vectors().rekey_prefix_all`),
      idempotent, branché au scan (batch-save). Bug corrigé au passage :
      `rekey_prefix_all` ratait la clé **nue** du sémantique (`kind='photo'`,
      0/30 826 avec séparateur) — désormais déplacée aussi, en transaction.
      Validé sur **copie** de la base réelle (`test_rekey_everywhere.py` : nom
      humain + visage + sémantique déplacés octet pour octet, idempotent ;
      `test_rekey_vectors` 12/12, `test_vectors` 29/29 inchangés). **Reste
      (non bloquant)** : la détection de déplacement du scan (~l. 1705) matche
      par **nom + taille** et rate les fichiers renommés ET déplacés → passer à
      la signature de contenu quand le démon écrira un hash par fichier (Phase 2).
      Le point de re-clé est prêt pour le renommage intelligent et le worker
      « appliquer un plan ».
    - **Phase 2 — démon d'analyse** produisant le plan JSON à provenance, relu
      par un humain avant application. **✓ FAIT pour le dédoublonnage (01/08)** :
      `plan_rangement.py` → `docs/plan_rangement.{json,md}`, **291 quarantaines /
      8,4 Go**, 0 fusion de nom requise (sécurité vérifiée sur l'index). Reste le
      rangement par année des `_A TRIER` (besoin de l'inventaire complet).
    - **Phase 3 — application : ✓ FAIT et testé pour le dédoublonnage (01/08)**
      (`appliquer_plan.py`, `test_appliquer_plan.py`). Applique les 291
      quarantaines, réversible : re-vérifie sha256, fusionne les noms avant
      retrait, déplace vers `.corbeille-rangement/` + manifeste, re-clé l'index
      (mêmes primitives que `rekey_everywhere`), journal undo. Dry-run par défaut,
      `--limite N`, `--undo`. **Appliqué en vrai (01/08) : 290 quarantaines,
      ~8,4 Go récupérés.**
    - **Phase 3b — purge de la corbeille : ✓ FAIT et testé (01/08)**
      (`purger_corbeille.py`, `test_purger_corbeille.py`, `24 - Purger la
      corbeille.bat`). Supprime définitivement les groupes > 30 j, mais seulement
      si la canonique existe encore (filet anti-perte). Dry-run par défaut,
      `--verifier-canon`.
    - **Orchestrateur de maintenance intégré au serveur : ✓ FAIT et testé
      (01/08)** (`maintenance.py`, `test_maintenance.py`, thread
      `maintenance_orchestrator` dans `server.py`, `25 - Maintenance.bat`).
      Remplace la planification Windows : un thread de fond appelle `run_cycle`,
      cadence + autonomie par étape (auto pour purge/dédoublonnage, propose pour
      recensement lourd/renommage/rangement). Mutations in-process via
      `rekey_everywhere` (pas de cache périmé), lecture seule en sous-processus,
      priorité UI. **À valider en réel** (édition monolithe non testable hors
      machine). **Reste :** rangement par année des `_A TRIER` ; branchement de
      l'application du renommage `_Uploads` ; installateur nouveau PC (prochain).

    - **Rangement par année — GÉNÉRATEUR + APPLICATEUR FAITS ET TESTÉS (02/08,
      branche `feat/rangement-annee-apply`, à valider en réel).**
      Génération (lecture seule) : `rangement_annee.py` (pur, testé 10/10 —
      `test_rangement_annee.py`) : `_A TRIER` → `<base>/AAAA/` via `_best_time`,
      `_SANS_DATE/` si pas de date fiable (jamais deviné), aplati, collisions de
      plan détectées. `server.generer_plan_annee()` construit le plan depuis
      l'index en mémoire → `docs/plan_rangement_annee.{json,md}`, avec désormais
      un **`new_key`** par move (clé cible calculée côté serveur où les racines/
      `UPLOAD_DIR` sont connus). Exposé dans `/reglages`.
      **Application : `appliquer_plan_annee.py`** (calqué sur `appliquer_plan.py`
      du dédoublonnage) : **serveur arrêté**, **dry-run par défaut**, `--appliquer`,
      `--limite N`, `--undo`. Par move : saute si src absent, **refuse toute
      collision au dst** (jamais d'écrasement), déplace, re-clé via `rekey_stores`
      (miroir exact de `rekey_everywhere` — tags + visages/personnes/animaux/chats
      + vecteur sémantique), journal undo. Pas de fusion de nom (déplacement 1:1).
      Testé : `test_appliquer_plan_annee.py` (move + re-clé nom humain préservé,
      collision refusée, undo, repli `new_key` absent, idempotence). Lanceur ASCII
      pur `26 - Ranger par annee.bat` (dry-run → lot de 20 → reste, confirmations
      `choice`). `verifier_bat.py` OK, `py_compile` OK.
      **RESTE : valider en réel** — générer le plan depuis `/reglages`, arrêter le
      serveur, dry-run puis `--limite 20`, vérifier sur le NAS, puis le reste
      (annulable via `--undo`). La quarantaine des doublons reste un geste séparé
      (déjà appliqué, 8,4 Go) — une collision au dst est ici refusée, pas fusionnée.

    Note : le garde-fou anti-doublon **à l'upload** (point 17, `_upload_content_dup`)
    est déjà en place — il empêche d'*ajouter* des doublons ; ce chantier-ci
    nettoie ceux **déjà** sur le NAS.

---

## Multi-utilisateur / foyer partagé (futur, non prioritaire)

Objectif à terme : plusieurs personnes du foyer déposent leurs photos (aujourd'hui
Mike + Florine), chacune gardant **sa** hiérarchie de dossiers. Modèle visé : une
racine par personne (« Photos Mike », « Photos Flo »), un **`owner` dérivé de la
racine de premier niveau** stocké par entrée. Le multi-racines existe déjà
(`media_roots()` + `dossiers_a_taguer.txt`), et le rangement par année est déjà
**opt-in** (n'agit que sous `_A TRIER`) : la structure libre d'un autre utilisateur
n'est donc jamais touchée. Ce qui reste à construire, quand le besoin sera là :

- **Dédoublonnage scopé par racine / propriétaire.** Aujourd'hui `plan_rangement.py`
  détecte les doublons par **contenu à l'échelle de tout le fonds** : la même photo
  chez deux personnes serait vue comme un doublon (quarantaine + fusion de tags).
  En multi-utilisateur, chacun garde sa copie → scoper la détection par racine (ou
  par `owner`). Tant que ce n'est pas fait : **ne pas appliquer le dédoublonnage
  cross-racines** (l'application est manuelle, donc sûr si on relit le plan).
- **Rangement par année configurable par racine.** Liste explicite des racines qui
  optent pour l'auto-rangement (ceinture-bretelles : même si un `_A TRIER` traînait
  chez un utilisateur qui n'en veut pas, sa racine reste exclue).
- **Renommer une racine sans casser l'index.** « Photos » → « Photos Mike » change
  ≈ 30 000 clés (chemins absolus). Soit garder le dossier physique et n'afficher
  qu'un libellé, soit un **outil de re-clé de préfixe de racine** dédié (primitive
  `rekey_everywhere` / `rekey_prefix_all` déjà testée, mais à emballer + tester sur
  une racine entière).
- **Comptes et droits d'accès.** Aujourd'hui le serveur est **ouvert sur le réseau
  local, sans authentification** — « racine partagée accessible à tous » est l'état
  actuel. Un vrai cloisonnement par utilisateur (comptes, permissions par racine)
  est un chantier à part entière, à poser au-dessus du modèle `owner` ci-dessus.

Séquencement raisonnable le jour venu : `owner` par entrée → dédoublonnage scopé →
rangement configurable par racine → outil de renommage de racine → (plus tard)
comptes/droits. Décidé avec Mike (02/08) : **noté pour plus tard, pas maintenant.**

## Cap long terme — multimodalité et recherche AI

Le projet a commencé par les **images** ; il ira vers la **vidéo** puis
l'**audio** (chantiers de fin de roadmap, dans cet ordre). Cette trajectoire doit
rester présente dans chaque décision d'architecture, même en travaillant sur les
images :

- Plusieurs briques incluent **déjà** les vidéos dans leur périmètre — rangement,
  dédoublonnage par contenu, renommage `YYYYMMDD_…`, vue Dossiers. Le pipeline IA,
  lui, ne tague encore que les photos ; la vidéo (échantillonnage de trames,
  éventuelle transcription) puis l'audio viendront ensuite.
- **Cap produit : une recherche AI dans le serveur**, où l'on pose des questions
  riches en langage naturel sur le fonds (« les étés à Bremblens avec Luna »,
  « les vidéos de Noël »). Cela suppose d'assembler des assertions/descriptions
  (à terme multimodales) et de les passer à un LLM de raisonnement — c'est là, et
  seulement là, que la **compression de contexte** (voir Outillage) deviendra
  pertinente, et que **exposer le serveur comme MCP** (`mcp-builder`) prendrait
  son sens, pour que n'importe quel agent interroge la médiathèque.

Ordre de valeur : consolider les images (reconnaissance, rangement, renommage,
UI), **puis** la vidéo, **puis** l'audio. Toute nouvelle abstraction (magasin de
vecteurs, magasin de sujets, schéma d'index) se conçoit en gardant ces deux
modalités futures à l'esprit, pour ne pas avoir à tout refaire.

## Déploiement & migration (nouveau PC) — ✓ FAIT (01/08)

Remonter le projet sur une machine neuve est automatisé et documenté
(`INSTALLATION.md`). Trois choses vivent séparément : le **code** (git clone),
l'**état** (`migrer.py` — archive de `photos.db`+wal/shm + configs `.txt`,
**testé**), l'**environnement** (`installer.py` — `.venv`, torch CUDA/CPU auto,
deps `requirements.txt`, `ollama pull`, gabarits config, `--check` doctor,
`--prewarm`, `--autostart`). Lanceurs `1 - Installer (nouveau PC).bat`,
`Migrer - Exporter/Importer …bat` (ASCII pur). Les **daemons de maintenance**
vivant dans le serveur, « démarrer le serveur » relance tout — pas de tâche
Windows à recréer. Les **noms humains** sont dans les XMP (voyagent avec le NAS).
Reste à **valider sur le vrai nouveau PC** (`installer.py` non testable hors
Windows ; `--check` diagnostique).

## Décisions documentées

Toute évaluation aboutit à une entrée dans `eval/DECISIONS.md`. Quatre idées y
ont été **rejetées sur mesure** : les contre-exemples pour la classification,
les prototypes multiples pour les animaux, **MegaDescriptor** (deux fois :
une mesure invalide, puis une mesure valide), la **résolution des découpes**,
et `sqlite-vec`
(numpy exhaustif suffit, 10 ms sur 100 000 vecteurs).

Rejeter une idée sur mesure vaut autant qu'en adopter une : c'est ce qui évite
de la retester dans six mois. **Encore faut-il que la mesure soit valide** :
deux entrées du journal documentent des bancs d'essai qui ne mesuraient pas ce
qu'ils prétendaient — l'un circulaire, l'autre inéquitable.
