# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (29/08/2026, session 64, ~02:00 — SI LE PC A PLANTÉ, LIS CECI)

**Tout le code ci-dessous est VÉRIFIÉ vert cette nuit** (les trois bancs de test lancés nommément, jamais `discover` : `ecriture_meta`, `rangement_annee`, `appliquer_plan_annee` — tous VERTS ; la voie C de réparation confirmée par `verifier_reparation_exif.py` sur une copie). Une partie a été écrite par un tour qui a planté avant de le dire ; Mike a relancé. **Une seule session** — le « deuxième écrivain était moi.** Ne pas re-faire ce travail : le vérifier sur le disque, il y est.

**RIEN de cette session n'est encore dans git après `a6ff878`** (les agents
étaient fermés). Sur le disque, non gravés : `server.py` (réparation EXIF
corrigée), `ecriture_meta.py` + test, `rangement_annee.py` +
`appliquer_plan_annee.py` + tests (cible `Photos Mike`, 7 magasins), les
bats `34` et `35`, `verifier_reparation_exif.py`, `eval/DECISIONS.md`,
`QUESTIONS_MIKE.md`, `ROADMAP.md`, ce fichier. **Premier geste après le
redémarrage du serveur : `livrer`** (règle 5 : `server.py` doit tourner).

### Le rangement des 1 217 photos — DÉCISION DE MIKE : nettoyage manuel

**Ce qui s'est passé (29/08 matin).** Le rangement a rebondi : `_run_plan_annee`
n'est appelé QUE par le bouton Réglages, jamais au démarrage ; le plan datait du
28/08 18:57 (cibles RACINE) ; bat 26 l'a relu et re-rangé à la racine ; bat 34 a
refusé les 17 dossiers (pleins). **Rien perdu.**

**Décision de Mike (29/08) : il NETTOIE la racine À LA MAIN, serveur ALLUMÉ.**
Beaucoup des fichiers racine viennent de l'album des 40 ans de Florine, déjà
dans le fonds — donc des doublons à effacer, pas à ranger. C'est SÛR : le scan
(5 min) via `forget_everywhere` purge tags + détections + vecteurs, **aucun nom
humain perdu** (fiches keyées par nom). Le dance undo→bat26 pour les 658 Takeout
est donc ABANDONNÉ. **État à vérifier en début de session** : `device_list_dir`
sur `N:\Photos\<annee>` (racine) — combien reste-t-il ? Un keeper (non-doublon)
laissé à la racine se remet dans `Photos Mike\<annee>` en le DÉPLAÇANT à la main
(le scan re-clé sans re-taguer, `_sync_dir` étape 1, décisions préservées) — ou
me le signaler et je le range.

**Dédoublonner `_A TRIER` (déjà rangé) — OUTILS PRÊTS (29/08).** Les collisions du bat 26 sont des JUMEAUX déjà dans le fonds, différant de quelques octets de tags (donc `recensement_doublons` sha256 les rate). `verifier_doublons_atrier.py` (lecture seule) les confirme par `exiftool -ImageDataHash` (validé 30/30 sur Samsung 2021) ; `deplacer_doublons_atrier.py` les met en `.corbeille-rangement` (serveur ALLUMÉ, ne touche pas la base, réversible `--undo`, auto-purge bat 24) ; garde « aucun nom perdu » via `--db`. **Bat 36** enchaîne détection → aperçu → retrait. Le plein dépasse 600 s → via le bat, pas le banc.

**Reste à ranger par le plan : les 559 photos 2021 dans
`_A TRIER\211108-210801 Samsung Mike\`** (correctement annulées, toujours là).
Elles, elles passent par le plan : serveur allumé → **bouton Réglages « Plan de
rangement par année »** → VÉRIFIER que `docs/plan_rangement_annee.json` vise
`Photos Mike` (`device_list_dir` ne monte pas le NAS ; lire le JSON qui, lui,
est dans le projet) → serveur arrêté → **bat 26** (le garde-fou laisse passer un
plan sain, refuse un plan-racine) → démarrer → bat 34 si des dossiers année sont
vides.

**Garde-fou posé et testé** (`appliquer_plan_annee.plan_vise_la_racine` ;
`test_appliquer_plan_annee.py` 6) VERT) : bat 26 refuse un plan qui range à la
racine et dit de le régénérer. Agit sans redémarrage (bat 26 lit ce script).

**À CODER ensuite** : `_run_plan_annee()` au démarrage du serveur, pour qu'un
plan périmé ne puisse plus être appliqué faute d'avoir été régénéré.

### Tranché par Mike cette nuit

- **Google** : il efface (`photos.google.com` sur PC, sauvegarde du téléphone
  COUPÉE avant, corbeille à vider ensuite ; le Takeout dézippé reste la 2e
  copie des Motion Photos complets). La vérification a rendu : ABSENT 0, les
  199 « NAS plus petit » sont nos copies (14 Motion Photos amputées par
  `repair_file`, `_original` intact ; 185 de padding, zéro tag perdu).
- **`_Uploads`** → boîte de réception par propriétaire,
  `Photos <Nom>\_A TRIER\` (`eval/DECISIONS.md`). À coder dans le chantier 17.
- **`repair_file`** ne détruit plus : `write_metadata` réécrit XMP + IPTC
  sans toucher l'EXIF quand ExifTool ne sait pas le relire
  (`verifier_reparation_exif.py`, voie C ; `ecriture_meta.py`, 14 verts).

## Prochain pas (après le nettoyage racine + rangement Samsung + `livrer`)

0. **Demander à Mike de reconnecter `N:\Photos`** (voir l'encadré ROADMAP),
   puis `device_list_dir` sur les dossiers racine `N:\Photos\<annee>` pour voir
   où en est son nettoyage manuel.
1. **Supprimer `_to_delete/`** (43 Mo). Geste de Mike.
2. **Le 9 septembre au matin** : Windows a-t-il DEMANDÉ ? `Get-WinEvent
   -FilterHashtable @{LogName='System'; Id=1074}`.
3. **Chantier 17** : PROPRIÉTAIRE, avec `_Uploads` → boîte de réception ;
   puis attribution rétroactive des 3 767 décisions.
4. **Chantier 18 (confidentialité)** : le jeu étiqueté et son banc d'abord.
5. **Le panneau `?` des raccourcis** — brique : un JS commun injecté partout.
6. **UNIFIER le re-clé** (trois primitives) — l'annulation de cette nuit en
   est le premier client réel.
7. **Reste d'audit** : O8–O9, O11, O13–O15 ; I1 ; `animal:luna` (3) vs
   `animal:Luna` (355) ; quatre pages sans `components.css` (`/map` est
   témoin de `verifier_pages_composants`).

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
