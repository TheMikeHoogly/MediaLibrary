# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (26/08/2026, fin de session 53)

**Le serveur tourne le code de cette session** (démarrage 23:09:18,
`code_a_jour=True`). Traite autonome, Mike absent : la branche est **poussée,
`main` INTACTE** — la fusion attend son retour.

**Le filtre qui mentait ne ment plus.** `animal:Zzzznexistepas` rendait
**1 500 photos** annoncées comme un filtre ; il en rend zéro et il dit
pourquoi, sur les cinq axes, dans les deux canaux. `personne:` / `animal:` /
`lieu:` deviennent au passage des filtres réels — l'interface disait déjà de
les écrire. Banc neuf : `verifier_filtre_negatif.py`, **15 contrôles, 0 grief**
(première exécution : 8 griefs, corrigés le jour même).

**Le Takeout a de quoi s'ouvrir.** Les `.zip` sont dans `C:\GOOGLE PHOTOS`.
`dezipper_takeout.py` + `31 - Dezipper le Takeout Google.bat` : inventaire
d'abord (lots manquants, place, conflits), extraction ensuite, reprenable, et
rien ne s'écrit sur un verdict rouge. **Non lancé** : ce dossier n'est pas
connecté à la session.

### Les trois choses de la journée qui changent la suite

1. **Un banc a payé son écriture à sa première exécution.** Huit griefs, dont
   une régression que je venais d'introduire : un extracteur de jetons qui
   jugeait les axes des AUTRES (`espece:` annonçait « espèce inconnue :
   Caline » sur `animal:Caline` et mangeait le jeton). Le contrôle négatif
   n'est pas une formalité de fin, c'est ce qui a trouvé le défaut.
2. **Le contrôle POSITIF vaut le négatif.** Une valeur réelle doit rendre au
   moins une photo, sinon un moteur qui rend zéro pour tout serait vert. Les
   valeurs de contrôle sont lues dans le fonds (`/api/names`, `lieux.txt`),
   jamais en dur.
3. **La règle du jeton insatisfaisable n'a plus qu'UN endroit où être fausse.**
   `extraire_especes` est devenue une vue sur `recherche.extraire_jetons`.
   C'est la leçon de `rekey_stores` appliquée avant le sinistre.

## Prochain pas

1. **Les boutons de `gallery` — option 1, tranchée par Mike : tout
   convertir.** `.tb` 34 px, `.geobtn` 28 px, `.fchip` 35 px, `.georow button`
   34 px, `#ss-stop` 34 px → `.btn` canonique. Coût accepté : **+19 px** de
   hauteur de barres. Preuve dans l'ordre : `verifier_css_cascade --page`
   (feuille commune EN PREMIER dans `--apres`), `verifier_cibles`,
   `verifier_contraste`, `verifier_controles`, tests UI, banc des pages
   composants sur le **serveur vivant**, puis l'œil.
2. **Le panneau `?` des raccourcis**, et d'abord sa brique : **un JS commun
   injecté sur toutes les pages**, comme `tokens.css` et `base.css`
   (`_UI_GLOBAL_FILES`). Il n'en existe aucun ; ce serait le premier. Contenu
   déjà relevé dans `docs/RACCOURCIS.md`.
3. **La suite du chantier 17** : la notion de PROPRIÉTAIRE, puis l'attribution
   rétroactive des 3 767 décisions à Mike (ordre de travail complet dans
   `ROADMAP.md`). Deux questions restent ouvertes dans `QUESTIONS_MIKE.md` et
   bloquent l'écriture partagée.
4. **Réparer `appliquer_plan.rekey_stores`** — cinq magasins sur sept. Puis
   **unifier** : la primitive complète existe DEUX fois
   (`server.rekey_everywhere` et `deplacer_dossiers`).
5. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** dans `/reglages` ;
   `animal:luna` en minuscule sur 3 photos à côté de `animal:Luna` sur 355.
   Puis les quatre pages sans `components.css` : `browse`, `faces`, `map`,
   `reglages`. O15 balaie au passage les 3 047 vignettes orphelines du
   déplacement du 26/08 — effet de bord attendu, pas une panne.

## En fin de projet — décidé, mesuré, en attente d'un geste

**La copie hors site attend que le chantier 17 soit fini** (choix de Mike,
26/08). Le Takeout, lui, ne dépend de rien.

- **Le Takeout Google** : `.zip` arrivés dans `C:\GOOGLE PHOTOS`. Lancer
  **`31 - Dezipper le Takeout Google.bat`** — il inventorie, demande, extrait,
  et affiche la commande suivante :
  `verifier_photos_google.py --takeout "<...>\Takeout\Google Photos"`
  (famille `verifier_`, donc lançable au banc). Quatre verdicts, et **un seul
  ABSENT interdit tout effacement**. Effacer se fait sur `photos.google.com` —
  jamais depuis l'app du téléphone, qui efface aussi l'appareil — et le quota
  ne bouge qu'une fois la CORBEILLE vidée (60 j). **Le compte est à 96 %** :
  quand il est plein, Gmail cesse de RECEVOIR.
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
