# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (27/08/2026, fin de session 59)

**Le serveur TOURNE et TAGUE** (redémarré 22:02 par Mike ; ~1 650 photos du
Takeout rapatrié en analyse). Session 59 menée SANS restart ni écriture base
— tout ce qui suit est lecture seule ou `ui/` relu à chaud.

**La visionneuse débordait sur téléphone — trouvé, corrigé, prouvé.** À
390 px, `#lb-bar` en `nowrap` faisait 566 px dans 370 : **« Fermer » était
HORS ÉCRAN sans aucun défilement**, « Supprimer » à moitié coupé, et
« 📅 Même jour (31 mai) » plié en quatre lignes de 78 px. Correctif : deux
déclarations dans `gallery.html` (relu à chaud) — `flex-wrap: wrap` sur la
barre, `white-space: nowrap` sur ses `.btn`. Cascade 0 disparue / 0 changée /
2 apparues (les voulues), cibles 0 manquement, 35 tests UI verts, l'œil posé
à 390 (trois rangées, tout à 44 px) et à 1 200 (une rangée, inchangé).
**Pourquoi la session 58 ne voyait rien : le zoom navigateur (~50 %) gardait
~1 020 px CSS quelle que soit la fenêtre. La mesure mobile se fait par une
IFRAME de 390 px posée sur une page du même origine** — serveur vivant, zoom
et fenêtre de Mike intacts.

