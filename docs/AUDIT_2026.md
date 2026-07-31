# Audit & roadmap — Photothèque locale (juillet 2026)

Cible matérielle réelle : **RTX 3050 Laptop, 4 096 Mo de VRAM**, corpus sur NAS SMB
(`\\NAS-Bremblens\home\Photos`). Toutes les recommandations ci-dessous sont filtrées par
cette contrainte : ce qui ne tient pas dans 4 Go n'est pas retenu, même si c'est meilleur.

---

## 1. Ce que le projet fait déjà bien

Il faut le dire avant de critiquer, parce que ça oriente la suite :

- **Zéro dépendance côté serveur.** `http.server` + stdlib. Un seul `.py` à copier, aucun
  build, aucun Docker. C'est un choix architectural fort et il faut le préserver.
- **Pipelines IA séparés et versionnés.** `ANIMAL_PIPELINE_VERSION = "yolo11s|det0.30|dinov2_base"`
  avec `migrate_animal_pipeline()` qui relance détection + empreintes mais **préserve les noms**.
  C'est de la vraie hygiène MLOps, rarement vue dans un projet perso.
- **Écriture atomique de l'index** (`tmp` + `os.replace`, avec repli non-atomique sur verrou SMB).
  Le commentaire explique *pourquoi*. Excellent.
- **Arbitrage GPU opportuniste** (`FACE_GPU_MIN_FREE_MB`, `PET_GPU_MIN_FREE_MB`,
  `ANIMAL_GPU_MIN_FREE_MB`) : chaque pipeline monte sur CUDA seulement si la VRAM est libre.
  L'intention est juste — l'implémentation est à centraliser (§4.1).
- **Ré-embedding adaptatif des visages faibles** (`REEMBED_*`) qui cède le NAS après une
  requête UI (`REEMBED_UI_QUIET = 12`). Très peu de logiciels grand public font ça.
- **Vérité stockée dans les fichiers**, pas seulement en base : les tags `personne:Nom` /
  `animal:Nom` sont écrits en métadonnées XMP via exiftool. Le travail survit à l'appli.

Le projet n'est pas un prototype. C'est un système. Les critiques qui suivent sont des
critiques de mise à l'échelle et d'expérience, pas de compétence.

---

## 2. Dette structurelle — les 5 points qui bloquent la suite

### 2.1 Le monolithe de 7 472 lignes

`server.py` contient la config, les stores, 4 pipelines ML, 7 workers threadés, le routeur
HTTP et **7 pages HTML complètes en chaînes littérales** (`HTML_PAGE`, `GALLERY_PAGE`,
`BROWSE_PAGE`, `MAP_PAGE`, `PETS_PAGE`, `FACES_PAGE`, `PEOPLE_PAGE`). Conséquences concrètes :

- Aucun outil ne comprend le CSS ou le JS : pas de linter, pas de coloration, pas
  d'autocomplétion, pas de formatage. Les erreurs de CSS se découvrent à l'œil.
- Les tokens visuels sont **dupliqués 7 fois**. `#0f0f0f`, `#0a84ff`, `#161616`, `border-radius: 8px`
  réapparaissent dans chaque page avec des variantes involontaires (`.pchip` a `color: #cbd`,
  `.chip` a `color: #bbb` — sans raison).
- Chaque édition de page force Claude (ou toi) à relire un fichier de 313 Ko.

**Ce n'est pas une raison d'abandonner le zéro-build.** La sortie propre : garder un serveur
Python sans dépendances, mais servir les assets depuis des fichiers `ui/*.css` / `ui/*.js`
lus au démarrage (ou embarqués à la volée par un petit `bundle.py` de 30 lignes si tu veux
conserver le mono-fichier distribuable). Le meilleur des deux.

### 2.2 Les stores JSON ne passeront pas l'échelle

`TagStore` charge **tout** le JSON en mémoire et **réécrit tout le fichier** à chaque `set()`.
Avec 16 120 vignettes de visages déjà présentes et des embeddings base64 stockés dans
`faces_index.json`, tu es sur une courbe O(n) par écriture et O(n²) par session de nommage.

