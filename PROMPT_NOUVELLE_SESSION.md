# Reprise — MediaLibrary, après le 16 septembre 2026 (soir)

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md` et `docs/DECISIONS_OUTILLAGE.md`,
> les chiffres dans `PERFORMANCE.md`, les choix de Mike dans `QUESTIONS_MIKE.md`.

---

## 0. L'état, en dix lignes

**17/09, quatre livraisons ; Flo essaie la photothèque, et ce qu'elle a
demandé est devenu le CHANTIER 19.**
1. **`/aide` réécrite** (P2) en quatre gestes ; **chacun trie ses dépôts** ;
   mot de passe dans le menu du compte ; lampe des dépôts réparée.
2. **Fin de keep-alive** : « Request timed out » ne s'écrit plus au journal
   (ce n'était pas une panne — 17 sur 17 à +28-30 s d'une réponse servie).
3. **Réglages sait supprimer un compte** (deux clics, pas de `confirm()`).
4. **Accès distant par Tailscale** préparé pour Papa (Bolivie) et Flo :
   trois brouillons Gmail prêts, NON envoyés (`docs/ACCES_DISTANT_TAILSCALE.md`).
5. **CHANTIER 19 — la vie privée à la demande** (`docs/CHANTIER_19_VIE_PRIVEE.md`) :
   brique 2 **livrée** (un dépôt d'`_Uploads` n'est visible que de son
   déposant, 44 445 clés en 27 ms) ; le filet « intime » est **mesuré et
   refusé en automatique** ; les briques 3, 4, 5, 6 restent à construire.

Acquis d'avant : veille (P1), campagne de retag ABANDONNÉE, un compte par
propriétaire (Mike admin, Flo, Papa).

---

## 1. Par où commencer

1. **Vérifier la livraison** dans `.git/logs/refs/heads/main`.
2. **CHANTIER 19**, dans cet ordre — le plan et les pièges sont dans
   `docs/CHANTIER_19_VIE_PRIVEE.md`, à relire AVANT d'écrire une ligne :
   - **Brique 6 d'abord, parce qu'elle est un trou** : « Changer mon mot de
     passe » n'exige pas le mot de passe ACTUEL — une session ouverte suffit
     à fermer la porte derrière soi. Puis l'**e-mail par compte**
     (`comptes.json`, hors git) : (a) rappel + (b) réinitialisation par
     l'admin ; le vrai « mot de passe oublié » par SMTP seulement si
     quelqu'un reste bloqué (choix de Mike à demander le moment venu).
   - **Brique 3** : « masquer cette photo » pour une personne reconnue
     (tranché : propriétaire + personne voient ; la personne seule lève ; la
     photo ne bouge pas ; l'état en base, jamais dans le XMP).
   - **Brique 5** : onglet Partage. **Défaut tranché** : liste vide = tout le
     monde pour Mike, Flo et Papa ; un compte créé ensuite part fermé. Donc
     TROIS états (`null` / `[]` / `[noms]`) et une migration qui pose `null`
     sur les trois comptes existants. Un banc doit prouver qu'une photo non
     partagée ne fuit ni par un compteur, ni par une fiche, ni par la
     recherche — le filtre reste AU MAGASIN.
   - **Brique 4** ensuite (les personnes reconnues voient leurs photos), qui
     ne se pose que sur la 5. Elle exige un index clé → noms en mémoire :
     mesurer avant/après, la grille du fonds est à 3,7 s.
   - **Brique 1** (filet intime) en dernier : file de revue, pas masquage.
3. **Ce qui n'est pas prouvé en réel** : la vue d'un NON-admin. Les bancs
   tiennent la règle ; un compte d'essai le montrerait à l'écran (Mike le
   crée, s'y connecte dans Chrome, le supprime après).
4. **P2, l'e-mail** : trois brouillons Gmail prêts, non envoyés. Mike envoie,
   mots de passe à part.
5. **Tailscale** : partager `msi-mike` avec `markushuegli@gmail.com` et
   `flolaeser@gmail.com`, limiter `autogroup:shared` au port 8080, rappeler
   l'expiration de clé. En attente que Mike se connecte à la console.
6. **D1, la copie hors site** : à Mike seul.

---

## 2. Les pièges

- **Un rapport de sonde est un CACHE** : `docs/motion_photos.json` ne se
  croit qu'avec `--frais`, et le bat 42 le lit tel quel. Relancer le banc
  (5 passes de 480 s, `--fils 4`) avant tout bat 42.
- **Le XMP d'une Motion Photo survit au strip** : ne jamais compter sur lui.

- **exiftool et les chemins accentués** : passés sur la ligne de commande, ils
  arrivent mutilés (« File not found », une entrée de moins dans le lot,
  aucune erreur). **8,4 % du fonds** est concerné (3 714 clés sur 44 477).
  Tout appel passe désormais par `exiftool_json` et son fichier d'arguments ;
  un nouvel appel écrit ailleurs doit faire pareil.
- **Un banc qui INJECTE une lecture ne tient que la règle.** Les durées vidéo
  étaient injectées ; c'est en allant les chercher pour de vrai que le défaut
  ci-dessus est apparu. Quand une règle dépend d'un outil externe, une mesure
  doit lire cet outil au moins une fois sur de vraies données.
- **Un banc qui découpe le source sur le TEXTE mesure ses VOISINS** — et sa
  propre prose. Deux bancs sont tombés là-dessus le 14/09 : l'un découpait
  vingt méthodes du routeur, l'autre lisait la docstring qui NOMME les mots
  qu'il interdit. Découper sur l'ARBRE, docstring retirée.
- **Un composant canonique se réutilise TEL QUEL ou se laisse tranquille.**
  `.vue` est la cellule CARRÉE de la planche contact (`aspect-ratio: 1` dans
  `components.css`) : la page `/arbitrage` l'avait reprise, une photo en
  portrait tenait sur un cinquième de la largeur. Vu à l'écran, pas à la
  lecture — **regarder la page, pas seulement ses bancs.**
- **La grille récursive vient de l'INDEX** : une photo déposée à l'instant
  dans un SOUS-dossier n'y paraît qu'au prochain scan (~30 min,
  `NAS_SCAN_CYCLES`) — et, symétriquement, une photo effacée y reste visible
  jusque-là. Son propre dossier, lui, est à jour tout de suite.
- **Le rangement par année ne s'applique JAMAIS tout seul** : la maintenance
  bâtit le plan, le bat 26 l'applique. C'est voulu. Et le bat 26 commence
  désormais par `verifier_plan_annee.py`, qui JUGE les collisions au lieu de
  les compter : **une collision n'est pas une permission d'effacer**.
- **Un instrument qui tranche au-delà de ce qu'il mesure est pire qu'un
  instrument muet.** `verifier_plan_annee` classait « deux vidéos distinctes »
  quatre fichiers de MÊME durée à la centième et 0,5 % d'écart de taille. D'où
  le verdict `VOISIN` et ses deux garde-fous : une borne de 5 % sur la taille,
  et le refus de voisiner deux durées INCONNUES — deux zéros sont égaux.
- **Le recensement dure 1 h 09** et **chaque redémarrage le tue**. Avant de
  livrer en rafale : `maint.lourde` dans `/api/maint/status`.
- **Deux balayages SMB simultanés** : l'énumération passe de 305 s à 2 100 s.
- **Windows : KB5124008 casse Plan9**, donc `device_bash`. UBR **9278**,
  Windows Update en pause jusqu'au 17.10. `Get-HotFix` MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **La VM n'atteint pas le LAN** : tout ce qui interroge le serveur passe par
  l'agent de banc ou par **Chrome** (`http://192.168.0.13:8080`).
