# Reprise — MediaLibrary, après la journée du 14 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`, les chiffres de
> performance dans `PERFORMANCE.md`, les choix de Mike en attente dans
> `QUESTIONS_MIKE.md`.

---

## 0. L'état, en dix lignes

**Trois livraisons le 14/09.** La marche du NAS coupée sur la grille récursive
(`/files?dir=1&rec=1` : **23,4 s → 6,5 s**, `parcours` 16,8 s → **48 ms**) ;
**`_A TRIER` par propriétaire** avec la salle d'arbitrage protégée et le
bat 36 qui sait enfin comparer une vidéo ; la page **`/arbitrage`**.

**Un compte par propriétaire** : Mike (admin), Flo, **Papa** (créé le 14/09).

**La salle d'arbitrage est close et vide** — Mike a tranché : les retouches,
rotations comme coupes, étaient les siennes. Pour les images comme pour les
vidéos, **c'est le NAS qui porte la bonne version**. Une copie plus grosse
n'est pas une copie meilleure.

**Mike a accepté les 8 heures de GPU d'une prochaine campagne** — le coût,
pas le contenu. Voir § 1.

Index : **44 471 clés**, 0 file d'attente, vignettes à jour, 0 cycle
inexpliqué. `main` à jour, arbre de travail propre, **87 Mo de corbeilles
locales vidées** — les journaux d'annulation, eux, sont intacts.

---

## 1. Par où commencer

**Mike a dit OUI aux 8 heures de GPU d'une prochaine campagne** (14/09 au
soir). Le COÛT est accepté ; **le CONTENU ne l'est pas**, et c'est à moi de le
produire. « Oui aux 8 heures » n'est pas « oui à ce modèle-là avec ce
prompt-là ». Il reste deux choses à mesurer, et **une seule expérience répond
aux deux**.

### 0. LE TIRAGE EN AVEUGLE — à lancer en premier, il occupe le GPU

**Deux modèles × deux prompts sur le MÊME tirage aléatoire.** Ce qu'il
tranche :

- **quel modèle** — référence en place `qwen3.5:4b|v3fr|kb1`, 11,3 s/photo,
  3,4 Go de VRAM (`modele.txt` porte l'historique : `qwen3-vl:4b` déborde,
  `qwen3.5:2b` casse le format) ;
- **ce que la question « document sensible » ajouterait** — mesuré le 14/09 :
  **23 photos sur 44 459** (0,05 %) sont candidates aujourd'hui, dont 13
  « carte bancaire ». **C'est un PLANCHER** : `candidat_sensible` lit le
  vocabulaire du prompt ACTUEL, or la question sert à trouver ce qu'il ne
  nomme pas. Ce qui décide est l'ÉCART entre les deux prompts sur un tirage
  neutre.

**Le protocole est dans la skill `vision-eval`, et il n'est pas négociable** :
hypothèse écrite AVANT de mesurer, jeu de validation figé issu du corpus réel
et versionné dans `eval/`, VRAM mesurée EN INFÉRENCE (pas la taille annoncée),
comparaison contre le pipeline EN PLACE, décision écrite.

**Ce qui existe et ce qui manque.** `mesure_modele_vision.py` compare déjà
deux modèles Ollama avec le prompt de prod — mais il est conçu pour **un petit
lot CIBLÉ**, « quelques clés précises, pas un tirage aléatoire ». Or la
roadmap exige l'inverse : **« mesuré en aveugle sur un tirage A/B — pas sur 8
photos choisies, la faute nommée dans Pistes ouvertes »**. C'est donc le
premier geste : lui donner un tirage aléatoire reproductible (graine fixée,
clés versionnées dans `eval/`) et la seconde dimension du prompt. Compter
aussi ce que la skill impose et que le script ne fait pas encore : la
COHÉRENCE inter-photos d'une même scène, et le taux de sortie malformée
(`_salvage_tags` / `parse_tags`).

**Ordre de grandeur** : 200 photos × 2 modèles × 2 prompts × ~12 s ≈ **2 h 40
de GPU**. À lancer par l'agent banc, puis on code pendant ce temps.

**Le verrou, AVANT de lancer quoi que ce soit qui écrive** :
`python mesure_copie_base.py` — quatre secondes. C'est la seule fenêtre pour
avoir un AVANT, et elle a été manquée la fois précédente : le bilan de la
campagne du 05/09 n'a jamais pu être fait faute d'instantané.