Chiffre d'ordre de grandeur : un embedding InsightFace = 512 float32 = 2 Ko brut, ~2,7 Ko en
base64. 16 000 visages ≈ **43 Mo réécrits à chaque sauvegarde**, sur SMB.

**Cible : SQLite.** Elle est dans la stdlib — le zéro-dépendance est préservé. Un seul fichier
`photos.db`, écritures transactionnelles, index sur les clés, plus de réécriture globale.
Et surtout : ça débloque §3.4 (recherche vectorielle).

### 2.3 Pas de recherche sémantique

Aujourd'hui l'utilisateur cherche par **chips de tags** générés par un VLM, plus un filtre
texte `#q` qui fait du `includes()` sur les mots-clés. Il ne peut pas demander
« Luna endormie sur le canapé en hiver ». C'est le plus grand écart fonctionnel avec l'état
de l'art 2026, et c'est aussi le plus rentable (§3.1).

### 2.4 La grille ne tient pas 100 000 photos

`grid-template-columns: repeat(5, 1fr)` en dur, `repeat(3, 1fr)` sous 700 px, et le DOM contient
une `.cell` par photo. Immich fait défiler 100 000+ assets sans lag grâce au **virtual scroll** ;
ici, au-delà de quelques milliers de cellules, le navigateur mobile décroche. Il manque aussi
la densité adaptative (`auto-fill, minmax()` + `container queries`) et le
`justified layout` (rangées de hauteur égale, ratios respectés) qui est la convention du domaine.

### 2.5 Aucun plancher de qualité UI

Constats à la lecture des 7 blocs `<style>` :

| Point | État | Impact |
|---|---|---|
| États de focus clavier | absents (`outline: none` sur les inputs, rien en remplacement) | inutilisable au clavier |
| `prefers-reduced-motion` | non respecté | `transform: scale(1.05)` au survol + diaporamas |
| Contraste | `color: #555` / `#666` sur `#0f0f0f` ≈ ratio 2,5:1 | sous le seuil AA (4,5:1) |
| Cibles tactiles | `.prop input` = 18×18 px, `.prop .x` = 1 px 5 px de padding | sous les 44×44 px recommandés |
| `aria-*`, rôles, libellés | absents | lecteurs d'écran aveugles |
| États vides / erreurs | non traités | l'utilisateur ne sait pas quoi faire |
| Annulation | aucune (`delete_cat`, `untag_cat` sont définitifs) | peur de cliquer |

Le dernier point est le plus grave pour l'usage réel : **le nommage de clusters est une tâche
de jugement, faite en série, sur téléphone, avec des erreurs inévitables.** Sans annulation ni
sélection par plage, la tâche est punitive.

---

## 3. État de l'art 2026, filtré pour 4 Go de VRAM

### 3.1 Le changement d'architecture le plus rentable : un encodeur, trois usages

Aujourd'hui chaque photo passe par `qwen3-vl:2b` qui **génère du texte** pour produire des
mots-clés. C'est le mauvais outil pour le tagging : lent, non déterministe, il faut un
`_salvage_tags()` et un `parse_tags()` pour rattraper le JSON malformé — le code le prouve.

**SigLIP 2** (Google, ViT-B 86M / So400m 400M) est un encodeur vision-langage multilingue qui
place images et textes dans le même espace vectoriel. Il surpasse SigLIP à toutes les échelles
en classification zéro-shot et en recherche image↔texte, et il est **nativement multilingue** —
donc les tags français sortent sans traduction. Un seul passage d'encodage par photo donne :

1. **Le tagging**, par classification zéro-shot contre un **vocabulaire contrôlé** que tu
   définis (`plage`, `neige`, `repas de famille`, `intérieur`, `nuit`…). Déterministe,
   cohérent d'une photo à l'autre, et tu peux ajouter un tag rétroactivement **sans réanalyser
   les photos** — il suffit d'encoder la nouvelle étiquette texte. C'est impossible avec un VLM.
