---
name: vision-eval
description: Protocole d'évaluation d'un modèle de vision avant adoption dans la photothèque — tagging (VLM ou encodeur zéro-shot), reconnaissance faciale, re-identification de chats, recherche sémantique. À utiliser dès qu'il est question de changer, comparer, tester ou remplacer un modèle (qwen3-vl, SigLIP, InsightFace/buffalo_l, DINOv2, MegaDescriptor, YOLO), d'ajuster un seuil de clustering, ou d'interpréter un benchmark public. Impose un jeu de validation issu du corpus réel, une mesure de VRAM sur RTX 3050 4 Go, une comparaison contre le pipeline en place et une décision écrite.
---

# Protocole d'évaluation des modèles de vision

## Pourquoi cette skill existe

Un benchmark public ne dit pas si un modèle marche **sur ce corpus, sur ce GPU**. Ce projet
tourne sur une **RTX 3050 Laptop avec 4 096 Mo de VRAM**, partagée entre Ollama (tagging),
InsightFace (visages) et l'encodeur d'empreintes animales. Un modèle qui gagne 3 points sur un
classement mais fait déborder la VRAM dégrade *tous* les pipelines. Un modèle qui fait +0,5 %
sur LFW ne change rien : LFW est saturé, tout le monde est au-dessus de 99 %.

La règle : **aucun modèle n'entre en production sans les cinq étapes ci-dessous.**

## Étape 0 — Formuler l'hypothèse avant de mesurer

Écris, avant tout téléchargement, en une phrase : *quel défaut observé* ce modèle est censé
corriger, et *quelle métrique* le prouverait. Sans cela, l'évaluation dérive vers « le nouveau
modèle a l'air mieux ».

Exemples valides :
- « Caline et Inti tombent dans le même cluster à `PET_CLUSTER_SIM = 0.60` ; MegaDescriptor
  devrait les séparer à un seuil calibré, mesuré en pureté de cluster. »
- « Les tags varient d'une photo à l'autre pour la même scène ; un vocabulaire contrôlé
  zéro-shot devrait être déterministe, mesuré en cohérence inter-photos. »

Exemple invalide : « Qwen3-VL 4b est meilleur que 2b sur les benchmarks. » (Déjà testé et
documenté dans `modele.txt` : il déborde en RAM et est ~3× plus lent.)

## Étape 1 — Jeu de validation figé, issu du corpus réel

**Ne jamais évaluer sur des données publiques seules.** Le corpus est un fonds photo familial
sur NAS : scènes d'intérieur mal éclairées, photos de téléphone, visages de profil, trois chats
domestiques dont deux se ressemblent.

Constitue un jeu figé, **versionné dans `eval/`**, et réutilisé identique à chaque évaluation :

| Tâche | Jeu de validation minimal |
|---|---|
| Tagging | 150 photos couvrant tous les cas : intérieur/extérieur, jour/nuit, groupes, paysages, repas, animaux, documents scannés. Étiquetées à la main avec le vocabulaire cible. |
| Visages | 200 visages avec identité vraie, dont **au moins 60 « difficiles »** au sens de `_face_is_poor()` : score < 0,78 ou largeur < 90 px. C'est là que les modèles se séparent. |
| Chats | Toutes les photos où l'identité de Caline / Inti / Luna est certaine, plus 30 photos de chats tiers comme distracteurs. |
| Recherche sémantique | 30 requêtes en français écrites comme un utilisateur les formulerait, avec la liste des photos attendues. |

Le jeu difficile n'est pas optionnel : les benchmarks pertinents en 2026 pour départager les
modèles de visages sont **IJB-C** et **TinyFace** (basse résolution), pas LFW. Reproduis cette
logique localement — un modèle qui gagne seulement sur les portraits nets n'apporte rien.

## Étape 2 — Mesurer la VRAM réellement consommée

Pas la taille annoncée du modèle : l'occupation observée, **pendant l'inférence, en lot**.

```
nvidia-smi --query-gpu=memory.used,memory.total --format=csv -l 1
```

Le projet fournit déjà `Moniteur GPU.bat` et `hw_state()`. Consigne :

- pic de VRAM en inférence par lot, et non à vide ;
- VRAM restante disponible **pendant** qu'Ollama est résident (`keep_alive: "30m"` maintient le
  modèle en mémoire 30 minutes après la dernière photo) ;
