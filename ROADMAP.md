# Feuille de route

Ce fichier survit aux sessions, contrairement à une liste de tâches en mémoire.
Il est référencé par `CLAUDE.md`, donc relu au début de chaque session.

Dernière mise à jour : 31 juillet 2026.

---

## Fait, et vérifié

| # | Chantier | Preuve |
|---|---|---|
| 1 | **Migration SQLite** — `TagStore` → `SqliteStore`, écriture incrémentale | 64 676 entrées migrées et vérifiées, 42/42 tests. 48,8 Mo réécrits par `set()` → une ligne |
| 2 | **Embeddings hors JSON** — table BLOB, octets float16 préservés | 19 309 vecteurs sortis, base 58,8 → 47,2 Mo, `people` 11,5 Mo → 147 Ko |
| 3 | **Réparation GPU** — build CPU + orphelin `~orch` | `torch 2.13.0+cu130`, InsightFace sur CUDA |
| 4 | **Recherche sémantique SigLIP 2** — encodeur, index vectoriel, route, UI | 90 % de justesse au rang 1 ; recherche en 0,7 ms sur 8 730 vecteurs |
| 5 | **Recherche hybride** — noms humains + sens de l'image | 326 noms reconnus, y compris composés |
| 6 | **Vérification d'espèce** — SigLIP contre les classes COCO | 23 rejets justifiés sur 24 relus un par un |
| 7 | **Nommage généralisé** — chats → tous animaux, par espèce | `ANIMAL_NAMEABLE`, espèce déduite du groupe |
| 8 | **Attribution unifiée** — une action au lieu de boutons binaires | Sous-ensembles, noms multiples, annulation 10 s |
| 9 | **Prototypes multiples** (personnes) | 97,4 % contre 96,7 %, 0 régression |
| 10 | **Ordonnanceur + arbitre VRAM** | Tour de rôle à déficit, 16/16 tests |
| 11 | **Garde-fous de méthode** — `verifier_bat.py`, hook, journal de décisions | Règle ASCII bloquée à l'écriture |
| 12 | **MegaDescriptor rejeté, mesure valide** | À armes égales : DINOv2 97,4 % contre 94,0 %. Banc validé contre la production (97,4 % / 85,6 % vs 85,5 %) |
| 13 | **Résolution des découpes : sans effet** | 256 px 97,8 %, pleine résolution 97,4 %, 512 px 97,0 % — deux photos d'écart, du bruit |
| 14 | **Circularité du banc détectée et corrigée** | 100 % de justesse = alarme, pas succès : la vérité terrain était auto-générée |
| 15 | **Récupération d'images corrompues** | 987 fichiers inventoriés, orientation et analyse profonde corrigées |
| 16 | **Recherche à trois dimensions** — qui / où / quoi | `Luna à Bremblens en hiver` : tag humain + dossier + sens. `lieux.txt` déduit des chemins, 120 lieux |

## Prochaine étape décidée

**Le magasin de sujets commun** (point 7). C'est du code invisible, mais c'est
lui qui rend l'harmonisation possible sans tout dupliquer : `PEOPLE_STORE` et
`PETS_STORE` ont déjà la même forme, et chaque amélioration portée sur cette
abstraction vaudra automatiquement des deux côtés. Ensuite seulement la page
« Sujets » unifiée, puis le plancher d'accessibilité.

## Outillage

- **Dépôt git** — `20 - Preparer le depot git.bat` crée le dépôt local.
  `server.py` fait plus de 8 500 lignes sans aucun historique. Publication sur
  GitHub en dépôt **privé**, puis activation du connecteur dans claude.ai.
- **Figma** — utile pour le chantier UI : le design system « chambre noire »
  existe en prototype (`ui/prototype.html`) et les skills Figma savent le
  pousser en bibliothèque de composants.
- Les connecteurs se connectent dans les réglages de claude.ai (section
  Connecteurs), par OAuth. Aucun ne peut être autorisé depuis une session
  Claude Code.

## En cours

- **Encodage sémantique du fonds** — 29 549 photos encodées sur 30 682
  (96 %). Terminé pour l'essentiel.
- **Seconde passe de récupération** — les 945 fichiers à en-tête détruit n'ont
  jamais reçu la recherche de flux JPEG. Relancer
  `17 - Recuperer les images illisibles.bat`.
- **Remettre `recuperees/` sur le NAS** — ces images sont hors photothèque,
  donc ni taguées ni analysées.

## À faire, par ordre de valeur

### Reconnaissance

1. **Étoffer la vérité terrain humaine** — 91 photos confirmées sur 12 072
   taguées (0,8 %). Le banc de classification rejoué à l'échelle réelle a
   rendu 100 % : la mesure était devenue circulaire, l'auto-attribution ayant
   posé presque tous les tags. Corrigé (le jeu se limite aux confirmations
   humaines), mais 23 visages ne permettent pas de trancher. **Confirmer une
   centaine de propositions dans l'interface vaudrait plus que n'importe quel
   changement d'algorithme.**
