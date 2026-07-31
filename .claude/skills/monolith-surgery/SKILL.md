---
name: monolith-surgery
description: Règles d'édition sûre de server.py, le monolithe de ~7500 lignes de la photothèque locale. À utiliser avant toute modification du serveur — ajout de route HTTP, modification d'un worker ou d'une file, changement de config de pipeline, édition d'une des pages HTML inline, migration de store, extraction de code vers ui/. Liste les invariants à ne pas casser (écriture atomique des index, versions de pipeline, préservation des noms humains, arbitrage VRAM 4 Go, cohérence des 7 pages) et la méthode de navigation dans un fichier de cette taille.
---

# Chirurgie du monolithe — `server.py`

## Ce que tu manipules

Un fichier de ~7 500 lignes (313 Ko) qui contient **tout** : configuration, stores JSON,
quatre pipelines ML, sept workers threadés, un routeur HTTP en stdlib et sept pages HTML
complètes en chaînes littérales. Aucune dépendance externe côté serveur, aucun build step.

C'est un choix architectural délibéré et efficace — le projet se déploie en copiant un
fichier. **Ne propose pas de le découper en paquet Python, ni d'introduire un framework.**
La direction de refactoring validée est l'extraction des **assets** (CSS/JS/HTML) vers `ui/`,
pas l'éclatement de la logique.

## Navigation — ne lis jamais le fichier entier

Lire 313 Ko coûte cher et n'aide pas. Repères stables :

| Zone | Lignes ~ | Contenu |
|---|---|---|
| Config | 40–200 | chemins, seuils, `*_GPU_*`, versions de pipeline |
| `TagStore` | 211–312 | store JSON générique, écriture atomique |
| Métadonnées | 327–560 | exiftool, piexif, GPS |
| Dates / EXIF | 598–750 | `_best_time`, backfill |
| Tagging Ollama | 751–950 | `ollama_generate`, `parse_tags`, `tagger_worker` |
| Index / clés | 946–1200 | `_pkey`, `_resolve_key`, `_tag_index` |
| Maintenance | 1193–1420 | `scan_uploads`, `maintenance_loop` |
| **Pages HTML** | 1426–2950, 5199–6210 | `HTML_PAGE`, `GALLERY_PAGE`, `BROWSE_PAGE`, `MAP_PAGE`, `PETS_PAGE`, `FACES_PAGE`, `PEOPLE_PAGE` |
| Matériel / GPU | 2964–3160 | `hw_state`, `system_busy`, `pick_app` |
| Visages | 3026–3250 | InsightFace, détection, workers |
| Animaux (YOLO) | 3251–3400 | détection, workers |
| Empreintes chats | 3403–4080 | DINOv2, clusters, nommage |
| Ré-embedding | 4084–4175 | `_face_is_poor`, `reembed_*` |
| Clusters personnes | 4176–4900 | clustering, nommage, écriture des tags |
| Routeur HTTP | 6218–6400 | `do_GET`, `do_POST` |

Méthode : `Grep` sur un nom de fonction ou une constante, puis `Read` avec `offset`/`limit`
autour du résultat. Pour les pages HTML, `Grep` la classe CSS ou l'`id` visé.

