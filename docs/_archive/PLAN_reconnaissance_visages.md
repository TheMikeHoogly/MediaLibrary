# Reconnaissance de personnes — plan technique

Objectif retenu (d'après tes réponses) : **identification nommée** — tu étiquettes
quelques visages, le système auto-tague ensuite toutes les autres photos de ces
personnes. Matériel : **GPU NVIDIA** disponible (déjà utilisé par Ollama).

Ce document explique *comment* c'est faisable et *dans quel ordre*. Rien n'est
codé pour l'instant : c'est le plan à valider avant d'engager le travail.

---

## 1. Le principe, en trois étapes

Toute reconnaissance faciale enchaîne trois opérations :

1. **Détection** — trouver les visages dans une photo (une boîte par visage).
2. **Embedding** — transformer chaque visage en un vecteur numérique (≈ 512
   nombres) qui « résume » le visage. Deux photos de la même personne donnent
   deux vecteurs proches ; deux personnes différentes donnent des vecteurs
   éloignés.
3. **Comparaison** — mesurer la distance entre vecteurs (distance cosinus).
   En dessous d'un seuil → « même personne ».

L'identification nommée, c'est simplement : tu fournis quelques visages de
référence par personne (« ça, c'est Papa »), on calcule leur embedding moyen,
puis chaque nouveau visage est rattaché à la personne dont la référence est la
plus proche.

---

## 2. Outil recommandé : InsightFace (sur GPU)

Deux familles d'outils locaux existent :

- **`face_recognition` / dlib** — très simple, mais précision moyenne et GPU mal
  exploité.
- **InsightFace** (modèle `buffalo_l`, exécuté via **ONNX Runtime GPU**) — état
  de l'art en précision, rapide sur GPU, détection robuste (profil, petits
  visages). **C'est le bon choix ici** vu que tu as un GPU.

Tout tourne **en local**, aucune donnée ne sort de la machine — cohérent avec ta
démarche actuelle (Ollama local, tags écrits dans les fichiers).

Dépendances : `insightface`, `onnxruntime-gpu`, `numpy`, plus **CUDA / cuDNN**
pour qu'onnxruntime voie le GPU (c'est la partie installation la plus délicate ;
un repli CPU reste possible mais plus lent). Ce module est **indépendant
d'Ollama** — il n'interfère pas avec le tagging existant.

---

## 3. Intégration dans l'architecture existante

Le projet a déjà tous les bons patterns ; on les réutilise :

| Existant (tagging)                     | Équivalent pour les visages                        |
|----------------------------------------|----------------------------------------------------|
| `tagger_worker` (thread de fond + file)| `face_worker` : détecte + calcule les embeddings   |
| `tags_index.json`                      | `faces_index.json` (séparé, pour ne pas l'alourdir)|
| Écriture XMP/IPTC via ExifTool         | Écriture des noms via ExifTool (mêmes fonctions)   |
| Galerie filtrable par mots-clés        | Même filtre, avec des tags `personne:Nom`          |
| Vue `/map` récemment ajoutée           | Nouvelle vue `/people`                             |

### Fichiers de données proposés

- **`faces_index.json`** — par photo, la liste des visages détectés :
  `{clé_photo: [{bbox, embedding, det_score}, ...]}`.
  L'embedding (512 floats) stocké en `float16`/base64 pèse ≈ 1 Ko par visage —
  gérable même à 100 000 photos.
- **`people.json`** — les personnes que tu as nommées :
  `{person_id: {name, ref_embeddings:[...], count}}`.

---

## 4. Pipeline proposé (dans `server.py`)

1. **Scan des visages** (`face_worker`, thread de fond comme le tagging) :
   pour chaque photo, InsightFace renvoie les visages + embeddings → écrits dans
   `faces_index.json`. Réutilise le redimensionnement PIL déjà en place. Un
   premier passage sur toute la bibliothèque est long, mais **une seule fois**.
2. **Pré-regroupement (optionnel)** : un clustering rapide regroupe les visages
   qui se ressemblent, pour t'éviter d'étiqueter un par un.
3. **UI d'étiquetage `/people`** : tu vois les groupes / visages non nommés et tu
   leur donnes un nom. Chaque nom alimente `people.json`.
4. **Attribution automatique** : pour chaque visage, on cherche la personne dont
   l'embedding de référence est le plus proche ; si la distance cosinus < seuil
   (≈ 0,35–0,50 à régler), le visage est attribué. Sinon → « inconnu ».
5. **Écriture dans les fichiers (optionnel, à décider)** : via ExifTool, écrire
   soit des mots-clés `personne:Nom` (repris tels quels par ta galerie et son
   filtre combinable), soit le standard **XMP-mwg-rs Region** (zones de visages
   lues par Lightroom, l'Explorateur Windows, Synology Photos…).
6. **Navigation** : nouvelle vue `/people` (mosaïque par personne) + le nom
   devient un filtre normal dans la galerie existante. Idée bonus : croiser avec
   la carte (« photos de Papa à Rome »).

---

## 5. Livraison incrémentale (recommandé)

- **Phase 1** — `face_worker` + `faces_index.json` + un endpoint de contrôle
  (compter les visages détectés). Valide que la détection marche bien sur *tes*
  photos avant d'aller plus loin.
- **Phase 2** — UI `/people` : étiquetage + attribution automatique en mémoire.
- **Phase 3** — écriture des noms dans les fichiers + filtre « personne » dans la
  galerie.
- **Phase 4** — réglages : seuil de confiance, fusion/renommage de personnes,
  gestion des faux positifs.

---

## 6. Points à trancher avant de commencer (Phase 1)

Ce sont des décisions qui t'appartiennent — elles orientent la mise en œuvre :

1. **Écrire les noms DANS les fichiers, ou seulement dans l'index ?**
   Dans les fichiers = portable (Lightroom, NAS) mais modifie tes originaux ;
   dans l'index seulement = réversible et non intrusif.
2. **Validation manuelle avant auto-tag ?** Attribution automatique directe, ou
   proposition à confirmer d'un clic pour éviter les erreurs ?
3. **Standard d'écriture** : mots-clés `personne:Nom` (simple, déjà filtrable)
   vs zones de visage XMP-mwg-rs (plus riche, interopérable) — ou les deux.
4. **Mineurs / consentement** : sujet sensible ; définir à l'avance qui on
   accepte d'indexer et de nommer.
5. **Visages de profil / flous** (score de détection bas) : les ignorer sous un
   seuil pour limiter le bruit ?

---

## 7. Coûts et risques

- **Installation `onnxruntime-gpu` + CUDA/cuDNN** : la partie la plus délicate.
  Un repli CPU fonctionne pour tester, en plus lent.
- **Premier scan complet** de la bibliothèque : long, mais unique (ensuite,
  seuls les nouveaux fichiers sont traités, comme le tagging).
- **Vie privée** : tout reste local ; à cadrer surtout si tu écris les noms dans
  les fichiers eux-mêmes.

---

*Quand tu veux avancer, on démarre par la Phase 1 (détection + `faces_index.json`),
et on décide des points de la section 6 à ce moment-là.*
