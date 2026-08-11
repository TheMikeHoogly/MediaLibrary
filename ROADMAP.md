# Feuille de route — MediaLibrary

L'état vit dans les fichiers, pas dans l'historique. Ce fichier = **carte des
priorités**. Détail ailleurs : `eval/DECISIONS.md` (décisions tranchées),
`docs/RANGEMENT_2026.md` (rangement), `docs/AUDIT_EXTERNE_2026.md` (direction
tagging), `PROMPT_NOUVELLE_SESSION.md` (reprise), et l'historique git (chaque
chantier fini y est — c'est pourquoi les récits de travaux terminés ne vivent PAS ici).

## État actuel (11 août 2026)

**Sessions 11/08 matin + après-midi : commitées et fusionnées** (tout vérifié en réel,
détail dans git) : Lieux (25, 0,8 s) ; fixes clusters ; perf `/sujets` (>45 s → 0,8 s) ;
page `/files?q=` ; fix racine faux positifs confirmé (rebuild curateur → 0 carte) ;
**fusion `/sujets`** (entrée unique de la nav) ; passe DESIGN PEOPLE+PETS ; fix bandeau
timm `/pets` (fausse alerte : `timm` présent, chargement paresseux — mention neutre
« en veille », actif au prochain redémarrage).

**Session 11/08 (soir)** — deux volets, **livrés mais PAS vérifiés en réel** (redémarrage en
attente) ni commités :
1. **Recherche sur la Carte** (ROADMAP #5) : champ « Rechercher (noms, lieux, sens)… » sur
   `/map`, même vocabulaire hybride que la galerie (`/api/search`, plafond `n` aligné à 1500) ;
   le filtre recompose marqueurs/compteur et **se compose avec la zone et le diaporama**
   (jointure par `url`, commune à `/api/geo` et `/api/search`). Placeholder d'accueil aligné.
2. **Passe DESIGN terminée sur les 5 pages restantes** (MAP/GALLERY/HTML/BROWSE/FACES,
   mêmes mappings que PEOPLE/PETS) + divergences tranchées (chips galerie alignés sur le
   canon `min-height:32px` ; les 6 `outline:none` restants purgés — plancher `base.css`).
   Lint tokens : 0 interdit, 0 avertissement sur les 11 constantes.
3. **Éval INT8 (vision-eval) : REJETÉ** — cf. `eval/DECISIONS.md` + `eval/eval_int8_vectors.py`
   (mesure sur copie réelle, 130 576 vecteurs ; la base est déjà en f16 et locale ; recall@10
   sémantique 0,9685 réfute « sans perte »).

## État antérieur (10 août 2026) — commité, détail dans git

Refonte `/people` + outillage **faux positifs** ; tokenisation value-preserving 7 pages ;
**`exclude` fait autorité partout** + auto-guérison `🩹` ; le ré-embedding saute les photos
jugées par un humain (⚠ geste Mike : re-rejeter le groupe Caline une fois) ; Lieux = 3ᵉ type
d'entité.

- **Git** : tout est commité/fusionné jusqu'à l'après-midi du 11/08 ; **reste à commiter la
  session du soir** (après vérif) — `27 - Commit de session.bat` ; **`git push` = geste de Mike**.
- **Ouvert (gestes Mike)** :
  - **Nettoyer Flo** : la fiche reste polluée tant qu'un passage n'est pas fait. Ouvrir Flo →
    « Corriger » (seuil ~0.2, monter en surveillant la grille) ou « Nettoyer (référence) »
    pour une séparation fine. Retrait **sûr** (cf. Acquis « exclude »).
  - Toujours en attente : appliquer les lots de renommage + activer `gps_place` (cf. « À faire »).

## Acquis — ne pas reproposer (détail : git + `DECISIONS.md`)

| Domaine | Acquis |
|---|---|
| Stockage | SQLite (64 676 entrées), embeddings BLOB, `photos.db` local WAL, backup NAS snapshot |
| Reconnaissance | SigLIP 2 (sémantique 90 % r1) ; animaux 97,4 % r1 ; prototypes multiples (personnes) ; vérif d'espèce |
| Nommage | Attribution unifiée (sous-ensemble, multi-noms, annulation 10 s) personnes+animaux ; rejets réversibles ; **archive « Inconnus »** ; **reclassement `personne:`→`animal:` réversible** (journal undo ; Mutz+Caline faits) |
| Fichiers | `/browse` (renommer/déplacer/supprimer réversible) ; upload dossiers ; fix SMB Errno 22 ; `rekey_everywhere` ; purge orphelins/fantômes |
| Rangement | Dédoublonnage contenu appliqué (8,4 Go) ; rangement par année appliqué ; orchestrateur de maintenance |
| Renommage | Cœur + plan + applicateur réversibles prêts (plan = 2114) ; géocodage inverse `gps_place` codé |
| UI | Design system « chambre noire » (tokens, plancher a11y, `verifier_ui_tokens`) ; planche contact ; tri clavier ; `/reglages` tour de contrôle ; **`/people` réorganisé (10/08)** : personnes identifiées + panneau de correction EN TÊTE, files de travail dessous → fin du saut de scroll ; **filtre par nom** ; **indicateur d'activité réseau global** (spinner « Traitement… », enrobage `fetch` dans la nav partagée, 7 pages) |
| Correction | **Faux positifs (10/08)** : « Corriger » + « Nettoyer (référence) » (retrait de masse piloté par les données, seuil ajustable). Retrait **SÛR** (`untag`→`exclude`) ; **`exclude` fait autorité PARTOUT** + auto-guérison des tags resurgis (détail : git) |
| Perf | **Scoring vectorisé (10/08)** : matmul unique + `media_roots()` calculé 1× → re-score 6338 photos **156 s → quelques s** ; `SubjectStore.photos()` mode `light` (détail : git) |
| Tagging | `qwen3-vl:2b` ; hybride assertions+image ; 1 lecture exiftool/photo |
| GPU | torch CUDA `2.13.0+cu130` + `onnxruntime_gpu` ; `FACE_USE_GPU=False` volontaire (4 Go pris par Ollama) |
| Hygiène | Nettoyage de session **réversible** (`_corbeille_session/` + lint `*.md`, `29 - …bat`), au protocole de `CLAUDE.md` |

## À faire — par ordre de valeur

1. **Vérité terrain humaine (priorité n°1).** ~0,8 % de confirmations humaines (91/12 072).
   Confirmer ~100 propositions dans `/people` vaut plus que tout changement d'algo. Tri
   clavier prêt (Espace=oui, X=non, Z=annuler, lettre=corriger). `/people` réorganisé +
   filtre par nom (10/08) → la revue en volume est désormais directe et confortable.
2. **Appliquer les lots de renommage** (`/reglages` → Renommage, plan = 2114, lots de 200
   réversibles) + **activer le géocodage `gps_place`** : lancer `18 - …gazetteer.bat`, puis
   `enrichir_lieux.py` (aperçu) puis `--ecrire`, puis redémarrer. Gestes Mike.
3. **Cross-pipeline (Mutz/Caline)** — outil de reclassement `personne:`→`animal:` **livré**
   (Mutz+Caline faits, réversible). Fix **auto** amont humain/animal **REJETÉ** (18 % faux
   rejets, cf. DECISIONS) ; seule piste restante = re-mesurer sur découpes SANS marge avant
   d'y revenir. Relancer l'outil quand un nouveau nom d'animal se retrouve en `personne:`.
4. **Page « Sujets » unifiée — TERMINÉE (11/08).** Les 3 tranches livrées et vérifiées en
   réel : surcouche lecture seule (10/08), Lieux 3ᵉ type d'entité (10–11/08), **fusion**
   (11/08 : `/sujets` entrée unique de la nav, `/people`+`/pets` vues spécialisées,
   rangée « Files de travail »). Plus rien à faire ici.
5. **Recherche — livrée, à VÉRIFIER en réel (11/08 soir).** Vocabulaire hybride (noms + lieux
   + sens) partagé à la page Carte ; « les étés à Bremblens avec Luna » couvert par
   `semantic_search`. Reste après vérif : rien de cadré.
6. **Reconnaissance — algo.** Clustering par densité (HDBSCAN / Chinese Whispers) au lieu
   d'un seuil global unique ; AdaFace sur le ré-embedding des visages faibles ; écrire les
   tags SigLIP (aujourd'hui proposés — décision à prendre car modifie les XMP).
7. **Perf / archi.** `GpuArbiter` unique (baux + priorités UI > tagging > visages > chats)
   remplaçant les 4 politiques `*_GPU_MIN_FREE_MB` séparées — session dédiée.
   *(INT8 des embeddings : REJETÉ le 11/08, cf. `DECISIONS.md` — ne pas reproposer.)*
8. **Extraire les 7 pages HTML → `ui/` + `tokens.css`** (sans build step). **Value-preserving :
   FAIT sur les 7 pages** (commité, vérifié en réel) — les espacements/rayons/tailles qui
   **égalent déjà un token** pointent vers lui (12px→`--e-3`, 999px→`--r-pill`, 0.85rem→`--t-sm`,
   6px→`--r-md`…), prouvé identique (résolution tokens + diff = zéro écart ; `getComputedStyle`).
   Non tokenisé : positions/tailles, font-sizes **px** (≠ rem), valeurs hors échelle ; `#4A8C7B`
   Leaflet reste en dur (API refuse `var()`). Divergences nommées tranchées : GALLERY `.pchip`/
   `.chip` fusionnés ; PEOPLE `#222`→`--salle-3`, `#f0a35b`→`--veilleuse`.
   - **Passe DESIGN : FAITE sur les 7 pages** — PEOPLE+PETS (11/08 après-midi, vérifiée en
     réel), MAP/GALLERY/HTML/BROWSE/FACES (11/08 soir, **à vérifier au redémarrage**).
     Fonds photo #000 et overlays translucides conservés (tolérés, hors palette).
   - **Reste** : extraction physique vers `ui/` (via `bundle.py`) — tokens déjà tous référencés.
9. **Éval tagging (parké, déjà cadré).** Mesurer V2 « assertions en contexte, sans
   impératif de noms » (~4,3 s, jamais notée) + fusion programmatique des noms/date/lieu
   (Knowledge Builder). Cf. `docs/AUDIT_EXTERNE_2026.md` + `eval/PLAN_assertions_vs_pixels.md`.
10. **Données / finitions.** **Flo** : outillage de nettoyage livré (10/08) ; le passage
    lui-même = geste Mike (Corriger / Nettoyer référence). Édition des réglages depuis
    `/reglages` (aujourd'hui lecture seule) ; 2ᵉ passe de récupération des 945 illisibles +
    remettre `recuperees/` sur NAS. *(Doublon de fiche Caline : réglé le 9/08.)*
11. **À évaluer (mesurer avant d'adopter, discipline `vision-eval`).** Florence-2
    (caption + detection + OCR) comme candidat léger.

### Résiduels faible valeur (ne pas prioriser)
- `/reglages` : bouton **Pause globale** des workers (aujourd'hui : pause maintenance seule) ;
  retrait de l'ancien bandeau `#pending` (l'état vit maintenant dans `/reglages`).

## En réserve — futur, non prioritaire

Multi-utilisateur (owner par racine, comptes/droits ; décidé « plus tard »).
Multimodalité images → **vidéo** → **audio**, puis **recherche AI en langage naturel** et
**exposer le serveur en MCP** (`mcp-builder`). Bibliothèque Figma comme source des composants.

## Méthode

1. **Un score parfait est une alarme** — deux bancs ne mesuraient pas ce qu'ils prétendaient.
2. **Une correction n'est acquise qu'une fois son effet observé en réel** — un proxy n'est
   pas le juge.

Idées déjà **rejetées sur mesure** (ne pas reproposer) : contre-exemples de classification,
prototypes multiples pour animaux, MegaDescriptor (2×), résolution des découpes, `sqlite-vec`,
injection des noms au prompt, détecteur ML de triage, garde amont humain/animal. Détail
chiffré : `eval/DECISIONS.md`.
