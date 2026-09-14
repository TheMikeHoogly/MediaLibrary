# Reprise — MediaLibrary, après la journée du 14 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`, les chiffres de
> performance dans `PERFORMANCE.md`.

---

## 0. L'état, en dix lignes

**Deux livraisons le 14/09.** Le matin, la marche du NAS coupée sur la grille
récursive : `/files?dir=1&rec=1` passe de **23,4 s à 6,5 s**, `parcours`
16,8 s → **48 ms**, zéro aller-retour SMB (`PERFORMANCE.md` § 3.25). Le soir,
**`_A TRIER` par propriétaire** et les défauts voisins (`ROADMAP.md` § B8).

La campagne de retag est finie (nuit du 12 au 13), les 248 dépôts d'`Uploads`
sont triés (13/09, par Mike). Index : **44 477 clés**, 0 clé sans fichier,
0 fichier hors index, 0 cycle inexpliqué.

---

## 1. Par où commencer

**Le CHARGEMENT À LA DEMANDE** (`ROADMAP.md` § C3, décidé par Mike le 13/09).
Sa cible a changé depuis la coupe de la marche : `enrichir` n'existe plus sur
cette page. Ce qui reste, mesuré le 14/09 :

| poste | ms | ce que c'est |
|---|---:|---|
| `mode_index` | 3 164 | bâtir 44 468 dictionnaires depuis l'index |
| `envoi` | 1 117 | 33,6 Mo sur le fil |
| `gabarit` | 712 | rendu HTML |
| `json` | 452 | sérialisation |
| `marques` | 431 | |
| `index` | 285 | balayage + comptage des mots-clés |

Borner le nombre de fiches **BÂTIES** attaque enfin le premier poste. La page
est bornée par le CPU (6,25 s de CPU pour 6,52 s d'horloge) : il n'y a plus
d'attente à retirer.

**Un préalable d'une heure, à faire d'abord** : les CINQ producteurs de fiches
(navigation, tags, recherche/semblables, même jour, grille indexée) construisent
chacun la leur. Seul le cinquième passe par `_fiche_depuis_cle`. La pagination
devra se poser DERRIÈRE les cinq — les unifier avant évite de câbler cinq fois
le même mécanisme.

**UNE décision appartient toujours à Mike** : « faut-il une prochaine campagne,
et avec quoi ? » — `ROADMAP.md` § B liste les quatre choses à poser sur la
table. **Ne rien proposer tant qu'elles n'y sont pas.**

---

## 2. Ce que les deux livraisons du 14/09 ont mis dans le code

**Matin — la grille récursive vient de l'index**
- `_nom_relatif(k, prefixe)` : le chemin relatif d'une clé **dans sa casse
  d'origine** (`Path.relative_to` ne peut pas servir, la clé garde la casse du
  NAS et `folder` sort d'un `resolve()` qui minuscule l'hôte SMB).
- `_fiche_depuis_cle(...)` : la fiche de galerie d'une entrée, **sans toucher
  au disque**. Cinquième producteur de `file_data`.
- `grille_indexee = rec and not remplace_la_grille` ;
  `_lister_dossier_frais(folder, False)` TOUJOURS.
- Une photo déposée dans un SOUS-dossier n'apparaît dans la vue récursive
  qu'au prochain scan (~30 min, `NAS_SCAN_CYCLES`) ; son propre dossier la
  montre tout de suite, et le bandeau de la page le dit.

**Soir — `_A TRIER` par propriétaire**
- `auteurs.dossier_de(nom)` : l'inverse **contrôlé par aller-retour** de
  `proprietaire_de`. Un nom de compte qui porte un séparateur ne fabrique pas
  de chemin.
- `server.dossier_a_trier_de(utilisateur)` / `cible_a_trier(utilisateur)` :
  la boîte du compte connecté si son dossier existe, sinon la racine — qui
  est celle de l'admin (`visibilite.chez_soi`). La boîte d'un propriétaire se
  CRÉE au premier dépôt (`FileOps.mkdir`) ; **l'ancre, jamais**.