Les constantes de configuration sont **documentées en commentaire dans le fichier**, souvent
avec la raison du réglage et l'historique des essais. Lis ces commentaires avant de changer
une valeur : plusieurs encodent une décision déjà éprouvée (`FACE_USE_GPU = False` parce que
la VRAM est prise par Ollama, `qwen3-vl:4b` écarté parce qu'il déborde).

## Invariants — les casser est une régression, même si le code tourne

### 1. Les noms attribués par un humain sont sacrés

Les tags `personne:Nom` et `animal:Nom` sont écrits dans les métadonnées XMP des fichiers via
exiftool. Ils représentent des heures de tri humain et **survivent à la base de données**.

- Toute migration doit les préserver : `migrate_animal_pipeline()` relance détection et
  empreintes mais conserve les noms — reproduis ce contrat pour toute nouvelle migration.
- `reconcile_named_tags()` et `reimport_name_tags()` existent pour rattraper les divergences
  entre index et fichiers. Ne les contourne pas.
- Une suppression de nom passe par la file (`PERSON_QUEUE`) et doit être annulable.

Si un changement risque de perdre un nom, il est faux — quel que soit son gain par ailleurs.

### 2. L'écriture des index reste atomique

`TagStore._save()` écrit dans un `.tmp` puis `os.replace()`, avec repli non atomique si le
rename échoue (verrou SMB). Le commentaire explique le sinistre que ça évite : un index
corrompu par une coupure NAS, donc une perte de tags au redémarrage.

- N'introduis pas d'écriture directe sur `self.path`.
- Toute écriture d'index se fait sous `self.lock`.
- Lors de la migration vers SQLite, la garantie équivalente est la **transaction** : un
  `commit()` par unité de travail, jamais d'écriture partielle visible.

### 3. Les versions de pipeline gouvernent les recalculs

`ANIMAL_PIPELINE_VERSION = "yolo11s|det0.30|dinov2_base"` encode détecteur + seuil + modèle
d'empreinte. Changer l'un des trois **oblige** à bumper la chaîne, sinon des embeddings
incompatibles cohabitent silencieusement dans le même index — panne difficile à diagnostiquer.

Applique le même schéma à tout nouveau pipeline (tagging, recherche sémantique) : une chaîne
de version qui liste les composants dont dépend la validité des données stockées.

### 4. La VRAM est de 4 096 Mo, partagée

Trois consommateurs se disputent le GPU : Ollama (résident 30 min via `keep_alive: "30m"`),
InsightFace, et l'encodeur d'empreintes. Chacun a aujourd'hui son propre seuil
(`FACE_GPU_MIN_FREE_MB = 1200`, `ANIMAL_GPU_MIN_FREE_MB = 1600`, `PET_GPU_MIN_FREE_MB = 1800`)
et interroge `hw_state()` séparément.

- **N'ajoute pas une cinquième politique GPU indépendante.** Si un nouveau modèle a besoin du
  GPU, il passe par le mécanisme existant — ou, mieux, contribue à le centraliser dans un
  arbitre unique avec baux et priorités (UI > tagging > visages > chats).
- Tout code GPU doit avoir un repli CPU fonctionnel : c'est le mode par défaut du projet.
- Le débordement silencieux en RAM système est le pire échec — il ne lève pas d'erreur, il
  divise la vitesse par trois. Vérifie explicitement.

### 5. L'UI cède la priorité au NAS

`LAST_HEAVY_AT` et `REEMBED_UI_QUIET = 12` garantissent qu'une requête utilisateur suspend le
travail de fond sur le NAS. Toute nouvelle boucle de fond qui lit le NAS doit respecter le même
contrat — sinon la navigation devient saccadée pendant les traitements.

### 6. Les sept pages doivent rester cohérentes

Une modification de composant partagé (chip, bouton, grille, barre) touche **jusqu'à sept
blocs `<style>`**. Ne corrige pas une seule page : soit tu propages, soit tu extrais vers un
token partagé. Une divergence non intentionnelle entre pages est déjà présente dans le code
(`.pchip { color: #cbd }` vs `.chip { color: #bbb }`) — ne l'aggrave pas.

Pour toute édition d'UI, charge la skill **`photo-ui`** : elle contient les tokens et le
plancher d'accessibilité obligatoire.

### 7. Zéro dépendance côté serveur

Les seuls imports lourds sont **paresseux, dans les fonctions** (`import numpy as np` apparaît
une vingtaine de fois localement, jamais en tête de fichier). C'est intentionnel : le serveur
démarre et sert des pages même sans torch, insightface ou ultralytics installés.

- **Ne remonte jamais un import ML en tête de fichier.**
- Tout nouvel import lourd est paresseux et échoue proprement, avec un message qui dit quel
  `.bat` d'installation lancer.
- Côté client : pas de npm, pas de bundler. Le seul CDN toléré aujourd'hui est Leaflet pour la
  carte.

## Les fichiers `.bat` sont en ASCII PUR — règle absolue

`cmd.exe` relit le fichier de commandes par **décalage d'octets** après chaque
commande exécutée. Un seul caractère UTF-8 multi-octets désaligne son curseur :
l'interpréteur atterrit alors au milieu des lignes suivantes et tente d'exécuter
des fragments (`'nir'`, `'e.py'`, `'/b'`, `'Contenu'`). Le script paraît
fonctionner puis saute silencieusement des étapes — y compris des étapes de
vérification, ce qui est le pire des cas.

Interdits dans le **contenu** d'un `.bat`, même en commentaire `REM` :

- lettres accentuées (`é`, `è`, `à`, `ê`, `ç`…) ;
- guillemets français `«` `»` — l'oubli le plus fréquent ;
- traits de séparation `─` `═`, puces `•`, flèches `→`, symboles `✓` `✗` `⚠` ;
- tout emoji.

Utilise `=` et `-` pour les séparateurs, `"` pour les citations, et écris sans
accents (`arrete`, `deja`, `verifie`). Le **nom** du fichier peut rester accentué
(`4 - Réparer les tags.bat`) : seul le contenu est relu par le parseur.

Vérification obligatoire avant de livrer un `.bat` :

```bash
LC_ALL=C grep -nP '[\x80-\xFF]' "mon script.bat"   # doit ne rien renvoyer
head -c3 "mon script.bat" | xxd -p                 # ne doit PAS valoir efbbbf (BOM)
```

Et vérifie la sortie de la commande : un test de contrôle mal écrit qui affiche
« 0 » pour tout est pire que pas de test. Cette erreur a déjà été commise deux
fois sur ce projet.

## Ajouter une route HTTP

Le routeur est manuel : `do_GET` (l. ~6218) et `do_POST` (l. ~6314) comparent `self.path`.

1. Ajoute la branche dans la bonne méthode, en respectant l'ordre existant (préfixes avant
   égalités exactes).
