# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` (photothèque) et
`docs/DECISIONS_OUTILLAGE.md` (canaux, pilotage, livraison) ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

> **`N:\\Photos` se connecte à chaque session** — règle dans `CLAUDE.md`
> (« Tester en réel »), depuis le 29/08.

## Priorité (26/08/2026, refixée session 53)

Le garde-fou du filtre est posé (jeton insatisfaisable → RIEN, dit, banc
`verifier_filtre_negatif.py`) ; l'ordre reprend à ce qui reste.

**1. Les boutons de `gallery` — FAIT (session 59), œil bureau et 390 px
passés ; reste la décision `.fchip`.**

**1 bis. Les cinq familles maison au `.btn` canonique — DÉJÀ FAIT, VÉRIFIÉ
(05/09). Cette ligne était périmée.** `.tb`, `.geobtn`, `.fchip`,
`.georow button`, `#ss-stop` ne peignent plus que leur ÉTAT dans
`ui/pages/gallery.html` ; taille, forme, police et survol viennent de
`components.css` (le coût de +19 px de hauteur de barres est écrit dans le CSS,
donc accepté et mesuré à l'époque). **Preuve refaite dans l'ordre habituel** :
`verifier_css_cascade --commun`, `verifier_cibles` (0 manquement prouvé),
`verifier_contraste` (24 couples AA), `verifier_controles` (0 grief de niveau A
sur 165 gestionnaires) — et le **regard en réel** sur serveur vivant, page par
page depuis un navigateur connecté : les **7 pages adoptantes** (`/files`,
`/people`, `/pets`, `/sujets`, `/tranche`, `/residu`, `/`) reçoivent bien
`components.css` AVANT leur propre `<style>` (elles gardent le dernier mot) et
aucune ne traîne le marqueur ; les 3 non converties (`/map` = témoin,
`/browse`, `/reglages`) ne le reçoivent pas et gardent `tokens.css`. **Reste
ouvert, et c'est un AUTRE chantier** : l'adoption de `components.css` par
`browse`, `faces` et `reglages` — `/map` est le témoin, on n'y touche pas.
Seule divergence encore signalée par la cascade, et elle est VOULUE :
`.tb.active { border-color }` vaut `--fixateur` sur la galerie et `transparent`
sur la carte (rendu identique, la carte n'ayant pas adopté la feuille commune).

**1 ter. La résilience des fils de travail : FAIT (session 61)** — superviseur,
relance à attente doublante, cinq morts consécutives alertent (`/sante` + journal).

**1 quinquies. Google — CLOS pour l'essentiel (29/08).** Mike efface chez
Google ; les 297 « Google porte mieux » sont rapatriés, ABSENT 0, les 199
« NAS plus petit » sont nos propres copies, zéro tag perdu. **Reste un
correctif tranché par banc** (`verifier_reparation_exif.py`) : quand
l'écriture EXIF échoue (« Error reading OtherImageStart »), `write_metadata`
doit retomber sur XMP+IPTC seulement au lieu d'appeler `repair_file` (qui
détruit le trailer ou l'ICC) ; un banc l'exige sur un Motion Photo. Ne PAS
toucher au Takeout de `C:\GOOGLE PHOTOS\extrait` avant la copie hors site.

**1 sexies. Le rangement par année — CLOS (29-31/08).** Deux garde-fous
testés contre le rebond du 29/08 : `plan_vise_la_racine` refuse un
plan-racine, `plan_perime` refuse un plan plus vieux que la dernière
bannière `DEMARRAGE` — et le plan est recalculé à chaque démarrage. Bat 26 a
rangé 29 sur 38 ; les 9 restants (ré-encodages Google homonymes) sont en
quarantaine par bat 37. Bat 34 fait par Mike le 31/08.

**1 quater. Le 9 septembre au matin : VÉRIFIER que Windows a demandé.**
Patch Tuesday tombe le 8 ; le redémarrage arrivait toujours vers 01:30 la nuit
suivante. Trois réglages posés le 28/08 (notification activée, préversions
coupées, `NoAutoRebootWithLoggedOnUsers=1`) et **aucun n'est prouvé**. Lire
`Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074}` et la bannière du
journal ; sinon regarder « Stratégies de mise à jour configurées ». Attention
au bruit : depuis le 28/08 la machine a aussi coupé BRUTALEMENT (Id 41) pour
cause thermique — voir `diagnostic_thermique.py`, ne pas confondre les deux.

**1 septies. RÈGLE Motion Photo — le STRIP est FAIT (bat 42, 03/09 23:30) ;
reste la purge des originaux (bat 43).** **Constaté le 05/09 dans le manifeste,
pas supposé** : `docs/strip_motionphoto_manifeste.json` daté du 03/09 à
23:30:17 porte **2 409 photos strippées et 32 ratées** (« pas de `_original` :
exiftool n'a rien changé »), soit exactement les 2 441 comptées — **9,27 Go de
vidéo retirés des JPEG**. Le plantage du PC est arrivé APRÈS, pas pendant : les
quatre dossiers d'années concernés (`Photos Mike` 2021, 2024, 2025, 2026) ne
portent **aucun `_exiftool_tmp`**, le symptôme qui aurait signé une
interruption brutale. **Ce qui reste, c'est bat 43** : les 2 409
`*.jpg_original` — les versions COMPLÈTES, avec la vidéo — sont toujours sur le
NAS (6 tirés au hasard, 6 présents) ; ce sont eux les 9,27 Go encore occupés.
Bat 43 les met en quarantaine (rien n'est supprimé), bat 24 purge ensuite.
Relancer bat 42 serait inutile : ces photos n'ont plus de vidéo.

Le compte et l'outillage, pour mémoire — COMPTÉ (01/09), OUTILLÉ :
Compte (`mesure_motion_photos.py`, reprenable, 40 271/40 291 JPEG) : **2 441
Motion Photos, toutes chez Mike** (2021 : 461 · 2024 : 1 241 · 2025 : 504 ·
2026 : 188 · 47 sans année), **8,64 Go de vidéo** sur 16,83 Go touchés ;
16 519 trailers SEF SANS vidéo (Flo 2017-2019, rien à y gagner), 31 sans
taille, 2 en erreur. Rapport `docs/motion_photos.json` (hors git). Outillage
POSÉ : **bat 42** (strip, aperçu → essai 20 → tout, serveur ARRÊTÉ exigé,
undo = `*.jpg_original`) puis **bat 43** (originaux en quarantaine
`.corbeille-rangement` ; option `_A TRIER` = les 125 du 29/08). 11 tests ;
pièges du banc et spec : amorce + git.

**1 octies. Les VIDÉOS — phases 0 et 1 CLOSES (30/08).**
- **Phase 0, rangement par année** : `inventaire_videos.py` date par le NOM
  (`AAAAMMJJ_HHMMSS`, `VID-…-WA`), sinon ExifTool `-fast`, sinon le dossier
  année du Takeout — jamais le mtime ; `appliquer_plan_annee.py --plan …`
  range (mêmes gardes, même undo), **bat 39**. Mesuré : 3 073 vidéos, 73,7 Go,
  0 sans date, 0 conflit.
- **Phase 1, les vidéos dans la GALERIE : CLOSE** — livrée le 30/08 matin,
  la LECTURE observée par Mike le soir (« la vidéo fonctionne »). Scan :
  **4 086 vidéos** indexées (index 43 703 → 47 789), image-clé ffmpeg par
  `/api/thumb`, badge « ▶ durée », `<video controls>` sur l'original en flux.
- **Phase 2 — TAGGING et RECHERCHE des vidéos : demandée par Mike (31/08),
  à MESURER avant d'écrire.** La voie sobre, et la seule qui tienne dans
  4 Go de VRAM : **pas de modèle vidéo**, on traite des IMAGES-CLÉS. Le
  serveur en extrait déjà une par vidéo (ffmpeg, `/api/thumb`) ; il en
  faudra plusieurs pour qu'un plan de fin ne soit pas invisible.
  - (a) **Tagger** : N images-clés → le tagueur de prod (`qwen3-vl:2b`,
    prompt v2ctx inchangé) → mots-clés FUSIONNÉS sur l'entrée vidéo, une
    description par vidéo. Aucun cinquième pipeline (invariant n° 4).
  - (b) **Chercher** : les mêmes images-clés encodées par SigLIP →
    `vectors` → les vidéos entrent dans la recherche IA existante, avec le
    MAX des similarités de leurs images (une vidéo est pertinente si UN de
    ses plans l'est).
  - (c) **La question qui décide du coût** : combien d'images par vidéo ?
    1 (≈ 4 086 taggings, ~5 h) ; 3 aux quarts (≈ 12 000, ~15 h) ; une toutes
    les 10 s (des dizaines de milliers, hors de portée). **À trancher par un
    banc**, pas par une intuition : prendre 30 vidéos, tagger 1 image puis
    3, et mesurer ce que la 2ᵉ et la 3ᵉ AJOUTENT vraiment.
  - (d) **Le SON est écarté pour l'instant** : une transcription (Whisper)
    serait un cinquième pipeline et un second modèle en VRAM. À parquer,
    pas à improviser.
  - **Contrainte de calendrier** : rien de tout ça ne se lance avant que le
    refroidissement soit réparé (voir la surchauffe du 30-31/08).

**1 nonies. L'INTELLIGENCE de la recherche IA (Mike, 29/08).** **MESURÉ
(nuit du 30/08, `mesure_requete_fr_en.py`, 40 paires)** : rappel@200 FR 0,583
· EN 0,683 · FR+EN 0,663, gabarit 0,551 ; l'anglais bat le français 33/40.
**Tranché par Mike, CÂBLÉ et OBSERVÉ le 30/08** : `elargissement_fr_en.py`
(dictionnaire FR→EN par co-occurrence, Dice, couverture ≥ 50 % ; règle dans
`eval/DECISIONS.md`), `mesure_elargissement.py` sur la copie : fr 0,583 →
**fr+dico 0,658** (idéal 0,663) ; serveur `encoder_requete` (moyenne des
vecteurs FR et EN), `/api/search` rend `elargi`, la galerie l'affiche.
Observé 13:46 : « 📖 2 276 paires sur 19 413 photos », « 1 500 photo(s) —
ours en peluche (+ teddy bear) ». Au premier démarrage le dictionnaire était
VIDE sans erreur (itération de `STORE.data` pendant le scan, probable) :
instantané sous `STORE.lock`, ligne 📖, `dico_fr_en` dans
`/api/search/status`. **Corrigé le même jour** : sur `/files` (grille
`_Uploads`, 20 photos) la recherche IA rendait 0 — elle relance TOUJOURS
côté serveur (« ↵ Entrée pour relancer »), observé 1 500. Défauts du 29/08
(grille-résultat, puces `_Uploads`) : corrigés, récit dans git. **Ce qui
reste, à mesurer avant de coder** : le NOM DE DOSSIER comme indice (`06 EVG
Nounours` sur « nounours ») ; les synonymes des tags ; un mode « filtrer dans
cette grille » HONNÊTE (classer la grille entière, pas le top-200 du fonds).

**1 decies. Les DOUBLONS par l'image — APPLIQUÉ PAR MIKE le 30/08, un
caillou reste.** Mesure (8 passes, ExifTool `ImageDataHash`) : 2 990 groupes,
2 757 identiques, 233 différentes (chez Mike seul, laissées) ; règle de la
canonique et du texte IA dans `eval/DECISIONS.md`. Outils :
`verifier_doublons_image.py` (aperçu), `appliquer_doublons_image.py`
(quarantaine réversible + manifeste, `--undo`, noms recopiés d'abord), bat 40.
**Appliqué** : lot 1 à 10:28 (894), le reste à 14:04 (2 035) — **2 929
fichiers en `.corbeille-rangement\dedup_image_*`**, index 47 789 → 44 860,
218 décisions fusionnées, 0 texte hérité, 19 noms recopiés. **Caillou** : 10 de
ces 19 noms ne s'affichent pas sur la canonique — re-retirés au démarrage
(« faux positifs : exclusion humaine ré-appliquée », 3 à 12:32 = les 3 du
lot 1, 25 à 16:13) : la canonique EXCLUAIT la personne que la copie nommait ;
le propriétaire l'emporte (29/08), rien n'est perdu (XMP de la copie en
corbeille + manifeste), mais la fiche ne DIT pas le désaccord. Les 10 sont
listés dans `QUESTIONS_MIKE.md`. **Le caillou est CLOS (30/08 soir)** : Mike a tranché les 10
photo par photo, verdicts appliqués par l'API et observés après redémarrage ;
`confirm` grave `confirmed` et l'exclusion confirmée perd son autorité sans
s'effacer (`eval/DECISIONS.md`). Le dédoublonnage au sha256 (23/08) était vrai
et aveugle — chiffres dans `eval/DECISIONS.md` (29/08).

**1 undecies. Les mots-clés ANGLAIS dans `kw_fr` — APPLIQUÉ (30/08).**
Cause mesurée : 22 196 entrées au `kw_en` vide (XMP relu entier dans `kw_fr`,
pas le tagueur ; le tagueur v2ctx ne fuit que 11/4 804). Règle
`scission_fr_en.py` (vocabulaires appris, vote par tag), applicateur + bat 41 :
**22 176 scindées par Mike à 15:08** (`undo_scission_*.json`), observé
(« chaise » → puces FR, élargi « chair »). Le serveur scinde lui-même à la
relecture d'un XMP (`read_meta_and_gps` → `scinder_entree`, livré `a78faa4`,
pas encore exercé). Imparfait et dit : ~5 600 tags neutres des deux langues
restent côté FR ; « calico » (82) est une fuite du vieux tagueur, à re-tagger.

**1 duodecies. La recherche IA VISIBLE PARTOUT (Mike, 30/08 12:55).** Le champ
de recherche ne vivait que dans la galerie ; Mike le veut sur chaque onglet.
**FAIT, OBSERVÉ (session 68, 30/08 16:55)** : un vrai `<form action="/files">`
`name=q` dans la barre commune (`APP_NAV_HTML`) — Entrée suffit, rien ne dépend
du JS — masqué sur `/files` où la galerie a la sienne ; raccourci **`/`** ;
44 px de cible ; à 390 px la barre fait deux lignes (94 px), pas trois. Et **la
brique JS commune existe** : `ui/global.js`, injectée par `_send_html` juste
après la barre (`injecter_js_commun`, règle pure), relue à chaud, cuite par
`bundle.py`, chaîne vide sans `ui/` ; les deux scripts inline de la barre
(onglet actif, sablier) y ont déménagé. `test_ui_global.py` (17, rougissent).
Observé : « chaise » depuis Dossiers → 1 500 photos, IA, « chaise (+ chair) ».
Reste : la Carte garde son propre champ « Rechercher (noms, lieux, sens) » —
deux champs sur cette page, à trancher un jour (celui de la barre cherche le
fonds entier, celui de la carte filtre la carte).

**1 terdecies. La visionneuse : la description en clair, les mots-clés au
survol, le DOSSIER de la photo en lien (Mike, 30/08 19:50) — FAIT, OBSERVÉ
(session 68).** Sous la photo : faits, puis la description (texte, plus en
italique gris), puis une pastille `📁 Photos/Photos Flo/2022 Bolivia`.
**Corrigé après l'essai de Mike (21:05)** : la pastille ouvre la vue
DOSSIERS — `/browse/<i>/<rel>#voir=<nom>`, tuile surlignée, défilée en vue.
**Et la vue Dossiers est une PLANCHE (Mike, 21:20, session 68)** : les
fichiers images et vidéos y sont des tuiles avec vignette (`/api/thumb` 512,
badge ▶, nom + taille, case de sélection) — la gestion de fichiers (renommer,
couper, corbeille) lit les mêmes `.row`/`.sel`, rien n'a bougé ; les dossiers
restent une liste étroite au-dessus, les fichiers non visuels aussi. Et dans
l'ANNUAIRE Sujets, cliquer un sujet ouvre sa GALERIE (`/files?q=personne:Nom`
/ `animal:` / lieu en `q=`) ; la FICHE (corriger, renommer) reste sous les
onglets Personnes / Animaux de la sous-barre. Les mots-clés sont repliés : survol de la zone (souris)
OU bouton « Mots-clés » (`aria-expanded`, doigt et clavier — un contenu au
seul survol serait injoignable, WCAG 1.4.13) ; repliés à chaque photo.
Observé : masque → Floufline, Bolivia ; `verifier_controles` 25 natifs, 0 non
remonté.

**1 quaterdecies. Classification : la vignette ouvre la photo ENTIÈRE en
loupe (Mike, 30/08 20:10) — FAIT, OBSERVÉ (session 68).** La vignette de
chaque carte (personnes, animaux, faux positifs) est un `<button>` ; un clic
ouvre la photo complète en place (`.loupe`), rend la carte ACTIVE, Échap / clic
/ Fermer referment, et les touches de jugement (Espace, X, Z, lettre) passent
au travers en refermant. Focus rendu à la vignette, ou à celle de la carte
active si le sondage a repeint les cartes. `verifier_controles` : 20 natifs,
0 grief. **Et le visage visé est ENCADRÉ (même session, 20:45)** : les cartes
portent `box` (`_boite_visage` / `_boite_animal`, bbox de la détection en
pixels d'origine, None si l'index est périmé — 5 tests), la loupe pose un
liseré veilleuse recalé sur l'image affichée (`object-fit: contain`,
naturalWidth, recalcul au redimensionnement). Observé : le bon visage encadré
sur une photo à trois enfants.

**1 quindecies. UPLOAD : de fond, et reprenable — FAIT, OBSERVÉ (03/09).**
(a) plus de `setTimeout` dans la boucle d'envoi (02/09, `29047e7`).
(b) `/api/upload/check` : hash LOCAL (`crypto.subtle`) avant l'envoi,
SKIP sans transfert si déjà présent ; dégrade sans HTTPS. 10 tests
(`test_upload_precontrole.py`). Observé après redémarrage réel.

**2. Le pense-bête des raccourcis DANS l'interface — CLOS (31/08).**
Panneau `?` sur `ui/global.js` (bouton dans la barre, touche `?`, `Échap`
ferme, focus rendu ; contenu = `docs/RACCOURCIS.md` servi tel quel par
`GET /api/raccourcis`, section de la page courante en tête). **Et
l'instrument est posé** : `verifier_raccourcis.py` relève ce que les pages
écoutent (`=== `, `!== `, la plage `/^[a-zA-Z]$/`, une constante de lettres
indexée), compare au relevé et rend DEUX chiffres — écoutées non
documentées / promises plus écoutées. **Vert sur les 13 sources au premier
lancement, mais après avoir trouvé DEUX défauts dans l'instrument lui-même**
(`strip()` effaçait la touche `Espace` ; la plage `A`–`Z` développée
fabriquait seize faux griefs). 15 tests, rouges sur chaque mutation.
Portée dite : ni `keyCode`, ni écouteur assemblé à l'exécution, ni ce que
`server.py` injecte.

**2 bis. RE-TAGGER tout le fonds ? — QUESTION DE MIKE (31/08), à MESURER
avant de répondre.** Le fait qui la motive : **22 196 entrées (52 %) n'ont
jamais vu le tagueur actuel** — leurs mots-clés viennent d'un XMP relu
(index reconstruit depuis les fichiers, 11/07), pas de `v2ctx` adopté le
12/08. Le fonds est donc tagué par DEUX générations d'outil, et « calico »
(82 photos) est une trace du plus ancien. **Mais** : ~4,3 s par photo
mesuré, soit **~26 h de GPU** pour ces 22 196 — sur une machine qui a coupé
quatre fois en trois jours. **Ordre recommandé** : (1) un banc de
comparaison sur ~100 photos déjà taguées, moitié « XMP relu » moitié
`v2ctx`, qui CHIFFRE le gain avant de le payer ; (2) si le gain est net,
re-tagger d'abord le sous-ensemble « XMP relu », pas le fonds entier ;
(3) rien avant le dépoussiérage. Ne pas relancer un tagging global à
l'aveugle : 26 h de GPU pour un gain inconnu, c'est un pari, pas une mesure.

**Le banc de comparaison (1) — TERMINÉ (04/09 soir, complet: true, 100/100).** `mesure_retag_gain.py` (nouveau, chantier 2 bis) rejoue le tagueur de PROD sur 50 photos « v0 » (sans `pipe`, XMP relu) et 50 déjà `v2ctx`, et mesure la similarité de Jaccard entre l'ancien et le nouveau jeu de mots-clés — le groupe `v2ctx` sert de PLANCHER DE BRUIT (le modèle n'est pas déterministe, deux passes du même pipeline sur la même photo ne rendent pas exactement les mêmes mots). Résultat : jaccard moyen v0 = 0,589 (divergence ~41 %) contre v2ctx = 0,739 (divergence ~26 %, le bruit) — écart de **0,15** (15 points). Un signal RÉEL (v0 diverge nettement plus que le bruit du modèle) mais MODÉRÉ, pas spectaculaire. Le détail : v0 perd en moyenne 4,86 mots-clés et en gagne 3,4 par photo (le nouveau prompt est plus discipliné que l'ancien XMP relu), contre 2,76 perdus / 2,04 gagnés pour `v2ctx` (bruit pur). Rapport : `docs/retag_gain_echantillon.json` — **une liste à JUGER par Mike**, rien n'a bougé dans l'index ni dans un fichier. Reste sa décision : 0,15 de gain net justifie-t-il ~26 h de GPU sur une machine qui a déjà coupé quatre fois, même nettoyée et turbo off ? Piste (2) toujours valable si oui : re-tagger d'abord le seul sous-ensemble « XMP relu », pas le fonds entier.

**2 ter. Le menu de COMPTE — FAIT, OBSERVÉ (31/08).** Pastille avec
l'initiale + nom dans la barre (surface papier, comme l'onglet actif : aucun
accent inventé), menu déroulant bâti à l'OUVERTURE (`/api/moi` une fois par
page ; le bâtir au chargement ferait payer treize pages pour un geste rare).
Contenu : Mes photos (`?q=personne:Nom`), Mon dossier privé (**seulement
s'il existe** — `_prive_url`, mis en cache 60 s, sinon un `stat` SMB par
page), taille des vignettes (3 crans, `--vig` sur `:root` + localStorage,
les deux planches gardent leur `clamp` en repli), Raccourcis, puis Réglages
et Santé pour l'admin seul, et Se déconnecter. `⚙️ Réglages` a QUITTÉ la
barre : un lien admin-seulement n'a rien à faire dans la barre de tous.
Observé : densité 96 → 86 → 210 px sur la planche, Échap ferme, cible 44 px.
`--encre` a été retiré du « Se déconnecter » — mesuré à 3,50:1 sur
`--salle-2`, sous le plancher AA, et se déconnecter ne détruit rien.

**2 quater. RE-TAGGER en FR seul, modèle qwen3.5:4b, EN UNE SEULE PASSE
coordonnée par photo — DÉCIDÉ (05/09), révisé le même jour sur mesure
réelle. **GO de Mike pour l'implémentation, reçu le 05/09 au soir** : passage au code, dans l'ordre des 6 étapes ci-dessous.** Suite du 2 bis : Mike tranche deux choses le 05/09 — (i) plus de
bilingue FR/EN, FR seul pour l'avenir (le retag devient donc inévitable
pour TOUT le fonds, pas seulement les 22 196 « v0 » du 2 bis) ; (ii)
« meilleur, pas plus gros » — chercher un modèle qui batte `qwen3-vl:4b`
sans dépasser son gabarit, plutôt que d'accepter la lenteur mesurée le
04/09. **Et Mike précise, toujours le 05/09** : ce retag complet, unique,
compte comme la PREMIÈRE PASSE OFFICIELLE de MediaLibrary (tout le fonds a
été tagué jusqu'ici par un pipeline qu'on juge nous-mêmes médiocre) — ça
justifie d'y mettre le soin qu'une initialisation mérite, UNE fois, sans
toucher à la logique de l'agent de tagging standard (le flux rapide des
nouveaux uploads au jour le jour reste tel quel).

