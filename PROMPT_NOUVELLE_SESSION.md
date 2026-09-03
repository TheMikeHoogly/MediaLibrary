# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (03/09/2026, session 71 — précontrôle upload, ménage ROADMAP)

**Git** : `feat/compte-motion-photo` FUSIONNÉE dans `main` ce commit (fast-
forward, technique du bat 27, jamais de `checkout main`) — vérifier
`.git/logs/refs/heads/main`. Elle portait déjà le compte Motion Photo
(session 70) et le pré-contrôle d'upload (ce commit, voir plus bas).
**Serveur** : redémarré 03/09 ~19:16 sur ce code (`code_a_jour` vérifié vrai
en réel). **Carnet `QUESTIONS_MIKE.md` : vide.**

**UPLOAD (1 quindecies) — FAIT, OBSERVÉ.** (a) déjà réglé le 02/09
(`29047e7`) : plus de `setTimeout` dans la boucle d'envoi, le focus perdu ne
la throttle plus. (b) fait cette session : `/api/upload/check` — le client
hashe le fichier EN LOCAL (`crypto.subtle`, SHA-256) et n'envoie que
taille+hash ; le serveur répond `SKIP` sans qu'un octet du fichier ait
traversé le réseau si un identique est déjà dans Uploads. Dégrade proprement
(envoi direct, comme avant) si `crypto.subtle` est indisponible — c'est le
cas sur `http://192.168.0.13:8080` en clair (Web Crypto exige un contexte
sécurisé) : **seul le nom Tailscale en HTTPS profite pleinement de
l'optimisation sur le LAN**. `_upload_dup_by_hash` factorisée hors de
`_upload_content_dup`. 10 tests (`test_upload_precontrole.py`, lit le vrai
code de `server.py` par `ast`, aucun import de `server.py` — la VM ne sait
pas ouvrir `photos.db`, `disk I/O error` propre, rien écrit, vérifié après
coup). **Reste pour Mike** : observer une VRAIE reprise après coupure sur un
gros album (le SKIP n'est prouvé qu'en synthétique + en direct sur le
serveur vivant, jamais sur un album réel interrompu — je n'allais pas écrire
dans ton vrai dossier Uploads sans ton feu vert).

**ROADMAP.md dégonflée (session 71)** : les six sections `## État (…,
session 57 à 63)` — narration de travaux déjà CLOS, déjà dans git —
condensées en un seul bloc `Ce qu'il faut garder`, comme le sont déjà les
sessions 28 à 56. **99 951 → 87 918 octets** (le seuil du lint est
100 000). **Reste un plus gros caillou, repéré mais PAS touché** : la
section `## À faire — par ordre de valeur` (~530 lignes) mélange les
chantiers 17/18 encore VIVANTS (spec citée par la Priorité du haut — n'y
touche pas) et environ 320 lignes d'items `0ter` à `16`, presque tous
CLOS entre le 12/08 et le 22/08, antérieurs au refixage des priorités du
26/08. Probablement le plus gros gisement de condensation qui reste, mais
je n'ai pas vérifié un par un s'il en subsiste un « ne pas reproposer » qui
ne vit nulle part ailleurs — à faire AVEC Mike (relire chaque item avant
de couper), pas en un passage solitaire.

## Prochain pas

1. **Mike lance le bat 42** (strip Motion Photo : aperçu → essai 20 → tout,
   serveur ARRÊTÉ), vérifie des stills, puis **bat 43** (purge). ~8,6 Go
   rendus. Rien de tout ça ne s'est encore produit — c'est le geste concret
   le plus ancien encore en attente.
2. **Ventilation/dépoussiérage** (Mike) → feu vert des trois bancs GPU en
   pause : sensibles (ch. 18, ~90 questions), re-tagging 2 bis (~100 photos
   comparées AVANT les 26 h de GPU), vidéos phase 2 (30 vidéos, 1 puis 3
   images-clés). Rien ne se relance sans son feu vert.
3. **La Carte a deux champs** (barre + « Rechercher (noms, lieux, sens) ») :
   à trancher avec Mike — garder les deux ou fondre.
4. Condenser `## À faire — par ordre de valeur` AVEC Mike (voir ci-dessus) :
   le prochain vrai gain d'« efficience » sur `ROADMAP.md`.
5. Chantier 17 (étape 7 onboarding, conflit `faces` entre fiches, 403 du
   banc) ; chantier 18 la suite (liste à juger → seuil → écran d'envoi →
   passe rétroactive).
6. 9 septembre au matin : Windows a-t-il demandé le redémarrage du Patch
   Tuesday ? (`Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074}`,
   ne pas confondre avec la coupure thermique brutale — Id 41 — du 29/08).
7. UNIFIER le re-clé (`server.rekey_everywhere`,
   `deplacer_dossiers.recle_une_cle`, `appliquer_plan.rekey_stores` : trois
   copies d'une même règle, déjà divergentes une fois).

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
Dérive par rapport à QUOI — le signal thermique du 29/08 était ENTRE les
sessions, pas dedans (`ROADMAP.md`, sessions 57→63).

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton
`b64:`), plafond **600 s** : un banc long est REPRENABLE (cache écrit à
chaque passe) et se lance avec `--budget-s 450`.

**Ne JAMAIS lancer `unittest discover` depuis la VM** : plusieurs tests
importent `server.py`, qui ouvre `photos.db` — la VM ne sait même pas
l'ouvrir en LECTURE par-dessus le montage (`disk I/O error` immédiat,
observé le 03/09, rien écrit). Un test qui a besoin du code de `server.py`
le lit par `ast` (voir `test_ui_global.py`, `test_upload_precontrole.py`),
il ne l'importe pas.

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
> résiduel indélébile) — même un `rev-parse` en lecture seule est à éviter,
> la règle est catégorique, pas seulement pour les écritures ; un lock qui
> traîne se renomme (`mv`), ne s'efface pas.
>
> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).
