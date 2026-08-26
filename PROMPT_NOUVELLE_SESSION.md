# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (26/08/2026, fin de session 49)

**Rien ne tourne, rien n'attend.** Le serveur porte le code livré ; `/files`,
`/sujets`, `/people` et `/browse` ont été observés dans Chrome après
modification — les pages de `ui/` sont relues À CHAUD, seul `server.py` exige
un redémarrage.

**Le point 3 du plancher a son instrument, et le chip est FINI.**

`verifier_cibles.py` (neuf, 65 tests) lit la hauteur DÉCLARÉE de chaque cible
dans la cascade à quatre étages. Verdict en **deux chiffres qui ne disent pas
la même chose** : **0 manquement prouvé** sur **221** cibles, et **66 cibles
dont le plancher n'est pas déclaré** — le contenu décide, le texte ne peut pas
le savoir. La seconde moitié n'est pas un feu vert.

Ce qu'il a fait tomber, tout corrigé et observé : `subjects` annulait son
propre plancher (`min-height: 0`, et cette seule règle rendait quinze boutons
non décidables) ; `gallery` déclarait 32 px sur des `<a>` **inline** — la
règle ne faisait rien ; les deux boutons « Annuler » des toasts étaient à
36 px. La case de 18 px de `people` est un indicateur (déclarée, deux chemins
de code) ; la loupe de `pets` reste à 26 px, **tranché par Mike**.

**`gallery` adopte `components.css` — 7 pages sur 11.** Le chip canonique
n'avait pas de `font:` ; `subjects` et `gallery` l'avaient réparé à
l'identique sans se concerter, donc il est monté dans la feuille commune.
`.pchip` était un alias exact : supprimé. Preuve : `subjects` 0 écart après la
cascade, `gallery` 2 écarts, tous deux voulus.

## Prochain pas

1. **Converger les NOMS de boutons, et c'est un choix de Mike.** Les 66
   cibles sans plancher déclaré ne sont plus un problème de marqueur : sur
   les 16 de `gallery`, aucune n'est un chip — ce sont ses boutons maison
   (`.tb`, `.geobtn`, `.fchip`, `#lb-*`). Adopter la feuille ne leur donne
   rien ; les renommer en `.btn` leur donnerait le plancher **et changerait
   ce qu'on voit**. Ne pas le faire sans lui. Restent aussi quatre pages sans
   marqueur : `browse`, `faces`, `map`, `reglages`.
   **L'ordre de `--apres` est la moitié de la preuve** : la feuille commune
   EN PREMIER. Preuve attendue, dans cet ordre : `verifier_css_cascade --page`,
   `verifier_cibles`, `verifier_contraste`, `verifier_controles`, les tests
   UI, le banc des pages composants sur le **serveur vivant**, puis l'œil.
2. **Quatre points du plancher n'ont toujours pas d'instrument** : mouvement
   réduit (4), sémantique (5, partiellement couverte par
   `verifier_controles`), navigation clavier des tâches répétitives (6),
   états vides et erreurs rédigés (7). Trois sur trois des points
   instrumentés ont trouvé un manquement RÉEL au premier lancement. C'est le
   pari le plus rentable des trois dernières sessions.
3. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans `/reglages`.
   O15 (purge de `photo_thumbs/`) gagne en poids.

## En fin de projet — décidé, mesuré, en attente d'un geste

Ces deux points ne sont plus des questions ouvertes : tout est chiffré, il ne
manque que le temps. **Ne pas les faire passer devant le code.**

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
