# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (27/08/2026, fin de session 58)

**Le serveur est ARRÊTÉ** (mon `arret` de 21:09) — le rangement par année
l'exigeait. Le redémarrer est le premier geste de la reprise.

**Les 3 776 photos que Google seul détenait sont sur le NAS.** Copiées sous
`_A TRIER\Takeout Google\<année>` (12,6 Go, 0 grief, journal dans
`_corbeille_copies/`), puis le serveur a commencé à les taguer. **Rien ne
s'efface chez Google** avant que `verifier_photos_google.py` ne compte ZÉRO
absente.

**Le rangement par année décrochait encore les décisions humaines — corrigé et
PROUVÉ EN RÉEL.** `appliquer_plan.rekey_stores` se disait « miroir de
`server.rekey_everywhere` » et re-cléait DEUX magasins de sujets sur quatre :
`people` et `pets` sont keyés par NOM, `store.rekey(chemin)` n'y trouve
jamais rien, et la boucle ne regardait pas le retour. Le rangement des 559
photos de `_A TRIER` a rendu `{'ok': 539, 'skip': 20, 'decisions': 27}` :
**27 décisions transportées** que l'ancien code aurait laissées derrière. Le
premier lot de 20 en avait rendu **zéro** — un échantillon qu'on n'a pas
choisi ne prouve rien, ni dans un sens ni dans l'autre.

Au passage, le script **PROUVE** désormais que le serveur est arrêté au lieu
de le demander dans son en-tête — et **deux fois**, parce que la base est en
WAL : `BEGIN IMMEDIATE` peut réussir pendant que le serveur vit, donc on lui
demande AUSSI s'il répond.

**Six familles de boutons de `gallery` passent au `.btn` canonique** —
livré en `commit`, **branche non fusionnée**, parce que l'ŒIL manque. Cascade :
69 déclarations disparues, 0 apparue, 0 valeur changée. Plancher 44 px prouvé :
**9 → 22 cibles sur 31**. Et le bouton qui **supprime une photo** était en
contour à **3,03:1** — la forme que le système avait mesurée et remplacée deux
jours plus tôt ; elle survivait parce que `verifier_contraste` ne lit que
`tokens.css` et `components.css`, jamais les `<style>` des pages.

**L'AVANT du trailer Samsung est photographié** (`_rapport_sef_avant.json`,
**à ne pas supprimer**) : 1 736 JPEG rapatriés, 746 avec leur SEF, 1 715 sans
aucun nom. Quand le serveur en aura nommé, `--comparer` donnera l'avant/après
du MÊME fichier.

### Les trois choses de la journée qui changent la suite

1. **Un écart TOUJOURS du même signe n'est pas du bruit.** Six lignes de
   contrôle ont renversé un verdict que j'avais écrit dans le ROADMAP : les
   173 « flux différents » portaient toutes un trailer Samsung, pas une autre
   image.
2. **Un docstring qui dit « miroir de » n'est pas une preuve** — et le test
   qui le dit doit ROUGIR sur l'ancien code, sinon il ne dit rien.
3. **Une portée qu'on ne lit pas est une portée qui ment pour vous.**
   `verifier_contraste` annonce depuis toujours qu'il ne juge que deux
   feuilles. Un « Supprimer » à 3:1 a vécu dans l'angle mort qu'il déclarait.

## Prochain pas

1. **REDÉMARRER le serveur**, puis **l'ŒIL sur `gallery`** : c'est ce qui
   manque pour fusionner la branche
   `feat/six-familles-de-boutons-maison-passent-au-btn-canonique`. Dans
   l'ordre : `verifier_pages_composants` sur le serveur VIVANT, puis regarder
   la barre d'outils, la barre géo, la visionneuse et le diaporama. Le coût
   accepté est +19 px de hauteur de barres — vérifier que ça ne casse pas le
   retour à la ligne sur petit écran.
2. **`.fchip`** : une seule classe pour des `<a>` de navigation ET des
   `<span>` d'information. Décision en attente dans `QUESTIONS_MIKE.md` ;
   ça vit dans `server.py`, donc redémarrage.
