# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (28/08/2026, fin de session 61)

**Le serveur TOURNE** (redémarré 08:44, `code_a_jour`, zéro fil mort depuis).

**Les vingt fils de `main()` ont un filet.** Règle de Mike : le fil mort SE
RELANCE, cinq morts consécutives ALERTENT. `fil_surveille` tient le registre
`FILS`, relance avec une attente qui double (1 → 300 s), remet le compteur à
zéro dès qu'une reprise tient 5 min, et **`/sante` affiche les fils AVANT les
fichiers** — le manque exact du 27/08. Qui boucle et qui rend a été MESURÉ
(balayage AST des `while True:`) : quinze bouclent et se relancent, cinq
rendent (les `_backfill`, `reconcile_named_tags`) et ont le DROIT de finir.
`test_fils_surveilles.py` : 10 contrôles, 10 rouges sur le code d'avant.

**`.fchip` est mort** : les `<a>` prennent `.btn btn--nav`, les `<span>`
deviennent `.fetiquette`. Instruments et banc vivant verts. **L'œil manque** —
Chrome n'était pas connecté après le redémarrage du PC.

**Google : ABSENT = 0.** 13 905 médias, 4 293 CERTAIN (55,6 Go), 9 612 « taille
différente ». Le NAS est plus gros 9 315 fois d'un écart médian de 4 101 octets
(nos XMP, bénin) mais **plus PETIT 297 fois, dont 89 de plus d'un Mo**. Les
vidéos : 3 114, dont **3 104 identiques au bit près** ; les 10 autres sont plus
petites côté NAS (−73 Mo, −40 Mo…). **Ces ~106 fichiers ne s'effacent pas chez
Google avant d'être rapatriés** ; le reste peut partir.

**Windows** : la cause des redémarrages est nommée (toujours 01:29–01:33, les
heures d'activité s'arrêtaient à 01:00). Trois réglages posés le 28/08,
**aucun prouvé** — épreuve la nuit du 8 au 9 septembre.

## Prochain pas

1. **Rapatrier les ~106 fichiers que Google porte mieux que le NAS** (10
   vidéos, ~96 photos ; liste dans `_rapport_google_apres.json`, verdict
   PROBABLE avec le NAS plus petit). Même outil que pour les absentes. Puis
   relancer `verifier_photos_google.py` : c'est ce qui rend l'effacement
   GLOBAL chez Google sûr — et donc court, parce que sélectionner 4 293
   fichiers à la main dans l'interface web est irréaliste.

2. **L'ŒIL sur `.fchip`** : la conversion est faite et prouvée aux
   instruments, mais personne ne l'a REGARDÉE — Chrome n'était pas connecté.
   Barre de dossiers de `/files`, bandeau « Semblables à », bandeau « même
   jour » : les `<a>` doivent être des boutons de 44 px, les `<span>` des
   étiquettes sans bordure. Mesure mobile par iframe 390 px (le zoom du
   navigateur fausse le redimensionnement de fenêtre).

3. **Le trailer Samsung — l'expérience armée n'attend que des NOMS.** Le
   tableau de corrélation a parlé le 27/08 : **rien n'accuse notre écriture**
   (nommées 86,9 % avec SEF, non nommées 83,9 %, Wilson qui se recouvrent).
   La preuve de CAUSE reste l'avant/après du MÊME fichier :
   `verifier_trailer_samsung.py --racine b64:XFxOQVMtQnJlbWJsZW5zXGhvbWVcUGhvdG9z
   --echantillon=0 --comparer=_rapport_sef_avant.json` (jeton `b64:` en
   argument SÉPARÉ). **Ne pas supprimer `_rapport_sef_avant.json`** : il n'est
   pas dans git, le disque en porte la seule copie.