2. Réponds toujours avec un code de statut et un `Content-Type` explicites.
3. Les routes qui lisent le NAS appellent `note_heavy_activity()` — c'est ce qui alimente
   l'invariant n° 5.
4. Les routes qui déclenchent un travail lourd retournent immédiatement et **poussent dans une
   file** ; elles ne bloquent pas la réponse. Suis le modèle de `enqueue()` / `enqueue_face()` /
   `enqueue_animal()`.
5. `ThreadingHTTPServer` : tout état partagé touché par une route est protégé par un `Lock`.
   Les verrous existants sont nommés (`PENDING_LOCK`, `CLUSTER_LOCK`, `PET_CLUSTER_LOCK`).

## Extraire les pages vers `ui/`

Chantier prioritaire mais à faire **après** la migration SQLite, pour ne pas refactorer deux
fois. Méthode :

1. Une page à la fois, en commençant par la plus simple (`BROWSE_PAGE`, ~35 lignes de style).
2. Extraire d'abord le CSS commun vers `ui/tokens.css` + `ui/base.css`, en **remplaçant les
   valeurs en dur par les tokens de la skill `photo-ui`** — c'est le moment de corriger les
   divergences, pas de les transporter.
3. Le serveur lit les fichiers `ui/` au démarrage et les met en cache mémoire. En mode
   développement, relire à chaque requête si `mtime` a changé.
4. Pour conserver un livrable mono-fichier, un `bundle.py` de quelques dizaines de lignes
   réinjecte les assets dans une copie de `server.py`. Le zéro-build reste vrai pour
   l'utilisateur final.
5. Après chaque page extraite : la page doit être **visuellement identique** avant d'accepter
   tout changement de design. Deux chantiers séparés, jamais mélangés.

## Avant de livrer

- Le serveur démarre-t-il **sans** torch / insightface / ultralytics installés ?
- Les index existants sont-ils lus sans migration forcée, ou la migration est-elle explicite,
  journalisée et réversible ?
- Un nom attribué par un humain a-t-il pu être perdu ?
- Le pic de VRAM reste-t-il compatible avec les trois consommateurs simultanés ?
- Si l'UI a changé : les tokens et les sept points d'accessibilité de `photo-ui` sont-ils
  respectés ?
- Pour un changement risqué, fais relire le diff par un agent dédié ou la skill
  `engineering:code-review`.
