# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (29/08/2026, session 66, après-midi)

**Git** : tout fusionné jusqu'à `fix/le-plan-dit-quand-il-a-fini` (13:19) ;
la session 66 livre `feat/les-9-homonymes-google-en-quarantaine` — vérifier
`.git/logs/refs/heads/main`.

**Serveur** : redémarré par Mike à 13:24 sur le code livré, zéro fil mort.

**Le rangement `_A TRIER`** : bat 26 a tourné à 13:22 (**29 rangés**, undo
`docs/undo_annee_20260829_1322*.json`). Les **9 restants** du plan sont des
ré-encodages Google (9 des 21 `IMAGE_DIFFERENTE` de `_reprise_google.json`)
dont `Photos Mike\<année>` a déjà l'homonyme : bat 26 les saute (collision),
à vie. Mesuré : mêmes noms des deux côtés, et le NAS porte le GPS que Google
a retiré. **Décision Mike : quarantaine des 9, le NAS reste** — outillé :
`verifier_doublons_atrier.py` écrit `homonymes_differents` (avec la règle des
noms), `deplacer_doublons_atrier.py --homonymes-differents` (opt-in, testé en
bac à sable : aperçu, application, undo, garde sur nom manquant), **bat 37**.
Rapport régénéré par le banc sur le vrai NAS (13:36, 9 entrées, aucun nom
manquant). **OBSERVÉ** : bat 37 à 13:49 (9/9, 0 skip), le serveur les a vus
partir à 13:53 (`index 43708 → 43699 (+0 / −9)`), et le bouton « Plan de
rangement par année » a rendu **0 à ranger** à 14:11:55 — le correctif de
13:17 (le bouton dit quand il a fini) est donc aussi observé. Reste **bat 34**.

**Chantier 17, étape 2 — `#contesté` VISIBLE (14:16)** : `auteurs.contestations`
(pure, 5 tests, 27 verts), route `/api/people/contestes`, `contestes` compté
dans `/api/people/list`, badge sur la carte + bouton « ⚖ N contesté(s) » dans
la fiche `/people` (vignette, qui a perdu, qui l'emporte et pourquoi).
Serveur redémarré 14:16:05 sur ce code, zéro fil mort, plan 0. Observé à
vide : `{"contestes": []}` et la page rend — un vrai contesté n'existera qu'avec
un deuxième utilisateur (étape 4).

**`N:\\Photos`** : règle permanente dans `CLAUDE.md` (« Tester en réel »).

**Carnet `QUESTIONS_MIKE.md`** : vide.

## Prochain pas

1. **Bat 34** (dossiers année vides à la racine), puis `_to_delete/` (43 Mo) —
   gestes de Mike.
2. **Chantier 17, étape 3** : la VUE par utilisateur (`PRIVE`) et son banc
   de non-fuite — le plancher du chantier (« un compteur qui fuit est un
   défaut de niveau A »). `proprietaire_de` (`auteurs.py`) est la brique.
   Reste de l'étape 2 : un conflit de `faces` ENTRE fiches n'a pas de règle.
3. **`ROADMAP.md` pèse 1 545 lignes** dont ~740 de chronique de sessions
   closes et ~325 de points CLOS racontés : contraire à son rôle (« carte des
   priorités, rien d'autre »). À réduire vers ~200 lignes — le détail vit
   dans git. Contradictions internes vues : point 1 dit « reste `.fchip` »
   (mort depuis), 1 ter « à écrire » (fait session 61), « 3 767 » vs
   « 3 364 » décisions. À faire AVEC Mike (c'est sa carte).
4. **Le 9 septembre au matin** : Windows a-t-il DEMANDÉ ? `Get-WinEvent
   -FilterHashtable @{LogName='System'; Id=1074}`.
5. **Règle Motion Photo (1 septies)** : strip `-trailer:all=` en deux temps
   réversibles, à planifier avec Mike.
6. **Chantier 18** · panneau `?` · UNIFIER le re-clé · reste d'audit.

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