**Le modèle — qwen3.5:4b, sur 8 photos (mêmes que le 2 bis), sans dépasser
le budget VRAM.** `qwen3.5:2b`/`qwen3.5:4b` tirés (déjà en local pour zéro
coût, `diagnostic_tirer_modele.py`), comparés à `qwen3-vl:2b`/`qwen3-vl:4b`
par `mesure_modele_vision.py` (`--sortie` ajouté pour ne pas écraser une
comparaison précédente). Résultat : `qwen3.5:4b` (4,7B, Q4_K_M, 3,4 Go —
MÊME gabarit que `qwen3-vl:4b`) corrige le chat calico (« tricolore »/
« calico », plus « tigré ») et le lac confondu avec l'océan, ne répète
pas la fuite de noms Inti/Luna — et tourne à **11,3 s/photo en régime
établi contre 35,2 s pour `qwen3-vl:4b`, soit ~3× plus vite, pour une
vitesse quasi identique à `qwen3-vl:2b` actuellement en prod (11,2 s/photo)**.
Un défaut trouvé, à surveiller : une hallucination isolée (« lgbtq » sur
une photo de QR code, aucun rapport). `qwen3.5:2b` est écarté tel quel :
plus rapide encore (3,6 s/photo) mais casse le format demandé (parfois UNE
phrase entière au lieu de 6-10 mots-clés courts — romprait l'affichage des
puces).

