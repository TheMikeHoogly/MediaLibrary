# Feuille de route — MediaLibrary

L'état vit dans les fichiers, pas dans l'historique. Ce fichier = **carte des
priorités**. Détail ailleurs : `eval/DECISIONS.md` (décisions tranchées),
`docs/RANGEMENT_2026.md` (rangement), `docs/AUDIT_EXTERNE_2026.md` (direction
tagging), `PROMPT_NOUVELLE_SESSION.md` (reprise), et l'historique git (chaque
chantier fini y est — c'est pourquoi les récits de travaux terminés ne vivent PAS ici).

## État actuel (9 août 2026)

- **Session 9/08 — allègement `/people`, tour de contrôle, nettoyage :**
  - **`/people` allégé (item 4) : CODÉ + DÉPLOYÉ, à VALIDER EN RÉEL.** Le rendu des
    ~2081 groupes + 342 personnes + inconnus passe d'une passe unique (~11 300
    vignettes → figes) à un **rendu par lots au défilement** (`renderInBatches`,
    sentinelle `IntersectionObserver`, lots de 24 ; repli tout-rendre sans IO).
    `carteGroupeP`/`carteInconnu` inchangés, cartes = vrais nœuds DOM (`remove()`
    après nommage marche toujours). ⏳ **Redémarrer le serveur** puis tester via
    Claude-in-Chrome (défiler groupes, nommer un groupe, ouvrir Inconnus).
  - **Tour de contrôle (item 2) : déjà ~fait, complété.** `/api/maint/status` +
    `/reglages` exposaient déjà matériel/files/pending/compteurs/maintenance ; ajout
    d'une carte **« Empreintes animaux »** = **stock réel** (`photo_vectors().count('animals')`,
    ~4826) au lieu du compteur de session qui restait à 0 après redémarrage.
  - **Intégrité Mutz/Caline vérifiée (lecture seule) : AUCUN nom perdu.** Mutz = 110
    photos (105 `animal:` + 5 `personne:`), Caline = 904 (863 `animal:` + 83 `personne:`
    + 9 `caline` nus = adjectif, à ne pas toucher) + fiche `people[caline]` en double.
    Le souci est de **préfixe/doublon** (items #5 & #12), pas de perte. Sur *tous* les
    noms, seuls 2 collisionnent.
  - **Outil de reclassement `personne:`→`animal:` : ✅ VALIDÉ EN RÉEL.** Dans
    `/reglages` → « Reclassement des animaux mal classes » : Aperçu / Appliquer / Annuler,
    réversible (journal `docs/undo_reclassement_*.json`), réutilise `write_person_tag/untag`
    + `PERSON_QUEUE` + `PEOPLE.delete`. **Appliqué le 9/08 : 88 photos reclassées** (Mutz
    5, Caline 83), fiche `people[caline]` en double retirée ; vérifié photo par photo
    (88/88 en `animal:`, 0 en `personne:`, aucune perte). Traite les items #5 (cross-pipeline
    Mutz) et #12 (doublon personne↔animal) pour ces deux noms. Bug corrigé après coup :
    un Appliquer à vide ne crée plus de journal, et Annuler vise le dernier journal NON vide.
  - **Nettoyage de fin de session : LIVRÉ.** `nettoyer_session.py` + `29 - Nettoyage
    de session.bat` : quarantaine **réversible** (`_corbeille_session/AAAA-MM-JJ/` +
    `manifest.json`, liste blanche stricte) + **lint de cohérence des `*.md`**. Passe
    initiale faite (13 éléments éphémères, 1,8 Mo). Étape ajoutée au protocole
    (`CLAUDE.md`). Corrigés au passage : lien cassé `README.md`
    (`AUDIT_2026`→`AUDIT_EXTERNE_2026`), `.gitignore` ignore la corbeille.
- **#3 archive « Inconnus » + fix curateur (nom neuf) : ✅ VALIDÉS EN RÉEL** (checklist
  complète via Claude-in-Chrome : archiver → sort de la file + Inconnus ; nommer un
  inconnu → crée la personne + lève l'archive ; Réactiver → retour, sans perte ; nom
  neuf depuis « À vérifier » → crée la fiche `PEOPLE_STORE`). Nuance : archiver/attribuer
  agit sur le sous-ensemble de 18 visages affiché (plafond serveur), cohérent, pas un bug.
- Branches : `main == origin/main == feat/menage-ui-gpu-0807`. Le serveur tourne la
  branche de travail. **`git push` / merges = gestes de Mike** (`docs/GIT_WORKFLOW.md`).
- Éventuellement non commité : `server.py`, `0 - Démarrer le serveur.bat`,
  `verifier_orphelins.py` (+test), docs. **Ouvert** : géocodage `gps_place` à activer.

## Acquis — ne pas reproposer (détail : git + `DECISIONS.md`)