**Le tableau trailer/tag a parlé : la corrélation N'EST PAS LÀ.** `croiser
--exclure Takeout`, 3 000 tirés des 72 584 (le plein fonds dépasse le plafond
600 s du banc — refusé une fois, relancé en échantillon) : sur 975 Samsung
jugés, nommées **86,9 %** avec SEF (Wilson 83,4–89,8), non nommées
**83,9 %** (80,5–86,7). Recouvrement, et le signe du mauvais côté pour
accuser : **rien n'accuse notre écriture XMP** ; les 99 paires Google au
trailer zéro étaient un sous-ensemble biaisé. La CAUSE reste au juge armé :
l'avant/après du MÊME fichier (`_rapport_sef_avant.json`, **à ne pas
supprimer** — il n'est PAS dans git, le disque en porte la seule copie).

## Prochain pas

1. **`.fchip`** : décision en attente dans `QUESTIONS_MIKE.md` (les `<a>` en
   `.btn`, les `<span>` en `.fetiquette`). Ça vit dans `server.py`, donc
   redémarrage — attendre la fin du tagging ou l'accord de Mike.
2. **Le trailer Samsung — l'expérience armée n'attend que des NOMS.** Quand
   le curateur aura nommé, au banc :
   `verifier_trailer_samsung.py --racine b64:XFxOQVMtQnJlbWJsZW5zXGhvbWVcUGhvdG9z
   --echantillon=0 --comparer=_rapport_sef_avant.json` (jeton `b64:` en
   argument SÉPARÉ, jamais collé par `=`). Une seule transition compte : un
   nom apparu ET le SEF disparu. Le `--comparer` plein fonds tient dans le
   plafond (240 s : il ne lit que les 1 736 références) ; c'est `croiser`
   plein fonds qui ne tient pas (~70 000 lectures, refusé à 600 s).
3. **Le chantier 18 (confidentialité), partie indépendante de 17** : le jeu
   étiqueté et son banc D'ABORD — sans banc, le seuil est une opinion. Le
   verdict ne va PAS dans le XMP (l'étiquette serait la fuite).
4. **Le panneau `?` des raccourcis** — et d'abord sa brique : un JS commun
   injecté partout (`_UI_GLOBAL_FILES`, il n'en existe aucun). `server.py`,
   donc redémarrage. Contenu : `docs/RACCOURCIS.md`.
5. **La suite du chantier 17** : PROPRIÉTAIRE, puis attribution rétroactive
   des 3 767 décisions. Deux questions ouvertes bloquent l'écriture partagée.
6. **UNIFIER le re-clé** : la primitive complète existe TROIS fois
   (`server.rekey_everywhere`, `deplacer_dossiers.recle_une_cle`,
   `appliquer_plan.rekey_stores`). Elle a déjà divergé cinq jours. Une seule
   doit rester.
7. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** dans `/reglages` ;
   `animal:luna` (3) vs `animal:Luna` (355). Puis les quatre pages sans
   `components.css`. O15 balaie les 3 047 vignettes orphelines du 26/08.

## En fin de projet — décidé, mesuré, en attente d'un geste

- **Google** : les 3 776 ABSENTES sont copiées sur le NAS et se font taguer.
  Rien ne s'efface chez Google avant que `verifier_photos_google.py` ne
  compte ZÉRO absente ; avant d'effacer 75 Go : `verifier_google_pixels.py
  --octets` (~32 Go à lire, trois-quatre tranches de banc). Effacer sur
  `photos.google.com`, jamais depuis l'app du téléphone ; le quota (96 %) ne
  bouge qu'une fois la corbeille vidée (60 j).
- **La copie hors site (12 bis)** attend la fin du chantier 17 (choix de
  Mike, 26/08) : DS224+ → Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To,
  fonds 291 Go, clé imprimée, et une restauration d'épreuve.
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**Un nom inventé doit rendre ZÉRO — et le banc le demande dans les deux
sens.** Négatif seul : un moteur muet passe ; positif seul : un moteur qui
crie tout passe. Et les valeurs de contrôle se LISENT dans le fonds.

**Mesurer avec l'instrument du PROJET** : les fiches (`/api/names`), les tags
(`kw` de l'index), les détections (`animals`).

**Un écart TOUJOURS du même signe n'est pas du bruit** — les 173 « flux
différents » portaient tous un trailer Samsung.

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton
`b64:`, en argument séparé). **Et son plafond est 600 s** (`TIMEOUT_S`, max
1 800, pas d'option par ordre) : un banc qui lit 70 000 fichiers SMB n'y
tient pas — échantillonner (`--echantillon`), l'instrument porte Wilson.

**Une rangée peut être fausse quand chaque cible est conforme.**
`verifier_cibles` juge chaque bouton, personne ne jugeait leur tenue à
390 px : « Fermer » hors écran vivait derrière six cibles vertes. Le rendu
étroit se MESURE (iframe 390 px sur le serveur vivant), il ne se déduit pas.

### Lire

**Le journal du serveur d'abord** (`_journal_serveur.log`), depuis la
dernière bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "THREAD MORT\|EXCEPTION\|Traceback"

**Un commentaire est de la PROSE** — règle de lecture unique :
`verifier_controles.sans_le_css` ; l'exception est une DÉCLARATION.

**Un banc en lecture seule tourne aussi dans la VM** ; le banc Windows reste
la PREUVE et le seul chemin vers le serveur. Ce qui ÉCRIT n'est pas lançable
au banc.

### Juger

**Ce qui doit s'accorder, c'est le VERDICT, pas la valeur** (`44px` =
`var(--touch)`).

**Ne pas voir une cible ne la rend pas conforme** — tout rapport dit sa
PORTÉE, et elle se lit (`verifier_contraste` ne juge que deux feuilles).

**Une corrélation n'est pas une cause** — le banc du trailer le dit
lui-même : l'accusation se prouve par l'avant/après du MÊME fichier.

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui interrompt tagging et scan : pendant une passe du serveur,
on n'y touche pas.

**L'ordre de la cascade a QUATRE étages** : `components.css` → page →
`tokens.css` → `base.css`. Une feuille inchangée figure des DEUX côtés de
`--avant`/`--apres`.

**Changer une BALISE change son style par défaut** ; un `<button>` n'admet
que du contenu de phrase.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique.

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut.

**Un nom accentué passe au banc par le jeton `b64:`.**

> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h). Les epochs du
> serveur sont la seule heure fiable.
>
> **Le dossier monté a un cache** : `tail` peut rendre du vieux. Le `mtime`
> (`ls -l`, `date -r`) dit la vérité.