**Le chiffre à corriger : le « 9+ jours » annoncé le 04/09 mélangeait
deux mesures.** Sur les mêmes 8 photos, dans les mêmes conditions :
`qwen3-vl:4b` ≈ 16 jours pour re-tagger les ~39 783 entrées déjà taguées
(FR seul rend tout le fonds candidat, pas les 22 196 « v0 » seules) ;
`qwen3.5:4b` ≈ **5 jours**, comparable au débit actuel de `qwen3-vl:2b`.
**Attention** : ces 8 photos sont les cas difficiles du 04/09, pas un
tirage aléatoire — le débit réel en production sera vraisemblablement
meilleur ; le chiffre solide est le ratio (~3×), pas le nombre de jours
absolu.

(a) **Aucun mécanisme de retag en masse n'existe — par construction, et
c'est voulu** (commentaire à la ligne de `TAGGING_PIPELINE_VERSION` :
« PAS de re-tagging automatique au bump ... c'est une décision explicite
(ROADMAP) »). `tagger_worker` saute toute clé où `STORE.has(name)` est
vrai, quel que soit son `pipe`. **Mais la mécanique existe déjà pour un cas
voisin** : le scan approfondi (`_sync_dir`, bloc « fichiers modifiés »)
retire déjà une entrée du `STORE` et la remet dans `TAG_QUEUE` quand le
fichier a changé — le même geste (`STORE.remove_many` + `enqueue`),
simplement déclenché par le `pipe` au lieu du `mtime`, donne un retag de
masse SANS nouvelle politique GPU (invariant `monolith-surgery` n° 4
respecté) ni nouvelle file. **Piste concrète, pas encore codée** : un fichier
bascule `retag_actif.txt` (même idée que `modele.txt`, lu par le scan, absent
= comportement actuel inchangé) portant la version cible ; tant qu'il est
présent, le scan approfondi enfile aussi les entrées dont le `pipe` ≠ cible.
**Ça répond DIRECTEMENT à la demande de Mike de continuer à faire évoluer le
projet pendant la campagne** : la progression vit dans `STORE` (durable, sur
disque), pas dans `TAG_QUEUE` (mémoire, perdue à un redémarrage) — un
redémarrage pour livrer un AUTRE changement (le geste `git_agent` l'exige
déjà pour tout `server.py` modifié) redécouvre tout seul, au prochain scan,
ce qui reste à re-tagger. Rien à écrire de spécial dans le protocole de
livraison : `STORE.set` n'écrit qu'APRÈS la réponse d'Ollama, donc une photo
interrompue en cours de génération repart proprement au tour suivant (aucune
écriture partielle, invariant n° 2).

