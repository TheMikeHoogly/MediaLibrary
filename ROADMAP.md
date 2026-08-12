# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; l'éphémère (état de
session, choses à observer) dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md` (I1–I17, O1–O15, A–F),
`docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (12/08/2026)

**Git sain** (vérifié) : `HEAD = main = origin/main = b4149ce`, tout est
commité, fusionné ET poussé ; `git branch --no-merged main` est **vide**. Le
protocole bats 27 → 28 fonctionne — rien à rattraper. Livré récemment (détail :
git) : files « À vérifier » personnes + animaux dans
`/sujets?vue=classification` ; audit O6 (encodage SigLIP par sous-lots de 4,
`SEMANTIC_LOCK` rendu entre deux) — **effet non observé**, pas encore un
acquis ; assurance-vie de la vérité terrain (`backup_verify` + export
`journal_jugements.jsonl`) — **dont l'échéance était cassée : corrigée en
session 6** (voir « À faire » n°2).

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine — au fil de l'eau, ce n'est PAS un blocage.**
   ~0,8 % de confirmations (91/12 072) ; instrumentation livrée, files garnies
   (18 personnes + 120 animaux). **Cadrage tranché par Mike (12/08)** : le
   stock n'est limité ni par l'outillage ni par la volonté, mais par la
   **connaissance** — beaucoup de groupes portent des visages que Mike ne sait
   pas nommer, et **Flo les nommera** quand l'outil sera à ~90 %. **300
   personnes sont déjà reconnues** : l'essentiel du travail humain est fait.
   On juge donc **quand l'occasion se présente**, et on avance ailleurs
   entre-temps. Métrique = erreurs découvertes, pas l'accord modèle-humain.
   Seule conséquence mécanique : le point 9 (algo) reste parqué — c'est un
   ordre de travaux, pas une dette.
2. **Observer en réel ce qui est livré** (modes opératoires :
   `PROMPT_NOUVELLE_SESSION.md`) : « Sauvegarde vérifiée : ok » (le plus
   important — jamais observé à ce jour), O6, seek vidéo mobile, test du Z.
3. **Éval tagging V2 — AVANT tout lot de renommage** (le banc de 150 photos est
   keyé par chemin ; renommer d'abord l'invaliderait). Protocole :
   `eval/PLAN_assertions_vs_pixels.md`. Si V2 confirme → câbler le **Knowledge
   Builder** (ADOPTÉ 31/07, jamais câblé) + créer la **version de pipeline
   tagging** manquante (audit D).
4. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos sur sa fiche,
   outillage livré : « Corriger » seuil ~0.2 ou « Nettoyer (référence) ») ;
   re-rejeter le groupe Caline une fois ; activer `gps_place`
   (`18 - …gazetteer.bat` → `enrichir_lieux.py` → `--ecrire` → redémarrer) ;
   **après l'éval V2** : lots de renommage (plan = 2114).
5. **Correctifs d'audit restants** : I4–I8, O7–O9, O11–O15 (dont purge de
   `photo_thumbs/` — le cache croît sans borne ; il est **gitignoré depuis le
   12/08**, il ne pollue plus `git status`). Résidu O1 : la section Lieux de
   `/sujets` charge 25 originaux `/media/…` au lieu de `/api/thumb` — à
   confirmer puis corriger.
6. **Navigation par similarité** : `/api/similar?key=` (cosinus sur vecteurs
   existants, bouton « semblables ») ; puis doublons proches bridés (>0,98 +
   même journée → quarantaine réversible, 50 paires jugées par Mike avant tout
   geste) ; rangée « même jour, autres années » (requête date, zéro IA).
7. **Extraction `ui/` — décision nette à prendre** : session dédiée `bundle.py`
   ou parcage explicite (item zombie ; préparatoire fait et vérifié, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets) ; seule piste : re-mesurer sur découpes SANS marge.
   Relancer si un nouveau nom d'animal apparaît en `personne:`.
9. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).**
   HDBSCAN/Chinese Whispers/AdaFace inévaluables à 0,8 % ; écrire les tags
   SigLIP = mutation XMP → exige la version de pipeline tagging (point 3).
10. **Données / finitions** : édition des réglages depuis `/reglages` ; 2ᵉ passe
    des 945 illisibles + `recuperees/` → NAS ; `docs/journaux/` gitignoré +
    purge des undo appliqués > 30 j (I12).
11. **À évaluer (discipline `vision-eval`)** : Florence-2 léger.

### Résiduels faible valeur (ne pas prioriser)
`/reglages` : Pause globale des workers ; retrait de l'ancien bandeau
`#pending`. `/pets` : libellé « empreintes calculées » (compteur depuis
démarrage, affiche 0 après redémarrage).

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Stockage** : SQLite local WAL (**43 048 entrées** au 12/08 — le 64 676 de
  la première version datait du 31/07, avant dédoublonnage et purges de dossiers
  cachés ; ce chiffre porte désormais sa date), embeddings BLOB, backup NAS
  snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers/Rangement** : `/browse` réversible, dédoublonnage appliqué
  (8,4 Go), rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles prêts (plan = 2114) ;
  `gps_place` codé (pas activé).
- **UI** : design system « chambre noire » (tokens, plancher a11y), planche
  contact, `/reglages`, `/people` réorganisé, `/sujets` guichet unique
  (sous-nav + onglet Classification + files « À vérifier » miroir
  personnes/animaux, clavier Espace/X/Z/lettre).
- **Correction** : faux positifs « Corriger »/« Nettoyer (référence) », retrait
  SÛR (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
- **Perf** : scoring vectorisé (156 s → qq s) ; `/api/thumb` (−98 % octets NAS,
  vérifié) ; `_send_file` Range/streaming (206 vérifié) ; workers sous
  ordonnanceur ; GpuArbiter 27/27.
- **Tagging** : `qwen3-vl:2b`, hybride assertions+image, 1 lecture
  exiftool/photo.
- **Hygiène** : nettoyage de session réversible (bat 29) ; commit guidé
  `SESSION_COMMIT.txt` (bat 27) ; fusion fast-forward sans checkout, serveur
  allumé (bat 28) ; **suppression des branches déjà fusionnées (bat 30)** —
  `git branch -d` refuse tout ce qui n'est pas dans `main`, donc sans risque.

## Réserve — futur, non prioritaire

Multi-utilisateur ; vidéo → audio ; serveur exposé en MCP (prérequis :
Knowledge Builder) ; bibliothèque Figma. **Vision** : mémoire familiale à
provenance — deux tests : « PC mort lundi, tout revit vendredi » et « aucun
fait affirmé sans provenance ». Récits LLM auto : écartés (hallucination).
