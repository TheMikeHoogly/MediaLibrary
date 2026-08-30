# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (30/08/2026, session 68 — la recherche IA est dans la barre)

**Git** : fusionné jusqu'à `feat/elargissement-fr-en` (`a78faa4`) ; la
session 68 livre `feat/recherche-dans-la-barre` — vérifier
`.git/logs/refs/heads/main`. **Serveur** : redémarré 16:55 sur ce code (index
**44 860**, 0 fil mort). **Carnet `QUESTIONS_MIKE.md` : vide** (les 10 noms tranchés le 30/08 soir).

**Doublons (1 decies) — APPLIQUÉS PAR MIKE le 30/08**, les deux lots : 2 929
fichiers en `.corbeille-rangement\dedup_image_*`, index 47 789 → 44 860, 218
décisions fusionnées, 19 noms recopiés. **Le caillou des 10 noms re-retirés est CLOS** :
Mike a tout tranché le soir même, verdicts appliqués et observés ; `confirm`
grave `confirmed`, qui neutralise l'exclusion sans l'effacer
(`test_confirm_grave.py`, `eval/DECISIONS.md`).

**Scission FR/EN (1 undecies) — APPLIQUÉE PAR MIKE 15:08** : 22 176 entrées.
Observé : « chaise » → puces françaises. Le serveur scinde à la relecture d'un
XMP (code livré, pas encore exercé : aucun import depuis).

**Classification : loupe sur la vignette (1 quaterdecies, Mike 20:10) — FAIT,
OBSERVÉ.** Reste : encadrer le visage visé dans la loupe (boîte à exposer
par `/api/curator/list`).
**Visionneuse (1 terdecies, Mike 19:50) — FAIT, OBSERVÉ** : description en
clair, mots-clés au survol ou par le bouton, lien `📁 dossier` →
`/files?dir=…&vers=<nom>` qui encadre la photo dans son dossier.
**Panneau `?` (point 2) — FAIT, OBSERVÉ** : `/api/raccourcis` sert
`docs/RACCOURCIS.md`, `global.js` le rend (section de la page en tête).
**Recherche IA partout (1 duodecies) — FAIT, OBSERVÉ (session 68)** : vrai
`<form action="/files">` `name=q` dans `APP_NAV_HTML`, masqué sur `/files`,
raccourci `/`, deux lignes à 390 px. **Et la brique JS commune existe** :
`ui/global.js` (onglet actif, sablier, recherche), injectée par
`_send_html` → `injecter_js_commun` juste après la barre, relue à chaud, cuite
par `bundle.py`. `test_ui_global.py` : 17 verts, rougissent sur mutation.

**Chantier 17** : étapes 1→6 posées. Reste : étape 7 (onboarding ; `/upload`
sous un compte → chez l'envoyeur), conflit de `faces` ENTRE fiches, contrôle
403 « photo partagée » du banc. **Vidéos phase 1** : la LECTURE n'a pas été
observée (un clic de Mike).

## Prochain pas

1. **FAIT (30/08 soir)** : les 10 noms tranchés et appliqués ; la
   confirmation fait autorité sur l'exclusion (gravé, testé).
2. **Panneau `?` : FAIT** (session 68, `feat/panneau-raccourcis`). Reste
   l'instrument qui relève les touches écoutées dans `ui/pages`.
3. **La loupe de la classification : encadrer le visage visé** (la boîte
   dans `/api/curator/list`, un rectangle veilleuse sur la photo).
4. **La Carte a deux champs** (barre + « Rechercher (noms, lieux, sens) ») :
   à trancher avec Mike — garder les deux (fonds entier / filtre carte) ou
   fondre.
5. **Vidéos** : faire LIRE une vidéo à Mike ; puis phase 2.
6. `ROADMAP.md` à réduire AVEC Mike (~1 500 lignes, rôle = carte).
7. 9 septembre : Windows a-t-il demandé ? (`Get-WinEvent … Id=1074`).
8. Règle Motion Photo (1 septies), chantier 18, UNIFIER le re-clé.

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, fonds 291 Go, clé imprimée,
  et une restauration d'épreuve. **La ligne internet ne change pas
  maintenant** (choix de Mike, 28/08).
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**La bonne ÉCHELLE, sinon la bonne conclusion sur les mauvaises données.**
J'ai comparé les durées de tagging à l'intérieur d'une session — plates — et
conclu « pas de bridage ». Le signal était ENTRE les sessions : 27,2 s contre
9,7–22,8 s. Avant de conclure « pas de dérive », demander : dérive par rapport
à QUOI.

**Interroger un outil externe CHAMP PAR CHAMP avant de le grouper.**
`power.limit` et `temperature.memory` rendent `[N/A]` sur cette carte, et un
seul champ refusé fait échouer TOUTE la requête `nvidia-smi` — sans dire
lequel. Les demander à l'aveugle aurait aveuglé `hw_state` sur sa propre VRAM.

**Un rouge causé par un NOM manquant ne prouve rien** sur le comportement.
Il faut que l'ancien code s'EXÉCUTE (`hasattr`, pas un accès direct). Et tous
les tests ne peuvent pas rougir : un garde d'un mécanisme NEUF ne le peut pas.

**Un banc qui imprime doit rester lisible par une console cp1252** — c'est
celle de l'agent git. Deux bancs sur ~90 étaient fautifs le 28/08, corrigés,
zéro restant (balayage AST des `print`).

**Ne JAMAIS lancer `unittest discover` depuis la VM** : trois tests ouvrent le
vrai `photos.db`.

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton `b64:`,
en argument SÉPARÉ) et son plafond est **600 s** — échantillonner au-delà.

