# Feuille de route — MediaLibrary

L'état vit dans les fichiers, pas dans l'historique. Ce fichier = **carte des
priorités**. Détail : `eval/DECISIONS.md`, `docs/AUDIT_INTERNE_2026-08.md`
(I1–I17, O1–O15, A–F), `docs/RANGEMENT_2026.md`, `docs/AUDIT_EXTERNE_2026.md`,
`PROMPT_NOUVELLE_SESSION.md` (reprise), et git (les récits de travaux terminés
ne vivent PAS ici).

## État actuel (12 août 2026)

**Session 12/08 (5) — audit O6 : LIVRÉE, À COMMITER (bat 27) + redémarrer.**
`SEMANTIC_LOCK` n'est plus tenu sur le lot entier (16 photos, 10–30 s) mais par
**sous-lot de 4** (`SEMANTIC_SUBBATCH`) : une recherche s'intercale entre deux
sous-lots. Si `ui_recent()` entre deux sous-lots → arrêt du lot (vecteurs déjà
produits conservés) ; seules les clés **tentées** peuvent rejoindre
`SEMANTIC_SKIP` (un lot interrompu n'écarte pas des photos jamais essayées).
Vérifs : py_compile + simulation isolée des 3 scénarios (complet / interrompu /
dernier sous-lot). **Effet à observer en réel après redémarrage** (réflexe n°2).

**Session 12/08 (4) — files « À vérifier » sous Classification + file ANIMAUX
en miroir : COMMITÉE (`daa9cbc`, branche `feat/verification-classification`),
serveur redémarré. VÉRIF PARTIELLE (programmatique, via Chrome)** : les deux
files s'affichent (Personnes 18, Animaux 120), `/api/pets/curator/list` 200,
~500 découpes 0 cassée. Contenu (détail : git) : jugement dans
`/sujets?vue=classification` (clavier unifié Espace/X/Z/lettre, même
journal/compteur), `build_cat_suggestions()`, `CAT_AUTO_LOG` annulable ;
3 correctifs adversariaux ((a) `par_humain` animaux annulable, (b) garde
anti-course `_note_juge` sur les 2 files, (c) clés fantômes) + verrou « une
carte ne se juge qu'une fois ». **Restent (gestes Mike)** : jugement clavier,
test du Z (la carte revient), vérité terrain (~100 confirmations).

**Session 12/08 (3) — audit I1 I2 O1–O5 O10 + assurance-vie + Sujets guichet
unique : COMMITÉE (`e17ac2d`), VÉRIF QUASI COMPLÈTE** (12/08 : `/api/thumb` clé
réelle → 200 JPEG 52 Ko vs original 4,7 Mo ; Range → 206 correct, seek prouvé
côté serveur). Contenu (détail : git) : vignettes + streaming + caches + locks ;
`backup_verify()` + `export_jugements()` à chaque backup horaire ; sous-nav
Sujets + onglet Classification. **Restent** : seek vidéo mobile ressenti,
carte « Sauvegarde vérifiée : ok » au 1er backup horaire (affichait « jamais »
juste après redémarrage, normal).

**Sessions antérieures (10–12/08) — commitées, vérifiées en réel, détail dans
git** : instrumentation vérité terrain + fix « Gérer » (12/08, 1–2) ; GpuArbiter
27/27 + triple audit → `docs/AUDIT_INTERNE_2026-08.md` (11/08 nuit) ; Lieux,
perf `/sujets` >45 s → 0,8 s, `/files?q=`, fusion `/sujets`, passes DESIGN,
recherche Carte, éval INT8 rejetée (11/08) ; refonte `/people` + outillage faux
positifs, `exclude` autorité partout, Lieux 3ᵉ entité (10/08 — ⚠ geste Mike
restant : re-rejeter le groupe Caline une fois).

- **Git** : commité jusqu'à `daa9cbc` (branche `feat/verification-classification`) ;
  **reste à commiter la session (5) — O6** — `27 - Commit de session.bat` ;
  **`git push` / merge dans `main` = gestes de Mike**.
- **Ouvert (gestes Mike)** :
  - **Commiter O6 (bat 27) puis redémarrer** ; ensuite, pendant l'encodage
    (`/reglages` : « encodage de N photo(s) »), une recherche doit répondre
    en ~1 s au lieu d'attendre la fin du lot.
  - **Vérifier au clavier la session (4)** dans `/sujets?vue=classification` :
    les deux files se jugent (Espace/X/Z/lettre) ; annuler (Z) une acceptation
    d'animal doit **faire revenir la carte** après rafraîchissement
    (correctif (a)).
  - **Session (3), restes** : seek vidéo mobile ressenti ; après le prochain
    backup horaire, carte « Sauvegarde vérifiée » = ok dans /reglages
    (⚠ jamais observée sur Windows : l'URI UNC doit être vue passer UNE fois
    — réflexe n°2).
  - **Nettoyer Flo** : ouvrir Flo → « Corriger » (seuil ~0.2) ou « Nettoyer
    (référence) ». Retrait **sûr** (cf. Acquis « exclude »).
  - Toujours en attente : lots de renommage (après éval V2) + activer `gps_place`
    (I2+O10 faits — plus de préalable technique, vérif en réel d'abord).

## Acquis — ne pas reproposer (détail : git + `DECISIONS.md`)

| Domaine | Acquis |
|---|---|
| Stockage | SQLite (64 676 entrées), embeddings BLOB, `photos.db` local WAL, backup NAS snapshot |
| Reconnaissance | SigLIP 2 (sémantique 90 % r1) ; animaux 97,4 % r1 ; prototypes multiples (personnes) ; vérif d'espèce |
| Nommage | Attribution unifiée (sous-ensemble, multi-noms, annulation 10 s) personnes+animaux ; rejets réversibles ; **archive « Inconnus »** ; **reclassement `personne:`→`animal:` réversible** (journal undo ; Mutz+Caline faits) |
| Fichiers | `/browse` (renommer/déplacer/supprimer réversible) ; upload dossiers ; fix SMB Errno 22 ; `rekey_everywhere` ; purge orphelins/fantômes |
| Rangement | Dédoublonnage contenu appliqué (8,4 Go) ; rangement par année appliqué ; orchestrateur de maintenance |
| Renommage | Cœur + plan + applicateur réversibles prêts (plan = 2114) ; géocodage inverse `gps_place` codé |
| UI | Design system « chambre noire » (tokens, plancher a11y, `verifier_ui_tokens`) ; planche contact ; tri clavier ; `/reglages` tour de contrôle ; `/people` réorganisé (10/08, fiches+correction en tête, filtre par nom) ; indicateur d'activité réseau global (7 pages) |
| Correction | **Faux positifs (10/08)** : « Corriger » + « Nettoyer (référence) » (retrait de masse piloté par les données, seuil ajustable). Retrait **SÛR** (`untag`→`exclude`) ; **`exclude` fait autorité PARTOUT** + auto-guérison des tags resurgis (détail : git) |
| Perf | **Scoring vectorisé (10/08)** : matmul unique + `media_roots()` calculé 1× → re-score 6338 photos **156 s → quelques s** ; `SubjectStore.photos()` mode `light` (détail : git) |
| Tagging | `qwen3-vl:2b` ; hybride assertions+image ; 1 lecture exiftool/photo |
| GPU | torch CUDA `2.13.0+cu130` + `onnxruntime_gpu` ; `FACE_USE_GPU=False` volontaire (4 Go pris par Ollama) |
| Hygiène | Nettoyage de session **réversible** (`_corbeille_session/` + lint `*.md`, `29 - …bat`) ; **commit guidé** : `SESSION_COMMIT.txt` (branche+titre proposés par le bat 27) — protocole `CLAUDE.md` |
| Perf serveur | **(12/08)** `/api/thumb` (vignettes 512/1600, −98 % octets NAS), `_send_file` Range+streaming, cache `media_roots`, index `ix_vectors_k`, écritures vecteurs sous lock, workers sous ordonnanceur ; **O6** : encodage sémantique en sous-lots de 4, verrou rendu entre deux (la recherche ne bloque plus) |
| Robustesse | **(12/08)** `backup_verify` (restauration à blanc + comptage jugements) + export `journal_jugements.jsonl` → NAS ; boucle maintenance blindée ; gps_places suit rekey/forget |
| Sujets | **(12/08)** Sous-nav partagée (Annuaire · Personnes · Animaux · Classification) + onglet **Classification** (compteurs vivants, liens profonds ancrés vers /people et /pets) |
| Vérification | **(12/08, session 4)** Les files « À vérifier » vivent DANS Classification, personnes **et animaux** (miroir : mêmes cartes, même clavier, même journal/compteur de séance). Curateur animaux = `build_cat_suggestions()` (zone d'incertitude entre `PET_MATCH_SIM` et `CAT_AUTO_SIM`/`CAT_AUTO_MARGIN`, tri par marge), bande « ajoutés automatiquement » annulable. Garde anti-course `_note_juge` sur les 2 files ; `par_humain` (animaux) annulable ; une carte ne se juge qu'une fois |

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine (priorité n°1).** ~0,8 % de confirmations (91/12 072).
   Instrumentation LIVRÉE (sessions 12/08 1–4). Reste le **geste Mike** :
   confirmer ~100 propositions dans `/sujets?vue=classification` ; métrique =
   confirmations/minute et erreurs découvertes, pas l'accord modèle-humain.
2. **`/sujets` guichet unique — LIVRÉ (12/08, sessions 3–4).** Reste (si le
   besoin se confirme à l'usage) : y amener aussi groupes à nommer / inconnus
   (aujourd'hui : cartes qui routent vers les ancres de /people et /pets).
3. ~~Assurance-vie de la vérité terrain~~ **LIVRÉE (12/08)** — reste la vérif
   en réel (« Sauvegarde vérifiée : ok » observée une fois dans /reglages).
4. **Éval tagging V2 — AVANT les lots de renommage** (le jeu figé de 150 photos est keyé
   par chemin ; renommer d'abord invaliderait le banc — mode de panne déjà documenté).
   Protocole prêt : `eval/PLAN_assertions_vs_pixels.md`. Si V2 confirme → **câbler le
   Knowledge Builder** (ADOPTÉ le 31/07, jamais câblé) + créer la **version de pipeline
   tagging** manquante (audit D).
5. **Gestes Mike, dans cet ordre** : nettoyer Flo (outillage livré) ; activer
   `gps_place` (I2+O10 faits ; `18 - …gazetteer.bat` → `enrichir_lieux.py` →
   `--ecrire` → redémarrer) ; **après l'éval V2** : lots de renommage (plan = 2114).
6. **Correctifs d'audit — I1, I2, O1–O6, O10 FAITS (12/08).** Restent (détail :
   `docs/AUDIT_INTERNE_2026-08.md`) : I4–I8, O7–O9, O11–O15 (dont purge de
   `photo_thumbs/` avec O15 — le cache vignettes croît sans borne). Résidu O1
   repéré (12/08) : la section **Lieux** de `/sujets` charge 25 originaux
   `/media/…` (pas `/api/thumb` — items sans `key` côté client ?) — petit, à
   confirmer puis corriger.
7. **Navigation par similarité** : `/api/similar?key=` (cosinus sur `photo_vectors()`
   existant, bouton « semblables » dans la visionneuse) ; puis **doublons proches bridés**
   (>0,98 + même journée → quarantaine réversible, 50 paires jugées par Mike avant tout
   geste) ; rangée « même jour, autres années » en galerie (requête date, zéro IA).
8. **Extraction `ui/` — décision nette à prendre** : session dédiée `bundle.py` ou parcage
   explicite (item zombie depuis plusieurs sessions ; tout le préparatoire est fait et
   vérifié, détail dans git).
9. **Cross-pipeline (Mutz/Caline)** — outil livré, réversible. Fix auto REJETÉ (18 % faux
   rejets) ; seule piste restante : re-mesurer sur découpes SANS marge. Relancer l'outil
   si un nouveau nom d'animal apparaît en `personne:`.
10. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).** HDBSCAN/Chinese
   Whispers/AdaFace inévaluables (étalon circulaire à 0,8 %) ; écrire les tags
   SigLIP = mutation XMP, exige la version de pipeline tagging (point 4).
11. **Données / finitions.** Édition des réglages depuis `/reglages` ; 2ᵉ passe des 945
    illisibles + remettre `recuperees/` sur NAS ; `docs/journaux/` gitignoré + purge des
    undo appliqués > 30 j (I12).
12. **À évaluer (discipline `vision-eval`).** Florence-2 (caption+detection+OCR) léger.

### Résiduels faible valeur (ne pas prioriser)
- `/reglages` : bouton Pause globale des workers ; retrait de l'ancien bandeau `#pending`.
- `/pets` : « empreintes calculées » = compteur depuis le démarrage, affiche 0 après
  redémarrage — libellé à préciser un jour.

## En réserve — futur, non prioritaire

Multi-utilisateur (« plus tard ») ; multimodalité vidéo → audio ; recherche AI en
langage naturel ; serveur exposé en MCP (prérequis : Knowledge Builder) ;
bibliothèque Figma. **Vision (audit 11/08)** : mémoire familiale **à
provenance** — deux tests : « PC mort lundi, tout revit vendredi » et « aucun
fait affirmé sans provenance ». Récits LLM auto : écartés (hallucination).

## Méthode

1. **Un score parfait est une alarme** — deux bancs ne mesuraient pas ce qu'ils prétendaient.
2. **Une correction n'est acquise qu'une fois son effet observé en réel** — un proxy n'est
   pas le juge.

Idées déjà rejetées sur mesure : ne rien reproposer sans relire `eval/DECISIONS.md`.
