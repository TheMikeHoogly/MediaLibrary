# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (nuit du 31/08 au 01/09, session 70 — le compte Motion Photo)

**Git** : fusionné jusqu'à `feat/menu-de-compte` (`34a9f1d`, 31/08 22:33) ;
la session 70 livre `feat/compte-motion-photo` en BRANCHE (traite autonome,
`commit` — la fusion attend Mike) — vérifier `.git/logs/refs/heads/main`.
**Serveur** : redémarré 31/08 22:39 sur `34a9f1d` (index 44 852, 0 fil mort).
**Carnet `QUESTIONS_MIKE.md` : vide.**

**Motion Photo (1 septies) — COMPTÉ et OUTILLÉ (session 70).** Le banc
`mesure_motion_photos.py` (reprenable, ~14 passes de 450 s par le canal banc)
a couvert 40 271/40 291 JPEG de l'index : **2 441 Motion Photos, toutes chez
Mike** (2021 : 461 · 2024 : 1 241 · 2025 : 504 · 2026 : 188 · 47 sans année),
**8,64 Go de vidéo à reprendre** sur 16,83 Go de fichiers. Et **16 519
trailers SEF SANS vidéo** (Flo 2017-2019 surtout) : PAS des Motion, rien à y
gagner. Rapport `docs/motion_photos.json`. Outillage posé, 11 tests verts
(Windows aussi), bats contrôlés ASCII : **bat 42** = strip (aperçu → essai
20 → tout ; serveur ARRÊTÉ exigé par `refus_d_ecriture` ; chaque fichier
laisse `photo.jpg_original` = undo ; manifeste
`docs/strip_motionphoto_manifeste.json`) ; **bat 43** = purge des originaux
en QUARANTAINE `.corbeille-rangement\strip_motionphoto_*` (manifeste,
réversible ; l'option `_A TRIER` couvre les 125 de la décision du 29/08).
**Le strip et la purge sont des gestes de MIKE** — rien ne se lance d'ici.

**Ventilation : PAS FAITE (Mike, 31/08 soir)** — les bancs GPU restent en
PAUSE : sensibles (ch. 18, ~90 questions), re-tagging (2 bis), vidéos
phase 2 (1 octies d). Ne rien relancer sans son feu vert. La liaison avec le
PC est tombée ~01:35 et revenue ~02:20 (cause inconnue — demander à Mike si
le PC a coupé, Kernel-Power 41 ?).

**Menu de compte, panneau `?`, loupe encadrée, visionneuse, planche Dossiers,
recherche IA partout : FAITS, OBSERVÉS** — détail dans `ROADMAP.md` et git.

## Prochain pas

1. **Mike lance le bat 42** (strip : aperçu → essai 20 → tout, serveur
   arrêté), vérifie des stills, puis **bat 43** (purge). ~8,6 Go rendus.
2. **Fusionner `feat/compte-motion-photo`** (`livrer`, ou 27 - Git) après
   son regard.
3. **Ventilation/dépoussiérage** (Mike) → feu vert des trois bancs GPU :
   sensibles (ch. 18), re-tagging 2 bis (~100 photos comparées AVANT les
   26 h), vidéos phase 2 (30 vidéos, 1 puis 3 images-clés).
4. **UPLOAD : de fond, et reprenable (Mike, 01/09 — 1 quindecies)** :
   (a) l'envoi se met en pause quand l'onglet perd le focus — suspect : les
   minuteurs JS throttlés en arrière-plan ; MESURER où ça bloque, puis
   enchaîner les `fetch` sans `setTimeout` ; (b) à la reprise d'un envoi
   interrompu, SAUTER ce que le serveur a déjà (nom+taille, ou hash, demandé
   avant d'envoyer chaque fichier).
5. **La Carte a deux champs** (barre + « Rechercher (noms, lieux, sens) ») :
   à trancher avec Mike — garder les deux ou fondre.
6. Chantier 17 (étape 7 onboarding, conflit `faces` entre fiches, 403 du
   banc) ; chantier 18 la suite (liste à juger → seuil → écran d'envoi →
   passe rétroactive).
7. `ROADMAP.md` à réduire AVEC Mike (~1 540 lignes, rôle = carte).
8. 9 septembre : Windows a-t-il demandé ? (`Get-WinEvent … Id=1074`).
9. UNIFIER le re-clé (3 copies de la primitive).

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, clé imprimée, restauration
  d'épreuve. Ne PAS toucher au Takeout `C:\GOOGLE PHOTOS\extrait` avant.
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**Un marqueur n'est pas la chose.** `SEFT` en queue ≠ Motion Photo : 16 519
JPEG portent un trailer SEF de MÉTADONNÉES sans vidéo. Et un `ftyp` nu dans
l'entropie JPEG ment — 3 « Motion » sur 3 avaient une vidéo estimée à 100 %
du fichier avant que la boîte soit validée (taille big-endian + brand
lisible). L'annuaire `SEFH` en queue DIT s'il y a un bloc `MotionPhoto_Data` —
sans lecture pleine.

**Les fils n'accélèrent pas un partage SMB déjà saturé** : 8 lecteurs ont fait
MOINS que 1 (2,6 contre 4,5 fichiers/s) et semé 21 `EINVAL` muets. Mesurer
avant de paralléliser — et une erreur non nommée et non cachée rend
« TERMINÉ » inatteignable.

**La bonne ÉCHELLE, sinon la bonne conclusion sur les mauvaises données.**
Dérive par rapport à QUOI — le signal était ENTRE les sessions.

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton
`b64:`), plafond **600 s** : un banc long est REPRENABLE (cache écrit à
chaque passe) et se lance avec `--budget-s 450`.

**Ne JAMAIS lancer `unittest discover` depuis la VM** : trois tests ouvrent le
vrai `photos.db`.

**ExifTool sous Windows perd les accents des arguments** : argfile UTF-8 BOM
(`server._run_exiftool`, repris par `appliquer_strip_motionphoto`).

### Lire

**Le journal du serveur d'abord**, depuis la dernière bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "FIL MORT\|THREAD MORT\|Traceback"

**Savoir d'où vient un chiffre.** `verifier_photos_google` lit le DISQUE ;
`generer_plan_annee` lit l'index en mémoire — les confondre a coûté des heures.

**Le plan n'est régénéré QUE par le bouton Réglages / `POST
/api/maint/plan-annee`.** `plan_vise_la_racine` et `plan_perime` gardent.

### Juger

**Avant de RECOMMANDER une règle, relire `eval/DECISIONS.md` en entier sur le
sujet.** Le carnet des décisions n'est pas un journal — c'est la contrainte.

**Un rattrapage ne doit jamais dépendre de la ressource qui vient de tomber.**

**Un `replace` sur un motif présent DEUX fois touche le mauvais — `assert
count == 1` avant.**

**Un banc vert n'est pas un regard.**

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui interrompt tagging et scan.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique ;
les applicateurs le PROUVENT (`refus_d_ecriture` : HTTP + verrou).

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut ; le
strip le VÉRIFIE fichier par fichier.

> **`N:\Photos` se CONNECTE à chaque session** (picker « Add folder », non
> persistant) : demander à Mike au « Go ». Connecté : `device_list_dir` /
> `device_stage_files` / `device_commit_files` — mais PAS monté dans
> `device_bash` (réseau) : un script sur tout le fonds passe par l'agent banc
> (Windows, UNC).
>
> **Piège git via `device_bash`** : jamais de git d'ici (`.git/index.lock`
> résiduel indélébile) ; un lock qui traîne se renomme (`mv`), ne s'efface pas.
>
> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).
