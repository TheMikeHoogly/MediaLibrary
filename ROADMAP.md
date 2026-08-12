# Feuille de route — MediaLibrary

L'état vit dans les fichiers, pas dans l'historique. Ce fichier = **carte des
priorités**. Détail ailleurs : `eval/DECISIONS.md` (décisions tranchées),
`docs/AUDIT_INTERNE_2026-08.md` (triple audit 11/08 : incohérences I1–I17,
optimisations O1–O15, angles morts A–F), `docs/RANGEMENT_2026.md`,
`docs/AUDIT_EXTERNE_2026.md`, `PROMPT_NOUVELLE_SESSION.md` (reprise), et git
(chaque chantier fini y est — les récits de travaux terminés ne vivent PAS ici).

## État actuel (12 août 2026)

**Session 12/08 (4) — files « À vérifier » sous Classification + file ANIMAUX
créée : LIVRÉE, À COMMITER (bat 27) + redémarrer + VÉRIFIER EN RÉEL.**
La file de vérification quitte `/people` : elle se juge maintenant **dans
`/sujets?vue=classification`**, à côté d'une **file animaux créée en miroir**
(`build_cat_suggestions()`, `GET /api/pets/curator/list`, journal
`CAT_AUTO_LOG` des rattachements auto annulables, jugements animaux
instrumentés dans `_do_assign` — même journal, même compteur de séance).
Tri clavier **unifié** (personnes d'abord, puis animaux : Espace/X/Z/lettre).
`/people` et `/pets` gardent fiches, correction, groupes, inconnus, et pointent
vers Classification. **3 correctifs issus de la relecture adversariale** :
(a) `par_humain` posé par un nommage d'animal est désormais **annulable**
(sinon accepter-puis-annuler faisait disparaître la proposition pour toujours —
`par_humain` n'était lu par personne avant cette file) ; (b) garde
**anti-course** `_note_juge`/`_juges_depuis` sur les DEUX files : une
reconstruction démarrée avant un jugement ne réinjecte plus la carte jugée
(reste du mode de panne « je corrige et ça revient ») ; (c) garde **clés
fantômes** côté animaux (plus de carte sans vignette). Plus : verrou
« une carte ne se juge qu'une fois » (deux Espace rapides = un seul jugement).
Vérifs : `python`+`node --check` sur les 10 pages, `verifier_ui_tokens.py`
(0 interdit dur), parcours clavier complet simulé (jsdom) sur les deux files.

**Session 12/08 (3) — correctifs d'audit + assurance-vie + Sujets guichet unique :
COMMITÉE (`e17ac2d`, branche `feat/audit-assurance-sujets`), VÉRIF EN RÉEL PARTIELLE**
(`/sujets?vue=classification`, sous-nav, cartes /reglages : présentes ; `/api/thumb`,
seek vidéo et « Sauvegarde vérifiée : ok » restent à observer). Trois volets :
(a) **Correctifs d'audit** : I1 (workers visages/animaux sous `creneau()`), I2
(gps_places.json suit rekey/forget, copy-on-write + flush atomique), O1 (`/api/thumb`
512/1600 px, cache disque + mtime, confiné, fallback 302 → original ; clients
galerie/carte/diaporamas), O2 (`_send_file` streaming 1 Mo + Range → seek vidéo),
O3 (cache `media_roots` TTL 8 s / rebuild 60 s), O4 (écritures vecteurs sous
`STORE.lock`), O5 (boucle maintenance blindée, backup hors du try du scan), O10
(index `ix_vectors_k`). (b) **Assurance-vie (audit A)** : `backup_verify()` après
chaque backup (restauration à blanc du snapshot NAS, integrity_check + comptage
confirmed/exclude vs vivant, URI SQLite compatible UNC) + `export_jugements()`
(journal → NAS, atomique) ; cartes « Dernier scan » et « Sauvegarde vérifiée »
dans /reglages. (c) **/sujets guichet unique** : sous-nav Sujets partagée
(Annuaire · Personnes · Animaux · Classification) sur /sujets /people /pets +
**onglet Classification** (compteurs vivants par type, liens profonds ancrés
#verifier/#groupes/#inconnus avec re-visée anti-cible-mouvante). Diff relu par
agent adversarial, correctifs appliqués (confinement thumb, URI UNC, fallbacks).
**Vérifs en réel attendues** : voir « Gestes Mike » ci-dessous.

**Sessions 12/08 (1–2) — commitées (`a9a7d8b`…`d9eda80`), VÉRIFIÉES EN RÉEL** :
instrumentation vérité terrain (file par marge, journal des jugements, compteur de
séance) ; régression « Gérer » corrigée (2 causes : `#panel` avant la grille +
`curMark` sans scroll au chargement). Détail dans git.

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

- **Git** : commité jusqu'à `e17ac2d` (branche `feat/audit-assurance-sujets`) ;
  **reste à commiter la session (4)** — `27 - Commit de session.bat` ;
  **`git push` / merge dans `main` = gestes de Mike**.
- **Ouvert (gestes Mike)** :
  - **Redémarrer, puis vérifier en réel la session (4)** : `/sujets?vue=classification`
    → les deux files « À vérifier » (personnes ET animaux) s'affichent et se
    jugent au clavier ; la file animaux propose bien quelque chose (sinon
    `↻ Rafraîchir` : la 1re construction est asynchrone) ; annuler (Z) une
    acceptation d'animal doit **faire revenir la carte** après rafraîchissement
    (c'est le correctif (a)) ; `/people` et `/pets` n'ont plus de file mais un
    lien vers Classification.
  - **Vérifier en réel la session (3)** après redémarrage : grille galerie rapide
    (onglet Réseau : `/api/thumb` 200, plus d'originaux) ; seek vidéo mobile ;
    après le prochain backup horaire, carte « Sauvegarde vérifiée » = ok dans
    /reglages (⚠ jamais observée sur Windows : l'URI UNC doit être vue passer
    UNE fois — réflexe n°2).
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
| UI | Design system « chambre noire » (tokens, plancher a11y, `verifier_ui_tokens`) ; planche contact ; tri clavier ; `/reglages` tour de contrôle ; **`/people` réorganisé (10/08)** : personnes identifiées + panneau de correction EN TÊTE, files de travail dessous → fin du saut de scroll ; **filtre par nom** ; **indicateur d'activité réseau global** (spinner « Traitement… », enrobage `fetch` dans la nav partagée, 7 pages) |
| Correction | **Faux positifs (10/08)** : « Corriger » + « Nettoyer (référence) » (retrait de masse piloté par les données, seuil ajustable). Retrait **SÛR** (`untag`→`exclude`) ; **`exclude` fait autorité PARTOUT** + auto-guérison des tags resurgis (détail : git) |
| Perf | **Scoring vectorisé (10/08)** : matmul unique + `media_roots()` calculé 1× → re-score 6338 photos **156 s → quelques s** ; `SubjectStore.photos()` mode `light` (détail : git) |
| Tagging | `qwen3-vl:2b` ; hybride assertions+image ; 1 lecture exiftool/photo |
| GPU | torch CUDA `2.13.0+cu130` + `onnxruntime_gpu` ; `FACE_USE_GPU=False` volontaire (4 Go pris par Ollama) |
| Hygiène | Nettoyage de session **réversible** (`_corbeille_session/` + lint `*.md`, `29 - …bat`) ; **commit guidé** : `SESSION_COMMIT.txt` (branche+titre proposés par le bat 27) — protocole `CLAUDE.md` |
| Perf serveur | **(12/08)** `/api/thumb` (vignettes 512/1600, −98 % octets NAS), `_send_file` Range+streaming, cache `media_roots`, index `ix_vectors_k`, écritures vecteurs sous lock, workers sous ordonnanceur |
| Robustesse | **(12/08)** `backup_verify` (restauration à blanc + comptage jugements) + export `journal_jugements.jsonl` → NAS ; boucle maintenance blindée ; gps_places suit rekey/forget |
| Sujets | **(12/08)** Sous-nav partagée (Annuaire · Personnes · Animaux · Classification) + onglet **Classification** (compteurs vivants, liens profonds ancrés vers /people et /pets) |
| Vérification | **(12/08, session 4)** Les files « À vérifier » vivent DANS Classification, personnes **et animaux** (miroir : mêmes cartes, même clavier, même journal/compteur de séance). Curateur animaux = `build_cat_suggestions()` (zone d'incertitude entre `PET_MATCH_SIM` et `CAT_AUTO_SIM`/`CAT_AUTO_MARGIN`, tri par marge), bande « ajoutés automatiquement » annulable. Garde anti-course `_note_juge` sur les 2 files ; `par_humain` (animaux) annulable ; une carte ne se juge qu'une fois |

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine (priorité n°1).** ~0,8 % de confirmations (91/12 072).
   L'instrumentation est LIVRÉE (12/08 : file par marge, journal des jugements, compteur
   de séance ; session 4 : guichet unique de jugement, personnes + animaux — cf. État
   actuel). Reste le **geste Mike** : confirmer ~100 propositions dans
   `/sujets?vue=classification` (tri clavier) ; la métrique qui compte =
   confirmations/minute et erreurs découvertes, pas l'accord modèle-humain.
2. **`/sujets` guichet unique — navigation, Classification ET jugement LIVRÉS
   (12/08, sessions 3–4 ; vérif en réel attendue).** Le travail de vérification se fait
   maintenant dans `/sujets` même. Reste (si le besoin se confirme à l'usage) : y amener
   aussi les groupes à nommer / inconnus (aujourd'hui : cartes qui routent vers les
   ancres de /people et /pets).
3. ~~Assurance-vie de la vérité terrain~~ **LIVRÉE (12/08)** — `backup_verify` +
   `export_jugements` à chaque backup horaire ; reste la **vérif en réel** (une carte
   « Sauvegarde vérifiée : ok » observée dans /reglages sur la machine Windows).
4. **Éval tagging V2 — AVANT les lots de renommage** (le jeu figé de 150 photos est keyé
   par chemin ; renommer d'abord invaliderait le banc — mode de panne déjà documenté).
   Protocole prêt : `eval/PLAN_assertions_vs_pixels.md`. Si V2 confirme → **câbler le
   Knowledge Builder** (ADOPTÉ le 31/07, jamais câblé) + créer la **version de pipeline
   tagging** manquante (audit D).
5. **Gestes Mike, dans cet ordre** : nettoyer Flo (outillage livré) ; activer
   `gps_place` (I2+O10 faits ; `18 - …gazetteer.bat` → `enrichir_lieux.py` →
   `--ecrire` → redémarrer) ; **après l'éval V2** : lots de renommage (plan = 2114).
6. **Correctifs d'audit — I1, I2, O1–O5, O10 FAITS (12/08).** Restent (détail :
   `docs/AUDIT_INTERNE_2026-08.md`) : O6 (recherche bloquée par le lot d'encodage,
   sous-lots de 4), puis I4–I8, O7–O9, O11–O15 (dont purge de `photo_thumbs/`
   avec O15 — le cache vignettes croît sans borne).
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