- **Chrome, jamais le navigateur intégré** (demande de Mike, 13/09).
- **Git : jamais depuis la VM**, même en lecture apparente. Préfixes de branche
  admis : `feat|fix|chore|docs|test` — `perf/` a été refusé.
- **L'agent git consomme l'ordre AVANT de travailler** : le canal revenu à
  `rien` ne veut pas dire « fini ». C'est `_etat_git.json` qui le dit, et il
  faut comparer son `dernier.quand`, pas le mtime du fichier — ~6 min quand
  `server.py` est touché.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.
- **Un banc qui cite un appel AU CARACTÈRE PRÈS interdit la ligne suivante.**
  `test_sensibles` exigeait `brancher(_st, utilisateur_vu, sensible=…)` tel
  quel et a refusé la livraison quand la brique 2 lui a ajouté `depot=`.
  Juger un BLOC, pas une mise en page.
- **`os.path` ne reconnaît pas `\\` hors Windows** : une règle de chemin
  écrite avec lui répond autre chose au banc (Linux) qu'au serveur (Windows).
  Normaliser soi-même (`_depot_normal`). Attrapé le 17/09 par son banc.
- **`hidden` perd contre tout `display`** d'une classe plus spécifique. Tout
  nouvel élément de la barre qui naît caché : sa règle `[hidden]`, sinon
  `test_ui_global.HiddenCacheVraiment` tombe. Dans une PAGE, aucun banc ne
  le voit : regarder les pixels.
- **Un onglet Chrome en arrière-plan ne charge pas les `loading="lazy"`** :
  des vignettes vides sur une capture ne sont pas un défaut (vu le 16/09,
  `fetch` direct : 200 en 5 ms).

---

- **La veille et le NAS** : ses vignettes portent `veille=1`, qui DISPENSE
  la requête de `note_heavy_activity()`. Tout nouveau client ambiant (cadre,
  écran d'accueil) doit faire pareil, sinon le fond ne tourne plus jamais.
- **Chrome piloté** : le premier clic après un chargement de page est
  parfois perdu (le menu du compte ne s'ouvre pas) — recliquer, ce n'est pas
  un défaut de la page. Un clic par `ref` peut aussi manquer : préférer les
  coordonnées d'une capture fraîche.
- **Suppression dans le dépôt** : elle demande une permission par session.
  Ne JAMAIS écrire de fichier d'essai (mutations de banc) à la racine du
  dépôt : `$HOME` de la VM, hors `mnt/`.

## 3. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

Et, après toute analyse : **la contre-vérifier** (règle 11). Elle a travaillé
cinq fois le 14/09, et chaque fois elle a rapporté quelque chose : la prémisse
du chantier de la marche est tombée avant le code ; un compteur qui mélangeait
deux causes a été scindé avant d'être lu ; un banc qui injectait une lecture
masquait un défaut touchant 8,4 % du fonds ; une conclusion « aucun de ces 18
fichiers n'a de jumeau » était fausse parce que `os.path.basename` rend le
chemin ENTIER sur un chemin Windows sous Linux ; et la page `/arbitrage`,
regardée à l'écran, a montré une rotation que trois mesures n'avaient pas vue.
