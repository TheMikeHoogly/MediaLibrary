# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (29/08/2026, session 66, soir)

**Git** : tout fusionné jusqu'à `feat/l-ecriture-restreinte` (`708099d`,
21:54) ; puis `feat/la-corbeille-a-6-mois` (`eafd363`) et
`fix/la-corbeille-des-effacements-est-sur-le-nas` — vérifier `.git/logs/refs/heads/main`.

**Serveur** : redémarré à 22:16:56 sur le code de l'étape 6, `code_a_jour`
vrai, zéro fil mort, porte fermée (2 comptes). Index 43 702.

**Chantier 17, étape 6 — la CORBEILLE À 6 MOIS, POSÉE ET OBSERVÉE (22:19)** :
journal `par` + `expire` (+180 j), `FileOps.corbeille()/restaurer(ts)/purger()`
(12 tests), `/api/corbeille` (admin) + `restaurer|purger`, section Réglages.
Observé : effacer `Photos Mike\PRIVE\Mike-test.jpg` → entrée (Mike, +180 j,
2,9 Mo) → restaurée, journal vide, vignette 200 ; purge à blanc : rien.
**Corbeille déplacée sur le NAS** (choix de Mike, 22:38) :
`\\NAS…\Photos\.corbeille-effacements`, observé : effacer → panier sur le NAS
(Mike, 2,9 Mo) → restauré, vignette 200. **Carnet vide** : la copie canonique entre propriétaires est celle de
`Photos Mike` par défaut (tranché 29/08 soir).