### 1. Pendant que le tirage tourne : unifier les CINQ producteurs de fiches

`file_data` est bâti à cinq endroits — navigation, tags, recherche/semblables,
même jour, et la grille indexée du 14/09. Seul le dernier passe par
`_fiche_depuis_cle` ; les quatre autres recopient la même construction. La
pagination devra se poser DERRIÈRE les cinq : les unifier avant coûte une
heure et évite de câbler cinq fois le même mécanisme, puis de le corriger cinq
fois.

### 2. Ensuite : le chargement à la demande

`ROADMAP.md` § C3, décidé par Mike le 13/09. **Sa cible a changé** depuis que
la marche est coupée : `enrichir` n'existe plus sur cette page.

| poste | ms | ce que c'est |
|---|---:|---|
| `mode_index` | 3 164 | bâtir 44 468 dictionnaires depuis l'index |
| `envoi` | 1 117 | 33,6 Mo sur le fil |
| `gabarit` | 712 | rendu HTML |
| `json` | 452 | sérialisation |
| `marques` | 431 | |
| `index` | 285 | balayage + comptage des mots-clés |

La page est **bornée par le CPU** (6,25 s de CPU pour 6,52 s d'horloge) : il
n'y a plus d'attente à retirer. Borner le nombre de fiches **BÂTIES** attaque
le premier poste.

**Puis** : B5/B6 (petites mesures), la **veille en plein écran** (P1), la
copie hors site (D1, à Mike), et **en dernier** la démo de bienvenue et son
e-mail (P2) — un mode d'emploi écrit avant que l'interface soit figée décrit
une interface qui n'existera plus.

**Ce qui n'attend que Mike** : le bat 26 pour les 19 fichiers d'`_A TRIER`
(14 doublons, 4 voisins, 1 différent — voir § 3), les deux détachements git
(A6), la fenêtre de réversibilité des 68 copies qui se ferme **vers le 13/10**,
et le KB Windows à masquer **vers le 16/10**.

## 2. Ce que les trois livraisons du 14/09 ont mis dans le code

- `_nom_relatif(k, prefixe)` — le chemin relatif d'une clé **dans sa casse
  d'origine**. `Path.relative_to` ne peut pas servir : la clé garde la casse du
  NAS, `folder` sort d'un `resolve()` qui minuscule l'hôte SMB.
- `_fiche_depuis_cle(...)` — la fiche de galerie d'une entrée, **sans toucher
  au disque**. Le cinquième producteur de `file_data` (voir § 1).
- `grille_indexee = rec and not remplace_la_grille` ;
  `_lister_dossier_frais(folder, False)` TOUJOURS.
- `auteurs.dossier_de(nom)` — l'inverse **contrôlé par aller-retour** de
  `proprietaire_de`. Un nom de compte portant un séparateur ne fabrique pas de
  chemin.
- `server.dossier_a_trier_de(utilisateur)` / `cible_a_trier(utilisateur)` — la
  boîte du compte connecté si son dossier existe, sinon la racine (celle de
  l'admin). La boîte d'un propriétaire se CRÉE au premier dépôt ; **l'ancre,
  jamais**.
- `rangement_annee.SALLES_ARBITRAGE` / `est_arbitrage(chemin)` — la règle vit
  là, et le bat 36 la LIT. Ancrée sur la PLACE (après un `_A TRIER`), pas sur
  le nom. Le plan compte ce qu'il laisse (`arbitrage`).
- `verifier_doublons_atrier` — compare aussi les VIDÉOS (empreinte tête+milieu
  + durée), deux verdicts séparés : `videos_confirmes` retirables,
  `videos_tronquees` derrière `--videos-tronquees`.
- `exiftool_json(...)` — **fichier d'arguments UTF-8** ; plus aucun chemin sur
  la ligne de commande (voir § 3).
- Route `/arbitrage` + `_serve_arbitrage_list()` — lecture seule, aucun bouton.

---

## 3. Les pièges

- **exiftool et les chemins accentués** : passés sur la ligne de commande, ils
  arrivent mutilés (« File not found », une entrée de moins dans le lot,
  aucune erreur). **8,4 % du fonds** est concerné (3 714 clés sur 44 477).
  Tout appel passe désormais par `exiftool_json` et son fichier d'arguments ;
  un nouvel appel écrit ailleurs doit faire pareil.
- **Un banc qui INJECTE une lecture ne tient que la règle.** Les durées vidéo
  étaient injectées ; c'est en allant les chercher pour de vrai que le défaut
  ci-dessus est apparu. Quand une règle dépend d'un outil externe, une mesure
  doit lire cet outil au moins une fois sur de vraies données.
- **Un banc qui découpe le source sur le TEXTE mesure ses VOISINS** — et sa
  propre prose. Deux bancs sont tombés là-dessus le 14/09 : l'un découpait
  vingt méthodes du routeur, l'autre lisait la docstring qui NOMME les mots
  qu'il interdit. Découper sur l'ARBRE, docstring retirée.
- **Un composant canonique se réutilise TEL QUEL ou se laisse tranquille.**
  `.vue` est la cellule CARRÉE de la planche contact (`aspect-ratio: 1` dans
  `components.css`) : la page `/arbitrage` l'avait reprise, une photo en
  portrait tenait sur un cinquième de la largeur. Vu à l'écran, pas à la
  lecture — **regarder la page, pas seulement ses bancs.**
- **La grille récursive vient de l'INDEX** : une photo déposée à l'instant
  dans un SOUS-dossier n'y paraît qu'au prochain scan (~30 min,
  `NAS_SCAN_CYCLES`) — et, symétriquement, une photo effacée y reste visible
  jusque-là. Son propre dossier, lui, est à jour tout de suite.
- **Le rangement par année ne s'applique JAMAIS tout seul** : la maintenance
  bâtit le plan, le bat 26 l'applique. C'est voulu. Et le bat 26 commence
  désormais par `verifier_plan_annee.py`, qui JUGE les collisions au lieu de
  les compter : **une collision n'est pas une permission d'effacer**.
- **Un instrument qui tranche au-delà de ce qu'il mesure est pire qu'un
  instrument muet.** `verifier_plan_annee` classait « deux vidéos distinctes »
  quatre fichiers de MÊME durée à la centième et 0,5 % d'écart de taille. D'où
  le verdict `VOISIN` et ses deux garde-fous : une borne de 5 % sur la taille,
  et le refus de voisiner deux durées INCONNUES — deux zéros sont égaux.
- **Le recensement dure 1 h 09** et **chaque redémarrage le tue**. Avant de
  livrer en rafale : `maint.lourde` dans `/api/maint/status`.
- **Deux balayages SMB simultanés** : l'énumération passe de 305 s à 2 100 s.
- **Windows : KB5124008 casse Plan9**, donc `device_bash`. UBR **9278**,
  Windows Update en pause jusqu'au 17.10. `Get-HotFix` MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **La VM n'atteint pas le LAN** : tout ce qui interroge le serveur passe par
  l'agent de banc ou par **Chrome** (`http://192.168.0.13:8080`).
- **Chrome, jamais le navigateur intégré** (demande de Mike, 13/09).
- **Git : jamais depuis la VM**, même en lecture apparente. Préfixes de branche
  admis : `feat|fix|chore|docs|test` — `perf/` a été refusé.
- **L'agent git consomme l'ordre AVANT de travailler** : le canal revenu à
  `rien` ne veut pas dire « fini ». C'est `_etat_git.json` qui le dit, et il
  faut comparer son `dernier.quand`, pas le mtime du fichier — ~6 min quand
  `server.py` est touché.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 4. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

Et, après toute analyse : **la contre-vérifier** (règle 11). Elle a travaillé
cinq fois le 14/09, et chaque fois elle a rapporté quelque chose : la prémisse
du chantier de la marche est tombée avant le code ; un compteur qui mélangeait
deux causes a été scindé avant d'être lu ; un banc qui injectait une lecture
masquait un défaut touchant 8,4 % du fonds ; une conclusion « aucun de ces 18
fichiers n'a de jumeau » était fausse parce que `os.path.basename` rend le
chemin ENTIER sur un chemin Windows sous Linux ; et la page `/arbitrage`,
regardée à l'écran, a montré une rotation que trois mesures n'avaient pas vue.
