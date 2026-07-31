# Reconnaissance des chats — plan technique

Objectif retenu : **identification nommée** — tu étiquettes quelques photos de
chaque chat, le système auto-tague ensuite toutes les autres photos de Caline,
Inti et Luna. Même logique que la reconnaissance de personnes, mais adaptée aux
animaux.

Rien n'est codé pour l'instant : c'est le plan à valider avant d'engager le
travail, comme pour les visages.

---

## 0. Pourquoi ça ne marche pas déjà

Ta reconnaissance actuelle repose sur **InsightFace / `buffalo_l`**, un modèle
entraîné *uniquement sur des visages humains*. Il ne détecte aucun animal :
Caline, Inti et Luna lui sont invisibles. Les rares « animaux » qui apparaissent
viennent des mots-clés du tagging Ollama (`qwen3-vl:2b`), qui écrit parfois
« chat » — sans jamais tracer de boîte ni nommer l'individu.

Il faut donc une **chaîne dédiée aux animaux, en parallèle** de la chaîne
visages. Les deux ne se gênent pas : détecteurs différents, index séparés.

---

## 1. La réalité à connaître d'emblée (fiabilité)

La ré-identification *individuelle* d'un chat est **nettement moins fiable** que
pour un visage humain. Raisons :

- pas de modèle « état de l'art » grand public comme InsightFace pour les chats ;
- deux chats de robe similaire (deux tigrés, deux noirs) sont difficiles à
  séparer, même pour un humain sur une petite vignette ;
- poses très variables (endormi en boule, de dos, en mouvement) → peu de
  « museau bien de face » exploitable.

**Bonne nouvelle pour ton cas** : 3 chats seulement, et s'ils sont visuellement
distincts (robes/couleurs différentes), l'approche par embedding visuel marche
souvent très bien. On calibrera le seuil sur *tes* photos. Prévois quand même
une **validation manuelle** plutôt qu'un auto-tag aveugle (voir §6).

---

## 2. La chaîne en deux étapes

Contrairement aux visages (un seul modèle fait tout), il faut **deux modèles** :

1. **Détection** — trouver les chats dans une photo (une boîte par chat).
   Outil : **YOLO** (Ultralytics, ex. `yolo11n`/`yolo11s`), classe COCO
   « cat ». Rapide sur ton GPU, robuste, tourne en local via `onnxruntime` ou
   `torch` (déjà présents pour les visages). Détecte aussi « dog », « bird »…
   si tu veux élargir plus tard.

2. **Embedding pour reconnaître l'individu** — transformer chaque découpe de
   chat en un vecteur numérique, puis comparer par distance cosinus (exactement
   la même mécanique que `people.json`). InsightFace ne sert à rien ici. Deux
   options :

   | Option | Idée | Qualité | Coût |
   |--------|------|---------|------|
   | **A — DINOv2** (ViT-S/14) | Embedding visuel auto-supervisé, très bon en similarité fine | La meilleure pour distinguer des individus | ~90 Mo de modèle, tourne sur GPU |
   | **B — CLIP** (ViT-B/32) | Embedding image généraliste | Correct si robes bien distinctes, plus faible si proches | Léger, souvent déjà dispo |

   **Recommandation : option A (DINOv2)** — c'est le meilleur compromis local
   pour de la ré-identification fine, et ça reste 100 % hors-ligne.

   *Variante « museau »* : on pourrait ajouter un détecteur de tête/museau de
   chat pour embedder seulement la face (plus discriminant). Ça ajoute un modèle
   et de la complexité — à garder en Phase 4 si le corps entier ne suffit pas.

Tout reste **en local**, aucune donnée ne sort de la machine, cohérent avec ta
démarche (Ollama local, tags dans les fichiers).

---

## 3. Intégration dans l'architecture existante

On réutilise **exactement** les patterns déjà en place pour les visages :

| Existant (visages)                         | Équivalent pour les chats                          |
|--------------------------------------------|----------------------------------------------------|
| `face_worker` (thread + file)              | `animal_worker` : détecte (YOLO) + embed (DINOv2)  |
| `faces_index.json`                         | `animals_index.json` (séparé)                      |
| `people.json` (refs par personne)          | `pets.json` (refs par chat)                        |
| `cluster_faces` / `build_clusters`         | réutilisés tels quels sur les embeddings chats     |
| `pick_app` (bascule CPU/GPU adaptative)    | même logique de bascule pour YOLO + DINOv2         |
| vue `/people` (mosaïque + étiquetage)      | nouvelle vue `/pets`                               |
| `face_thumbs/` (cache vignettes)           | `animal_thumbs/` (cache des découpes)             |
| filtre galerie + écriture ExifTool         | mêmes fonctions, tag `animal:Nom`                  |

