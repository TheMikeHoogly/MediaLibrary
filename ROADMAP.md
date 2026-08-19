# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (19/08/2026, session 27)

**La vue s'affiche : `date · lieu · noms` sous chaque vignette et dans la
visionneuse, avec leurs SOURCES.** Un seul producteur côté client
(`faitsHtml`), un seul assembleur côté serveur (`faits_vue.assertions`) : la
planche et la fiche ne peuvent plus se contredire. Les quatre modes de `/files`
(navigation, tags, recherche, même jour) partagent le même objet-photo.

**L'index inversé des noms est mesuré, pas supposé** (`mesure_faits_vue.py`,
base réelle) : une page de 50 coûte **1,11 ms** avec, **9,65 ms** avec le
balayage naïf de `_noms_attendus` — **×8,7**. `_faits_ctx()` le bâtit une fois
par page, en **deux passes** (tous les `exclude` avant tous les `faces`) : en
une seule, l'autorité d'un retrait dépendrait de l'ordre du dict, et un nom
retiré pourrait revenir. Index entier : 2,234 s (51,9 µs/photo).

**Observé en réel** après redémarrage (`code_a_jour` vrai) : `q=Ins` rend 11
photos — **11 avec une date, 11 avec un lieu, 5 avec des noms** — page en
**1 048–1 462 ms** (contre 1 539 ms avant) ; `q=montagne` rend 1 500 photos en
**477–1 082 ms** (1 233 Ko). L'affichage est gratuit à l'échelle de la page.

**Le chiffre honnête a bougé : 69,95 %** (30 122 photos avec un fait NON-date),
non 69,14 % — `lieux.txt` a grossi. C'est sur lui que se mesure le filtre
(14a-iv), jamais sur les 99,79 %. Matière : date 99,32 %, personne 43,79 %,
lieu 31,11 %, espèce 11,03 %, animal 2,17 %. L'autorité vivante **retire 13
noms et en ajoute 2** — la raison même de ne pas graver le champ.

**La livraison git est automatisée, et c'est une PORTE — observée.**
`git_agent.py` (fenêtre « MediaLibrary - Git ») surveille `_commande_git.txt`
et refuse tant que la preuve manque : l'ordre s'inverse, éditer → redémarrer →
**observer** → livrer. Premier acte, **il s'est commité lui-même** (`a43f9d0`,
10 fichiers) — push et fast-forward de main compris, cinq contrôles passés.
`force=` lève les négociables, jamais le verrou, `main`, un binaire ni un
`checkout` risqué. 21 tests ; `_etat_git.json` dit ce qu'il a TENTÉ,
`.git/logs/*` ce qui s'est PASSÉ.

## À faire — par ordre de valeur

1. **Vérité terrain humaine — au fil de l'eau, PAS un blocage.** ~0,8 %
   (91/12 072) : limité par la CONNAISSANCE, pas l'outillage — Flo nommera ce
   que Mike ne sait pas nommer, quand l'outil sera à ~90 %.
2. **Observer en réel ce qui est livré** — **fait ✔** (chaque livraison du
   19/08 a son contrôle positif). Reste : re-upload = une entrée, seek vidéo
   mobile, test du Z.
3. **Chaîne « noms → descriptions → recherche » — 3a, 3b, 3c CLOS le 16/08.**
   La re-passe ne se fera pas. Reste ouvert : **le prompt de PRODUCTION est celui
   qui hallucine le plus** (adopté sur un 25-15 ; toute photo taguée le paie).
   **Pas de retour à V0 sans protocole.** (Le wagon de 14 — affichage
   date · lieu · noms — est arrivé le 19/08.)
4. **Gestes Mike** : `gps_place` ✔ ; renommage appliqué ✔ (7 058) ; nettoyer
   Flo (5 909 photos) ; re-rejeter Caline.
5. **Correctifs d'audit** : I4–I8, O7–O9, O11–O15. O1 clos ; O15 (purge de
   `photo_thumbs/`) gagne en poids.
6. **Navigation par similarité et par date** : « Semblables » et « même jour »
   livrés et observés. Reste : doublons proches bridés (>0,98 + même journée →
   quarantaine réversible, 50 paires jugées avant geste).
