# Reprise — MediaLibrary, après le 18 septembre 2026 (matin)

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md`, `eval/DECISIONS_UI.md` et `docs/DECISIONS_OUTILLAGE.md`,
> les chiffres dans `PERFORMANCE.md`, les choix de Mike dans `QUESTIONS_MIKE.md`.

---

## 0. L'état, en dix lignes

**Le CHANTIER 19 est fini côté code : briques 2, 3, 4, 5 et 6 livrées et
fusionnées. La brique 1 est MESURÉE et volontairement NON câblée — deux
choix attendent Mike dans `QUESTIONS_MIKE.md`.**

-5. **Les axes de vie privée survivent au tagging** (19/09) :
   `visibilite.preserver_axes` — le tagueur remplace l'entrée au PREMIER
   tagging, la branche `retag` fusionnait déjà. Défense en profondeur : le
   cas ne se produit pas aujourd'hui, mais un masque effacé ne se voit pas.

-4. **« Ce que j'ai masqué »** (19/09) : `/files?masque=moi`, cinquième mode
   de grille-résultat, entrée dans le menu du compte, état vide rédigé.
   Aller-retour complet vu à l'écran. Deux bancs qui citaient « les QUATRE
   modes » ont été mis à jour — ils jugent désormais ce que la ligne DIT.

-3. **Brique 1 — mesurée le 19/09, rien câblé** (`mesure_captures_ecran.py`).
   Le « signal franc » des captures d'écran est aux trois quarts illisible :
   443 `.png` sur 44 445, **aucun** champ d'appareil, **aucune** dimension
   dans la base, et le mot-clé `capture d ecran` du tagueur ne désigne
   **1 photo** — un `.jpg`. Câbler « PNG donc capture » trancherait au-delà
   de la mesure. Deux questions pour Mike : la file de revue (a) ou un modèle
   dédié (b) ; et faut-il poser largeur/hauteur/appareil au passage de la
   vignette pour rendre le signal lisible.

-2. **Brique 4 — être reconnu sur une photo la rouvre** (nuit du 18 au 19/09).
   D'un cran, et d'un seul : elle rouvre ce que la LISTE DE PARTAGE a fermé,
   jamais un masque (un banc prend les quatre masques un par un). **Pas
   d'index clé → noms** : la question n'est posée que pour les clés que le
   partage fermerait, et un banc COMPTE les appels pour que personne
   n'inverse l'ordre. +34 ms sur 44 445 clés quand quelqu'un restreint, zéro
   sinon.

-1. **Brique 5 — qui voit mes photos** (nuit du 18 au 19/09). Trois états
   (champ absent = tout le monde, `[]` = personne, `[noms]` = ceux-là) ; la
   migration prévue tombe, le troisième état est ÉCRIT. **L'admin n'est pas
   un passe-partout** (choix de Mike). Gratuit tant que personne ne restreint
   (`fermes_pour` rend un ensemble vide, chemin rapide) ; quand quelqu'un
   restreint, 20 ms sur 44 445 clés — 107 ms avant d'avoir mémoïsé
   `auteurs.proprietaire_de`, ce qui profite à tout le projet.

0. **Brique 3 — le masque d'une personne reconnue** (soir du 18/09). Le geste
   est dans la visionneuse ; la photo ne bouge pas ; restent son propriétaire,
   elle, l'admin. Seule elle lève (l'admin en secours) — **pas le
   propriétaire**. Règle pure dans `visibilite`, filtre AU MAGASIN (les cinq),
   état en base (`masque_par`), jamais dans le XMP. Le bouton n'existe que si
   le SERVEUR le dit (`GET /api/masque`). Posé et levé en réel à 19 h 55.

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

6. **Deux choix de Mike, le 18/09** : pas de SMTP (le « mot de passe oublié »
   par lien est REFUSÉ, `eval/DECISIONS.md`), et **c'est lui qui pose les
   adresses e-mail pour l'instant** — les Réglages ont donc un bouton
   « Adresse » par ligne (Poser / Effacer). Les adresses de Flo et de Papa
   sont vérifiées dans son Gmail ; **elles ne sont pas encore posées**, c'est
   son geste.

Acquis d'avant : chantier 19 briques 2 (dépôts au déposant) ; filet « intime »
mesuré et REFUSÉ en automatique ; veille (P1) ; campagne de retag ABANDONNÉE ;
trois comptes (Mike admin, Flo, Papa) ; Tailscale préparé, e-mails en
brouillons NON envoyés.

---

## 1. Par où commencer

1. **Vérifier l'état réel** (`.git/HEAD`, `.git/logs/HEAD`,
   `.git/logs/refs/heads/main`) : la brique 6 est FUSIONNÉE dans `main`,
   écrans compris.
2. **CHANTIER 19, suite** — la brique 3 est faite ; **la prochaine est la 5** — l'ordre du plan
   (`docs/CHANTIER_19_VIE_PRIVEE.md`, à relire AVANT d'écrire une ligne) :
   - **Brique 1 : plus rien à coder tant que Mike n'a pas répondu** (les deux
     questions sont écrites). Pour mémoire — **file de revue, pas masquage** — la mesure du 17/09 a montré que le zéro-shot SigLIP ne
     sépare pas (le max des témoins dépasse le p99 des intimes). Les N plus
     fortes marges vont dans l'onglet Sensibles du PROPRIÉTAIRE, qui tranche.
     Un modèle dédié ne se pose que si un jeu de validation constitué par Flo
     et Mike le justifie — et ce jeu-là, je ne le regarde pas.
     **Les captures d'écran**, elles, se détectent sans modèle (pas
     d'appareil dans l'EXIF, PNG, dimensions d'écran) : signal franc, à
     MESURER avant d'être câblé.
   - **Brique 1** (filet intime) en dernier : file de revue, pas masquage.
3. **P2, l'e-mail** : trois brouillons Gmail prêts, non envoyés. Mike envoie,
   mots de passe à part.
4. **Tailscale** : partager `msi-mike` avec `markushuegli@gmail.com` et
   `flolaeser@gmail.com`, limiter `autogroup:shared` au port 8080, rappeler
   l'expiration de clé. En attente que Mike se connecte à la console.
5. **D1, la copie hors site** : à Mike seul.

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
