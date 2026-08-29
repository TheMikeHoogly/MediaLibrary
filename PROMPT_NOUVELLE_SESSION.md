# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (29/08/2026, session 65, matin)

**Tout ce qui précède est GRAVÉ** : `main` = `9ef9134` (réparation EXIF voie C,
`ecriture_meta.py`, rangement par année + garde-fou racine, bats 34/35/36,
outils de dédoublonnage `_A TRIER`). Vérifié dans `.git/logs/refs/heads/main`.

**Le NAS ce matin** (`N:\Photos` connecté) : la RACINE est PROPRE — plus aucun
dossier `<annee>` à la racine, le nettoyage manuel de Mike est fini. Les
**559 Samsung 2021** sont toujours dans `_A TRIER\211108-210801 Samsung Mike\`.
Mike fait tourner **bat 36** (dédoublonnage `_A TRIER`, serveur allumé), puis
**bat 34**.

### Fait en session 65, NON gravé, NON observé (serveur intouché : bat 36 tourne)

Le deuxième étage du garde-fou anti-plan-périmé :

- `server.py` : `fil_surveille(_run_plan_annee, nom='plan:annee', boucle=False)`
  au démarrage, entre les backfills et `face_worker` — le plan se recalcule à
  CHAQUE démarrage (ligne `🗂 plan rangement annee : N a ranger…` au journal).
- `appliquer_plan_annee.py` : `dernier_demarrage()` lit la dernière bannière
  `DEMARRAGE` de `_journal_serveur.log`, `plan_perime()` refuse (REFUS, code 1,
  `--forcer` passe outre) un plan dont le mtime est antérieur. Sans journal :
  laisse passer. `test_appliquer_plan_annee.py` **7)** — tout vert.
- `ROADMAP.md` 1 sexies mis à jour.

Et le **chantier 17, étape 2** (Mike a suivi mes deux recommandations, gravées
dans `eval/DECISIONS.md`) : `auteurs.py` + `test_auteurs.py` (22 verts),
`recle_decisions` transporte `auteurs` (+3 tests), `server.py` : thread-local
`utilisateur_courant()`, `_auteurs.garnir(PEOPLE_STORE/PETS_STORE)`,
`migrer_auteurs()` lancé par `fil_surveille` au démarrage (attendu au journal :
`✍ auteurs : N décision(s) attribuée(s) à Mike sur M fiche(s)`, N ≈ 3 700,
puis plus rien aux démarrages suivants). `.gitignore` : `docs/migration_auteurs.json`.

**Conséquence immédiate** : le plan de 09:53 est antérieur au démarrage de
10:51:59 → bat 26 le REFUSE tant que le serveur n'a pas redémarré sur le
nouveau code (et c'est juste : bat 36 déplace des fichiers depuis).

## Prochain pas

1. **Au signal de Mike** (bat 36 et 34 finis) : `redemarrer` → journal :
   bannière neuve + ligne `🗂 plan rangement annee` + ligne `✍ auteurs` (et
   zéro `FIL MORT`) ; lire
   `docs/plan_rangement_annee.json` (vise `Photos Mike\2021`, ~559 moves) ;
   `code_a_jour` vrai. Puis `SESSION_COMMIT.txt` + `livrer`, vérifier
   `.git/logs/refs/heads/main`.
2. Mike : `arret` → **bat 26** (le plan passe les deux gardes) → `marche` →
   vérifier `_A TRIER\211108-210801 Samsung Mike\` vide, `Photos Mike\2021`
   +559, et 27 décisions-témoins intactes.
3. **Chantier 17** : PROPRIÉTAIRE, avec `_Uploads` → boîte de réception
   `Photos <Nom>\_A TRIER\` (tranché, `eval/DECISIONS.md`) ; puis attribution
   rétroactive des 3 767 décisions.
4. **Supprimer `_to_delete/`** (43 Mo). Geste de Mike.
5. **Le 9 septembre au matin** : Windows a-t-il DEMANDÉ ? `Get-WinEvent
   -FilterHashtable @{LogName='System'; Id=1074}`.
6. **Chantier 18 (confidentialité)** : le jeu étiqueté et son banc d'abord.
7. Le panneau `?` des raccourcis · UNIFIER le re-clé (trois primitives) ·
   reste d'audit (O8–O9, O11, O13–O15 ; I1 ; `animal:luna` vs `animal:Luna` ;
   quatre pages sans `components.css`).

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