7. **Extraction `ui/`** : décision à prendre — session dédiée `bundle.py` ou
   parcage explicite (item zombie ; préparatoire fait).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nom d'animal sort en `personne:`.
9. **Reconnaissance — algo.** BARRIÈRE : vérité terrain ≥ ~5 %. HDBSCAN /
   Chinese Whispers / AdaFace inévaluables à 0,8 %.
10. **Données / finitions**, dans cet ordre :
    (a) **Compter ce que le scan OUBLIE — CLOS (18/08).** Trois constats mineurs
    non traités : un ajout vu PAR LE SCAN est étiqueté `tagging` ; `dict.__ior__`
    non redéfini dans `TrackedDict` (aucun usage) ; `cycles_vus` est la longueur
    d'un anneau de 10 — il affiche « 10 » à vie.
    (b) **Garde-fou du repli sur le NOM + noms périmés — CLOS (19/08), observé.**
    **`taken` en base : REJETÉ (19/08)** — le garde-fou est passé à la LECTURE
    (voir l'État). Rien n'est écrit.
    (c) Réglages éditables depuis `/reglages` ; 2ᵉ passe des 945 illisibles +
    `recuperees/` → NAS ; purge des undo > 30 j (I12) ; deux images TRONQUÉES
    visibles dans `erreurs_images` à chaque démarrage.
11. **UI — harmonisation des vues (12/08, skill `photo-ui`)** : (a) clic sur
    l'image d'une personne → sa démo aléatoire ; (b) lieux : texte sous l'image
    en tooltip ; (c) harmoniser visages/lieux/animaux — mêmes fonctions partout,
    **sauf** l'effacement, réservé à Classification ; (d) zoom pinch + molette —
    `maximum-scale=1` retiré ✔ ; (e) **boutons de tri : CLOS (19/08), observé** — l'ordre du serveur
    s'appelle « Pertinence », un seul ordre allumé, le clic n'est plus avalé.
    Reste : bandeau `#pending`, libellé `/pets`, « Meme jour (14 aout) » là où
    la page dit « 14 août ».
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** « PC mort lundi,
    tout revit vendredi » : restaurer le snapshot NAS sur un dossier vierge,
    chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`). Tant qu'il n'a pas tourné, c'est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08).** Recherche,
    fiches et `faits` en outils MCP locaux (JSON-RPC stdio, zéro dépendance —
    skill `mcp-builder`). Écriture plus tard. Briques de 14a.
14. **Recherche IA locale contextuelle.**
    (a) **Déterministe — (i) et (ii) CLOS et OBSERVÉS le 19/08** : `faits` est
    une VUE (`faits_vue.py`), et la règle de LIEU est unifiée sur ses trois
    appelants, corrigée et mesurée (voir l'État, banc `mesure_lieu_visible.py`).
    **(iii) CLOS et OBSERVÉ le 19/08** : la vue s'affiche sur la planche et
    dans la visionneuse, index inversé des noms bâti une fois par page (×8,7).
    Reste : **(iv) le filtre**, mesuré sur **69,95 %** (photos avec un fait
    NON-date), jamais sur 99,79 %.
    (b) ensuite seulement, **escalade ponctuelle** vers un modèle chargé à la
    demande (bail GpuArbiter, déchargé après) — `vision-eval`, jamais câblé
    sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger. **Parqué** faute
    d'hypothèse (banc 3b).

### Résiduels faible valeur (ne pas prioriser)
**MESURÉ le 15/08, et c'est pourquoi on n'y touche pas** : les deux planchers
1990 (`_fname_time`, `meme_jour.ANNEE_MIN`) coûtent **7** photos et **0**, et ils
sont **couplés** ; le plancher 1990 subsiste aussi dans `plan_rangement.py`,
`recensement_doublons.py`, `diagnostic_dates.py`, sans effet tant qu'aucun
dossier d'avant 1990 n'y passe. Le **plafond 2100** (`22082010141.jpg` → 2082) : 72 en base, coût 0 — elles
portent un `taken`. Enfin
`/files?dir=1&rec=1` (racine NAS) ne répond pas en 6 min, cause non cherchée.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Stockage** : SQLite local WAL (**43 064 entrées**), embeddings BLOB, backup
  NAS snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers/Rangement** : `/browse` réversible, dédoublonnage (8,4 Go),
  rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles ; **7 058 renommages
  appliqués et observés** (0 sauté, noms humains intacts) ; `gps_place` actif
  dans les noms (1 175 en portent un) ; garde-fou date de SCAN
  (`date_de_scan_presumee`, asymétrique, toléré à un an).
- **UI** : design system « chambre noire » (tokens, plancher a11y), planche
  contact, `/reglages`, `/people`, `/sujets` guichet unique ; **faits
  `date · lieu · noms` sous chaque vignette et dans la visionneuse**, avec
  leur SOURCE (exif / nom du fichier / année du dossier — gps / chemin),
  produits par la VUE et par un seul rendu partagé.
- **Correction** : faux positifs « Corriger »/« Nettoyer », retrait SÛR
  (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
- **Perf** : scoring vectorisé (156 s → qq s) ; `/api/thumb` (−98 % octets NAS) ;
  `_send_file` Range/streaming ; workers sous ordonnanceur ; GpuArbiter 27/27.
- **Tagging** : `qwen3-vl:2b`, prompt v2ctx ; Knowledge Builder : faits
  noms/date/lieu structurés et sourcés (`faits`), noms JAMAIS via le prompt ;
  `TAGGING_PIPELINE_VERSION` estampillée (`pipe`) — **sur les 81 photos taguées
  DEPUIS**, pas sur le fonds ; 1 lecture exiftool/photo.
- **Index/vecteurs** : cascade `forget_everywhere` au scan ; **2 374 vecteurs
  orphelins purgés et observés** (0 muet sur 1 600 résultats, contre 2,6 %),
  quarantaine réversible `_corbeille_vecteurs/`.
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, trois tâches de
  fond EXIF dans `/reglages` ; comptes de l'index au goulot (`comptes_index.py`).
- **Recherche** : quatre dimensions (noms · lieux · période · sens) ; **une
  seule règle de date** (filtre, tri, « même jour », `_best_time`, fait — la
  date de SCAN écartée à la lecture) et **une seule règle de LIEU**
  (`faits_vue`, segments + mots collés découpés — jamais de sous-chaîne),
  partagées par le renommage, le KB, `/sujets` et la recherche.
- **Mesure** : `mesure_dates_scan.py` (`--lecture`), `mesure_tri_recherche.py`,
  `mesure_faits_backfill.py`, `mesure_faits_vue.py`, `mesure_lieu_visible.py` —
  lecture seule sur COPIE, jamais sur `photos.db`.
- **Pilotage** : arrêt/redémarrage commandés par `_commande_serveur.txt`
  (`pilotage.py`, 22 tests ; `superviseur.bat` relance sur le code 42 et
  s'arrête après 5 sorties anormales) — la sandbox observe enfin ses propres
  livraisons. `GET /api/serveur` dit `demarre_a` et **`code_a_jour`**.
- **Hygiène et livraison** : nettoyage réversible (29) ; `27 - Git.bat` reste
  le guichet des gestes de Mike (état, commit guidé, fusion sans checkout,
  purge des branches, GitHub, rapport de l'agent au choix 8) ; **`git_agent.py`
  livre pour la sandbox** — `livrer` dans `_commande_git.txt`, puis commit +
  push + fast-forward, **après contrôles** (serveur à jour, tests des modules
  touchés, `.bat` ASCII, lint). L'ordre s'inverse : **observer AVANT de
  commiter**.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — **déclencheur nommé** : un « mode Flo » minimal (file
  de nommage des visages qu'elle seule sait nommer), à ouvrir quand l'outil est à
  ~90 %. C'est lui qui débloque la vérité terrain.
- **Vidéo → audio** : coût élevé, valeur incertaine, aucun déclencheur.
- **Bibliothèque Figma** : le design system vit dans le code ; un miroir serait
  de la doc à double entretien.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).