- comportement en cas de manque : erreur franche, ou fuite silencieuse vers la RAM système
  (ce second cas est le pire — c'est ce qui rend `qwen3-vl:4b` ~3× plus lent).

**Critère de rejet immédiat :** si le pic dépasse le seuil que le pipeline s'accorde
(`FACE_GPU_MIN_FREE_MB = 1200`, `ANIMAL_GPU_MIN_FREE_MB = 1600`, `PET_GPU_MIN_FREE_MB = 1800`),
le modèle est rejeté ou doit être quantifié avant réévaluation.

Avant de rejeter pour cause de VRAM, teste systématiquement **ONNX Runtime en INT8** : la
quantification INT8 préservant la précision est devenue standard en 2026 côté InsightFace, et
elle divise souvent l'empreinte par 4 sans perte mesurable.

## Étape 3 — Comparer contre le pipeline en place, pas contre le vide

Le point de comparaison est **toujours** la configuration actuelle :

| Tâche | Référence en place |
|---|---|
| Tagging | `qwen3-vl:2b` via Ollama, `temperature: 0.2`, `num_ctx: 4096`, `format: json` |
| Visages | InsightFace `buffalo_l`, `FACE_DET_THRESHOLD = 0.50`, `FACE_MAX_SIDE = 1600` |
| Chats | `vit_base_patch14_dinov2.lvd142m`, `PET_CLUSTER_SIM = 0.60` |
| Détection animaux | `yolo11s.pt`, `ANIMAL_DET_THRESHOLD = 0.30` |

`compare_models.py` et `compare_report.txt` existent déjà — étends-les plutôt que de créer un
nouveau script à chaque essai.

### Métriques par tâche

**Tagging** — la justesse ne suffit pas :
- justesse des tags (précision / rappel contre les étiquettes manuelles) ;
- **cohérence** : deux photos de la même scène reçoivent-elles les mêmes tags ? C'est la
  faiblesse principale d'un VLM génératif, et la force d'un encodeur zéro-shot ;
- **taux de sortie malformée** : le code contient `_salvage_tags()` et `parse_tags()` pour
  rattraper du JSON cassé. Compte les rattrapages — un encodeur ne peut pas en produire ;
- secondes par photo, et extrapolation à la taille réelle du corpus.

**Visages** :
- pureté et complétude des clusters, séparément sur le jeu facile et le jeu difficile ;
- taux de faux appariements au seuil de production (`FACE_MATCH_SIM = 0.42`) — un faux positif
  qui écrit un tag `personne:` dans les métadonnées d'un fichier est bien plus coûteux qu'un
  faux négatif ;
- courbe justesse / seuil, pour vérifier qu'un seuil unique est même viable. S'il ne l'est
  pas, la conclusion porte sur l'**algorithme de clustering** (HDBSCAN, Chinese Whispers) et
  non sur le modèle d'embedding.

**Chats** :
- rang-1 et mAP sur le jeu figé ;
- **la paire la plus confondue explicitement** : si Caline et Inti sont le cas d'échec, la
  métrique agrégée peut progresser sans rien régler. Rapporte la matrice de confusion.

**Recherche sémantique** :
- Recall@10 sur les 30 requêtes françaises. Le modèle doit être multilingue nativement ;
  toute solution exigeant une traduction préalable des requêtes est disqualifiée.

## Étape 4 — Tester la migration, pas seulement le modèle

Un changement de modèle est une **migration de données**. Le projet a déjà l'appareillage :

- `ANIMAL_PIPELINE_VERSION` (`"yolo11s|det0.30|dinov2_base"`) et `migrate_animal_pipeline()` ;
- `rederive_pet_refs()`, `reimport_name_tags()`, `reconcile_named_tags()`.

Vérifie sur une copie avant tout déploiement :

1. Le bump de version relance bien détection et empreintes.
2. **Les noms attribués par un humain survivent.** C'est l'invariant central : les tags
   `personne:Nom` et `animal:Nom` écrits dans les métadonnées XMP représentent du travail
   humain irremplaçable. Une migration qui les perd est un échec, quel que soit le gain de
   justesse.
3. Le coût de recalcul complet est chiffré en heures, sur la vraie machine, avec le NAS.
4. Un retour arrière est possible : ancien index conservé jusqu'à validation.

## Étape 5 — Décision écrite

Consigne le résultat dans `eval/DECISIONS.md`, en une entrée par évaluation :

```markdown
## 2026-08-XX — MegaDescriptor-T vs DINOv2-base (re-ID chats)

Hypothèse : Caline/Inti confondues au seuil 0.60 ; un backbone spécialisé re-ID doit les séparer.
Jeu : eval/chats_v1 (N photos certaines + 30 distracteurs).
VRAM  : pic XXX Mo (vs YYY Mo pour DINOv2-base) — tient sous PET_GPU_MIN_FREE_MB.
Rang-1: XX % (vs YY %). Confusion Caline↔Inti : XX cas (vs YY).
Coût  : recalcul complet ≈ X h sur RTX 3050 + NAS.
Décision : adopté / rejeté / à revoir.
Raison : …
```

Une évaluation sans décision écrite ne compte pas : c'est ce qui évite de retester six mois
plus tard le modèle déjà écarté — comme `qwen3-vl:4b`, dont le rejet est heureusement
documenté dans `modele.txt`.

Si la décision est structurante (changement d'architecture, pas seulement de poids), produis un
ADR avec la skill `engineering:architecture`.

## Pièges à éviter

- **Conclure d'un classement public.** Les classements mesurent des modèles à pleine précision
  sur du matériel de datacenter. Ici la contrainte est 4 Go partagés.
- **Évaluer un modèle isolé.** Les pipelines se disputent la même VRAM ; un modèle qui gagne
  seul et ralentit les deux autres est une régression nette. Mesure toujours en charge réaliste.
- **Utiliser LFW.** Saturé. Utilise le jeu difficile local.
- **Comparer sur un échantillon différent à chaque fois.** Le jeu de validation est figé et
  versionné, sinon les mesures ne sont pas comparables entre elles.
- **Oublier le coût de recalcul.** Un modèle 5 % meilleur qui impose 40 heures de recalcul sur
  un NAS SMB peut ne pas valoir le changement.
- **Confondre modèle et clustering.** Beaucoup de défauts attribués à l'embedding viennent en
  réalité d'un seuil global unique appliqué à un corpus hétérogène. Teste l'algorithme de
  regroupement avant de changer de modèle.