(b) **RÉVISÉ (05/09, sur mesure réelle) — un seul passage, coordonné par
photo, bat la passe préalable en deux phases envisagée d'abord.** Première
idée (abandonnée) : geler la campagne, laisser `visages`/`animaux`/GPS
rattraper leur retard en une passe séparée, PUIS lancer le retag — parce
qu'Ollama garde une priorité GPU de fait (« hors bail », contrat historique,
non touché). Mike a demandé de ne pas s'y figer et de chercher mieux : la
mesure (`mesure_detection_cpu.py`, 8 photos, sur la machine réelle) montre
que la question ne se pose quasiment pas. **Les visages tournent déjà 100%
CPU** (`FACE_USE_GPU = False`, volontaire, VRAM prise par Ollama) : 0,34 s
en moyenne, pic à 1,4 s sur la photo la plus chargée (10 visages). **Les
animaux (YOLO) tournent CPU ou GPU selon la VRAM libre** : 0,17-0,34 s
typique, un pic isolé à 4,9 s CPU (1,8 s GPU) sur la même photo chargée.
**Le lieu (GPS → nom de lieu) n'est même pas une question de GPU** :
`gps_places.json` est produit HORS LIGNE par `enrichir_lieux.py`, la lecture
serveur ne fait qu'un accès cache mémoire, zéro coût, zéro réseau au moment
du tagage. Conclusion : détecter visages + animaux JUSTE AVANT d'appeler
Ollama, photo par photo, dans le pipeline de retag lui-même (pas dans une
phase séparée), coûte en moyenne ~1 s de plus par photo (pire cas ~6-7 s sur
une photo de groupe) contre les 11,3 s de l'appel au modèle — un surcoût de
l'ordre de 10 %, pour une couverture de contexte de 100 % au lieu de
« ce qu'une passe préalable a eu le temps de rattraper ». **C'est ce
schéma qui est retenu**, PAS un chantier séparé : le pipeline de retag
(distinct de `tagger_worker`, qui garde sa logique standard pour les
nouveaux uploads du quotidien) appelle `detect_faces()` et `detect_animals()`
pour la clé si l'entrée manque encore de l'un des deux AVANT de construire
les assertions et d'appeler `ollama_generate` — les deux fonctions existent
déjà, gèrent déjà seules le choix CPU/GPU, rien à réinventer côté
arbitrage.