3. **Le trailer Samsung : l'AVANT est photographié, il n'y a plus qu'à
   attendre puis comparer.** `_rapport_sef_avant.json` porte l'état des
   **1 736 JPEG rapatriés — 746 avec leur SEF, 1 715 sans aucun nom**. Quand
   le serveur en aura nommé, lancer au banc :
   `verifier_trailer_samsung.py --racine b64:<le fonds> --echantillon 0
   --comparer _rapport_sef_avant.json` — le rapprochement se fait par NOM de
   fichier, donc le rangement par année ne le casse pas. Une seule transition
   compte : **un nom apparu ET le SEF disparu**. **Ne pas supprimer
   `_rapport_sef_avant.json`** : une fois ces photos nommées, cet « avant »
   ne se refabrique plus.
   En attendant qu'il y ait des noms, le tableau de corrélation
   (`croiser`, sans `--comparer`) répond déjà — mais **avec
   `--exclure Takeout`** : les photos rapatriées sont des copies de Google,
   SEF intact et pas encore nommées, et les compter fabriquerait la
   corrélation cherchée. Si c'est confirmé, c'est un défaut qui court depuis
   le début du projet.

4. **Le chantier 18 (confidentialité), partie qui ne dépend pas de 17** : le
   détecteur greffé sur le tagueur, l'axe `sensible:`, et **d'abord le jeu
   étiqueté et son banc** — sans banc, le seuil est une opinion. Attention :
   le verdict ne va PAS dans le XMP (l'étiquette serait elle-même la fuite).
5. **Le panneau `?` des raccourcis**, et d'abord sa brique : **un JS commun
   injecté sur toutes les pages** (`_UI_GLOBAL_FILES`). Il n'en existe aucun.
   Contenu dans `docs/RACCOURCIS.md`.
6. **La suite du chantier 17** : la notion de PROPRIÉTAIRE, puis
   l'attribution rétroactive des 3 767 décisions à Mike. Deux questions
   ouvertes bloquent l'écriture partagée.
7. **UNIFIER le re-clé** : la réparation est faite (27/08), mais la
   primitive complète existe désormais **TROIS fois**
   (`server.rekey_everywhere`, `deplacer_dossiers.recle_une_cle`,
   `appliquer_plan.rekey_stores`). Trois endroits où la même règle peut
   diverger — elle l'a déjà fait pendant cinq jours. Une seule doit rester.
8. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** dans `/reglages` ;
   `animal:luna` en minuscule sur 3 photos à côté de `animal:Luna` sur 355.
   Puis les quatre pages sans `components.css`. O15 balaie au passage les
   3 047 vignettes orphelines du déplacement du 26/08.

## En fin de projet — décidé, mesuré, en attente d'un geste

**La copie hors site attend que le chantier 17 soit fini** (choix de Mike,
26/08). Le Takeout, lui, ne dépend de rien.

- **Le Takeout Google : OUVERT, CONFRONTÉ, et le rapatriement est OUTILLÉ**
  (27/08). Ce qui reste est un geste sur l'archive :
  **`32 - Copier les absentes de Google.bat`**, puis `26 - Ranger par
  annee.bat`, puis relancer `verifier_photos_google.py` (famille `verifier_`,
  lançable au banc — le chemin passe par le jeton `b64:`, il porte des
  espaces). Effacer
  se fait sur `photos.google.com` — jamais depuis l'app du téléphone, qui
  efface aussi l'appareil — et le quota ne bouge qu'une fois la CORBEILLE
  vidée (60 j). **Le compte est à 96 %** : quand il est plein, Gmail cesse de
  RECEVOIR. Avant d'effacer 75 Go chez un tiers :
  `verifier_google_pixels.py --octets`, qui hache le flux au lieu d'en
  comparer la longueur (~32 Go à lire, trois ou quatre tranches de banc).
- **La copie hors site (12 bis)** : Synology DS224+ → **Infomaniak Swiss
  Backup**, Hyper Backup/Swift, ~**CHF 6 TTC/mois** pour 1 To, données en
  Suisse. Fonds mesuré : **291 Go**. Clé de chiffrement imprimée et rangée
  ailleurs. Et une restauration d'épreuve : une sauvegarde jamais restaurée
  n'est pas une sauvegarde.
- **HTTPS : FAIT** (26/08). `tailscale serve --bg --https=443 localhost:8080`
  → `https://msi-mike.goat-draco.ts.net/`. Zéro ligne de code changée.

## Réflexes

### Mesurer

**Un nom inventé doit rendre ZÉRO — et le banc doit le demander AUSSI dans
l'autre sens.** Le contrôle négatif seul laisse passer un moteur qui rend zéro
pour tout ; le contrôle positif seul laisse passer celui qui rend tout pour
rien. Les deux, ou rien. Et les valeurs de contrôle se LISENT dans le fonds :
un banc qui teste un nom en dur rougit le jour où ce nom disparaît, sans
qu'aucun code n'ait bougé.

**Mesurer avec l'instrument du PROJET.** Trois fois le 26/08, une requête
maison s'est trompée là où l'instrument avait raison. Trois instruments, trois
questions : les fiches (`/api/names`), les tags (`kw` de l'index), les
détections (`animals`).

**Un écart TOUJOURS du même signe n'est pas du bruit.** 173 paires
« différentes » l'étaient toutes dans le même sens, de −67 à −4 864 405
octets. J'avais écrit « probablement deux photos différentes » — une
coïncidence n'a pas de signe. Le contrôle a coûté six lignes et a renversé le
verdict : c'était un TRAILER, pas une image.

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`.** Pas de virgule, pas
d'espace (jeton `b64:`). Une option en liste séparée par des virgules est une
option qui sera REFUSÉE — la rendre répétable, dès l'écriture.

**Un docstring qui dit « miroir de » n'est pas une preuve.**
`appliquer_plan.rekey_stores` l'affirmait, et re-cléait DEUX magasins de
sujets sur quatre — sans lever d'erreur, parce que la boucle ne regardait même
pas le retour de `rekey`. Corrigé le 27/08, cinq jours après que le serveur,
lui, l'ait été. **Quand deux chemins font « la même chose », c'est un test qui
doit le dire** — et il doit ROUGIR sur l'ancien code, sinon il ne dit rien.

**Et une preuve d'arrêt qui dépend de l'instant n'en est pas une.** La base est
en WAL : `BEGIN IMMEDIATE` peut réussir pendant que le serveur vit. On lui
demande AUSSI s'il répond.

### Lire

**Le serveur a un journal : `_journal_serveur.log`** — miroir daté de sa
console, il porte les tracebacks des threads qui meurent. **Le lire AVANT de
supposer**, depuis la DERNIÈRE bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "THREAD MORT\|EXCEPTION\|Traceback"

**Un commentaire est de la PROSE, quel que soit le langage** — CSS compris.
Règle de lecture unique : `verifier_controles.sans_le_css`. L'exception est
une DÉCLARATION (`/* cible: hors-portee -- … */`) : elle se lit AVANT le
retrait et se ferme sur `*/`.

**Un banc en lecture seule tourne aussi dans la VM** : les `verifier_` qui ne
lisent que des fichiers se relancent en une seconde par `device_bash`. Le banc
Windows reste la PREUVE et le seul chemin vers le serveur : la VM n'atteint
pas le LAN. **Ce qui ÉCRIT n'est pas lançable au banc.**

### Juger

**Un verdict tiré à pile ou face est pire qu'un aveu d'ignorance.** Deux
règles CSS de même poids : « la dernière écrite gagne » n'est vrai que **si
les deux s'appliquent**.

**Ce qui doit s'accorder, c'est le VERDICT, pas la valeur.** `44px` et
`var(--touch)` sont la même hauteur.

**Ne pas voir une cible ne la rend pas conforme.** Avant de croire un
« 0 grief », demander sur COMBIEN — et tout rapport dit sa PORTÉE.

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage. Ça ne dispense pas d'OBSERVER.

**L'ordre de la cascade a QUATRE étages** : `components.css` (au marqueur,
AVANT le `<style>` de la page) → la page → `tokens.css` → `base.css` (à
`</head>`, il gagne les égalités). Une feuille qui ne change pas doit figurer
**des deux côtés** de `--avant`/`--apres`.

**Changer une BALISE change son style par défaut.** Un `<button>` n'admet que
du contenu de PHRASE ; sinon `tabindex` + `role` + `keydown` Entrée **et**
Espace avec `preventDefault` — **les trois**.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique.

**Un `_exiftool_tmp` condamne sa photo.** Balayage possible mais **jamais par
défaut** (`--balayer-fantomes`).

**Un nom accentué passe au banc par le jeton `b64:`** :

    verifier_xmp_personnes.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4

> **Piège d'horloge** : `device_bash` tourne dans une VM en **UTC** — deux
> heures de moins que chez Mike. Les epochs du serveur sont la seule heure
> fiable.
>
> **Et le dossier monté a un cache** : `tail` peut rendre un contenu vieux de
> 25 min. Le `mtime` (`ls -l`, `date -r`) dit la vérité.