| Domaine | Acquis |
|---|---|
| Stockage | SQLite (64 676 entrées), embeddings BLOB, `photos.db` local WAL, backup NAS snapshot |
| Reconnaissance | SigLIP 2 (sémantique 90 % r1) ; animaux 97,4 % r1 ; prototypes multiples (personnes) ; vérif d'espèce |
| Nommage | Attribution unifiée (sous-ensemble, multi-noms, annulation 10 s) personnes+animaux ; rejets réversibles ; **archive « Inconnus »** |
| Fichiers | `/browse` (renommer/déplacer/supprimer réversible) ; upload dossiers ; fix SMB Errno 22 ; `rekey_everywhere` ; purge orphelins/fantômes |
| Rangement | Dédoublonnage contenu appliqué (8,4 Go) ; rangement par année appliqué ; orchestrateur de maintenance |
| Renommage | Cœur + plan + applicateur réversibles prêts (plan = 2114) ; géocodage inverse `gps_place` codé |
| UI | Design system « chambre noire » (tokens, plancher a11y, `verifier_ui_tokens`) ; planche contact ; tri clavier ; `/reglages` |
| Tagging | `qwen3-vl:2b` ; hybride assertions+image ; 1 lecture exiftool/photo |
| GPU | torch CUDA `2.13.0+cu130` + `onnxruntime_gpu` ; `FACE_USE_GPU=False` volontaire (4 Go pris par Ollama) |

## À faire — par ordre de valeur

1. **Vérité terrain humaine (priorité n°1).** ~0,8 % de confirmations humaines (91/12 072).
   Confirmer ~100 propositions dans `/people` vaut plus que tout changement d'algo. Tri
   clavier prêt (Espace=oui, X=non, Z=annuler, lettre=corriger).
2. **`/reglages` en « tour de contrôle »** — ✅ *l'essentiel EST fait* (endpoint
   `/api/maint/status` agrégé + cartes « État en direct » : `hw_state()`, files
   `TAG/FACE/ANIMAL/PERSON`, pending, compteurs, maintenance ; carte « Empreintes
   chats » `PET_EMBED_STATE` ajoutée 9/08). Reste possible, faible valeur : « Pause »
   **globale** des workers (aujourd'hui pause maintenance seule) + retrait du bandeau
   `#pending`. Ne pas reconstruire l'existant.
3. **Appliquer les lots de renommage** (`/reglages` → Renommage, plan = 2114, lots de 200
   réversibles) + **activer le géocodage `gps_place`** : lancer `18 - …gazetteer.bat`, puis
   `enrichir_lieux.py` (aperçu) puis `--ecrire`, puis redémarrer. Gestes Mike.
4. **Alléger `/people`** — ✅ *codé + déployé le 9/08 (rendu par lots `renderInBatches`),
   à VALIDER EN RÉEL après redémarrage.* La page rendait ~11 300 vignettes d'un coup
   (2081 groupes + 342 personnes) → figes ; désormais rendu par lots au défilement.
   Piste ultérieure si insuffisant : virtual-scroll intégral (cf. `photo-ui`, > 2000
   vignettes) — non nécessaire à ce stade.
5. **Cross-pipeline (Mutz).** Action manuelle « C'est un animal » (/people) + miroir /pets :
   livrée. Fix auto (garde amont humain/animal) **REJETÉ** (18 % faux rejets, cf. DECISIONS) ;
   seule piste = re-mesurer sur découpes SANS marge avant d'y revenir.
6. **Page « Sujets » unifiée** (Personnes + Animaux, filtre par type, lieu = 3ᵉ facette ;
   `SubjectStore` déjà unifié — surtout de l'UI).
7. **Recherche.** SigLIP 2 en langue naturelle (« les étés à Bremblens avec Luna ») ;
   partager le vocabulaire de la barre de recherche à la page Carte (marqueurs déjà FAITS).
8. **Reconnaissance — algo.** Clustering par densité (HDBSCAN / Chinese Whispers) au lieu
   d'un seuil global unique ; AdaFace sur le ré-embedding des visages faibles ; écrire les
   tags SigLIP (aujourd'hui proposés — décision à prendre car modifie les XMP).
9. **Perf / archi.** Embeddings visages en INT8 (~4× moins de stockage/SMB, sans perte) ;
   `GpuArbiter` unique (baux + priorités UI > tagging > visages > chats) remplaçant les 4
   politiques `*_GPU_MIN_FREE_MB` séparées.
10. **Extraire les 7 pages HTML → `ui/` + `tokens.css`** (sans build step ; corriger les
    divergences en passant). À faire avec/après l'allègement de `/people`.
11. **Éval tagging (parké, déjà cadré).** Mesurer V2 « assertions en contexte, sans
    impératif de noms » (~4,3 s, jamais notée) + fusion programmatique des noms/date/lieu
    (Knowledge Builder). Cf. `docs/AUDIT_EXTERNE_2026.md` + `eval/PLAN_assertions_vs_pixels.md`.
12. **Données / finitions.** Fiche « Flo » mal constituée (rend Florine ambiguë) ; doublons
    de fiches personnes↔animaux ; édition des réglages depuis `/reglages` (aujourd'hui
    lecture seule) ; 2ᵉ passe de récupération des 945 illisibles + remettre `recuperees/` sur NAS.
13. **À évaluer (mesurer avant d'adopter, discipline `vision-eval`).** Florence-2
    (caption + detection + OCR) comme candidat léger.

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