2. **La recherche en langue naturelle**, en encodant la requête de l'utilisateur (§2.3).
3. **La déduplication et les « photos similaires »**, gratuitement, par distance cosinus.

Le VLM reste utile, mais pour ce qu'il fait mieux qu'un encodeur : la **description en phrase**
d'une photo (accessibilité, légende d'album). On le réserve à ça, à la demande, pas sur
100 000 photos.

Budget VRAM : SigLIP 2 ViT-B en ONNX INT8 tient largement sous 500 Mo, et l'encodage tourne
même correctement en CPU. C'est *moins* lourd que la situation actuelle.

**Recommandation : pipeline hybride.** SigLIP 2 comme colonne vertébrale (tags + recherche +
similarité) ; `qwen3-vl:2b` gardé pour la description à la demande.

### 3.2 VLM locaux — comparatif à 4 Go

| Modèle | Taille | Tient en 4 Go | Verdict pour ce projet |
|---|---|---|---|
| **qwen3-vl:2b** | 2B | ✅ 100 % VRAM | **Garder.** Ton choix actuel est le bon : `modele.txt` documente déjà que le 4b déborde. |
| qwen3-vl:4b | 4B | ❌ déborde en RAM | Confirmé par ton propre banc d'essai (~3× plus lent). |
| MiniCPM-V 4.5 | 8B | ❌ (~6 Go) | Hors budget. |
| Moondream 2/3 | 1,9B | ✅ (<4 Go) | Rapide mais compréhension limitée des scènes complexes, taux d'hallucination plus élevé. Utile seulement comme repli. |
| SmolVLM2 | 2,2B | ✅ (~2 Go) | Alternative crédible si tu veux libérer de la VRAM pour les visages. |
| Florence-2 | 0,23B / 0,77B | ✅ largement | **À tester sérieusement.** Décrit comme la meilleure qualité parmi les plus petits modèles, et il fait nativement caption + detection + OCR. Un candidat pour remplacer *à la fois* une partie de YOLO et du tagging. |

L'action concrète n'est pas de changer de modèle sur la foi de ce tableau, mais de **mesurer**
sur ton corpus. C'est exactement ce que fait la skill `vision-eval` créée en §5.

### 3.3 Reconnaissance faciale — 3 gains sans changer de modèle

`buffalo_l` (InsightFace, ArcFace entraîné sur Glint360K) reste **le bon choix en 2026** :
ArcFace est toujours la fonction de perte la plus utilisée en production, et les checkpoints
open source récents en dérivent. Ne change pas de modèle. Change trois choses autour :

1. **Quantification INT8 des embeddings.** InsightFace Server a ajouté en 2026 une
   quantification INT8 *préservant la précision*, avec recherche sur 50 M+ images sur un seul
   GPU. Appliqué à ton `faces_index.json` : 512 int8 = 512 octets au lieu de 2 Ko, soit
   **~4× moins de stockage et de bande passante SMB**, sans perte mesurable. Résout une
   partie de §2.2.
2. **Le clustering, pas le modèle, est ton maillon faible.** `cluster_faces(vecs, meta, sim_thr,
   min_size)` avec `FACE_CLUSTER_SIM = 0.50` puis `_purify_clusters()` et un test de scission
   à `CLUSTER_SPLIT_SIM = 0.55` : tu as reconstruit à la main, par tâtonnement de seuils, ce que
   **HDBSCAN** ou **Chinese Whispers** font par densité, sans seuil global. Un seuil unique ne
   peut pas marcher pour un corpus qui mélange portraits nets et visages de 90 px de profil.
   C'est le changement qui fera le plus pour la qualité perçue du nommage.
