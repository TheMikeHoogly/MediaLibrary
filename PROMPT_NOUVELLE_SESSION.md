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

**La salle d'arbitrage est close et vide** — Mike a tranché, les retouches
étaient les siennes. **Une seule question lui appartient encore**, dans
`QUESTIONS_MIKE.md` : les 9 vidéos effacées étaient 25 à 50 % plus longues que
celles du fonds.

Index : **44 471 clés**, 0 file d'attente, vignettes à jour, 0 cycle
inexpliqué. `main` à jour, arbre de travail propre.

---

## 1. Par où commencer

**Le tableau de priorités a été reclassé le 14/09 au soir** (`ROADMAP.md` § B).
Les deux premiers points sont pour moi et ne dépendent de personne :

**1. Unifier les CINQ producteurs de fiches — une heure, à faire d'abord.**
`file_data` est bâti à cinq endroits : navigation, tags, recherche/semblables,
même jour, et la grille indexée du 14/09. Seul le dernier passe par
`_fiche_depuis_cle` ; les quatre autres recopient la même construction. La
pagination devra se poser DERRIÈRE les cinq — les unifier avant évite de
câbler cinq fois le même mécanisme, puis de le corriger cinq fois.

**2. Le chargement à la demande** (`ROADMAP.md` § C3, décidé par Mike le
13/09). **Sa cible a changé** depuis que la marche est coupée : `enrichir`
n'existe plus sur cette page. Ce qui reste, mesuré le 14/09 :

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

Ensuite : B5/B6 (petites mesures), puis préparer la décision « prochaine
campagne » — **UNE décision qui appartient à Mike**, et `ROADMAP.md` § B liste
les quatre choses à poser sur la table avant d'en parler. **Ne rien proposer
tant qu'elles n'y sont pas.**

**Deux demandes neuves de Mike (14/09), instruites dans « Pistes ouvertes »** :
une **veille en plein écran** après 5 minutes d'inactivité (P1) et une **démo
de bienvenue + l'e-mail** pour sa famille (P2, **en dernier** : un mode
d'emploi écrit avant que l'interface soit figée décrit une interface qui
n'existera plus).

---

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
  bâtit le plan, le bat 26 l'applique. C'est voulu.
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