**Le canal du banc TUE à 600 s et le rapport de la passe est perdu** :
un banc long est REPRENABLE (cache écrit à la fin de chaque passe) et se
lance avec un budget qui laisse 2–3 min de marge (`--budget-s 450`), car le
NAS ralentit quand le serveur énumère en même temps (1,2 → 0,8 fichier/s).

**ExifTool sous Windows perd les accents des arguments** : chemins via
argfile UTF-8 avec BOM (`server._run_exiftool`), sinon 36 « inconnus » sur 80.

**Un `<video>` dans un onglet Chrome CACHÉ ne charge rien** (Chrome diffère
le média : `document.visibilityState = hidden`, événement `stalled`). Le flux
se prouve par `fetch` + `Range` ; la lecture, par un œil devant l'onglet.

### Lire

**Un dossier « modifié hier soir » n'est pas vide.** Compter avant d'effacer :
`inventaire_racine_photos.py`, 8 s. Et un banc qui parcourt le NAS imprime
`flush=True` — un timeout à 600 s sans sortie tamponnée ne laisse rien.

**Le journal du serveur d'abord**, depuis la dernière bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "FIL MORT\|THREAD MORT\|Traceback"

**Savoir d'où vient un chiffre.** `verifier_photos_google` lit le **DISQUE**
(il ne touche jamais `STORE`) : il n'attend pas le tagging. `generer_plan_annee`
lit l'**index en mémoire** : un fichier n'y entre qu'une fois TAGUÉ. J'ai fait
attendre Mike des heures pour rien en confondant les deux.

**Le plan n'est régénéré QUE par le bouton Réglages / `POST /api/maint/plan-annee` — JAMAIS au démarrage.** Un `cible()` corrigé ne suffit pas : sans un clic, bat 26 relit un vieux plan et range au mauvais endroit (rebond du 29/08). Le garde-fou `plan_vise_la_racine` refuse maintenant un plan-racine ; régénérer et VÉRIFIER reste le réflexe.

**Un plan appliqué n'est pas un plan calculé.** `appliquer_plan_annee` relit
`docs/plan_rangement_annee.json` ; s'il date, il rend `skip: N` et ne range
rien.

### Juger

**Avant de RECOMMANDER une règle, relire `eval/DECISIONS.md` en entier sur le
sujet.** Le 29/08 j'ai proposé « le propriétaire l'emporte » sans voir que Mike
avait tranché « le dernier gagne » la veille : deux décisions contradictoires
gravées sous son nom, à démêler après coup. Le carnet des décisions n'est pas
un journal — c'est la contrainte.


**Un rattrapage ne doit jamais dépendre de la ressource qui vient de tomber.**
Ne pas pouvoir noter un échec est regrettable ; mourir en essayant fait perdre
tout le reste. Vaut aussi pour un `ROLLBACK` qui masque sa cause.

**Une corrélation n'est pas une cause.** Le banc du trailer le dit lui-même.

**Ne pas voir une cible ne la rend pas conforme** — tout rapport dit sa PORTÉE.

**Un `replace` sur un motif présent DEUX fois touche le mauvais — `assert
count == 1` avant.** Le 29/08, l'édition visée sur `people_list` a atterri
dans `pets_list` (même forme) ; le serveur a tourné, les tests étaient verts,
et `/api/people/list` ne portait pas le champ. Vu en lisant la VRAIE réponse.

**Un banc vert n'est pas un regard.** Les instruments savaient dire que les
règles étaient là ; ils ne pouvaient pas dire que l'étiquette avait cessé de
faire semblant d'être un bouton.

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui interrompt tagging et scan.

**L'ordre de la cascade a QUATRE étages** : `components.css` → page →
`tokens.css` → `base.css`.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique ;
`26 - Ranger par annee.bat` exige qu'il soit ARRÊTÉ, et le PROUVE deux fois.

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut.

> **`N:\\Photos` est CONNECTÉ (29/08)** — le NAS en direct. Se lit avec
> `device_list_dir` (rapide, rend tailles+mtime), se prélève avec
> `device_stage_files`, s'écrit avec `device_commit_files`. MAIS c'est un
> emplacement réseau : **PAS monté sous `$HOME/mnt/` dans `device_bash`**
> (seul `MediaLibrary` l'est). Donc pas de `grep`/`find`/python direct sur
> le NAS — pour un script sur tout le fonds, passer par l'agent banc
> (Windows, accès UNC) ; pour inspecter ou dédoublonner du ciblé,
> `device_list_dir` + `device_stage_files` suffisent. L'UNC `\\NAS-…` et un
> lecteur mappé restent, eux, ingrantables : c'est le picker de l'app qui
> a monté `N:\\Photos`.
>
> **Piège git via `device_bash`** : le bac à sable REFUSE à git de délier son propre `.git/index.lock` (« Operation not permitted »), donc chaque `git status` d'ici laisse un verrou résiduel qui bloquerait l'agent `livrer` natif de Mike. Ne PAS faire de git depuis `device_bash` juste avant que l'agent tourne ; si un lock traîne, le renommer (`mv`, permis) au lieu de `rm`. Deux `.git/index.lock.stale-*` inertes traînent — git les ignore, Mike ou une session peut les retirer.
>
> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).
>
> **Le dossier monté a un cache** : le `mtime` dit la vérité, `tail` peut
> mentir. Mais un gel SIMULTANÉ de plusieurs fichiers au même instant est
> aussi ce que produit une vraie fermeture — demander à Mike plutôt que de
> conclure.
