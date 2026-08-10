# Feuille de route — MediaLibrary

L'état vit dans les fichiers, pas dans l'historique. Ce fichier = **carte des
priorités**. Détail ailleurs : `eval/DECISIONS.md` (décisions tranchées),
`docs/RANGEMENT_2026.md` (rangement), `docs/AUDIT_EXTERNE_2026.md` (direction
tagging), `PROMPT_NOUVELLE_SESSION.md` (reprise), et l'historique git (chaque
chantier fini y est — c'est pourquoi les récits de travaux terminés ne vivent PAS ici).

## État actuel (10 août 2026)

Session 10/08 : gros travail sur `/people` et la **correction des faux positifs**, déclenché
par la fiche **Flo** (~6300 photos, très polluée par des profils tagués). Code livré sur le
disque de Mike et **validé en réel** (serveur redémarré plusieurs fois). Détail : table ci-dessous.

**Suite 10/08 — tokenisation UI #8 TERMINÉE (livrée disque, pas commitée, à activer par
redémarrage).** Les 6 pages restantes (GALLERY, MAP, PEOPLE, PETS, REGLAGES, HTML) sont passées
en tokens. Méthode : (1) **value-preserving** — seuls les `padding/margin/gap/border-radius/
font-size` qui **égalent exactement** un token pointent vers lui (12px→`--e-3`, 999px→`--r-pill`,
0.85rem→`--t-sm`…) ; **prouvé identique** hors-ligne (résolution des tokens + diff : zéro écart
sur les 6 blocs `<style>`) et sur le serveur en marche (`getComputedStyle` des tokens = valeurs
littérales). (2) **Divergences design nommées tranchées** : GALLERY `.pchip`/`.chip` **fusionnés**
en un seul jeu de sélecteurs groupés (fin de la divergence connue ; rendu inchangé, chips
personnes sans enfant `.n` → règle inerte) ; PEOPLE `#222` (fond de vignette, gris froid)
→ `var(--salle-3)` et `#f0a35b` (« hésite avec X ») → `var(--veilleuse)` (incertitude IA,
contraste ~6.4:1 sur `--salle-3`). Contrôles : `verifier_ui_tokens.py` = **0 interdit dur** ;
`py_compile` OK. **Reste : vérif visuelle Claude-in-Chrome après redémarrage** (les 2 couleurs
/people + la fusion changent — ou pas — le rendu ; à confirmer en réel). Non tokenisé
volontairement : valeurs **hors échelle** (0.8rem, radius 8/10px, px de PETS) et noirs/blancs
translucides (ombres, overlays, fonds photo, marqueurs Leaflet `#4A8C7B` que l'API refuse en
`var()`) — passe design ciblée ultérieure, hors périmètre value-preserving.

