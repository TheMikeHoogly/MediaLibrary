# Reprise — MediaLibrary, après le 18 septembre 2026 (matin)

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md` et `docs/DECISIONS_OUTILLAGE.md`,
> les chiffres dans `PERFORMANCE.md`, les choix de Mike dans `QUESTIONS_MIKE.md`.

---

## 0. L'état, en dix lignes

**Traite autonome du 18/09 au petit matin : la BRIQUE 6 du chantier 19 est
faite, en deux livraisons, regardées à l'écran à 09 h 30 et fusionnées.**

1. **Le trou du mot de passe est fermé** (`fix/le-mot-de-passe-exige-l-actuel`,
   commit `4751949`). « Changer mon mot de passe » exige l'ACTUEL ; le frein
   des connexions s'y applique ; l'admin réinitialise celui d'un AUTRE sans le
   connaître, le compte est marqué **provisoire**, et la première page que la
   personne ouvre lui demande d'en choisir un.
2. **Une adresse e-mail par compte** (`feat/une-adresse-par-compte`, commit
   `a850a86`, branchée sur la précédente). Facultative, effaçable, posée dans
   « Mon compte » (le panneau du menu porte désormais les deux gestes) ;
   visible d'elle et de l'admin seulement. **Le serveur n'envoie rien.**
3. **Un instrument neuf** : `mesure_etat_serveur.py` — lire `/api/serveur`
   (route ouverte) depuis la machine de Mike par l'agent de banc, donc
   **sans Chrome** : `uptime_s`, `demarre_a`, `code_a_jour`, et `--sert
   /connexion --motif …` pour prouver ce que le serveur SERT vraiment.
   Né d'une panne : le 17/09 au soir l'extension Chrome n'a pas répondu et il
   ne restait AUCUN moyen de savoir si le serveur exécutait le code du disque.
4. Les deux redémarrages ont été **observés** (07 h 41 et 07 h 53, `demarre_a`
   bougé, `code_a_jour` vrai) et les 78 bancs visés sont **verts sous Windows**.
5. **À l'écran** (Chrome `MSI-Mike`, 09 h 30) : « Refusé : mot de passe actuel
   incorrect. » et « Refusé : adresse e-mail invalide. » s'affichent pour de
   vrai ; « Proposer » tire `jxmn-qros-oykk`. Un `type="email"` fait jouer la
   validation NATIVE du navigateur avant notre `fetch` : deux étages de refus,
   et c'est voulu. `/files` sans paramètre montre « 0 photo(s) » parce qu'il
   montre `_Uploads`, vide — **pas une régression**.

Acquis d'avant : chantier 19 briques 2 (dépôts au déposant) ; filet « intime »
mesuré et REFUSÉ en automatique ; veille (P1) ; campagne de retag ABANDONNÉE ;
trois comptes (Mike admin, Flo, Papa) ; Tailscale préparé, e-mails en
brouillons NON envoyés.

---

## 1. Par où commencer

1. **Vérifier l'état réel** (`.git/HEAD`, `.git/logs/HEAD`,
   `.git/logs/refs/heads/main`) : la brique 6 est FUSIONNÉE dans `main`,
   écrans compris.
2. **CHANTIER 19, suite** — l'ordre du plan
   (`docs/CHANTIER_19_VIE_PRIVEE.md`, à relire AVANT d'écrire une ligne) :
   - **Brique 3, « masquer cette photo » pour une personne reconnue.** Tranché :
     propriétaire + personne + admin voient ; SEULE la personne lève ; la photo
     ne bouge pas ; l'état en base, jamais dans le XMP. Où ça se pose :
     `visibilite.visible` et `visibilite.filtre` (un masque de plus, et **les
     masques passent avant tout ce qui ouvre**), sur le modèle exact de
     `depot_reserve` du 17/09 — une règle PURE, l'appelant fournit la donnée.
     Le geste n'apparaît que si le compte connecté est parmi les `personne:`
     de la photo (CLAUDE.md n° 9). **Le banc doit prouver qu'une photo masquée
     ne fuit ni par un compteur, ni par une fiche, ni par la recherche.**
   - **Brique 5, onglet Partage** : trois états (`null` / `[]` / `[noms]`) et
     la migration qui pose `null` sur les trois comptes existants.
   - **Brique 4** (les personnes reconnues voient leurs photos) ensuite : elle
     exige un index clé → noms en mémoire — mesurer avant/après, la grille du
     fonds est à 3,7 s.
   - **Brique 1** (filet intime) en dernier : file de revue, pas masquage.
3. **P2, l'e-mail** : trois brouillons Gmail prêts, non envoyés. Mike envoie,
   mots de passe à part.
4. **Tailscale** : partager `msi-mike` avec `markushuegli@gmail.com` et
   `flolaeser@gmail.com`, limiter `autogroup:shared` au port 8080, rappeler
   l'expiration de clé. En attente que Mike se connecte à la console.
5. **D1, la copie hors site** : à Mike seul.

---

## 2. Les pièges

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
- **Git : jamais depuis la VM**, même en lecture apparente. Préfixes de branche
  admis : `feat|fix|chore|docs|test`.
- **L'agent git consomme l'ordre AVANT de travailler**, et met ~3 min quand
  `server.py` est touché (il fait tourner 78 bancs). C'est `_etat_git.json` et
  son `dernier.quand` qui disent si c'est fini, jamais le canal.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.
- **Un banc qui cite un appel AU CARACTÈRE PRÈS interdit la ligne suivante.**
  Juger un BLOC, pas une mise en page.
- **`os.path` ne reconnaît pas `\\` hors Windows** : normaliser soi-même.
- **`hidden` perd contre tout `display`** d'une classe plus spécifique. Tout
  nouvel élément de la barre qui naît caché : sa règle `[hidden]`.
- **Un onglet Chrome en arrière-plan ne charge pas les `loading="lazy"`.**
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
