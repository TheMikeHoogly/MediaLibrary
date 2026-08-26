# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (26/08/2026, fin de session 50)

**Rien ne tourne, rien n'attend.** Le serveur porte le code livré et il a été
observé page par page dans Chrome. Les pages de `ui/` sont relues À CHAUD ;
seul `server.py` exige un redémarrage.

### Ce que la session a appris, et qui doit changer ta façon de vérifier

**Un filtre qui ment a produit un verdict faux sur une chatte de la famille.**
`/files?q=animal:Caline` affiche « 1500 photo(s) — animal:Caline ». Le
contrôle le prouve : `q=animal:Zzzznexistepas` affiche la même chose, et
`q=animal:Luna` aussi — alors que Luna en a 353. `_extraire_noms` cherche le
nom NU dans la requête et **ne connaît aucun préfixe `personne:` / `animal:`**
; le jeton part donc en recherche SÉMANTIQUE sur 43 000 photos, qui rend ses
1500 meilleures, et la page l'annonce comme un filtre. C'est **exactement** le
défaut corrigé le 21/08 pour `espece:licorne`, appliqué à un axe et oublié sur
les quatre autres. Et l'interface **écrit elle-même** ce vocabulaire sur ses
pastilles : recopier l'étiquette que le site affiche dans la barre de
recherche du même site donne une recherche muette.

**La règle enfreinte est celle du projet** : j'ai conclu « Caline n'existe
nulle part » à partir de `/api/names` (qui ne lit que les FICHES) et d'un
`total: null` lu comme un zéro. *Un banc qui ne SAIT pas ne rend pas vert* —
ça vaut pour les instruments ET pour celui qui les lit. **Le contrôle qui
manquait tenait en une requête : un nom inventé doit rendre zéro.**

### Et ce que deux noms posés à la main ont produit

Caline n'était pas perdue : elle n'avait **jamais été saisie**. Mike a nommé
les groupes, et une heure plus tard, mesuré sur le serveur vivant :

    Caline    0 -> 730 photos (la plus photographiee du fonds)
    Inti    530 -> 619        Luna  207 -> 353
    groupes d animaux NON NOMMES  189 -> 99
    apparitions restantes  ~1500 -> 442   plus gros groupe  439 -> 31

`curator_loop` (240 s) + `AUTO_ADD` (`sim ≥ 0,40`, marge `≥ 0,10`,
`CAT_AUTO_LOG` côté animaux) ont fait le reste. **C'est la thèse du point 16
enfin chiffrée** — la médiathèque s'améliore à chaque information humaine, et
le mécanisme n'était pas à écrire : il attendait une décision.

### Les autres acquis de la journée

- **Le plancher tactile a son instrument** : `verifier_cibles.py` (65 tests,
  huit rouges observés gravés). **221 cibles, 0 manquement prouvé**, 66 dont
  la hauteur n'est pas déclarée. Il lit le HTML statique, les chaînes JS ET ce
  que `document.createElement` bâtit — 31 cibles étaient invisibles avant.
- **Le chip est fini** : `.chip` vit dans `components.css` seul, `font:`
  compris ; `.pchip` supprimé ; **7 pages sur 11** reçoivent la feuille
  commune. `subjects` : 0 écart après la cascade.
- **Deux instruments lisaient la PROSE des commentaires CSS** comme des
  balises. Règle de lecture unique et partagée : `verifier_controles.sans_le_css`.
- **Le chantier 17 (multi-utilisateurs) est SPÉCIFIÉ** — six décisions de
  Mike, dans `ROADMAP.md`. Ne pas le rouvrir, l'exécuter.

### Le déplacement `Photos Mike` est PRÊT, et il n'a pas été lancé

`deplacer_dossiers.py` + `dossiers_a_deplacer.txt` (26 noms) +
`test_deplacer_dossiers.py` (23 tests, trois mutations vues). **26 dossiers,
25 559 photos, 983 décisions humaines.** Aperçu par défaut ; `--appliquer` et
`--undo <journal>` ; le serveur doit être arrêté et le script le **prouve**.

