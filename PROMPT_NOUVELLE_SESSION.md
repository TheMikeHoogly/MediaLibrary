# Reprise — MediaLibrary, après le 4 octobre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md` et `docs/DECISIONS_OUTILLAGE.md`,
> les chiffres dans `PERFORMANCE.md`, les choix de Mike dans `QUESTIONS_MIKE.md`.

---

## 0. Ce qui vient de se passer — 04/10 (Mike présent, ordre « 2, 1, 3, 4 »)

Cinq livraisons, toutes fusionnées dans `main` par l'agent, chacune vue en réel :

1. **`668b8bb` — thermique.** « 🔥 CHAUD … BRIDAGE THERMIQUE » à 36 °C : le
   drapeau de bridage était levé au REPOS (1 852 relevés, tous à 0–1 %, 0 sur
   95 sous charge). « CHAUD » ne vient plus que de la température (≥ 85 °C) ;
   le drapeau ne compte que si `util` ≥ `THERMIQUE_CHARGE_PCT` (10 %).
2. **`ec0004a` — `/api/sujets/list` 2,2 s → 0,6 s** (1er appel après
   démarrage 3,5 → 0,63 s). `_lieux_des_cles` mémorise la règle des lieux par
   chemin (sert aussi la recherche par lieu), `_prechauffer_lieux` au
   démarrage, `_compter_sujets` en une passe. `PERFORMANCE.md` § 3.27.
   **Et la file de revue** : « Voir les 24 suivantes » (`?depuis=`), compteur
   de famille qui baisse enfin à chaque verdict.
3. **`f105663` — planche du fonds 7,5 → 4,1–4,4 s** : rendu par tranches de
   600 cases (le navigateur bâtissait 44 430 cases : 2,8 s invisibles du
   serveur). Fiche « compacte » ÉCARTÉE par la mesure (gzip faisait déjà le
   travail). Choix de Mike : « l'allègement d'abord ». § 3.28.
4. **B3 tranché par Mike — pas de campagne** : le filet des pièces lit aussi
   les DESCRIPTIONS (`tagging_meta.DESC_PIECES`). Documents **22 → 87** en
   réel. Vérifier que cette 5ᵉ livraison est bien dans `main` (branche
   `feat/b3-le-filet-lit-les-descriptions`).

Contre-vérifications qui ont servi : la fiche compacte (annoncée ~2× moins de
Mo, mesurée 3,2 → 2,8 Mo gzippés) ; la règle d'élagage de la mémoire des lieux
(un petit compte l'aurait vidée à chaque appel — corrigée avant livraison).

---

## 1. Par où commencer

1. **Vérifier l'état réel** — `.git/HEAD`, `.git/logs/HEAD`,
   `.git/logs/refs/heads/main`, et le dernier rapport de `_etat_git.json`.
2. **`QUESTIONS_MIKE.md`** : aucune question ouverte.
3. **Cibles, par ordre de valeur** :
   - **la vraie pagination de la planche** (§ C3) : reste ~3,9 s SERVEUR sur
     le fonds — `mode_index` ~1 s, `envoi` ~1 s (gzip niveau 6 ≈ 0,5 s ; le
     niveau 1 rendrait ~270 ms contre +0,9 Mo — à juger pour les comptes
     distants), `gabarit`, `marques`, `index`, `motifs`. Plusieurs sessions :
     tri/filtres côté serveur, visionneuse, diaporama ;
   - **`/api/sujets/list`** : il reste `comptage` ~220 ms et `animaux` ~250 ms
     (passe des vignettes sur `ANIMAL_STORE`) — sans urgence ;
   - **la vue d'un NON-admin, prouvée à l'écran** (`verifier_non_fuite.py`,
     deux comptes) — geste de Mike.
4. **Gestes de Mike** : masquer **KB5124008** s'il revient (pause Windows
   Update jusqu'au 17.10) ; e-mails d'invitation (3 brouillons) ; Tailscale
   (Papa, Flo, port 8080) ; D1 copie hors site.
5. **Sauvegardes** : 16 échecs / 167 réussites dans le journal, chacun
   rattrapé au cycle suivant (NAS absent, ou `VACUUM` pendant une requête).
   À surveiller, pas à corriger sans un échec qui dure.

---

## 2. Les pièges

- **Le modèle à copier pour les briques 4 et 5 est la brique 3** (18/09) :
  une règle PURE dans `visibilite` (l'appelant fournit la donnée, la règle ne
  lit rien), un appelable de plus passé à `brancher` pour les CINQ magasins,
  un banc de RÈGLE (`test_visibilite`) et un banc de CÂBLAGE
  (`test_masque_personnel`, découpé sur l'ARBRE du source, docstrings
  retirées), et un droit que l'écran DEMANDE au serveur au lieu de le recopier.
- **La preuve de non-fuite route par route reste à Mike** :
  `verifier_non_fuite.py` veut deux comptes et leurs mots de passe.
- **L'agent de banc rend l'ordre à la FIN, pas au début.** Écrire trois ordres
  à la suite n'en fait tourner qu'un : les suivants sont écrasés, et le canal
  revenu à `rien` ne veut pas dire « fini ». Un ordre, puis attendre que
  `_etat_banc.json` porte CET ordre (`dernier.ordre`), puis le suivant.
  Attrapé le 18/09 en croyant avoir lancé trois bancs.
- **Les bancs ne tournent pas dans la VM.** Sur les 78 visés par la livraison,
  trois sont rouges sous Linux et VERTS sous Windows : `test_exiftool_preserve`
  (exiftool n'existe pas dans la VM), `test_cache_vignettes` (il lit l'index
  réel, 86 s), `test_galerie_enrichissement` (règles de chemin Windows).
  La VM sert à ÉCRIRE et à faire tourner les bancs PURS ; le juge est l'agent.
- **`/api/maint/status` est derrière la porte** : depuis la machine, sans
  cookie, il rend 401 — donc `maint.lourde` n'est PAS lisible par l'agent de
  banc. Pour savoir si un travail lourd tourne avant de redémarrer : le
  journal (`_journal_serveur.log`), où l'énumération NAS (~275 s toutes les
  ~30 min) et la sauvegarde horaire se lisent en clair.