2. **Regroupement par densité** (HDBSCAN, Chinese Whispers) à la place du
   seuil global unique. Un seuil ne peut pas servir à la fois des portraits
   nets et des profils de 90 px.
3. **AdaFace** sur le chemin de ré-embedding des visages faibles.
4. **Écrire les tags SigLIP** — aujourd'hui seulement proposés
   (`semantic.py --tags`). Décision à prendre : ils modifieraient les XMP.
5. **Comparer `qwen3-vl:2b` à SigLIP** sur le même échantillon annoté.
6. *(facultatif)* `MegaDescriptor-DINOv2-518` — dernière variante non testée.
   Peu d'espoir vu l'écart, mais `--equitable --modeles DINOv2-518` suffit.

> **La reconnaissance animale est à un bon point d'arrêt.** 97,4 % de rang-1,
> sept erreurs dont six sur la seule paire Inti/Luna — deux chats qui se
> ressemblent vraiment. Ni le modèle ni la résolution n'y changent rien : le
> gain restant est dans la donnée, pas dans l'algorithme.

### Harmonisation personnes / animaux / lieux

Le principe : **tout outil créé d'un côté doit servir de l'autre.** Les deux
pipelines résolvent le même problème — regrouper, nommer, corriger — et n'ont
divergé que par accident d'écriture.

| Capacité | Animaux | Personnes | À faire |
|---|---|---|---|
| Attribution unifiée (sous-ensemble, noms multiples, annulation) | oui | partiel | porter la sélection par vignette et les noms multiples côté visages |
| Vérification par SigLIP (« ce n'est pas un chat ») | oui | non | équivalent visages : rejeter un non-visage (statue, affiche, reflet) |
| Curateur avec suggestions et auto-attribution | non | oui | porter côté animaux : proposer des rattachements au lieu d'attendre un regroupement |
| « Trouver d'autres photos de X » | oui | oui | unifier le code, aujourd'hui dupliqué |
| Prototypes multiples | non (mesuré défavorable) | oui | rien à faire, décidé sur mesure |
| Fiche avec avatar, exclusions, confirmations | partiel | oui | même structure des deux côtés |

7. **Un magasin de sujets commun** — `PEOPLE_STORE` et `PETS_STORE` ont la
   même forme (nom, refs, faces, exclude, confirmed). Les unifier derrière une
   seule abstraction supprime la duplication et rend chaque amélioration
   automatiquement valable des deux côtés.
8. **Une seule page « Sujets »** au lieu de Personnes et Animaux séparées :
   même gestes, filtre par type. Le lieu devient une troisième facette.

### Interface

9. **Extraction des 7 pages HTML** vers `ui/` + design system « chambre noire »
   (`ui/prototype.html`, skill `photo-ui`).
10. **Plancher d'accessibilité** — focus clavier, contraste AA, cibles 44 px,
    `prefers-reduced-motion`. Aucun de ces points n'est satisfait aujourd'hui.
11. **Planche contact justifiée** + View Transitions + `content-visibility`.
12. **Raccourcis clavier** dans les tâches de tri répétitives.

### Recherche

13. **Adapter l'encodage au matériel en temps réel** — `_device_cible()` décide
    déjà GPU/CPU selon la VRAM libre, mais la taille de lot, la précision et
    la résolution d'entrée restent fixes. Les rendre fonction de
    `hw_state()` : gros lots quand la carte est libre, repli progressif sinon.
14. **Carte et lieux dans la recherche** — les 684 photos géolocalisées
    devraient enrichir `lieux.txt` par géocodage inverse, et la page Carte
    partager le même vocabulaire que la barre de recherche.

### Données

15. **Fiche « Flo »** — 3 478 photos, 80 références, 17 exclusions. Fiche
    probablement mal constituée : c'est elle qui rend Florine ambiguë.
16. **Doublons de fiches** entre personnes et animaux.

---

## Décisions documentées

Toute évaluation aboutit à une entrée dans `eval/DECISIONS.md`. Quatre idées y
ont été **rejetées sur mesure** : les contre-exemples pour la classification,
les prototypes multiples pour les animaux, **MegaDescriptor** (deux fois :
une mesure invalide, puis une mesure valide), la **résolution des découpes**,
et `sqlite-vec`
(numpy exhaustif suffit, 10 ms sur 100 000 vecteurs).

Rejeter une idée sur mesure vaut autant qu'en adopter une : c'est ce qui évite
de la retester dans six mois. **Encore faut-il que la mesure soit valide** :
deux entrées du journal documentent des bancs d'essai qui ne mesuraient pas ce
qu'ils prétendaient — l'un circulaire, l'autre inéquitable.