**Ce qu'il a fallu trouver avant de l'écrire** : `appliquer_plan.rekey_stores`
se dit « miroir de `server.rekey_everywhere` » et **re-clé cinq magasins sur
sept**. Manquent les décisions humaines dans `people`/`pets` (keyés par NOM :
`.rekey(chemin)` n'y trouve rien et **ne dit rien**) et `gps_places.json`.
C'est l'incident du 22/08 — 928 décisions perdues — dont le correctif n'a été
porté que côté serveur. **Ne jamais déplacer avec `rekey_stores`.**

## Prochain pas

**L'ordre est celui de la section « Priorité » du ROADMAP, et il a changé.**

1. **Le garde-fou du filtre.** Un jeton `<axe>:<valeur>` que le filtre ne sait
   pas satisfaire rend RIEN et le DIT — comme `espece:` déjà. Puis la barre de
   recherche comprend ce que les pastilles écrivent (ou les pastilles cessent
   de l'écrire). Puis **un banc de contrôle NÉGATIF** : pour chaque axe, une
   valeur inventée doit rendre 0.
2. **Les boutons de `gallery` — option 1, tranchée : tout convertir.** Les
   cinq familles maison (`.tb` 34 px, `.geobtn` 28 px, `.fchip` 35 px,
   `.georow button` 34 px, `#ss-stop` 34 px) passent au `.btn` canonique.
   Coût accepté : **+19 px** de hauteur de barres. Preuve dans l'ordre
   habituel : `verifier_css_cascade --page` (feuille commune EN PREMIER dans
   `--apres`), `verifier_cibles`, `verifier_contraste`, `verifier_controles`,
   tests UI, banc des pages composants sur le **serveur vivant**, puis l'œil.
3. **Le panneau `?` des raccourcis**, et d'abord sa brique : **un JS commun
   injecté sur toutes les pages**, comme `tokens.css` et `base.css`. Il n'en
   existe aucun ; ce serait le premier. Contenu déjà relevé dans
   `docs/RACCOURCIS.md`.
4. **Le déplacement `Photos Mike`** — le script est écrit et testé, il attend
   le geste de Mike : arrêter le serveur, `python deplacer_dossiers.py` pour
   l'aperçu, puis `--appliquer`. **Ensuite seulement** : redémarrer, vérifier
   que les compteurs de noms n'ont pas bougé (`/api/names`), et relancer
   `verifier_orphelins`.
5. **Unifier les deux chemins de re-clé.** La primitive complète existe
   maintenant DEUX fois (`server.rekey_everywhere` et `deplacer_dossiers`) :
   le troisième appelant reproduira le défaut. Et
   `appliquer_plan.rekey_stores` est toujours cassée — le rangement par année
   et le dédoublonnage la portent.

## En fin de projet — décidé, mesuré, en attente d'un geste

Tout est chiffré, il ne manque que le temps. **Ne pas les faire passer devant
le code** — et, décision de Mike du 26/08, **la copie hors site attend que le
chantier 17 (multi-utilisateurs) soit fini.** Le Takeout, lui, ne dépend de
rien : il se télécharge (~2 jours au 26/08).

- **Le Takeout Google** (lancé le 25/08 par Mike, ~75 Go). À son arrivée :
  dézipper, puis `verifier_photos_google.py --takeout "<dossier>"`. Quatre
  verdicts, et **un seul ABSENT interdit tout effacement**. Effacer se fait
  sur `photos.google.com` — jamais depuis l'app du téléphone, qui efface aussi
  l'appareil — et le quota ne bouge qu'une fois la CORBEILLE vidée (60 j).
  **Le compte est à 96 %** : quand il est plein, Gmail cesse de RECEVOIR.
- **La copie hors site (12 bis)** : Synology DS224+ → **Infomaniak Swiss
  Backup**, Hyper Backup/Swift, ~**CHF 6 TTC/mois** pour 1 To, données en
  Suisse. Fonds mesuré : **291 Go**. Premier envoi **~8 nuits** à 13,8 Mbit/s —
  **le débit n'est PAS un préalable**. Compte Infomaniak **personnel**. Clé de
  chiffrement imprimée et rangée ailleurs. Et une restauration d'épreuve : une
  sauvegarde jamais restaurée n'est pas une sauvegarde.

## Réflexes

**Le serveur a un journal : `_journal_serveur.log`** (`journal_serveur.py`),
miroir daté de sa console, lisible depuis la sandbox et qui survit à sa mort.
Il porte les **tracebacks des threads qui meurent**. **Le lire avant de
supposer** — et depuis la DERNIÈRE bannière, pas la première :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "THREAD MORT\|EXCEPTION\|Traceback"

Plantage dur d'une lib native : `_journal_serveur_crash.log`.

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** (signature mtime + taille) :
une page corrigée est servie sans redémarrage. **Seul `server.py` exige le
redémarrage.** Ça ne dispense pas d'OBSERVER.

**Un banc en lecture seule tourne aussi dans la VM.** `verifier_*` qui ne lit
que des fichiers se relance en une seconde par `device_bash` — c'est ce qui
permet d'itérer. Le banc Windows reste la PREUVE (console cp1252, chemins
réels) et le seul chemin vers le serveur : la VM n'atteint pas le LAN.

**Un verdict tiré à pile ou face est pire qu'un aveu d'ignorance** (26/08).
`.actbar .b` et `.fxtoast .b` pèsent pareil : « la dernière écrite gagne »
n'est vrai que **si les deux s'appliquent**. Sans lire l'ancêtre, un
instrument accusait cinq boutons de 44 px d'en faire 36 — il faisait corriger
ce qui allait bien. **Et l'inverse existe** : une seule règle non prouvable
AFFIRMÉE disait « trop petit » là où il fallait lire « pas de plancher ».
Deux défauts opposés sous le même mot envoient chercher la panne à deux
endroits opposés.

**Un docstring qui dit « miroir de » n'est pas une preuve** (26/08).
`appliquer_plan.rekey_stores` l'affirmait et re-cléait cinq magasins sur sept.
Deux d'entre eux échouent en SILENCE : `people` et `pets` sont keyés par NOM,
donc `.rekey(chemin)` n'y trouve rien et renvoie faux sans rien dire. **Quand
deux chemins font « la même chose », c'est un test qui doit le dire, pas un
commentaire.**

**Un nom inventé doit rendre ZÉRO** (26/08). Avant de croire un filtre,
demande-lui une valeur qui n'existe pas. `q=animal:Zzzznexistepas` rend 1500
photos : l'axe n'existe pas, la requête part en sémantique, et la page
l'annonce comme un filtre. **Le contrôle négatif coûte une requête et vaut un
verdict.**

**Et avant de croire une ABSENCE, vérifie que l'instrument mesure la bonne
chose** (26/08). `/api/names` ne lit que les FICHES : un nom qui vit sur des
photos sans fiche y est invisible. Trois instruments, trois questions
différentes — les fiches (`/api/names`), les tags (`kw` de l'index), les
détections (`animals`). Répondre avec le mauvais, c'est ce qui a fait déclarer
disparue une chatte qui a 730 photos.

**Un commentaire CSS est de la PROSE, et une feuille de style ne porte pas
de balise** (26/08, la sixième fois pour la première moitié). Deux
instruments lisaient les `<button>` cités dans les commentaires de `<style>`
comme des éléments réels — `verifier_cibles` annonçait 223 cibles au lieu de
221, et `verifier_controles` comptait un `<span onclick>` cité en prose comme
un grief de niveau A. Règle de lecture unique :
`verifier_controles.sans_le_css`, partagée. **Une règle de lecture écrite
deux fois est une divergence qui attend son heure.**

**Ne pas voir une cible ne la rend pas conforme** (26/08). Ça retire
seulement le dénominateur. Un banc d'UI qui ne lit que le HTML est aveugle à
tout ce que `document.createElement` bâtit — 49 contrôles sur les onze pages,
12 dans `gallery`. **Avant de croire un « 0 grief », demander sur COMBIEN.**

**Une chaîne d'ancêtres PARTIELLE prouve, elle ne réfute pas** (26/08). Un
fragment assemblé en JS dit bien ce qu'il contient, jamais ce qu'il y a
au-dessus de lui. Ne pas trouver l'ancêtre dans le connu ne dit pas qu'il
n'existe pas.

**Ce qui doit s'accorder, c'est le VERDICT, pas la valeur** (26/08). `44px`
et `var(--touch)` sont la même hauteur : les comparer en TEXTE rendait 52
non-décidables sur 192, dont aucune ne l'était. Même leçon que `.01ms` contre
`0.01ms` le 25/08, un étage plus haut.

**Une portée qui se sous-estime fait re-faire un correctif qui existe**
(26/08). `verifier_controles` déclarait encore, docstring ET sortie, un angle
mort qu'il avait fermé la veille. **Nommer un angle mort dit où l'on ne voit
pas ; le FERMER demande de réécrire ce qu'on a nommé.**

**Une exception qui déborde n'est plus une exception, c'est un trou** (26/08).
Une déclaration `/* cible: … */` liée à tout ce qui la suivait dans un rayon
d'octets exemptait aussi le bouton d'à côté. Elle couvre **le prochain
élément, un seul**.

**Un commentaire est de la PROSE, quel que soit le langage** (25/08, appris
cinq fois). **L'exception est une DÉCLARATION** (`/* contraste: hors-portee
-- … */`, `/* controle: redondant -- … */`, `/* cible: hors-portee -- … */`) :
elle vit dans un commentaire, donc elle se lit AVANT le retrait. Elle se
ferme sur `*/`, pas sur la première fin de ligne — une raison tronquée est
une raison qu'on ne relira pas.

**Un banc qui ne SAIT pas ne rend pas vert** (25/08). Tout rapport dit sa
PORTÉE, et **ce qui ne se calcule pas se DÉCLARE dans la source, avec une
raison obligatoire — jamais en dur dans l'instrument**, sinon il devient
aveugle au cas suivant sans qu'on le sache.

**L'ordre de la cascade a QUATRE étages** (25/08), et il est la moitié de
toute preuve CSS : `components.css` (au marqueur, AVANT le `<style>` de la
page) → la page → `tokens.css` → `base.css` (à `</head>`, il gagne les
égalités). Une feuille qui ne change pas doit figurer **des deux côtés**.

**Changer une BALISE change son style par défaut** (26/08). `<span>` →
`<button>` : la police, l'alignement et surtout `display` (inline →
inline-block, ce qui **rend actif** un `min-height` qui dormait). Un
`<button>` n'admet que du contenu de PHRASE ; sinon `tabindex` + `role` +
`keydown` Entrée **et** Espace avec `preventDefault` — **les trois**.

**Un nom accentué passe au banc par le jeton `b64:`** (23/08) :

    verifier_xmp_personnes.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4

`python3 -c "import base64;print(base64.urlsafe_b64encode('Béa'.encode()).decode().rstrip('='))"`.

**Un `_exiftool_tmp` condamne sa photo** (24/08) : ExifTool REFUSE d'écrire
tant que ce temporaire est là. Balayage possible mais **jamais par défaut**
(`--balayer-fantomes`) ; surveillance par `inventaire_fantomes.py`. **Un
fantôme SANS original à côté ne s'efface pas en lot.**

**Jamais deux écrivains, y compris contre soi-même** (24/08) :
`appliquer_xmp_personnes.py` pose un verrou (preuve par FRAÎCHEUR).

> **Piège d'horloge, payé le 23/08** : `device_bash` tourne dans une VM en
> **UTC**. Les epochs du serveur (`/api/maint/status`, `now`) sont la seule
> heure fiable.
>
> **Et le dossier monté a un cache** (24/08) : `tail` peut rendre un contenu
> vieux de 25 min. Le `mtime` (`ls -l`, `date -r`) dit la vérité.