3. **AdaFace pour les visages de mauvaise qualité.** AdaFace adapte sa marge selon la qualité
   de l'image ; sur les scénarios sans contrôle de qualité, il fait mesurablement mieux que
   les modèles standards. Tu as déjà tout l'appareillage pour l'exploiter : `_face_is_poor()`,
   `REEMBED_MIN_SCORE = 0.78`, `REEMBED_MIN_FACE_PX = 90`. Au lieu de **ré-embedder les visages
   faibles avec le même modèle**, ré-embedde-les avec un modèle fait pour eux. Les benchmarks
   qui séparent les modèles aujourd'hui sont IJB-C et **TinyFace** (basse résolution) — LFW est
   résolu, tout le monde est au-dessus de 99 %, ne l'utilise pas pour arbitrer.

### 3.4 Re-ID des chats — remplacer DINOv2 par MegaDescriptor

C'est la recommandation la plus nette du rapport. Tu utilises
`vit_base_patch14_dinov2.lvd142m` pour distinguer Caline, Inti et Luna.

**MegaDescriptor** est un modèle de fondation dédié à la re-identification d'individus sur un
large éventail d'espèces. Il est état de l'art sur les jeux de données de re-ID animale et
**surpasse significativement CLIP et DINOv2**. La littérature 2025-2026 est explicite : un
backbone spécialisé fournit une meilleure variété d'embedding initiale qu'un backbone
généraliste pour cette tâche précise.

- Disponible en variantes Swin-T / Swin-B — **le Swin-T tient sans problème dans 4 Go**, et
  devrait même être *plus léger* que ton `vit_base` actuel (`PET_GPU_MIN_FREE_MB = 1800`).
- Outillage : **WildlifeDatasets**, boîte à outils open source de re-ID animale, pour la
  calibration des seuils.
- Évaluation : **PetFace** (jeu de données et benchmark d'identification animale à grande
  échelle) — c'est le benchmark pertinent pour des chats domestiques, pas un benchmark faune.
- À noter : un modèle plus récent dépasse MegaDescriptor sur les espèces non vues
  (+19,2 % top-1 en moyenne sur 33 espèces) — à surveiller, mais MegaDescriptor est le choix
  sûr et disponible aujourd'hui.

Ton `ANIMAL_PIPELINE_VERSION` rend cette migration propre : passer à
`"yolo11s|det0.30|megadescriptor_t"` relance les empreintes et **conserve les noms**.
L'infrastructure est déjà là. C'est un changement à faible risque et fort gain.

Un mot sur `PET_CLUSTER_SIM = 0.60  # à calibrer` : ce commentaire est honnête. Avec
MegaDescriptor tu auras un espace d'embedding où les seuils *ont un sens*, et WildlifeDatasets
pour les calibrer sur tes trois chats plutôt qu'à l'intuition.

### 3.5 Recherche vectorielle — sqlite-vec

Pour stocker et interroger les embeddings SigLIP 2 / InsightFace / MegaDescriptor :

| Option | Verdict |
|---|---|
| **sqlite-vec** | **Retenu.** Extension SQLite, tourne sur Windows / Linux / macOS / Raspberry Pi / WASM. Recherche exhaustive très rapide, compétitive avec faiss et usearch en mémoire. Un seul fichier, cohérent avec ta philosophie mono-fichier, et il vit dans la même base que tes métadonnées (§2.2). |
| faiss | Bibliothèque, pas une base : ni persistance, ni API, ni gestion — tout à construire. Surdimensionné pour 100 k vecteurs. |
| usearch | Bon compromis HNSW, mais une dépendance de plus pour un gain nul à cette échelle. |

À 100 000 photos × 768 dimensions, la recherche exhaustive est de l'ordre de quelques dizaines
de millisecondes. Tu n'as pas besoin d'un index approximatif. `sqlite-vec` suffit et simplifie.

### 3.6 Arbitrage VRAM — un seul ordonnanceur