- `rangement_annee.SALLES_ARBITRAGE` / `est_arbitrage(chemin)` : la règle vit
  là, et le bat 36 la LIT. Ancrée sur la PLACE (après un `_A TRIER`), pas sur
  le nom. Le plan compte ce qu'il laisse (`arbitrage`).
- `verifier_doublons_atrier` : compare aussi les VIDÉOS (empreinte tête+milieu
  + durée), avec deux verdicts séparés — `videos_confirmes` retirables,
  `videos_tronquees` derrière `--videos-tronquees`.
- `exiftool_json(...)` : **fichier d'arguments UTF-8**, plus aucun chemin sur
  la ligne de commande (voir § 3).

---

## 3. Les pièges

- **exiftool et les chemins accentués** : passés sur la ligne de commande, ils
  arrivent mutilés (« File not found », une entrée de moins dans le lot,
  aucune erreur). **8,4 % du fonds** est concerné. Tout appel à exiftool passe
  désormais par `exiftool_json` et son fichier d'arguments. Si un nouvel appel
  est écrit ailleurs, il doit faire pareil — `docs/DECISIONS_OUTILLAGE.md`.
- **Un banc qui INJECTE une lecture ne tient que la règle.** Les durées vidéo
  étaient injectées ; c'est en allant les chercher pour de vrai que le défaut
  ci-dessus est apparu. Quand une règle dépend d'un outil externe, une mesure
  doit lire cet outil au moins une fois sur de vraies données.
- **La grille récursive vient de l'INDEX** (voir § 2).
- **Le recensement dure 1 h 09** et **chaque redémarrage le tue**. Avant de
  livrer en rafale : `maint.lourde` dans `/api/maint/status`.
- **Deux balayages SMB simultanés** : l'énumération passe de 305 s à 2 100 s.
- **Un outil qui descend récursivement dans `_A TRIER` traverse la salle
  d'arbitrage** — la règle existe maintenant (`est_arbitrage`), un outil neuf
  doit la lire au lieu d'en écrire une deuxième.
- **Windows : KB5124008 casse Plan9**, donc `device_bash`. UBR **9278**,
  Windows Update en pause jusqu'au 17.10. `Get-HotFix` MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **La VM n'atteint pas le LAN** : tout ce qui interroge le serveur passe par
  l'agent de banc ou par **Chrome** (`http://192.168.0.13:8080`).
- **Chrome, jamais le navigateur intégré** (demande de Mike, 13/09).
- **Git : jamais depuis la VM**, même en lecture apparente. Écrire `livrer`
  dans `_commande_git.txt`, et LIRE `.git/logs/*` à la main. Les préfixes de
  branche admis sont `feat|fix|chore|docs|test` — `perf/` a été refusé.
- **Canaux** : écrire `rien`, puis l'ordre UNE fois, puis ATTENDRE. L'agent
  git consomme l'ordre AVANT de travailler : le canal revenu à `rien` ne veut
  pas dire « fini », c'est `_etat_git.json` qui le dit (~6 min si `server.py`
  est touché).
- **Un banc qui lit le source par le TEXTE mesure une orthographe** — écrire
  sur l'ARBRE (`ast`).
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 4. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

Et, après toute analyse : **la contre-vérifier** (règle 11). Elle a travaillé
trois fois le 14/09, et chaque fois elle a rapporté quelque chose : la prémisse
du chantier de la marche est tombée avant le code (« un fichier manque à
l'index » : 0 d'un côté, 0 de l'autre) ; un compteur qui mélangeait deux causes
a été scindé avant d'être lu ; et un banc qui injectait une lecture a masqué,
jusqu'à ce qu'on aille lire pour de vrai, un défaut qui touchait 8,4 % du fonds.
