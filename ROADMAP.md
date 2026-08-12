# Feuille de route — MediaLibrary

L'état vit dans les fichiers, pas dans l'historique. Ce fichier = **carte des
priorités**. Détail ailleurs : `eval/DECISIONS.md` (décisions tranchées),
`docs/AUDIT_INTERNE_2026-08.md` (triple audit 11/08 : incohérences I1–I17,
optimisations O1–O15, angles morts A–F), `docs/RANGEMENT_2026.md`,
`docs/AUDIT_EXTERNE_2026.md`, `PROMPT_NOUVELLE_SESSION.md` (reprise), et git
(chaque chantier fini y est — les récits de travaux terminés ne vivent PAS ici).

## État actuel (12 août 2026)

**Session 12/08 — instrumentation vérité terrain : COMMITÉE (`a9a7d8b` + fix purge
`15e3204`), VÉRIFIÉE EN RÉEL.** File triée par marge (jamais le score absolu) ; chaque
geste → ligne append-only `journal_jugements.jsonl` (gitignoré) ; compteur de séance
dans /people. Détail dans git.

**Session 12/08 (suite) — régression « Gérer » : DEUX causes, corrigées.** (1) `#panel`
placé APRÈS la grille peinte par lots → cible de scroll mouvante, panneau ouvert hors
écran ; fix : `#panel` AVANT la grille + `scroll-margin-top` — **commité, VÉRIFIÉ EN
RÉEL** (clic profond → panneau visible en haut). (2) `curMark()` (instrumentation 12/08)
scrollait vers la file « À vérifier » au chargement, déclenchant une cascade de lots qui
échouait la vue au milieu de la grille (lien profond `?name=` caché) ; fix : scroll
seulement au tri clavier — **à commiter (bat 27) + redémarrer, vérif ensuite.**

**Session 11/08 (nuit) — GpuArbiter : COMMITÉ (`72d1946`), vérifié en réel.** Les 5
politiques GPU sous baux/priorités/éviction, tests 27/27 (`test_ordonnanceur.py`) ;
détail dans git. **Triple audit mené dans la foulée** → `docs/AUDIT_INTERNE_2026-08.md`.

**Sessions 11/08 matin + après-midi : commitées et fusionnées** (tout vérifié en réel,
détail dans git) : Lieux (25, 0,8 s) ; fixes clusters ; perf `/sujets` (>45 s → 0,8 s) ;
page `/files?q=` ; fix racine faux positifs confirmé (rebuild curateur → 0 carte) ;
**fusion `/sujets`** (entrée unique de la nav) ; passe DESIGN PEOPLE+PETS ; fix bandeau
timm `/pets` (fausse alerte : `timm` présent, chargement paresseux — mention neutre
« en veille », actif au prochain redémarrage).

**Session 11/08 (soir) : commitée (`ea4aa00`), vérifiée en réel** — recherche sur la Carte
(vocabulaire hybride partagé, composition zone×recherche×diaporama vérifiée ; « Bremblens »
→ 0 marqueur = normal tant que `gps_place` n'est pas activé) ; passe DESIGN des 5 pages
restantes vérifiée (tokens résolus, chips 32px, plancher focus-visible) ; éval INT8 REJETÉE
(cf. `eval/DECISIONS.md`). Détail dans git.

## État antérieur (10 août 2026) — commité, détail dans git

Refonte `/people` + outillage **faux positifs** ; tokenisation value-preserving 7 pages ;
**`exclude` fait autorité partout** + auto-guérison `🩹` ; le ré-embedding saute les photos
jugées par un humain (⚠ geste Mike : re-rejeter le groupe Caline une fois) ; Lieux = 3ᵉ type
d'entité.

- **Git** : tout est commité jusqu'à `15e3204` (branche `feat/verite-terrain-marge`) ;
  **reste à commiter le fix « Gérer »** — `27 - Commit de session.bat` ;
  **`git push` / merge dans `main` = gestes de Mike**.
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
| Hygiène | Nettoyage de session **réversible** (`_corbeille_session/` + lint `*.md`, `29 - …bat`) ; **commit guidé** : `SESSION_COMMIT.txt` (branche+titre proposés par le bat 27) — protocole `CLAUDE.md` |

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine (priorité n°1).** ~0,8 % de confirmations (91/12 072).
   L'instrumentation est LIVRÉE (12/08 : file par marge, journal des jugements, compteur
   de séance — cf. État actuel). Reste le **geste Mike** : confirmer ~100 propositions
   dans `/people` (tri clavier + filtre par nom prêts) ; la métrique qui compte =
   confirmations/minute et erreurs découvertes, pas l'accord modèle-humain.