Tu as aujourd'hui **quatre politiques GPU indépendantes** (`FACE_GPU_MIN_FREE_MB = 1200`,
`ANIMAL_GPU_MIN_FREE_MB = 1600`, `PET_GPU_MIN_FREE_MB = 1800`, plus Ollama avec
`keep_alive: "30m"` qui garde le modèle résident). Chacune interroge `hw_state()` et décide
seule. Sur 4 096 Mo, trois consommateurs qui décident indépendamment finiront par se marcher
dessus — et le `keep_alive: 30m` d'Ollama signifie que la VRAM reste occupée 30 minutes après
la dernière photo taguée.

**Cible : un `GpuArbiter` unique**, avec des baux (leases) explicites, une file de priorité
(UI interactive > tagging > visages > chats) et un seul point de vérité sur la VRAM libre.
C'est ~120 lignes et ça remplace quatre heuristiques dispersées. Combiné à l'INT8/ONNX (§3.3),
la contention devient largement théorique.

---

## 4. Expérience utilisateur — diagnostic et direction

### 4.1 Le problème de fond n'est pas esthétique, il est de tâche

L'application propose deux tâches très différentes et les traite avec la même interface :

- **Consulter** (galerie, carte, diaporama) — navigation, plaisir, sérendipité.
- **Superviser l'IA** (nommer les clusters, confirmer les propositions, corriger les erreurs) —
  travail répétitif, par lots, à fort besoin de vitesse et de réversibilité.

La seconde est celle où l'utilisateur passe du temps pénible, et c'est celle qui est la moins
outillée. Les gains les plus sensibles :

1. **Annulation partout.** Toute action destructive (`untag_cat`, `delete_cat`,
   `write_person_untag`) devient une action réversible pendant 10 secondes via un toast
   « Annuler ». Techniquement : une file d'opérations différées, ce que tu as déjà avec
   `PERSON_QUEUE`.
2. **Sélection par plage** (clic + Maj), « tout sélectionner », « inverser » — indispensable
   quand un cluster propose 300 vignettes (`find_more(name, limit=300)`).
3. **Raccourcis clavier** sur le tri des clusters : `1-9` pour assigner à une personne connue,
   `Espace` pour confirmer, `X` pour rejeter, `Z` pour annuler. C'est ce qui transforme une
   heure de clics en dix minutes.
4. **Un centre de tâches** au lieu du bandeau `#pending` de 8 px : ce que l'IA fait maintenant,
   combien il reste, sur quel appareil (CPU/GPU), et un bouton pause. Tu as déjà toutes les
   données (`PET_EMBED_STATE`, `hw_state()`, `system_busy()`, les tailles de files).
5. **La recherche en langue naturelle** (§3.1) — elle remplace à elle seule une bonne partie
   de la navigation par chips.

### 4.2 Direction visuelle proposée : « chambre noire »

L'UI actuelle est un gris neutre `#0f0f0f` avec l'accent bleu iOS `#0a84ff`. C'est propre, et
c'est exactement le réglage par défaut : rien dans cette palette ne dit *photographie de
famille*, et le bleu système est le choix que fait n'importe quelle application.

La proposition part du sujet lui-même — une **archive photographique** — et de son atelier :
la chambre noire.

**Palette (matériaux, pas décoration)**

| Rôle | Valeur | Justification matérielle |
|---|---|---|
| Fond | `#0C0B0A` | Noir **chaud**, pas gris neutre : l'obscurité de la chambre noire, pas celle d'un terminal. Les photos y paraissent plus chaudes et plus vivantes. |
| Papier | `#EDE7DC` | Les surfaces de travail (panneaux de nommage, feuilles de contact) sont du **papier baryté**, pas des rectangles gris. C'est ce qui distingue cette interface des dizaines d'UI sombres monochromes. |
| Veilleuse | `#FF7A1A` | La **lampe inactinique** : ambre. Réservée à un seul sens — « en cours de développement », c.-à-d. les états où l'IA travaille. Un signal, jamais une décoration. |
| Encre | `#C8321E` | Rouge de retouche : destructif, correction. |
| Graphite | `#6E6862` | Texte secondaire, à `4,6:1` sur le fond — au-dessus du seuil AA, contrairement aux `#555`/`#666` actuels. |