**Correctif 10/08 (soir) — les corrections de faux positifs n'étaient pas apprises.** Mike
corrigeait la même image (Phéno→Dévi) 5×, elle revenait. Cause : `exclude` (le rejet humain
durable) faisait autorité à l'AJOUT, à `find_more` et à `reconcile`, **mais pas** dans le
générateur de cartes « faux positif » (`build_suggestions` REMOVE) ni dans `reimport_name_tags`.
Dès que le tag erroné resurgissait (ré-import XMP quand l'écriture de retrait a échoué sur le
NAS, rescan d'un fichier modifié, clé en double via les 2 racines d'upload), la carte revenait.
**Fix livré (server.py, pas encore commité ; relu par un agent de revue)** : (1) le générateur
REMOVE ignore les photos exclues **et auto-guérit** (retire le tag resurgi + `del` XMP, journalise
`🩹`) ; (2) `reimport_name_tags` n'importe plus un tag présent dans l'`exclude` de la personne ;
(3) réversibilité (cas « je change d'avis ») : une **attribution positive** à une personne
**lève l'exclusion** de ces photos dans `_nommer_membres_visages` (sinon l'auto-guérison
retirerait le tag qu'on vient de reposer). `exclude` et l'assignation sont mutuellement exclusifs.

**Deux correctifs de curation supplémentaires (10/08 soir, livrés, pas commités) :**
- **Nouvelle personne invisible** : `assigner()` (champ « c'est… » d'une carte faux positif)
  retirait la carte mais ne rafraîchissait pas « Personnes identifiées » → la fiche créée
  n'apparaissait qu'après rechargement. Ajout de `loadPeople()` + invalidation du cache de noms.
- **Caline (chatte) revenait sans cesse comme personne** — VRAIE cause trouvée : `reembed_one_batch()`
  fait `e['faces'] = detect_faces(...)`, ce qui **écrasait la liste `faces` et effaçait les
  marquages humains** (pas_visage/non_group/inconnu/par_humain) sur les visages faibles — or les
  découpes de chat sont faibles. Fix : le ré-embedding **saute** toute photo qu'un humain a jugée
  ou dont un visage est assigné (préserve marques + références (clé,i)). Même classe que le bug
  faux positif : un traitement de fond jetait un jugement humain. ⚠ Les marques déjà effacées :
  **re-rejeter le groupe Caline une dernière fois** après redémarrage — ça tiendra ensuite.
**À activer : redémarrer le serveur** (pas de hot-reload) ; le curateur nettoiera tout seul
les tags resurgis au prochain passage. Vérif logique isolée OK ; à confirmer en réel.

- **Branche** : travaux du 10/08 **PAS encore commités**. Lancer `27 - Commit de session.bat`,
  puis `28 - Fusionner…` si voulu ; **`git push` = geste de Mike** (`docs/GIT_WORKFLOW.md`).
- **Ouvert (gestes Mike)** :
  - **Nettoyer Flo** : la fiche reste polluée tant qu'un passage n'est pas fait. Ouvrir Flo →
    « Corriger » (seuil ~0.2, monter en surveillant la grille) ou « Nettoyer (référence) »
    pour une séparation fine. Retrait **sûr** (cf. Acquis « exclude »).
  - Toujours en attente : appliquer les lots de renommage + activer `gps_place` (cf. « À faire »).
- **Chantier EN PAUSE** : page « Sujets » unifiée — **cadrée** (surcouche `/sujets` d'abord
  puis fusion ; **Lieux = 3ᵉ type d'entité** à côté de Personnes/Animaux) mais **pas commencée**
  en code (priorité donnée aux urgences Flo). Reprendre là (cf. « À faire » n°4).

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
| Correction | **Faux positifs (10/08)** : « Corriger » et « Nettoyer (référence) » partagent `scoredRemoval` (seuil ajustable, compteur live « N sous le seuil », retrait de masse **piloté par les données**, rendu par lots) ; grille de réf. triée « plus ressemblantes d'abord » (`order=best`). Retrait **SÛR** : `untag`→`exclude`, et le curateur auto **saute `exclude`** (jamais re-taggué). **`exclude` fait désormais autorité PARTOUT** (générateur REMOVE + `reimport_name_tags` corrigés le 10/08 soir ; auto-guérison des tags resurgis) |
| Perf | **Scoring vectorisé (10/08)** : `_stack_embs` + `_best_sims_for_tag` (un matmul au lieu de ~12000 produits par visage) ; `media_roots()` calculé UNE fois (au lieu de 6338×) → re-score d'une personne à 6338 photos **156 s → quelques s**. `SubjectStore.photos()` a un mode `light` |
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
4. **Page « Sujets » unifiée — 1ʳᵉ tranche LIVRÉE le 10/08 (soir).** Surcouche `/sujets`
   en place : onglet dans la nav partagée, page LECTURE SEULE (grille unifiée
   personnes+animaux, filtre par nom, bascule Tous/Personnes/Animaux, tri par nb de photos),
   API `/api/sujets/list` (réutilise `people_list`+`pets_list`). Chaque carte ouvre la fiche
   détail existante via **lien profond** `?name=` (ajouté à `/people` et `/pets`). Livrée,
   **pas commitée, à activer par redémarrage** ; à vérifier en réel (Claude-in-Chrome).
   **Reste :** **Lieux = 3ᵉ type d'entité** (dépend de `gps_place`) ; puis **fusion**
   (faire de `/sujets` l'entrée unique, `/people`+`/pets` en vues spécialisées).
   `SubjectStore` déjà unifié — surtout de l'UI.
5. **Recherche.** SigLIP 2 en langue naturelle (« les étés à Bremblens avec Luna ») ;
   partager le vocabulaire de la barre de recherche à la page Carte (marqueurs déjà FAITS).
6. **Reconnaissance — algo.** Clustering par densité (HDBSCAN / Chinese Whispers) au lieu
   d'un seuil global unique ; AdaFace sur le ré-embedding des visages faibles ; écrire les
   tags SigLIP (aujourd'hui proposés — décision à prendre car modifie les XMP).
7. **Perf / archi.** Embeddings visages en INT8 (~4× moins de stockage/SMB, sans perte) ;
   `GpuArbiter` unique (baux + priorités UI > tagging > visages > chats) remplaçant les 4
   politiques `*_GPU_MIN_FREE_MB` séparées.
8. **Extraire les 7 pages HTML → `ui/` + `tokens.css`** (sans build step ; corriger les
   divergences en passant). **Value-preserving : FAIT sur les 7 pages** (`/browse` le 10/08,
   puis GALLERY/MAP/PEOPLE/PETS/REGLAGES/HTML en suite 10/08 — cf. « État actuel »). L'extraction
   physique vers `ui/` (via `bundle.py`) reste à faire ; les tokens y sont déjà tous référencés.
   - **Modèle value-preserving (appliqué partout)** : les espacements/rayons/tailles qui
     **égalent déjà un token** pointent vers lui (12px→`--e-3`, 8px→`--e-2`, 16px→`--e-4`,
     0.75rem→`--t-xs`, 0.85rem→`--t-sm`, 999px→`--r-pill`, radius 6px→`--r-md`, 3px→`--r-sm`).
     Substitutions **à valeur identique**, prouvées (résolution des tokens + diff = zéro écart ;
     `getComputedStyle` sur serveur en marche). Ne PAS tokeniser : positions/largeurs/hauteurs,
     font-sizes en **px** (px ≠ rem, non équivalent), valeurs hors échelle. Les `#4A8C7B` des
     marqueurs **Leaflet** RESTENT en dur (l'API refuse `var()`).
   - **Divergences design nommées : TRANCHÉES** — GALLERY `.pchip`/`.chip` fusionnés (sélecteurs
     groupés) ; PEOPLE `#222`→`var(--salle-3)`, `#f0a35b`→`var(--veilleuse)`. À **confirmer en
     réel** (vérif visuelle après redémarrage).
   - **Reste (passe DESIGN ciblée, non faite — hors value-preserving)** : caler les valeurs
     **hors échelle 4px** (ex. `/browse` 14/11/10/6/30/22/2px, radius 8/10px, 0.9rem, 0.78rem,
     13px, 36px ; équivalents dans les autres pages) sur l'échelle — **change le rendu, vérif
     visuelle obligatoire** ; harmoniser les fonds photo (#000 vs `--salle-3`) entre PEOPLE et
     PETS si voulu.
   - **Méthode recommandée** : pour chaque page restante, UNE passe combinée (value-preserving
     + calage échelle + divergences) AVEC vérif visuelle Claude-in-Chrome, plutôt que 2 passes
     sur les mêmes déclarations. `/browse` a servi de modèle (value-preserving seul, identique).
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