- **La dernière bannière du journal** : `sed -n '/===== DEMARRAGE/,$p'` attrape
  la PREMIÈRE. Utiliser `tail -n +$(awk '/===== DEMARRAGE/{n=NR} END{print n}'
  fichier)`.
- **Un rapport de sonde est un CACHE** : `docs/motion_photos.json` ne se croit
  qu'avec `--frais`, et le bat 42 le lit tel quel.
- **Le XMP d'une Motion Photo survit au strip** : ne jamais compter sur lui.
- **exiftool et les chemins accentués** : passés sur la ligne de commande, ils
  arrivent mutilés (« File not found », une entrée de moins dans le lot, aucune
  erreur). **8,4 % du fonds** (3 714 clés sur 44 477). Tout appel passe par
  `exiftool_json` et son fichier d'arguments.
- **Un banc qui INJECTE une lecture ne tient que la règle.** Quand une règle
  dépend d'un outil externe, une mesure doit lire cet outil au moins une fois
  sur de vraies données.
- **Un banc qui découpe le source sur le TEXTE mesure ses VOISINS** — et sa
  propre prose. Découper sur l'ARBRE, docstring retirée.
- **Un composant canonique se réutilise TEL QUEL ou se laisse tranquille.**
  `.vue` est la cellule CARRÉE de la planche contact. Vu à l'écran, pas à la
  lecture — **regarder la page, pas seulement ses bancs.**
- **La grille récursive vient de l'INDEX** : une photo déposée à l'instant dans
  un SOUS-dossier n'y paraît qu'au prochain scan (~30 min) — et une photo
  effacée y reste visible jusque-là. Son propre dossier est à jour tout de suite.
- **Le rangement par année ne s'applique JAMAIS tout seul** : la maintenance
  bâtit le plan, le bat 26 l'applique, précédé de `verifier_plan_annee.py` —
  **une collision n'est pas une permission d'effacer**.
- **Le recensement dure 1 h 09** et **chaque redémarrage le tue**.
- **Deux balayages SMB simultanés** : l'énumération passe de 305 s à 2 100 s.
- **Windows : KB5124008 casse Plan9**, donc `device_bash`. UBR **9278**,
  Windows Update en pause jusqu'au 17.10. `Get-HotFix` MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **La VM n'atteint pas le LAN** : tout ce qui interroge le serveur passe par
  l'agent de banc (`mesure_etat_serveur.py` pour l'état) ou par **Chrome**.
- **Chrome, jamais le navigateur intégré** (demande de Mike, 13/09) — et
  Chrome peut être injoignable : deux navigateurs sont enregistrés sur le
  compte, il faut choisir celui de `MSI-Mike`, et si l'extension ne répond
  pas, `mesure_etat_serveur.py` remplace l'œil sur l'ÉTAT, jamais sur la PAGE.
- **Git : jamais depuis la VM**, même en lecture apparente — un `git status`
  y laisse un `.git/index.lock` vide que la VM ne peut pas effacer sans
  permission, et qui bloquerait l'agent (arrivé le 04/10). Lire `.git/HEAD`
  et `.git/logs/*` en texte, rien d'autre. Préfixes de branche
  admis : `feat|fix|chore|docs|test`.
- **L'agent git consomme l'ordre AVANT de travailler**, et met **~7 min**
  quand `server.py` est touché (il fait tourner ~80 bancs). Le 04/10 je l'ai
  cru « bloqué » au bout de 5 min : il ne l'était pas. C'est `_etat_git.json` et
  son `dernier.quand` qui disent si c'est fini, jamais le canal.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.
- **Un banc qui cite un appel AU CARACTÈRE PRÈS interdit la ligne suivante.**
  Juger un BLOC, pas une mise en page.
- **`os.path` ne reconnaît pas `\\` hors Windows** : normaliser soi-même.
- **`hidden` perd contre tout `display`** d'une classe plus spécifique. Tout
  nouvel élément de la barre qui naît caché : sa règle `[hidden]`.
- **Un onglet Chrome en arrière-plan ne déclenche AUCUN `IntersectionObserver`**
  (ni `loading="lazy"`, ni vignettes, ni tranches de la planche). Une capture
  d'écran force un rendu : c'est elle qui fait avancer un essai de défilement.
- **La veille et le NAS** : ses vignettes portent `veille=1`, qui DISPENSE la
  requête de `note_heavy_activity()`. Tout nouveau client ambiant doit faire
  pareil, sinon le fond ne tourne plus jamais.
- **Chrome piloté** : le premier clic après un chargement est parfois perdu.
- **Suppression dans le dépôt** : elle demande une permission par session. Ne
  JAMAIS écrire de fichier d'essai à la racine du dépôt : `$HOME` de la VM,
  hors `mnt/`.

## 3. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` (ou `commit` si Mike est absent) →
**vérifier dans `.git/logs/refs/heads/main`**.

Et, après toute analyse : **la contre-vérifier** (règle 11) — la falsifier,
pas la confirmer. Le 18/09 elle a servi deux fois : la règle du mot de passe
retirée d'une copie du module, trois cas du banc tombent (donc le banc mord) ;
et trois bancs rouges dans la VM, relancés sous Windows, se sont révélés verts
— conclure « ma modification a cassé trois bancs » aurait coûté la matinée.
