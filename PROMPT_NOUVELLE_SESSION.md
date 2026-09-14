# Reprise — MediaLibrary, après la nuit du 13 au 14 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`, les chiffres de
> performance dans `PERFORMANCE.md`.

---

## 0. L'état, en dix lignes

**La grille récursive ne marche plus sur le NAS** (livré le 14/09 au matin).
`/files?dir=1&rec=1` est passée de **23,4 s à 6,5 s** (8,0 s à froid) :
`parcours` 16,8 s → **48 ms**, zéro aller-retour SMB, le même compte de
photos. La page est désormais **bornée par le CPU** — 6,25 s de CPU pour
6,52 s d'horloge. Détail : `PERFORMANCE.md` § 3.25.

**La campagne de retag est finie** (nuit du 12 au 13) ; les 248 dépôts
d'`Uploads` sont triés (13/09, par Mike). Index au 14/09 08 h 49 :
**44 477 clés**, 44 468 fiches affichées, 8 images abîmées écartées, 0 clé
sans fichier, 0 fichier hors index, 0 cycle inexpliqué.

`main` porte la livraison du 14/09 (contrôler `.git/logs/refs/heads/main`).

---

## 1. Par où commencer

**Le point suivant est le CHARGEMENT À LA DEMANDE** (`ROADMAP.md` § C3,
décidé par Mike le 13/09) — et sa cible a changé depuis qu'il a été décidé.
`enrichir` n'existe plus sur cette page. Ce qui reste :

| poste | ms | ce que c'est |
|---|---:|---|
| `mode_index` | 3 164 | bâtir 44 468 dictionnaires depuis l'index |
| `envoi` | 1 117 | 33,6 Mo sur le fil |
| `gabarit` | 712 | rendu HTML |
| `json` | 452 | sérialisation |
| `marques` | 431 | |
| `index` | 285 | balayage + comptage des mots-clés |

Borner le nombre de fiches **BÂTIES** attaque enfin le premier poste. Ce que
la décision engage est inchangé (tri et filtres côté SERVEUR, pagination
DERRIÈRE les quatre modes « la grille est un résultat », `window.Vignettes`
réutilisé, un compteur qui dit le total RÉEL) — s'y ajoute un **cinquième**
producteur de fiches, `grille_indexee`.

Le reste du tableau de priorités est dans `ROADMAP.md` § B. **UNE décision
appartient toujours à Mike** : « faut-il une prochaine campagne, et avec
quoi ? » — § B liste les quatre choses à poser sur la table avant d'en parler.
**Ne rien proposer tant qu'elles n'y sont pas.**

---

## 2. Ce que le changement du 14/09 a mis dans le code

- `_nom_relatif(k, prefixe)` — le chemin relatif d'une clé **dans sa casse
  d'origine**. `Path.relative_to` ne peut pas servir : la clé garde la casse
  du NAS, `folder` sort d'un `resolve()` qui MINUSCULE l'hôte SMB. La
  comparaison se fait sur `_pkey`, la découpe sur la chaîne d'origine, avec un
  contrôle de longueur (« İ ».lower() rend deux caractères).
- `_fiche_depuis_cle(k, e, fctx, roots, memo, prefixe)` — la fiche de galerie
  d'une entrée, **sans toucher au disque**. C'est le **cinquième** producteur
  de `file_data`, après tags / recherche / semblables / même jour. Les quatre
  autres construisent encore la leur à la main : les y faire passer est un
  candidat évident, non fait faute de mesure.
- `_serve_gallery` : `grille_indexee = rec and not remplace_la_grille`,
  `_lister_dossier_frais(folder, False)` **toujours** (les sous-dossiers de la
  barre), `carte_cles` non bâtie quand elle ne sert pas.
- Bancs : `test_grille_indexee.py` (15, exécutés — pas du texte),
  `test_galerie_enrichissement.py` mis à l'arbre plutôt qu'au `str.count`.
- `mesure_ecart_index_marche.py` — compare index et disque fichier par
  fichier, sur un snapshot cohérent. À relancer avant toute conclusion sur
  « ce que l'index ignore ».

---

## 3. Les pièges (inchangés, sauf mention)

- **La grille récursive vient de l'INDEX** : une photo déposée à l'instant
  dans un SOUS-dossier n'y paraît qu'au prochain scan (un tour sur six,
  ~30 min — `NAS_SCAN_CYCLES`). Son propre dossier la montre tout de suite.
  Le bandeau de la page le dit ; si ce délai gêne un jour, la porte est
  `NAS_SCAN_CYCLES`, pas le retour de la marche.
- **Le recensement dure 1 h 09** et **chaque redémarrage le tue**. Avant de
  livrer en rafale : `maint.lourde` dans `/api/maint/status`.
- **Deux balayages SMB simultanés** : l'énumération passe de 305 s à 2 100 s.
- **Un outil qui descend récursivement dans `_A TRIER` traverse la salle
  d'arbitrage.**
- **Windows : KB5124008 casse Plan9**, donc `device_bash`. UBR **9278**,
  Windows Update en pause jusqu'au 17.10. `Get-HotFix` MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **La VM n'atteint pas le LAN** : tout ce qui interroge le serveur passe par
  l'agent de banc ou par **Chrome** (`http://192.168.0.13:8080`). Le NAS est
  monté sous `$HOME/mnt/Photos`.
- **Chrome, jamais le navigateur intégré** (demande de Mike, 13/09).
- **Git : jamais depuis la VM**, même en lecture apparente — écrire `livrer`
  dans `_commande_git.txt`, et LIRE `.git/logs/*` à la main.
- **Canaux** : écrire `rien`, puis l'ordre UNE fois, puis ATTENDRE le retour à
  `rien`. `_banc_sortie.txt` porte un EN-TÊTE qui dit de quel banc il vient.
- **Un `livrer` qui touche `server.py` lance ~73 bancs et dure ~6 minutes.**
- **Un banc qui lit le source par le TEXTE mesure une orthographe** — écrire
  sur l'ARBRE (`ast`). Deux des bancs cassés ce matin l'étaient pour ça.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 4. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

Et, après toute analyse : **la contre-vérifier** (règle 11). Elle a encore
travaillé cette nuit, et deux fois dans le bon sens : la prémisse du chantier
(« un fichier manque à l'index ») est TOMBÉE sous son propre contrôle avant
qu'une ligne soit écrite, et le premier compteur de la nouvelle branche
mentait — un seul nombre pour deux causes — avant d'être scindé.
