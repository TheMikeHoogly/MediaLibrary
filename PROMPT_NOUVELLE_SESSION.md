# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (27/08/2026, fin de session 54)

**Le serveur tourne le code de la session 53** (garde-fou du filtre, 15/15 au
banc négatif). Traite autonome : les branches sont **poussées, `main`
INTACTE** — la fusion attend Mike.

**Le Takeout Google a rendu son chiffre, et il change l'ordre du jour :
3 776 photos (12,6 Go) n'existent QUE chez Google**, dont **2 017 vidéos**,
concentrées sur 2024–2026. Rien ne s'efface là-bas tant qu'il en reste une —
et ces fichiers ne vivent aujourd'hui qu'à un seul endroit, chez un tiers dont
le quota est à 96 %. **C'est le geste le plus urgent du projet.**

L'export est ouvert et prouvé : 45 lots, 89,2 Go, **25 864 fichiers, 0 absent,
0 tronqué** (`verifier_takeout_ouvert.py` ; le bat de Mike arrive au même
compte par l'autre bout). Sur **13 905 médias** : CERTAIN 1 112 · PROBABLE
9 017 · **ABSENT 3 776**.

**Et la documentation de l'instrument avait tort sur les PROBABLE.** Elle
posait « Google a ré-encodé en mode économiseur » ; la mesure dit l'inverse —
le NAS est plus gros 8 741 fois sur 9 017, ratio médian **1,001**, et
seulement sur les JPEG. C'est **le XMP que la photothèque écrit elle-même**.
`verifier_google_pixels.py` (neuf) le compte : **8 802 sont la MÊME image**,
99 le sont avec un TRAILER en moins côté NAS, 95 restent indéterminées,
21 sont vraiment différentes.

### Les trois choses de la journée qui changent la suite

1. **Un chiffre m'a contredit et j'ai failli ne pas l'écouter.** J'avais écrit
   que les 173 « flux différent » étaient sans doute deux photos différentes
   de même nom. L'écart était **toujours du même signe** — un signal qu'une
   coïncidence n'explique pas. Contrôle : les 173 portent des octets APRÈS le
   `EOI` côté Google. L'instrument rangeait le TRAILER dans l'image.
2. **« Extraction effectuée OK » n'est pas une preuve** — le fichier écrit à
   moitié porte le bon nom. Le contrôle est le dézippage MOINS l'écriture :
   la même traversée, donc le geste et sa preuve ne peuvent pas diverger.
3. **Le canal du banc n'admet pas la virgule.** `--reprendre=a,b,c` a été
   REFUSÉ ; l'option est devenue répétable. Un argument que le canal refuse
   est un argument qui n'existe pas — à savoir AVANT d'écrire l'option.

## Prochain pas

1. **Copier les 3 776 ABSENTES sur le NAS** — geste de Mike, sur l'archive.
   Liste nommée dans `_google.json`. Puis relancer
   `verifier_photos_google.py` : c'est lui qui dira quand le feu passe au
   vert. **Rien ne s'efface chez Google avant.** Trois questions ouvertes
   dans `QUESTIONS_MIKE.md` (27/08), dont celle-ci.
2. **Les boutons de `gallery` — option 1, tranchée par Mike : tout
   convertir.** `.tb` 34 px, `.geobtn` 28 px, `.fchip` 35 px, `.georow
   button` 34 px, `#ss-stop` 34 px → `.btn` canonique. Coût accepté :
   **+19 px**. Preuve dans l'ordre : `verifier_css_cascade --page` (feuille
   commune EN PREMIER dans `--apres`), `verifier_cibles`,
   `verifier_contraste`, `verifier_controles`, tests UI, banc des pages
   composants sur le **serveur vivant**, puis l'œil.
3. **Le panneau `?` des raccourcis**, et d'abord sa brique : **un JS commun
   injecté sur toutes les pages**, comme `tokens.css` et `base.css`
   (`_UI_GLOBAL_FILES`). Il n'en existe aucun. Contenu dans
   `docs/RACCOURCIS.md`.
4. **La suite du chantier 17** : la notion de PROPRIÉTAIRE, puis
   l'attribution rétroactive des 3 767 décisions à Mike (ordre de travail
   complet dans `ROADMAP.md`).
5. **Réparer `appliquer_plan.rekey_stores`** — cinq magasins sur sept. Puis
   **unifier** : la primitive complète existe DEUX fois.
6. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** dans `/reglages` ;
   `animal:luna` en minuscule sur 3 photos à côté de `animal:Luna` sur 355.
   Puis les quatre pages sans `components.css`. O15 balaie au passage les
   3 047 vignettes orphelines du déplacement du 26/08.

## En fin de projet — décidé, mesuré, en attente d'un geste

**La copie hors site attend que le chantier 17 soit fini** (choix de Mike,
26/08). Le Takeout, lui, ne dépend de rien.

- **Le Takeout Google : OUVERT et CONFRONTÉ** (27/08). Ce qui reste est un
  geste sur l'archive, pas une mesure : **copier les 3 776 ABSENTES**, puis
  relancer `verifier_photos_google.py` (famille `verifier_`, lançable au
  banc — le chemin passe par le jeton `b64:`, il porte des espaces). Effacer
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
`appliquer_plan.rekey_stores` l'affirmait et re-cléait cinq magasins sur sept.
Quand deux chemins font « la même chose », c'est un test qui doit le dire.

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
