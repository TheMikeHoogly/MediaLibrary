# Reprise — MediaLibrary, après le 22 septembre 2026 (soir)

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md` et `docs/DECISIONS_OUTILLAGE.md`,
> les chiffres dans `PERFORMANCE.md`, les choix de Mike dans `QUESTIONS_MIKE.md`.

---

## 0. Ce qui vient de se passer — 22/09

**Le CHANTIER 19 EST FINI, brique 1 comprise.** Mike a répondu aux deux
questions : « je suis tes recommandations » → **(a) la file de revue**, et
donc **pas** les trois champs au passage de la vignette (ils n'avaient de sens
que pour un modèle dédié).

**Livré** (`6d1475f`) : l'onglet Sensibles porte une section « À regarder »,
sous les photos masquées, en **trois familles** — documents **22**, captures
`.png` **443**, ressemblances **400** (classées par marge). **Aucune photo
n'est masquée, aucune n'a bougé** : chaque fiche porte les trois gestes, et
« pas sensible » mémorise. Vu à l'écran : les 24 fiches d'une famille, un
verdict posé puis ANNULÉ (443 → 442 → 443), vignettes servies.

- La file « intime » vit dans **`_filet_intime.json`, hors git** — une liste
  de chemins qui « ressemblent à » vaut accusation, et le modèle ne sait pas
  trancher. Elle se refait en 45 s (`mesure_filet_intime.py --top 400`), et la
  page DIT de quand elle date.
- Bancs : `test_sensibles.LaFileDeRevue` (six), dont un qui exige le garde
  `_verdict_deja_rendu` dans CHAQUE boucle de famille — écrit d'abord en
  cherchant le nom dans le texte, il laissait passer le mutant.

---

## 0 bis. Le matin du 22/09 — la vue posée par lecture

**La page du fonds entier était DEUX FOIS plus lente qu'au 15/09, et personne
ne le savait.** Remesurée avant de toucher quoi que ce soit : 7,3 s, dont
**4,0 s dans la seule passe `marques`** — 406 ms une semaine plus tôt. Le
chantier 19 avait alourdi le prédicat de visibilité, et cette boucle posait une
VUE PAR CLÉ (`STORE.data` écrit dans son corps : 44 436 fois).

**Livré** (`7ec7767`) : vue hissée dans les trois boucles de la galerie, puis
**mémorisée par fil et par génération** — une génération par requête, et une de
plus à chaque écriture qui change une règle (partage, masque, magasin
remplacé). Couvre les **128 endroits** du projet qui écrivent `*_STORE.data`
dans une boucle, et ceux qu'on écrira demain.

| | avant | après |
|---|---:|---:|
| page du fonds (chaud) | 7 277 ms | **3 550 ms** |
| CPU | 7 156 ms | **3 469 ms** |
| `marques` | 4 028 ms | **417 ms** |
| vues posées pour la page | ~44 436 | **3** |

**Un compteur d'étendue** le tient : `vues_posees` dans `/api/perf`. Trois
mutants tués ; le banc qui exigeait « la liste de partage relue à CHAQUE
lecture » a été réécrit pour exiger les deux bouts (`PERFORMANCE.md` § 3.26).

---

## 0 bis. L'état d'avant, en dix lignes

**Le CHANTIER 19 est FINI côté code — briques 2, 3, 4, 5 et 6 livrées, vues à
l'écran et fusionnées dans `main`.** La brique 1 est mesurée et
volontairement NON câblée : **deux choix attendent Mike** dans
`QUESTIONS_MIKE.md`. Le détail de chaque brique vit dans git et dans
`docs/CHANTIER_19_VIE_PRIVEE.md` ; ce qui suit est la carte.

1. **Brique 6 — les comptes pour de bon.** « Changer mon mot de passe » exige
   l'ACTUEL (le frein des connexions s'y applique) ; l'admin réinitialise
   celui d'un AUTRE en **provisoire**, et la première page de la personne lui
   demande d'en choisir un. Chaque compte porte une **adresse e-mail**
   facultative et effaçable ; l'admin peut la poser pour quelqu'un
   (Réglages → « Adresse »). **Le serveur n'envoie jamais rien** — le
   « mot de passe oublié » par SMTP est refusé (Mike, 18/09).
2. **Brique 3 — masquer une photo où l'on est reconnu.** La photo NE BOUGE
   PAS : restent son propriétaire, la personne, l'admin. **Seule elle lève**
   (l'admin en secours), jamais le propriétaire. État en base (`masque_par`),
   jamais dans le XMP. Le bouton n'existe que si le SERVEUR le dit
   (`GET /api/masque`). Et **« Ce que j'ai masqué »** (`/files?masque=moi`,
   entrée du menu du compte) permet de les retrouver — sans quoi un masque ne
   se lève jamais.
3. **Brique 5 — qui voit mes photos.** Trois états : champ ABSENT = tout le
   monde, `[]` = personne, `[noms]` = ceux-là ; la migration prévue tombe, le
   troisième état est ÉCRIT. **L'admin n'est pas un passe-partout** (choix de
   Mike). Gratuit tant que personne ne restreint ; 20 ms sur 44 445 clés
   sinon — 107 ms avant d'avoir mémoïsé `auteurs.proprietaire_de`, gain qui
   profite à tout le projet.
4. **Brique 4 — être reconnu sur une photo la rouvre.** D'un cran, et d'un
   seul : elle rouvre ce que le PARTAGE a fermé, jamais un masque. **Pas
   d'index clé → noms** (le plan en annonçait un) : la question n'est posée
   que pour les clés que le partage ferme, et un banc COMPTE les appels.
   +34 ms quand quelqu'un restreint, zéro sinon.
5. **Brique 1 — mesurée, rien câblé** (`mesure_captures_ecran.py`). Le
   « signal franc » des captures d'écran est aux trois quarts illisible :
   443 `.png` sur 44 445, **aucun** champ d'appareil, **aucune** dimension
   dans la base, et le mot-clé `capture d ecran` du tagueur ne désigne
   **1 photo** — un `.jpg`. Câbler « PNG donc capture » trancherait au-delà
   de la mesure. → `QUESTIONS_MIKE.md`.
6. **Un masque ne se perd pas au tagging** : le tagueur REMPLACE l'entrée au
   premier tagging (il ne fusionnait que sur un re-tag).
   `visibilite.preserver_axes` reporte les six axes de vie privée. Le cas ne
   se produit pas aujourd'hui — « aujourd'hui » n'est pas une garantie.
7. **Un instrument neuf** : `mesure_etat_serveur.py` — lire `/api/serveur`
   (route ouverte) depuis la machine de Mike par l'agent de banc, donc **sans
   Chrome** : `uptime_s`, `demarre_a`, `code_a_jour`, et `--sert /connexion
   --motif …` pour prouver ce que le serveur SERT vraiment. Né d'une panne :
   le 17/09 au soir l'extension Chrome n'a pas répondu et il ne restait aucun
   moyen de savoir si le serveur exécutait le code du disque.
8. **Trouvé en chemin, documenté, pas corrigé** : `list(vue)` et
   `sorted(vue)` paient DEUX passes du filtre de visibilité
   (`PERFORMANCE.md` § 3.-1) ; `__length_hint__` n'y change rien et un cache
   rendrait `len()` faux. 47 appels de cette forme dans `server.py`.
9. **Tout est vu à l'écran** (Chrome `MSI-Mike`) : les deux refus du mot de
   passe, le bouton « Réinitialiser » et son tirage, le masque posé puis levé,
   les trois états du partage, la liste « Ce que j'ai masqué » et son état
   vide. **`/aide` a rattrapé le chantier** : « Mon compte », « Choisir qui
   voit tes photos », « Masquer une photo où tu es ».
10. **Ce qui n'est PAS prouvé en réel** : la vue d'un NON-admin, et la
    non-fuite ROUTE PAR ROUTE (`verifier_non_fuite.py` veut deux comptes et
    leurs mots de passe). Geste de Mike.

Acquis d'avant : veille (P1), campagne de retag ABANDONNÉE, trois comptes
(Mike admin, Flo, Papa), Tailscale préparé, e-mails en brouillons NON envoyés.

---

## 1. Par où commencer

1. **Vérifier l'état réel** — `.git/HEAD`, `.git/logs/HEAD`,
   `.git/logs/refs/heads/main` : tout ce qui est décrit au § 0 est FUSIONNÉ.
   Une doc dit l'intention de la fin de session ; git dit ce qui s'est passé.
2. **Lire `QUESTIONS_MIKE.md`** : deux questions ouvertes sur la brique 1, et
   rien ne se code là-dessus tant qu'il n'a pas répondu. La suite du chantier
   19 est **terminée** — ne pas rouvrir une brique livrée sans chiffre neuf.
3. **Prochaines cibles, si Mike ne dit rien d'autre** (par ordre de valeur, pas
   de facilité) :
   - **la file de revue à l'usage** : 443 + 400 fiches, c'est beaucoup pour
     une page qui en montre 24 par famille. Si Mike ou Flo s'en servent
     vraiment, il faudra un « voir la suite » qui reprenne où on s'est arrêté
     — aujourd'hui la file se refait à chaque chargement ;
   - **`/api/sujets/list` : 2,2 s** (mesuré le 22/09) — trois listes qui
     balaient le fonds ; le même réflexe que § 3.26 n'a PAS été appliqué là,
     faute de mesure par phase. Poser l'horloge d'abord ;
   - **`C3` étape 2 — la vraie pagination**, avec les chiffres du 22/09 :
     `mode_index` 835 ms, `envoi` 796, `gabarit` 406, `json` 275, et
     **19,3 Mo** envoyés. C'est le nombre de fiches BÂTIES qu'il faut borner ;
   - **la vue d'un NON-admin, prouvée à l'écran** : un compte d'essai créé et
     supprimé par Mike, et `verifier_non_fuite.py` lancé par lui — c'est le
     seul trou de preuve du chantier 19, et il ne se bouche que par lui ;
   - **`B3` — la question au tagueur sur les documents sensibles** : à
     instruire AVANT d'écrire une ligne (toute modification du prompt relance
     une passe complète : est-ce que ça vaut une campagne ?) ;
   - **`C3` étape 2 — la vraie pagination**, parquée : la page du fonds est
     bornée par le CPU (3,7 s), et borner le nombre de fiches bâties est le
     seul geste qui attaque encore le vrai poste.
4. **P2, l'e-mail** : trois brouillons Gmail prêts, non envoyés. Mike envoie,
   mots de passe à part.
5. **Tailscale** : partager `msi-mike` avec `markushuegli@gmail.com` et
   `flolaeser@gmail.com`, limiter `autogroup:shared` au port 8080, rappeler
   l'expiration de clé. En attente que Mike se connecte à la console.
6. **D1, la copie hors site** : à Mike seul.

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