Le risque assumé, et pourquoi il tient : un fond quasi noir avec un accent vif unique est un
cliché du design généré. Ce qui sort la proposition du cliché, c'est la **couche papier** :
l'interface alterne salle sombre (visionnage) et surfaces claires (travail). Les pages de
nommage sont du papier ; la galerie est la salle. C'est une distinction fonctionnelle rendue
visible, pas un effet.

**Typographie**

- Affichage : une grotesque **condensée** à interlettrage serré — les titres de section, les
  noms de personnes et de chats. Le caractère de la page.
- Texte : la pile système actuelle. Elle est bonne, on la garde.
- Utilitaire : **une monospace pour les données** — EXIF, scores de similarité, coordonnées
  GPS, compteurs. Justification directe : ce sont des données, elles s'alignent en colonnes,
  et `sim 0.62` en monospace se lit comme une mesure et non comme du texte.

**Signature : la planche contact**

La galerie devient une vraie **planche contact** : gouttières fines, rangées justifiées, et le
numéro de vue en monospace dans la marge. Les photos non encore traitées par l'IA portent un
liseré ambré — elles sont « encore dans le bain ». Le statut du pipeline devient une propriété
visible de la photo, pas une bannière séparée. C'est l'élément dont on se souvient, et il est
utile.

**Plancher de qualité, non négociable**

- `:focus-visible` visible partout (un liseré ambré de 2 px, cohérent avec la veilleuse).
- `@media (prefers-reduced-motion: reduce)` respecté sur tous les survols et diaporamas.
- Cibles tactiles à 44 px minimum. Les cases à cocher de 18 px de `.prop input` passent à
  une zone cliquable pleine vignette.
- Contraste AA sur tout le texte.
- `content-visibility: auto` + `container queries` pour la grille, en attendant le virtual
  scroll complet.

### 4.3 Plateforme web 2026 — ce qui remplace du JavaScript

Trois fonctionnalités mûres en 2026 s'appliquent directement ici :

- **View Transitions API** : la navigation entre galerie → photo → personne devient une
  transition continue (la vignette *devient* la photo plein écran). Support universel en 2026.
  Sur un serveur qui rend des pages complètes, la variante multi-document donne des
  transitions natives **sans SPA** — exactement ce qu'il te faut pour garder l'architecture.
- **Container queries** : arrivées au stade « utilise-les simplement » en 2026. La densité de
  la grille s'adapte à son conteneur, plus à la largeur de l'écran — ce qui règle proprement
  le cas de la grille de propositions dans un panneau latéral.
- **`content-visibility` / `contain-intrinsic-size`** : gain de rendu immédiat sur les grandes
  grilles, en attendant un virtual scroll à la Immich.

---

## 5. Outillage Claude — ce qu'il faut installer et ce que j'ai créé

### 5.1 Skills officielles à installer

Dans Claude Code, à la racine du projet :

```
/plugin marketplace add anthropics/skills
/plugin install example-skills@anthropic-agent-skills
```

Deux comptent pour ce projet :

- **`frontend-design`** — pousse vers une UI distinctive (typographie affirmée, mises en page
  intentionnelles) au lieu de la « bouillie IA » : dégradés violets, mises en page passe-partout.
  C'est la skill qui a servi à construire la direction du §4.2.
- **`web-design-guidelines`** — à utiliser comme **porte de revue avant de livrer**. La
  combinaison recommandée est : `frontend-design` pour produire, `web-design-guidelines` pour
  valider.

Le format `SKILL.md` est un standard ouvert (voir `agentskills.io`) : une skill lit ses
métadonnées, et Claude ne charge les instructions complètes que si la tâche correspond.
Une skill **écrase les réflexes par défaut du modèle** — c'est précisément son intérêt ici.

### 5.2 Skills spécifiques au projet — créées dans `.claude/skills/`

Les skills génériques ne connaissent pas ton projet. Les trois suivantes encodent tes
contraintes pour que **chaque future session Claude démarre outillée**, sans avoir à
réexpliquer le contexte.