(b bis) **Précision de Mike (05/09, complément) — l'identification humaine
ne se perd pas, elle se complète.** Le retag ne doit PAS effacer les
identifications déjà validées (`personne:Nom`/`animal:Nom`) ; il PEUT en
révéler ou en confirmer de nouvelles (nouveaux visages/animaux détectés,
meilleure reconnaissance). **Déjà garanti par l'architecture existante,
rien à coder en plus** — vérifié dans le code, pas supposé : les noms ne
vivent PAS dans les mots-clés produits par Ollama mais dans les fiches
durables `PEOPLE_STORE`/`PETS_STORE` (champs `faces`/`exclude`) ; à CHAQUE
écriture du worker de tagging (donc aussi pendant le retag complet, qui
réutilise cette même logique), `_noms_attendus()` recalcule les noms
attendus depuis ces fiches et les réinjecte dans `kw_fr` avant l'écriture —
commentaire du code, à la lettre : « PÉRENNITÉ : ne jamais perdre les tags
nommés (personne:/animal:) déjà écrits dans le fichier — un ré-tagging IA
les ré-intègre au lieu de les écraser ». Cette re-fusion couvre même la
course où Mike identifierait quelqu'un PENDANT un appel Ollama en cours
(jusqu'à 10 min) : un nom ajouté n'est pas écrasé par une fusion sur des
mots-clés déjà périmés, un nom retiré n'est pas ressuscité par erreur
(`exclude` fait autorité). Et la détection visages/animaux ajoutée par le
point (b) ne se déclenche QUE si la photo n'a pas encore d'entrée dans
`FACE_STORE`/`ANIMAL_STORE` (le scan existant saute les entrées déjà
présentes) — jamais de re-détection qui romprait un cluster déjà nommé.
Une photo déjà identifiée reste identifiée ; une photo pas encore vue peut
enfin l'être.

(c) **Un seul geste préalable reste utile, et il est hors GPU** : lancer
`enrichir_lieux.py` une fois avant la campagne pour rafraîchir
`gps_places.json` sur le plus de photos possible (script existant,
hors ligne, aucun rapport avec Ollama ni la VRAM).

(d) **Deux gardes-fous opérationnels, pas encore vérifiés :** l'endurance
thermique n'a été mesurée que par rafales de ~450 s (chantier
confidentialité, 04/09) — jamais sur plusieurs jours en continu ;
`mesure_thermique.py` (chantier clos, sessions 57-63) doit tourner et
alerter PENDANT toute la campagne, à confirmer actif avant de lancer. Et
pendant la campagne, ne PAS lancer de banc `mesure_`/`eval_` qui appelle
Ollama avec un AUTRE modèle en parallèle (un second modèle chargé ferait
swapper le premier sur une carte à 4 Go presque pleine, ralentissant les
deux). **Note à part, non bloquante** : le GPU d'InsightFace (CUDA) est
CASSÉ sur cette machine (`cublasLt64_13.dll` manquante) — sans effet sur la
décision ci-dessus (le CPU suffit largement), mais à réparer un jour pour
gagner encore un peu de marge.

**Ordre d'implémentation — étapes 1, 2 et 4 LIVRÉES (05/09, session 72) ;
3, 5 et 6 restent.** Deux écarts assumés par rapport au croquis ci-dessus, tous
deux dans le sens de la prudence, tous deux tenus par des tests :

- **L'index n'est PAS vidé à mesure.** Le croquis reprenait le geste du bloc
  « fichiers modifiés » (`STORE.remove_many` + `enqueue`) : sur ~40 000 photos
  et cinq jours, il ferait fondre la photothèque sous les yeux de Mike. Le
  retag n'enlève donc rien — la photo reste visible, nommée et cherchable
  jusqu'à la seconde où sa nouvelle entrée remplace l'ancienne. Bénéfice
  collatéral : la progression vit dans le `pipe` de l'entrée (durable, sur
  disque) au lieu d'une file mémoire, ce que le croquis voulait déjà.
- **Un retag raté ne coûte pas la photo.** `_marquer_echec` remplace l'entrée
  par `{failed: True}` : sur une photo DÉJÀ taguée — le cas de toute la
  campagne — un simple timeout d'Ollama lui aurait fait perdre ses mots-clés,
  sa description, sa date et son GPS. Les trois sorties d'échec du worker
  passent maintenant par `_echec_retag`, qui CONSERVE l'entrée et y pose une
  marque d'abandon (`retag_fail`), laquelle sert aussi de garde anti-boucle.
  Et un retag RÉUSSI complète l'entrée au lieu de la remplacer : ce que la
  passe n'a pas recalculé (date, GPS, import) survit à un hoquet d'ExifTool.

**Conséquence NON prévue, trouvée en écrivant le code, TRANCHÉE et CÂBLÉE
le même jour** : le dictionnaire FR→EN de la recherche (1 nonies, +0,075 de
rappel mesuré) était RÉAPPRIS toutes les 6 h sur les entrées BILINGUES de
l'index. Le FR seul les fait disparaître une à une — à la fin de la campagne le
dictionnaire aurait été vide et l'élargissement serait mort en silence,
ramenant le rappel de 0,658 à 0,583. **Mike a tranché : le GELER**
(`dico_fr_en.json`, écriture atomique, relu dès que l'index apprend moins de
paires que le fichier ; `source`/`appris`/`gele` rendus dans
`/api/search/status`). Une traduction ne se périme pas ; ce qui se périme,
c'est la matière qui l'a produite. Détail et alternatives rejetées :
`eval/DECISIONS.md`.