**Trois demandes de Mike le soir, toutes en ROADMAP** : recherche IA
(**1 nonies** — deux défauts corrigés et observés : « ours en peluche » sur
une page `?jour=` rendait 0 → 1 500 ; les puces « 60 tags » comptaient
`_Uploads` sur toute grille-résultat → comptent le résultat) ; doublons
(**1 decies** — mesuré sur copie de l'index : 2 921 groupes même seconde +
même nom dont 27 seulement au même octet : les copies taguées séparément ;
**pas de rescan**, banc d'image sur les candidats) ; vidéos dans la galerie
(**1 octies phase 1**, détaillée a→d).

**Bat 39 : FAIT par Mike (21:17, deux passes, 20 + 3 053 = 3 073 vidéos →
`Photos Mike\<année>`, undo `docs/undo_annee_20260829_2117*.json` et
`_2121*`)** ; le banc a reconfirmé à 21:22 **0 vidéo** dans `_A TRIER`.
Reste `_to_delete/` (43 Mo), geste de Mike.

**Chantier 17, étape 5 — l'ÉCRITURE RESTREINTE, POSÉE (21:33, choix de Mike :
fichier au propriétaire, fiche entière et maintenance à l'admin)** :
`visibilite.peut_ecrire` / `refus_ecriture` (7 tests, 21 verts), injecté dans
`fichiers.FileOps(garde=…)` — un seul goulot, consulté AVANT le disque sur
source et destination, et sur le journal AVANT de dépiler un `undo` (11 tests
neufs, tous verts) ; `server.py` : `refus_ecriture()` à côté de
`chemin_visible()`, `FileOpRefus` → son code (403/404) avec `{ok:false,
error}` que les clients lisent déjà, `_exige_admin` sur `people|pets/
rename|delete` et `/api/maint/*`. **Les décisions sur photo ne passent pas
par là** (arbitrées par `auteurs`). Verdict gravé dans `eval/DECISIONS.md`.
**Banc** : `verifier_non_fuite.py` contrôles 8–9 (B efface le PRIVE de A →
404 et A la voit encore ; B efface une PARTAGÉE de A → 403, intacte ; témoin
POSITIF : A renomme à l'identique → permis, `changed:false`, rien ne bouge ;
`people/delete` et `maint/census` par B → 403). **OBSERVÉ EN RÉEL (21:50,
lancé par Mike)** : **12 verts, 0 fuite** — dont B → 404 sur le PRIVE de A,
A la voit encore, A renomme à l'identique (permis, `changed=False`), B → 403
sur `people/delete` et `maint/census`. **Non observé** : le 403 sur une
photo PARTAGÉE de A — le banc la cherche par les noms et « 1 Bolivia » n'en
porte aucun ; couvert par `test_fichiers.py`, à observer avec
`--cle-partagee` (ou dès qu'un nom est posé sur la PRIVE : contrôles 4–6).

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

**Chantier 17, étape 3 — la VUE par utilisateur, MÉCANISME POSÉ (14:29)** :
`visibilite.py` (règle + vues + `brancher`, 14 tests dont le vrai
`SqliteStore`), branché aux cinq magasins par `utilisateur_vu()` (None sans
compte → dormant), garde `chemin_visible` sur `/media`, `/uploads`,
`/api/thumb`. Observé : serveur 14:29:28, zéro fil mort, `/api/people/list`
identique (Florine 6084, Mike 5619) avec `contestes: 0` partout. **Piège vu
et corrigé** : mon `replace` de `people_list` avait touché `pets_list`
(même forme de code) — `/api/people/list` ne portait PAS `contestes` après
la livraison `fe75093` ; vu en regardant la vraie réponse, pas au banc.

**Chantier 17, étape 4 — les COMPTES, POSÉS (14:53, mot de passe par compte,
choix de Mike)** : `comptes.py` (15 tests), `creer_compte.py`, `/connexion`,
`/api/connexion|deconnexion|moi|comptes*`, section Réglages, porte sur chaque
requête (`_ouvrir`), `comptes.json` hors git. Observé sans compte : porte
ouverte, rien ne change. **Le banc de non-fuite existe** : `verifier_non_fuite.py`
(vrai serveur, deux comptes, une clé PRIVE ; 7 contrôles). **OBSERVÉ EN RÉEL (15:09–15:20)** : comptes Mike et Flo créés par
`creer_compte.py`, porte fermée, connexions au journal (`🔐 connexion`),
`Photos Mike\PRIVE\1 Bolivia.jpg` indexée (`📒 +1`), et le banc rend
**5 verts, 0 fuite** (porte 401/302, A voit, B : thumb 404, faits « inconnue »).
Le banc a eu un défaut vu en réel : lancé sur une clé inexistante il disait
FUITE au lieu de « précondition non tenue » — corrigé (code 2, s'arrête) ; et
le contrôle `/media` ne dépendait plus d'une fiche (URL construite). **Reste
à observer** : les contrôles 4–6 (COMPTEUR A = B + 1, fiche, recherche) —
ils exigent un nom sur la photo PRIVE ; c'est le point 17b lui-même.

**Traite de l'après-midi** : bat 38 (0 dossier vide, 125 `_original`
RELIQUATS gardés), vidéos phase 0 (`inventaire_videos.py`, bat 39, ffmpeg
7.1.1 présent) — livrés, fusionnés, et bat 39 a tourné (ci-dessus).

**`N:\\Photos`** : règle permanente dans `CLAUDE.md` (« Tester en réel »).

**Carnet `QUESTIONS_MIKE.md`** : vide.

## Prochain pas

1. Au choix de Mike : **doublons** (1 decies :
   d'abord `mesure_doublons_image.py`, lecture seule, par l'agent banc) ;
   **vidéos phase 1** (1 octies : scan → vignette ffmpeg → galerie) ;
   **recherche IA** (1 nonies : banc en aveugle FR→EN avant de coder).
   Chantier 17, reste : étape 7 (onboarding ; `/upload` sous un compte devrait
   atterrir chez l'envoyeur, pas dans `_Uploads`), conflit de `faces` ENTRE
   fiches, contrôle 403 « photo partagée » du banc (`--cle-partagee`).
   `_to_delete/` (43 Mo) : geste de Mike.
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