| Skill | Ce qu'elle empêche |
|---|---|
| **`photo-ui`** | Que Claude réinvente une palette, réintroduise `#0a84ff`, oublie le focus clavier ou propose du React. Contient les tokens, les composants, le plancher d'accessibilité et l'interdiction du build step. |
| **`vision-eval`** | Qu'un modèle soit adopté « parce que le benchmark public est bon ». Impose un protocole : jeu de validation figé issu de *ton* corpus, mesure de VRAM réelle, comparaison contre le pipeline en place, et une décision écrite. |
| **`monolith-surgery`** | Qu'une édition de `server.py` casse un invariant : écriture atomique, versions de pipeline, préservation des noms lors des migrations, contention VRAM, cohérence entre les 7 pages. |

### 5.3 Autres capacités Claude applicables

- **Sous-agents de vérification.** Pour les changements risqués (migration SQLite, changement
  de modèle), lancer un agent dédié en lecture seule pour relire le diff avec un regard neuf.
  Les skills `engineering:code-review` et `engineering:architecture` que tu as déjà installées
  couvrent ça — `architecture` produira un ADR propre pour la décision MegaDescriptor.
- **Tâches planifiées.** Un rapport nocturne de santé de l'index : photos non taguées, clusters
  non nommés, visages faibles en attente de ré-embedding, dérive des seuils. Tu lis le résultat
  le matin au lieu d'aller le chercher dans l'UI.
- **Artifacts Cowork.** Un tableau de bord persistant du pipeline, rechargeable, plutôt qu'une
  page servie par `server.py` — utile quand le serveur est justement arrêté.
- **`skill-creator`** pour faire évoluer les trois skills ci-dessus, avec évaluation du
  déclenchement.

---

## 6. Roadmap priorisée

Ordonnée par **gain ressenti ÷ risque**, pas par élégance technique.

### Vague 1 — Fondations (débloque tout le reste)

1. **SQLite à la place des stores JSON.** Migration lisible, réversible, stdlib uniquement.
   Garder un export JSON pour l'inspection. → résout §2.2, prérequis de §3.5.
2. **Embeddings de visages en INT8.** ~4× moins de stockage, aucune perte mesurable.
3. **`GpuArbiter` unique** avec baux et priorités. → remplace 4 heuristiques.

### Vague 2 — Le grand gain fonctionnel

4. **SigLIP 2 + sqlite-vec : recherche en langue naturelle.** C'est la fonctionnalité qui
   change la nature de l'application. Elle réutilise l'infrastructure de la vague 1.
5. **Tagging par vocabulaire contrôlé zéro-shot**, en parallèle du VLM actuel pour comparaison.
   Décision arbitrée par la skill `vision-eval`, pas à l'intuition.
6. **`animal:` → MegaDescriptor.** Bump de `ANIMAL_PIPELINE_VERSION`, noms préservés par
   `migrate_animal_pipeline()`. Faible risque, gain net sur la distinction Caline / Inti / Luna.

### Vague 3 — L'expérience

7. **Extraction des 7 pages HTML** vers `ui/` + design system (`tokens.css`). Aucun changement
   fonctionnel, mais tout le reste devient éditable.
8. **Refonte de la supervision** : annulation, sélection par plage, raccourcis clavier, centre
   de tâches. C'est le travail qui rend l'usage quotidien agréable.
9. **Plancher d'accessibilité** : focus, contraste, cibles tactiles, `reduced-motion`.
10. **Planche contact justifiée** + View Transitions + `content-visibility`.

### Vague 4 — Qualité de reconnaissance

11. **HDBSCAN ou Chinese Whispers** à la place du clustering par seuil unique.
12. **AdaFace** sur le chemin de ré-embedding des visages faibles (`_face_is_poor()`).
13. **Calibration mesurée** des seuils via WildlifeDatasets, évaluation sur PetFace / TinyFace.