4. **Le chantier 18 (confidentialité), partie indépendante de 17** : le jeu
   étiqueté et son banc D'ABORD — sans banc, le seuil est une opinion. Le
   verdict ne va PAS dans le XMP (l'étiquette serait la fuite).
5. **Le panneau `?` des raccourcis** — et d'abord sa brique : un JS commun
   injecté partout (`_UI_GLOBAL_FILES`, il n'en existe aucun). `server.py`.
6. **La suite du chantier 17** : PROPRIÉTAIRE, puis attribution rétroactive
   des 3 767 décisions. Deux questions ouvertes bloquent l'écriture partagée.
7. **UNIFIER le re-clé** : la primitive complète existe TROIS fois
   (`server.rekey_everywhere`, `deplacer_dossiers.recle_une_cle`,
   `appliquer_plan.rekey_stores`). Elle a déjà divergé cinq jours.
8. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** dans `/reglages` ;
   `animal:luna` (3) vs `animal:Luna` (355). Puis les quatre pages sans
   `components.css`. O15 balaie les 3 047 vignettes orphelines du 26/08.

## En fin de projet — décidé, mesuré, en attente d'un geste

- **Google** : les 3 776 ABSENTES sont sur le NAS et se font taguer. Rien ne
  s'efface avant que `verifier_photos_google.py` ne compte ZÉRO absente ;
  avant d'effacer 75 Go : `verifier_google_pixels.py --octets` (~32 Go à lire,
  trois-quatre tranches de banc). Effacer sur `photos.google.com`, jamais
  depuis l'app du téléphone ; le quota (96 %) ne bouge qu'après vidage de la
  corbeille (60 j).
- **La copie hors site (12 bis)** attend la fin du chantier 17 (choix de Mike,
  26/08) : DS224+ → Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, fonds
  291 Go, clé imprimée, et une restauration d'épreuve.
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**Un rouge causé par un NOM manquant ne prouve rien.** La première version des
tests du verrou rougissait sur l'ancien code parce que la constante n'existait
pas encore. Il faut que l'ancien code s'EXÉCUTE pour qu'on voie en quoi il
était faux — `hasattr`, pas un accès direct.

**Et tous les tests ne peuvent pas rougir.** Un garde du mécanisme NEUF
(l'obstination est bornée) ne peut pas rougir avant qu'il existe. Le dire vaut
mieux que d'annoncer un compte flatteur.

**Un nom inventé doit rendre ZÉRO — et le banc le demande dans les deux
sens.** Les valeurs de contrôle se LISENT dans le fonds.

**Mesurer avec l'instrument du PROJET** : les fiches (`/api/names`), les tags
(`kw` de l'index), les détections (`animals`).

**Un écart TOUJOURS du même signe n'est pas du bruit.**

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton `b64:`,
en argument séparé). **Plafond 600 s** (`TIMEOUT_S`, max 1 800, pas d'option
par ordre) : un banc qui lit 70 000 fichiers SMB n'y tient pas —
échantillonner, l'instrument porte Wilson.

**Une rangée peut être fausse quand chaque cible est conforme.** Le rendu
étroit se MESURE — iframe 390 px sur le serveur vivant, parce que le zoom du
navigateur fausse le redimensionnement de fenêtre.

**Un banc qui imprime doit rester lisible par une console cp1252.** C'est
celle de l'agent git : un caractère hors table y lève `UnicodeEncodeError` et
fait ROUGIR un banc qui passe 52/52 — la livraison est refusée pour une raison
qui n'existe pas. Le 28/08, deux bancs sur ~90 étaient dans ce cas, les deux
corrigés, zéro restant (balayage AST des `print`). Filets en ASCII, et
`reconfigure(errors='replace')` là où le banc imprime des données de test qui
peuvent contenir n'importe quel Unicode.

**Ne JAMAIS lancer `unittest discover` depuis la VM.** Trois tests ouvrent le
vrai `photos.db` : ils échouent en « disk I/O error » (tant mieux), mais c'est
la règle « jamais deux écrivains » qu'on frôle. Le banc Windows est la preuve.

### Lire

**Le journal du serveur d'abord** (`_journal_serveur.log`), depuis la dernière
bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "THREAD MORT\|EXCEPTION\|Traceback"

C'est là qu'on a trouvé que la nuit du 27 était perdue AVANT le redémarrage.

**Un commentaire est de la PROSE** — `verifier_controles.sans_le_css` ;
l'exception est une DÉCLARATION.

**Un banc en lecture seule tourne aussi dans la VM** ; le banc Windows reste la
PREUVE et le seul chemin vers le serveur. Ce qui ÉCRIT n'est pas lançable au
banc.

### Juger

**Un rattrapage ne doit jamais dépendre de la ressource qui vient de tomber.**
C'est ce qui a tué le tagueur. Ne pas pouvoir noter un échec est regrettable ;
mourir en essayant de le noter fait perdre tout le reste. Vaut aussi pour un
`ROLLBACK` qui masque la cause.

**Une corrélation n'est pas une cause** — le banc du trailer le dit lui-même.

**Ce qui doit s'accorder, c'est le VERDICT, pas la valeur** (`44px` =
`var(--touch)`).

**Ne pas voir une cible ne la rend pas conforme** — tout rapport dit sa PORTÉE,
et elle se lit.

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui interrompt tagging et scan.

**L'ordre de la cascade a QUATRE étages** : `components.css` → page →
`tokens.css` → `base.css`. Une feuille inchangée figure des DEUX côtés de
`--avant`/`--apres`.

**Changer une BALISE change son style par défaut.**

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique.

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut.

**Un nom accentué passe au banc par le jeton `b64:`.**

> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h). Les epochs du
> serveur sont la seule heure fiable.
>
> **Le dossier monté a un cache** : `tail` peut rendre du vieux. Le `mtime`
> (`ls -l`, `date -r`) dit la vérité.