Ordre initial (rien n'était encore codé au moment de l'écrire) :
1. **FAIT.** `tagging_meta.py` : FR seul (`keywords_en` retiré du schéma), +
   exigence de vrai français et consigne anti-répétition (mots-clés distincts,
   description ≠ liste recopiée) — chacune sur un défaut OBSERVÉ dans
   `docs/comparaison_modeles_vision*.json`. 11 tests dans `test_tagging_meta.py`.
   **Le prompt a TOURNÉ en réel** avant d'être livré, deux fois, sur les 8
   mêmes photos et le même modèle (`docs/comparaison_v3fr.json` puis
   `docs/comparaison_v3fr2.json`, celui-ci = le prompt livré). Ce que ça a
   changé, et que seul le fait de tourner pouvait dire : la 1ʳᵉ formulation de
   l'anti-répétition (« ne réutilise pas un mot déjà présent dans un autre
   mot-clé ») était TROP stricte — le modèle contournait le mot juste plutôt
   que de le répéter (« code qr » devenu « code-barres ») et collait ses
   mots-clés par des traits d'union (« carte-visite », « image-floue »).
   Formulation corrigée (deux formulations d'une même chose interdites, traits
   d'union et soulignés interdits) : « code qr » et « carte de visite »
   reviennent, plus aucun trait d'union, `kw_en` vide partout, plus un seul
   anglicisme, et les descriptions disent la scène au lieu de recopier la
   liste. **Deux défauts SURVIVENT, du modèle et non du prompt, à surveiller
   aux spot-checks de l'étape 6** : l'étiquette de la bouteille de vin est
   encore transcrite (« château du grand », « année 1986 ») malgré la règle
   explicite — qwen3-vl et v2ctx le faisaient déjà ; et le lac de
   `20220918_103631.jpg` est appelé « mer » aux DEUX tirages FR seul, alors que
   le tirage bilingue disait « eau lac » — or corriger lac/océan était l'un des
   deux arguments qui ont fait choisir ce modèle. Huit photos difficiles et
   deux tirages ne tranchent rien : c'est un point à REGARDER pendant la
   campagne, pas une conclusion.
2. **FAIT.** `modele.txt` → `qwen3.5:4b` (pas une ligne de code) et
   `TAGGING_PIPELINE_VERSION` = `"qwen3.5:4b|v3fr|kb1"`, bumpée en même temps
   que le prompt. Bumper seul ne déclenche rien (voir (a)) tant que le levier
   de l'étape 4 n'est pas posé.
3. **OUTILLÉ, le geste reste à Mike.** `enrichir_lieux.py` tourne une fois
   (geste (c)) — **bat 44** (« Enrichir les lieux (geocodage hors ligne) ») :
   aperçu à blanc, puis `--ecrire` sur confirmation, `.bak` sur `lieux.txt`,
   refus explicite si le gazetteer manque (bat 18). **Le serveur peut rester
   allumé** (base lue en `mode=ro`) et il reprend `gps_places.json` tout seul
   au changement de `mtime` — aucun redémarrage. Ni la VM ni l'agent banc ne
   peuvent le lancer : il ouvre `photos.db` et il ÉCRIT.
4. **FAIT, PAS ACTIVÉ.** `retag_actif.txt` (levier externe, relu à chaque
   scan — le poser démarre, le retirer arrête au lot suivant), sélection pure
   `tagging_meta.cles_a_retaguer` (saute `failed`, vidéos, déjà à la version,
   déjà en file, déjà abandonnées), enfilement par lots de `RETAG_LOT` = 500
   dans le scan approfondi, et `_detecter_avant_retag` qui complète les
   détections MANQUANTES sous l'ordonnanceur existant (`creneau`, jamais une
   5ᵉ politique GPU). Tests : `test_retag_campagne.py` (16, sur le code de
   prod, sans importer `server.py`) + `test_tagging_meta.py`.
   **Portée honnête de la détection** : côté ANIMAUX le gain est immédiat
   (l'espèce entre dans les assertions par `ANIMAL_STORE`) ; côté VISAGES il
   est DIFFÉRÉ — `_assertions_pour` lit les noms du XMP, pas de `FACE_STORE` :
   détecter met la photo en état d'être nommée, ce qui profitera au passage
   SUIVANT, pas à celui-ci.
5. **FAIT (05/09), et le verdict est OUI.** `mesure_endurance_thermique.py`
   (banc neuf) rejoue le tagage de PRODUCTION et jette la réponse : il ne
   produit que de la chaleur. **8 tranches, 371 photos, 3 415 s (0,95 h) de
   charge : max 75 °C, médiane 67 °C, `clocks_throttle_reasons` JAMAIS actif
   sur 237 relevés, débit plat (×1,02 du premier au dernier quart).** Rapport
   cumulé : `docs/endurance_thermique.json`. **Le chiffre qui change le plan :
   8,9 s/photo en médiane sur 371 photos tirées au hasard**, contre les 11,3 s
   des 8 photos difficiles — le fonds (44 135 entrées) se re-tague en **~4,5
   jours**. Deux limites dites : ~85 % de service (tranches de 450 s séparées
   d'une pause, plafond du canal) alors que la campagne tournera à 100 %, et
   une heure n'est pas cinq jours. Le garde des cinq jours reste
   `thermique_loop`, qui écrit au journal dès 85 °C ou au premier aveu.
6. **Le seul pas qui reste, et il est à Mike** : créer
   `C:\Prog\Claude\MediaLibrary\retag_actif.txt`, **VIDE** → la campagne
   démarre, observée
   (`/api/maint/status` → `config.retag`, boucle thermique au journal,
   spot-checks < 10 photos de temps en temps sur le FORMAT et sur les
   hallucinations type « lgbtq »). **Ce qui est irréversible et doit être dit
   avant la première photo** : le retag RÉÉCRIT le XMP en français seul — les
   mots-clés anglais des fichiers sont perdus, il n'y a pas d'annulation. C'est
   la décision « FR seul » assumée, et le dictionnaire gelé garde la traduction
   ; mais ça se dit avant, pas après. Retirer le fichier arrête la campagne au
   lot suivant, et rien n'est perdu : la progression vit dans le `pipe`.
   **Garde-fou posé le 05/09 (question de Mike : « que dois-je faire avec ? »)**
   : le fichier peut porter une version cible, et une version qui n'est PAS
   celle du code ferait re-taguer le fonds ENTIER à chaque scan, sans fin — le
   worker estampille `TAGGING_PIPELINE_VERSION`, jamais ce qui est écrit là.
   `retag_cible()` refuse désormais toute cible étrangère, le dit une fois au
   journal, et le refus est LISIBLE dans `/api/maint/status`
   (`config.retag.refus` / `attendu`). **Observé en réel** : fichier posé avec
   `qwen3-vl:2b|v2ctx|kb1`, l'API a rendu
   `{actif: false, refus: …, attendu: qwen3.5:4b|v3fr|kb1}` et le journal la
   ligne de refus ; fichier retiré, retour à `{actif: false}`. Un fichier vide
   reste la forme recommandée — mais la sûreté ne dépend plus de ce que la main
   a tapé.

**Pendant la campagne, ce qui reste sûr à faire avancer** (aucune contention
GPU) : 1 bis (`.btn` canonique), l'étape 7 du chantier 17 (onboarding), le
reste de l'audit (point 5), toute doc/UI/CSS. **À éviter ou reporter** : la
phase 2 vidéo (1 octies, tagging d'images-clés — même GPU, même file), tout
nouveau banc `mesure_`/`eval_` GPU, tout chantier qui bumperait une AUTRE
version de pipeline pendant que celui-ci tourne (confusion de diagnostic si
les deux migrent en même temps).

**3. La suite du chantier 17 (multi-utilisateurs) — PRESQUE FINI.** Étapes 1
à 6 sur 7 POSÉES ET OBSERVÉES (sessions 65-66) : propriétaire + attribution
rétroactive, vue filtrée par utilisateur, comptes, écriture restreinte,
corbeille à 6 mois. Les six décisions de Mike sont EXÉCUTÉES, pas
seulement spécifiées ; `QUESTIONS_MIKE.md` est vide, plus rien ne bloque.
**Reste la seule étape 7 : l'onboarding rédigé** — le chantier se termine,
il ne se relance pas.

**3 bis. Le garde-fou de la confidentialité (chantier 18) — EN COURS
(session 68, 30/08 soir).** Catégories TRANCHÉES : **sept** — les six de la spec
plus `administratif` (Mike, 31/08, après la lettre de Lausanne que le banc
laissait passer ; `eval/DECISIONS.md`). Le cache du banc porte l'empreinte du
prompt : changer la question écarte les verdicts de l'ancienne.
**Le geste « rendre privée » est POSÉ et OBSERVÉ** (bouton 🔒 de la
visionneuse → `POST /api/files/prive`, règle pure `visibilite.cible_prive`,
annulable ; aller-retour prouvé en réel). **La mesure d'abord (18e) — TERMINÉE (04/09, complet: true, 90/90).**
`mesure_sensibles.py` a interrogé le modèle de prod sur l'échantillon
(60 candidats « document / reçu / capture… » + 30 témoins aléatoires, tirage
séedé) → `docs/sensibles_echantillon.json` : 66 « non », 19 illisibles,
1 facture, 1 banque, 3 administratif — **une liste à JUGER par Mike, rien
n'a bougé**. Chronologie du banc, utile pour la suite GPU du projet : lancé
le 30/08 soir (~16 s/photo) ; repris le 04/09 matin après le dégagement
PARTIEL des prises d'air seul — deux créneaux de ~450 s ont tenu (69 puis
73°C) mais la MACHINE ENTIÈRE a coupé par surchauffe au troisième ; **repris
et terminé le 04/09 soir** après nettoyage en profondeur + turbo boost
désactivé — cinq créneaux enchaînés sans incident, pic observé **66°C à
100 %** contre 69-73°C avant nettoyage pour la même charge. Le nettoyage
+ turbo off est la condition qui manquait, confirmée par la mesure, pas
seulement par l'intuition. Ensuite : la question dans la MÊME invocation
du tagueur
(pas de cinquième pipeline), l'axe `sensible:` en base seulement (jamais le
XMP — 18c), l'écran d'envoi aux trois gestes (PRIVE / corbeille / « non »,
mémorisé), la passe rétroactive. Et la **purge automatique de la corbeille
(180 j) est POSÉE** (maintenance, 1×/jour — `test_fichiers.py`).

**4. UNIFIER le re-clé** — la réparation est faite (27/08, voir l'état de
session 57), mais la primitive complète existe désormais **TROIS fois** :
`server.rekey_everywhere`, `deplacer_dossiers.recle_une_cle` et
`appliquer_plan.rekey_stores`. Trois endroits où la même règle peut diverger,
et elle a déjà divergé une fois pendant cinq jours. **Nuance (04/09, après
lecture des trois)** : la partie la plus risquée — les décisions humaines
dans les fiches PEOPLE/PETS — est DÉJÀ unifiée, les trois passent par
`recle_decisions.recler_fiche`. Ce qui reste TROIS copies, c'est
l'orchestration (quels magasins, dans quel ordre) — et ça peut diverger en
silence : trouvé et corrigé aujourd'hui un vrai cas, `maintenance.py`
(bat 25, StandaloneSv) appelait `rekey_stores` sans jamais transporter le
7ᵉ magasin (`gps_places.json`) — `deplacer_dossiers.py` le disait de
lui-même en commentaire depuis un moment (« il ignore aussi
gps_places.json ») sans que personne ne corrige l'appelant manquant.
Fusionner `server.rekey_everywhere` avec les deux autres n'est PAS une
suppression de code mort : il tourne sur des globals EN PROCESSUS
(`STORE`, `FACE_STORE`…) que les scripts autonomes n'ont pas — de vrais
contextes différents. Une vraie fusion demanderait de faire passer
`server.py` par des stores injectés plutôt que des globals, un chantier à
part, pas une correction solo. Vérifié (grep de tous les appelants) : les deux autres,
`appliquer_doublons_image.py` et `appliquer_plan_annee.py`, transportent
déjà `gps_places.json` eux-mêmes autour de `rekey_stores` — le trou était
propre à `StandaloneSv`.

**5. Le reste d'audit** : O8–O9, O11, O13–O15 ; **I1** visible dans
`/reglages` ; `animal:luna` en minuscule sur 3 photos à côté de `animal:Luna`
sur 355. Puis les quatre pages sans `components.css` (`browse`, `faces`,
`map`, `reglages`). O15 balaie au passage les 3 047 vignettes orphelines du
déplacement — effet de bord attendu, pas une panne.

**Ce qui a changé de nature (26/08)** : les animaux non nommés ne sont plus un
chantier. Deux noms posés par Mike ont fait tomber les groupes de **189 à 99**
et les apparitions non nommées à **442**, plus gros groupe à 31. C'est une
finition, à faire au fil de l'eau.

**En fin de projet, dans cet ordre** : le chantier 17, PUIS la copie hors site
— choix de Mike du 26/08.

**Le Takeout Google : CLOS** (27→29/08) — les 3 776 absentes sont rapatriées,
ABSENT = 0, les paires indéterminées tranchées (`eval/DECISIONS.md`).

## Historique détaillé (sessions ≤ 63, pré-05/09) — archivé dans git

Les comptes-rendus session par session (57→63, 54→56, 50→53, 47→49, 46,
45 bis/ter/quater, 44, 36→43, 28→35) sont retirés d'ici : ce fichier
grossissait vers le seuil de 100 000 octets (`nettoyer_session.py
--lint-only`), et leur contenu — chiffres, dates, décisions — est déjà dans
l'historique git de CE fichier (`git log -- ROADMAP.md`) ainsi que dans les
commits des chantiers eux-mêmes. Rien n'y était encore ouvert : tout ce qui
restait actionnable en a été extrait vers « Priorité » (ci-dessus) avant ce
nettoyage (05/09). Ne pas reproposer une mesure déjà faite sans motif neuf
— voir « Acquis » plus bas.

## Détail historique des chantiers 0–18 (pré-26/08) — archivé dans git

Le détail complet (specs, mesures, sous-étapes) des chantiers listés ici
entre le 12/08 et le 26/08 — rattachements, résidu ambigu, vérité terrain,
extraction `ui/`, cross-pipeline Mutz/Caline, reconnaissance (parquée), UI
onze pages, assurance-vie, MCP lecture seule, recherche IA contextuelle,
chantier 17 (multi-utilisateurs) et 18 (confidentialité) — vit dans
l'historique git de ce fichier, pas ici. Leur état COURANT (ce qui reste
vraiment ouvert) est dans « Priorité » en tête de fichier : chantier 17 →
point 3, chantier 18 → point 3 bis, les autres sont CLOS ou PARQUÉS et
listés dans « Acquis » ci-dessous. Retiré le 05/09 pour la même raison de
taille que l'historique par session.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Le chip est FINI (26/08)** : `.chip` vit dans `components.css` seul,
  `font:` compris, et **7 pages sur 11** reçoivent la feuille commune.
  `.pchip` n'existe plus. Ne pas re-proposer de re-déclarer un chip dans une
  page : ce qui reste local doit DIFFÉRER et se dire (`subjects` :
  `padding: 0 var(--e-4)` ; `gallery` : `user-select` et l'état `.on`).

- **Cibles tactiles (26/08)** : les **221** cibles des onze pages sont
  comptées — **0 manquement prouvé** (0 sous le plancher, 0 inerte), 112
  planchers déclarés et honorés, 10 non décidables, 66 dont la hauteur n'est
  pas déclarée (le contenu décide) et 33 exemptées. Mesuré par
  `verifier_cibles.py`, qui lit l'imbrication du HTML, ce que
  `document.createElement` bâtit, et la cascade à quatre étages. **Ne pas
  re-parcourir les pages à l'œil pour ça, et ne pas re-proposer de lire la
  LARGEUR** : angle mort assumé, dit dans le rapport.

- **Accessibilité des contrôles (26/08)** : les **154** gestionnaires de clic
  des onze pages sont posés sur des contrôles — 138 natifs, 3 opérables à la
  main, 13 déclarés redondants, **0 grief de niveau A**. Mesuré par
  `verifier_controles.py`, pas supposé. Ne pas reprendre à l'œil.

- **Stockage** : SQLite local WAL (**43 064 entrées**), embeddings BLOB, backup
  NAS snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers/Rangement** : `/browse` réversible, dédoublonnage (8,4 Go),
  rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles ; **7 058 renommages
  appliqués et observés** (0 sauté, noms humains intacts) ; `gps_place` actif
  dans les noms (1 175 en portent un) ; garde-fou date de SCAN
  (`date_de_scan_presumee`, asymétrique, toléré à un an).
- **UI** : design system « chambre noire » (tokens, plancher a11y), planche
  contact, `/reglages`, `/people`, `/sujets` guichet unique ; **faits
  `date · lieu · noms` sous chaque vignette et dans la visionneuse**, avec
  leur SOURCE (exif / nom du fichier / année du dossier — gps / chemin),
  produits par la VUE et par un seul rendu partagé.
- **Correction** : faux positifs « Corriger »/« Nettoyer », retrait SÛR
  (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
- **Perf** : scoring vectorisé (156 s → qq s) ; `/api/thumb` (−98 % octets NAS) ;
  `_send_file` Range/streaming ; workers sous ordonnanceur ; GpuArbiter 27/27.
- **Tagging** : `qwen3-vl:2b`, prompt v2ctx ; Knowledge Builder : faits
  noms/date/lieu structurés et sourcés (`faits`), noms JAMAIS via le prompt ;
  `TAGGING_PIPELINE_VERSION` estampillée (`pipe`) — **sur les 81 photos taguées
  DEPUIS**, pas sur le fonds ; 1 lecture exiftool/photo.
- **Index/vecteurs** : cascade `forget_everywhere` au scan — **pilotée par
  l'index, donc aveugle à une clé déjà oubliée (21/08)** ; **re-clé complet
  (22/08)** : `rekey_everywhere` transporte enfin les DÉCISIONS humaines des
  fiches `PEOPLE`/`PETS` (`recle_decisions.py`), et `journaux_deplacements.py`
  relit les journaux d'annulation comme carte des déplacements ; **2 374 vecteurs
  orphelins purgés et observés** (0 muet sur 1 600 résultats, contre 2,6 %),
  quarantaine réversible `_corbeille_vecteurs/`.
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, trois tâches de
  fond EXIF dans `/reglages` ; comptes de l'index au goulot (`comptes_index.py`).
- **Recherche** : quatre dimensions (noms · lieux · période · sens) ; **une
  seule règle de date** (filtre, tri, « même jour », `_best_time`, fait — la
  date de SCAN écartée à la lecture), **une seule règle de LIEU** (`faits_vue`,
  segments + mots collés découpés — jamais de sous-chaîne) et **une seule
  autorité des NOMS** (`_autorite_des_noms` : le filtre et l'affichage ne
  peuvent plus se contredire), partagées par le renommage, le KB, `/sujets` et
  la recherche.
- **Mesure** : `mesure_dates_scan.py` (`--lecture`), `mesure_tri_recherche.py`,
  `mesure_faits_backfill.py`, `mesure_faits_vue.py`, `mesure_lieu_visible.py` —
  `mesure_propagation_noms.py` (la règle d'AJOUT du curateur, garde-fou des
  clés fantômes compris), `mesure_visages_orphelins.py` (les décisions
  humaines posées sur des clés oubliées, et POURQUOI elles survivent) —
  lecture seule sur COPIE, jamais sur `photos.db` ; **`mesure_copie_base.py`
  fabrique cette copie** (API `backup`, source en `mode=ro`, copie DATÉE) — plus un
  geste de Mike, plus un aller-retour clavier avant de mesurer.
- **Pilotage** : trois canaux-fichiers, une seule façon de les lire
  (`canal.py`) — `_commande_serveur.txt` (redémarrer/arrêter, `pilotage.py`),
  `_commande_git.txt` (livrer, `git_agent.py`), `_commande_banc.txt` (mesurer,
  `banc_agent.py`). Les superviseurs se retirent quand la **génération**
  change. `GET /api/serveur` dit `demarre_a` et **`code_a_jour`**.
- **Hygiène et livraison** : nettoyage réversible (29) ; `27 - Git.bat` reste
  le guichet des gestes de Mike (état, commit guidé, fusion sans checkout,
  purge des branches, GitHub, rapport de l'agent au choix 8) ; **`git_agent.py`
  livre pour la sandbox** — `commit` ou `livrer` dans `_commande_git.txt`,
  **après contrôles** (serveur à jour, tests des modules touchés, `.bat` ASCII,
  lint). L'ordre s'inverse : **observer AVANT de commiter**.

## Pistes ouvertes par Mike (22/08) — à instruire, pas encore priorisées

- **Tirer plus d'intelligence du LLM local À MATÉRIEL CONSTANT.** Demande de
  Mike : évaluer ce que l'outillage actuel permet de gagner sans changer de
  modèle — le plafond de 4 Go de VRAM ne bouge pas, et « modèle plus gros »
  est déjà PARQUÉ pour cette raison (16/08). Axes à instruire, du moins cher au
  plus cher : sortie **contrainte** (grammaire / JSON forcé, qui supprime une
  classe entière d'erreurs de format sans coûter un octet de VRAM) ;
  **auto-cohérence** (plusieurs tirages, on garde ce qui se répète) ;
  **décodage spéculatif** ; quantifications récentes ; modèles petits parus
  depuis (le fonds tourne sur `qwen3-vl:2b`) ; et le **temps de calcul au
  moment de la réponse** plutôt que la taille. Source de départ donnée par
  Mike : `xda-developers.com/local-llms-used-prove-not-just-smaller-versions-cloud-models/`.
  **Habitude demandée** : se renseigner à l'ouverture de toute session qui
  touche au tagging, à la description ou à la recherche — ce domaine bouge vite
  et une doc de six mois est périmée.
  **Condition non négociable, et elle est déjà écrite** : rien ne se câble sans
  banc en aveugle sur un ET — apport réel **et** hallucination (`eval/METHODE.md`,
  et les trois conditions du point 16(c)). Le prompt de PRODUCTION double déjà
  les hallucinations, adopté sur un 25-15 : ce chantier-là commence par une
  mesure, pas par un modèle.

  **Mise à jour (05/09)** : chantier ouvert par la décision FR-only
  (2 quater) — modèles « petits parus depuis » enfin exploré :
  `qwen3.5:4b` trouvé et retenu (voir 2 quater). **La condition non
  négociable ci-dessus n'est qu'à MOITIÉ remplie** : la comparaison a
  mesuré l'apport réel (calico, lac, pas de fuite de noms) mais PAS en
  aveugle (le nom du modèle était connu en lisant le rapport) et sur un
  tirage CIBLÉ (8 photos difficiles), pas un vrai A/B comme celui qui a
  adopté v2ctx (25-15). À instruire si Mike veut la rigueur complète avant
  de lancer la campagne, ou à accepter tel quel — son choix, pas le mien à
  trancher seul.

- **Ouvrir la médiathèque à TOUTE LA FAMILLE, avec la vie privée au centre.**
  Aujourd'hui l'outil est pour Mike et Flo. La cible : chacun a son **dossier
  perso**, y dépose ses photos, et **contrôle qui voit quoi** — partages
  explicites, révocables, et le compte rendu de ce qui est partagé. L'outil
  rend alors ce qu'il sait faire : classer, ranger, retrouver.
  **Ce que ça change de nature** : le projet passe d'un outil mono-poste à un
  service multi-utilisateur, et la vie privée cesse d'être un réglage pour
  devenir la contrainte qui gouverne le modèle de données. Trois questions à
  trancher AVANT toute ligne de code — (a) l'unité de propriété : la photo, le
  dossier, ou la personne reconnue dessus ? une photo de Flo prise par Mike
  appartient à qui ? (b) ce que la RECHERCHE laisse fuir : un compte de
  résultats, un nom qui complète, une vignette de prévisualisation suffisent à
  révéler ce qu'on croyait caché ; (c) les **visages** : nommer quelqu'un dans
  la photo d'un autre, c'est écrire sur son bien — et les noms partent dans les
  XMP des fichiers (règle 2), donc hors de portée de tout réglage.
  **Absorbe l'item « mode Flo »** de la Réserve, dont le déclencheur était
  tombé le 21/08 : la file de nommage à plusieurs redevient utile ici, mais
  comme conséquence, pas comme préalable.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — « mode Flo » minimal (file de nommage des visages).
  **Son déclencheur est tombé le 21/08**, et l'item est désormais **absorbé par
  la piste « toute la famille »** ci-dessus (Mike, 22/08) : nommer à plusieurs
  est une conséquence du partage, pas un préalable à la vérité terrain.
- **Vidéo → audio** : coût élevé, valeur incertaine, aucun déclencheur.
- **Bibliothèque Figma** : le design system vit dans le code ; un miroir serait
  de la doc à double entretien.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).