La partie clustering / nommage / attribution (`cluster_faces`,
`build_clusters`, `name_cluster`, l'assignation par référence la plus proche)
est **agnostique du type de vecteur** : elle marchera sur les embeddings de
chats sans réécriture, juste branchée sur les nouveaux index.

### Fichiers de données proposés

- **`animals_index.json`** — par photo, la liste des animaux détectés :
  `{clé_photo: [{bbox, embedding, det_score, species}]}`.
- **`pets.json`** — les chats nommés :
  `{pet_id: {name, species, refs:[...], count, at}}`.

---

## 4. Pipeline proposé (dans `server.py`)

1. **Scan des animaux** (`animal_worker`, thread de fond comme le tagging) :
   pour chaque photo, YOLO renvoie les boîtes « cat » → on découpe → DINOv2
   calcule l'embedding → écrit dans `animals_index.json`. Réutilise le
   redimensionnement PIL déjà en place. Premier passage long mais **unique**.
2. **Pré-regroupement** : `cluster_faces` regroupe les découpes qui se
   ressemblent, pour t'éviter d'étiqueter une par une.
3. **UI d'étiquetage `/pets`** : tu vois les groupes non nommés, tu leur donnes
   un nom (Caline / Inti / Luna). Chaque nom alimente `pets.json`.
4. **Attribution automatique** : pour chaque découpe, on cherche le chat dont la
   référence est la plus proche ; si distance cosinus < seuil (à calibrer sur
   tes photos), on attribue. Sinon → « inconnu ».
5. **Écriture dans les fichiers (optionnel, à décider)** : via ExifTool, écrire
   des mots-clés `animal:Nom` repris par ta galerie et son filtre combinable.
6. **Navigation** : vue `/pets` (mosaïque par chat) + le nom devient un filtre
   normal dans la galerie existante.

---

## 5. Livraison incrémentale (recommandé)

- **Phase 1 — Détection.** `animal_worker` + YOLO + `animals_index.json` + un
  endpoint pour compter les chats détectés. On valide que la détection marche
  bien sur *tes* photos **avant** d'aller plus loin. (C'est exactement ce que tu
  as fait pour les visages.)
- **Phase 2 — Embeddings + étiquetage.** DINOv2 + vue `/pets` : regroupement,
  nommage, attribution automatique en mémoire. On calibre le seuil.
- **Phase 3 — Écriture des noms** dans les fichiers + filtre « animal » dans la
  galerie.
- **Phase 4 — Réglages** : seuil de confiance, fusion/renommage, faux positifs,
  éventuel détecteur de museau si la robe seule ne suffit pas.

---

## 6. Points à trancher avant de commencer (Phase 1)

1. **YOLO : quel format ?** `torch` (ultralytics, simple) vs export ONNX
   (cohérent avec onnxruntime des visages, un poil plus de mise en place).
2. **Embedding : DINOv2 (reco) ou CLIP ?** DINOv2 = meilleure séparation ;
   CLIP = plus léger si déjà installé.
3. **Élargir aux autres animaux ?** Le détecteur voit aussi chien/oiseau/etc.
   On se limite aux chats, ou on tague aussi « chien », « oiseau »… en générique
   sans nommage ?
4. **Validation manuelle avant auto-tag ?** Vu la fiabilité moindre, je
   recommande une confirmation d'un clic plutôt qu'une attribution directe.
5. **Écrire les noms DANS les fichiers, ou seulement dans l'index ?** Dans les
   fichiers = portable ; index seul = réversible et non intrusif.

---

## 7. Coûts et risques

- **Deux modèles à installer** (YOLO + DINOv2/CLIP) vs un seul pour les visages
  — mais tous deux tournent sur ta stack GPU existante (torch/onnxruntime).
- **Premier scan complet** : long, mais unique (ensuite seuls les nouveaux
  fichiers, comme le tagging).
- **Fiabilité de la ré-identification** : le vrai risque. À mesurer en Phase 1/2
  sur tes photos avant d'écrire quoi que ce soit dans les fichiers.
- **Vie privée** : tout reste local.

---

*Quand tu veux avancer, on démarre par la Phase 1 (détection YOLO +
`animals_index.json`), et on décide des points de la §6 à ce moment-là.*
