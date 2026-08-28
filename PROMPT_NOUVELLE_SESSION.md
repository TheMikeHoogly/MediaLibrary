# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (29/08/2026, session 64, en cours)

Git propre, tout fusionné (`36b706d` puis cette session). Trois fenêtres du
bat 0 vivantes, serveur redémarré 00:24:58, zéro fil mort.

### Google — vérifié, le feu vert est le geste de Mike

`verifier_photos_google` a tourné (165 s) : **ABSENT 0**, CERTAIN 4 280,
PROBABLE 9 625, **199 « NAS plus petit » — tous sous `_A TRIER\Google porte
mieux`, nos propres copies**. Mesuré fichier par fichier
(`diagnostic_trailer_google.py`, banc) :

- **14 Motion Photos Samsung de 2024, −1 à −3,3 Mo** : ExifTool refuse d'y
  écrire (« Error reading OtherImageStart »), `server.repair_file` fait
  `-all=` puis recopie — et **jette le trailer** : vidéo embarquée + profil
  ICC (88 tags). Le `nom.jpg_original` est à côté, 14/14 à la taille de
  Google. Rien de perdu ; le défaut, lui, est réel et ancien (les originaux
  de `Photos Mike\2024` font 2,3 Mo, Google 5,5).
- **185 à −2…−57 Ko** : écriture XMP normale, trailer conservé, zéro tag
  présent seulement chez Google. Du padding.

Trois questions posées à Mike (`QUESTIONS_MIKE.md`) : effacer chez Google ;
rapatrier les 1 217 ; `_Uploads` → boîte de réception par propriétaire.

### DÉFAUT trouvé : le plan par année range à la RACINE

Les 17 dossiers `Photos\2005…2026` ne sont PAS vides : **1 217 photos,
3,7 Go** (`inventaire_racine_photos.py`, 8 s). `rangement_annee.cible()`
vise `Photos\<année>`, pas `Photos Mike\<année>`. Quatre journaux
`docs/undo_annee_2026082{7,8}_*.json` (20+539+20+638) couvrent tout.
**Ne pas écrire de `.bat` d'effacement avant** : corriger `cible()` →
`--undo` ×4 serveur arrêté → plan → bat 26 → `rd` non récursif.

## Prochain pas

1. **Selon la réponse de Mike** : `repair_file` qui préserve le trailer
   (banc AVANT sur une copie d'un Motion Photo de
   `C:\GOOGLE PHOTOS\extrait`, `SEFT` en fin de fichier + `ftyp` + ICC
   après) ; puis le rapatriement des 1 217 dans l'ordre ci-dessus.
2. **Ranger les 297 « Google porte mieux »** — après la correction de
   `cible()`, sinon ils iront à la racine aussi. Le plan vient de l'index EN
   MÉMOIRE : attendre que `queues.tag` retombe, régénérer.
3. **Supprimer `_to_delete/`** (43 Mo). Geste de Mike.
4. **Le 9 septembre au matin** : Windows a-t-il DEMANDÉ ? `Get-WinEvent
   -FilterHashtable @{LogName='System'; Id=1074}`.
5. **Chantier 18 (confidentialité)** : le jeu étiqueté et son banc d'abord.
6. **Le panneau `?` des raccourcis** — brique : un JS commun injecté partout.
7. **Chantier 17** : PROPRIÉTAIRE (avec `_Uploads` redéfini), puis attribution
   rétroactive des 3 767 décisions.
8. **UNIFIER le re-clé** (trois primitives divergentes) — le rapatriement des
   1 217 en est le premier client.
9. **Reste d'audit** : O8–O9, O11, O13–O15 ; I1 ; `animal:luna` (3) vs
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

> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).
>
> **Le dossier monté a un cache** : le `mtime` dit la vérité, `tail` peut
> mentir. Mais un gel SIMULTANÉ de plusieurs fichiers au même instant est
> aussi ce que produit une vraie fermeture — demander à Mike plutôt que de
> conclure.
