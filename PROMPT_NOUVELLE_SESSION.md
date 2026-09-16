# Reprise — MediaLibrary, après le 16 septembre 2026 (soir)

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md` et `docs/DECISIONS_OUTILLAGE.md`,
> les chiffres dans `PERFORMANCE.md`, les choix de Mike dans `QUESTIONS_MIKE.md`.

---

## 0. L'état, en dix lignes

**16/09 au soir : P2, la moitié « démo » est livrée.** Choix de Mike :
enrichir `/aide`, pas de parcours guidé.
1. **`/aide` réécrite** : les quatre gestes (se connecter, envoyer, nommer,
   chercher), puis ce qu'il faut savoir. Relue dans Chrome.
2. **Chacun trie SES dépôts** (choix de Mike) : `depot_de` lit le carnet et
   donne au déposant la main sur son fichier dans `_Uploads` ; la lampe et
   `/tri` ne montrent que les siens. Avant, tout geste de Flo ou Papa dans
   `/tri` aurait été refusé.
3. **Mot de passe** : dans le menu du compte, pour tous (panneau, deux champs).
4. **La lampe des dépôts était allumée, vide, partout** (`display` battait
   `[hidden]`, 3ᵉ fois) : corrigée, et `HiddenCacheVraiment` la tient.
5. Page d'envoi : plus de « Aucune inscription requise » ni « v10 ».
7. **« Request timed out » dans le journal : ce n'était PAS une panne** — la
   fin normale d'un keep-alive muet 30 s (17 sur 17 à +28–30 s de la
   dernière réponse, toutes en 200). Désormais compté, plus écrit
   (`KEEPALIVE_FERMES`) ; observé : 602 requêtes, 0 ligne.
8. **E-mail de bienvenue** : brouillon dans `docs/EMAIL_BIENVENUE.md`. Mike
   veut des **brouillons Gmail** (Flo, Papa) — j'attends leurs adresses.
9. **Preuve du tri non-admin** : Mike crée un compte `Essai` (non admin) et
   s'y connecte dans Chrome ; ensuite j'envoie, je range, je tente sur un
   dépôt d'autrui. **Le supprimer après.**
6. `ROADMAP.md` portait B1–B4 EN DOUBLE (une version d'avant l'abandon) :
   la copie périmée est retirée (−137 lignes).

Acquis d'avant : veille livrée (P1), B5/B6 mesurés, campagne de retag
ABANDONNÉE, un compte par propriétaire (Mike admin, Flo, Papa).

---

## 1. Par où commencer

1. **Vérifier la livraison** (`feat/p2-aide-quatre-gestes`) dans
   `.git/logs/refs/heads/main` — le rapport de l'agent ne suffit pas.
2. **P2, l'e-mail** — le dernier morceau. Court, sans jargon : l'adresse
   `http://192.168.0.13:8080` (Wi-Fi de la maison), le prénom + le mot de
   passe que Mike donne, « change-le dans le menu à ton prénom », et un
   renvoi vers `/aide`. Le rédiger AVEC Mike (c'est lui qui l'envoie) ;
   lui proposer un brouillon Gmail seulement s'il le demande.
3. **Non vu en réel** : le tri par un NON-admin. Aucune connexion Flo/Papa
   possible depuis ici (mot de passe = Mike). Le banc couvre la règle ; la
   preuve réelle viendra au premier envoi de Flo — ou Mike peut tester avec
   un compte d'essai.
4. **La cible du 29/08 n'est pas construite** : `/upload` écrit toujours
   dans `_Uploads`, pas dans `Photos <Nom>\_A TRIER` (`eval/DECISIONS.md`).
   Le correctif du 16/09 suffit à l'usage ; à reposer à Mike seulement si
   `_Uploads` gêne.
5. **D1, la copie hors site** : à Mike seul — le lui rappeler une fois.

**Ce qui n'attend que Mike** : le bat 36 pour les 14 doublons d'`_A TRIER`
(+ regarder 4 voisins, renommer `20260731_232718.mp4`), le bat 24 (corbeille,
dont les 24 `_original`), la fenêtre des 68 copies (**vers le 13/10**), le KB
Windows (**vers le 16/10**), et couper « Photo animée » sur le téléphone.

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