2. **`/sujets` guichet unique.** La régression « Gérer » est corrigée (cf. État actuel ;
   vérif en réel après redémarrage). Reste : aller au bout de la fusion — **toutes** les
   fonctions de gestion d'une personne, d'un animal ou d'un lieu réunies dans `/sujets`,
   + un onglet **« Classification »** (groupes à nommer, faux positifs, …) séparant
   clairement personnes / animaux / lieux. (Skills : `photo-ui`, `monolith-surgery`.)
3. **Assurance-vie de la vérité terrain (angle mort majeur — audit A).** Les jugements
   humains ne vivent que dans `photos.db`, snapshot jamais restauré ni vérifié, même site.
   → Tâche `backup_verify` (integrity_check + restauration à blanc + comptage confirmed/
   exclude) + **export JSONL append-only** des jugements sur NAS (copiable hors site).
4. **Éval tagging V2 — AVANT les lots de renommage** (le jeu figé de 150 photos est keyé
   par chemin ; renommer d'abord invaliderait le banc — mode de panne déjà documenté).
   Protocole prêt : `eval/PLAN_assertions_vs_pixels.md`. Si V2 confirme → **câbler le
   Knowledge Builder** (ADOPTÉ le 31/07, jamais câblé) + créer la **version de pipeline
   tagging** manquante (audit D).
5. **Gestes Mike, dans cet ordre** : nettoyer Flo (outillage livré) ; **après I2+O10**
   (re-clé `gps_places.json` + index `vectors(k)` — sinon libellés orphelins et scans
   ×850 k lignes/lot) : activer `gps_place` (`18 - …gazetteer.bat` → `enrichir_lieux.py`
   → `--ecrire` → redémarrer) ; **après l'éval V2** : lots de renommage (plan = 2114).
6. **Correctifs d'audit** (détail : `docs/AUDIT_INTERNE_2026-08.md`). Prioritaires :
   I1 (workers visages/animaux hors ordonnanceur — la promesse « un seul travail lourd »
   ne les couvre pas), I2+O10 (prérequis du point 5), O1 (`/api/thumb` : vignettes de
   grille = originaux pleine résolution, −98 % d'octets NAS, meilleur ratio du lot),
   O2 (`_send_file` : Range + streaming), O3 (cache `media_roots`), O4 (écritures vectors
   sous `STORE.lock`), O5 (try/except `maintenance_loop` — un crash silencieux tue scan
   ET backup), O6 (recherche bloquée par le lot d'encodage). Puis I5–I8, O7–O13.
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
10. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).** HDBSCAN/Chinese Whispers
   inévaluables aujourd'hui (étalon circulaire à 0,8 %) ; AdaFace idem ; écrire les tags
   SigLIP = décision de mutation XMP, exige la version de pipeline tagging (point 4).
11. **Données / finitions.** Édition des réglages depuis `/reglages` ; 2ᵉ passe des 945
    illisibles + remettre `recuperees/` sur NAS ; `docs/journaux/` gitignoré + purge des
    undo appliqués > 30 j (I12).
12. **À évaluer (discipline `vision-eval`).** Florence-2 (caption+detection+OCR) léger.

### Résiduels faible valeur (ne pas prioriser)
- `/reglages` : bouton **Pause globale** des workers (aujourd'hui : pause maintenance seule) ;
  retrait de l'ancien bandeau `#pending` (l'état vit maintenant dans `/reglages`).
- `/pets` : « empreintes calculées » = compteur mémoire depuis le démarrage (`PET_EMBED_STATE`),
  affiche 0 après redémarrage — libellé à préciser (« depuis le démarrage ») un jour.

## En réserve — futur, non prioritaire

Multi-utilisateur (owner par racine, comptes/droits ; décidé « plus tard »).
Multimodalité images → **vidéo** → **audio**, puis **recherche AI en langage naturel** et
**exposer le serveur en MCP** (`mcp-builder` ; prérequis naturel : Knowledge Builder).
Bibliothèque Figma comme source des composants. **Vision (audit 11/08)** : une mémoire
familiale **à provenance** — chaque fait affiché (nom, lieu, tag) porte sa source et son
statut humain ; deux tests de vérité : « PC mort lundi, tout revit vendredi » et « aucun
fait affirmé sans provenance ». Récits LLM automatiques : écartés (hallucination sur
souvenirs) — la rangée « même jour » sans IA suffit.

## Méthode

1. **Un score parfait est une alarme** — deux bancs ne mesuraient pas ce qu'ils prétendaient.
2. **Une correction n'est acquise qu'une fois son effet observé en réel** — un proxy n'est
   pas le juge.

Idées déjà **rejetées sur mesure** (ne pas reproposer) : contre-exemples de classification,
prototypes multiples pour animaux, MegaDescriptor (2×), résolution des découpes, `sqlite-vec`,
injection des noms au prompt, détecteur ML de triage, garde amont humain/animal. Détail
chiffré : `eval/DECISIONS.md`.