Une remarque sur l'ordre : il est tentant de commencer par la vague 3, parce que c'est visible.
Mais l'extraction du HTML est beaucoup plus sûre une fois que les stores sont en SQLite — sinon
tu refactores deux fois. Et la vague 2 va introduire de nouvelles surfaces d'UI (la barre de
recherche sémantique) qu'il vaut mieux dessiner une seule fois, dans le nouveau système.

---

## Sources

État de l'art — modèles de vision :
- [Best Local Vision Models 2026: LLaVA, Qwen3-VL & Ollama — PromptQuorum](https://www.promptquorum.com/power-local-llm/local-vision-models-llava-ollama-2026)
- [Multimodal AI: The Best Open-Source Vision Language Models in 2026 — BentoML](https://www.bentoml.com/blog/multimodal-ai-a-guide-to-open-source-vision-language-models)
- [Top 10 Vision Language Models in 2026 — DataCamp](https://www.datacamp.com/blog/top-vision-language-models)
- [PhotoPrism — Model Comparison](https://docs.photoprism.app/developer-guide/vision/model-comparison/)
- [Compare Florence-2 vs. Moondream in 2026 — Slashdot](https://slashdot.org/software/comparison/Florence-2-vs-Moondream/)
- [Local AI for Photographers: Auto-Tag 100K Photos Without Cloud](https://localaimaster.com/blog/local-ai-photographers)

Encodeurs vision-langage et recherche sémantique :
- [SigLIP 2: Multilingual Vision-Language Encoders — arXiv 2502.14786](https://arxiv.org/abs/2502.14786)
- [SigLIP 2: A better multilingual vision language encoder — Hugging Face](https://huggingface.co/blog/siglip2)
- [Multimodal search using SigLIP-2 embeddings — Elasticsearch Labs](https://www.elastic.co/search-labs/blog/multimodal-search-siglip-2-elasticsearch)

Reconnaissance faciale :
- [deepinsight/insightface — GitHub](https://github.com/deepinsight/insightface)
- [ArcFace — InsightFace](https://insightface.ai/arcface)
- [Face Recognition Systems: Open Source Models & APIs (2026)](https://facecheck.id/Face-Search-face-recognition-api)

Re-identification animale :
- [WildlifeDatasets: An open-source toolkit for animal re-identification — arXiv 2311.09118](https://arxiv.org/abs/2311.09118)
- [PetFace: A Large-Scale Dataset and Benchmark for Animal Identification — arXiv 2407.13555](https://arxiv.org/html/2407.13555)
- [DS@GT AnimalCLEF: Triplet Learning over ViT Manifolds — arXiv 2509.12353](https://arxiv.org/pdf/2509.12353)
- [Multispecies Animal Re-ID Using a Large Community-Curated Dataset — arXiv 2412.05602](https://arxiv.org/html/2412.05602v1)
- [On Combining Animal Re-Identification Models to Address Small Datasets — IJCV](https://link.springer.com/article/10.1007/s11263-025-02708-9)

Recherche vectorielle locale :
- [Introducing sqlite-vec v0.1.0 — Alex Garcia](https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html)
- [Best Vector Databases in 2026: A Complete Comparison Guide — Firecrawl](https://www.firecrawl.dev/blog/best-vector-databases)
- [The Faiss library — arXiv 2401.08281](https://arxiv.org/pdf/2401.08281)

Design, UI et outillage agent :
- [anthropics/skills — frontend-design/SKILL.md](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md)
- [anthropics/skills — dépôt public des Agent Skills](https://github.com/anthropics/skills)
- [Equipping agents for the real world with Agent Skills — Anthropic](https://anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [11 Powerful Design & Frontend Skills for AI Agents](https://pixelsprompts.substack.com/p/11-powerful-design-and-frontend-skills)
- [CSS Innovations 2026: Emerging Features That Replace JavaScript — Locally Lost](https://locallylost.com/guides/css-innovations-2026-features-that-replace-javascript/)
- [immich-app/immich — GitHub](https://github.com/immich-app/immich)
