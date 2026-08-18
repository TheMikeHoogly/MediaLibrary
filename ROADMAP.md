# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; les invariants de méthode
dans `eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md` (I1–I17, O1–O15, A–F),
`docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (18/08/2026, session 20)

**Le scan rend enfin des comptes (chantier 10a).** `comptes_index.py` (module
PUR, 37 tests) branche un registre sur le **GOULOT** de l'index en mémoire —
`TrackedDict` dans `store_sqlite.py`, par où passe toute clé qui entre ou sort :
aucun retrait ne peut lui échapper. Chaque appelant **déclare son motif**
(`scan:disparus`, `scan:modifies`, `purge:cles_fantomes`,
`demarrage:dossiers_caches`, `rekey`, `tagging`) ; ce qui retire **sans** motif
tombe dans un bucket nommé, avec des exemples de clés. Et chaque cycle de scan
est **réconcilié** : `inexpliqué = (fin − début) − (ajouts − retraits)`. Non nul
= l'index a changé de taille **hors du goulot** — précisément le chiffre qui
manquait aux −250 du 17/08. Lecture : `/reglages` (panneau « Comptes de
l'index ») et `GET /api/maint/status` (clé `oublis`). L'étape 4 de `_sync_dir`
dit désormais `n/demandées`, et non plus un silence quand `n = 0`.

**LIVRÉ, PAS ENCORE OBSERVÉ EN RÉEL** : tant qu'aucun cycle n'a tourné chez
Mike, l'instrument est une promesse — pas un acquis.

**Rappel de la session 19** (détail : git et `eval/DECISIONS.md`) : **72** dates
de SCAN comptées en base contre 12 connues ; le désaccord des deux chemins a
livré le repli sur le NOM non gardé (1 cas) et **15 noms périmés** ; l'asymétrie
du garde-fou protège **1 369** dates antérieures. Rien n'a été corrigé — la
décision reste ouverte (point 10b).

## À faire — par ordre de valeur

1. **Vérité terrain humaine — au fil de l'eau, PAS un blocage.** ~0,8 % de
   confirmations (91/12 072). **Cadrage Mike (12/08)** : le stock est limité par
   la CONNAISSANCE, pas par l'outillage — Flo nommera ce que Mike ne sait pas
   nommer, quand l'outil sera à ~90 %. Métrique = erreurs découvertes.
2. **Observer en réel ce qui est livré** — **fait ✔**. Reste : re-upload = une
   entrée, seek vidéo mobile, test du Z.
3. **Chaîne « noms → descriptions → recherche » — 3a, 3b, 3c CLOS le 16/08.**
   La re-passe ne se fera pas. Reste ouvert, et c'est NEUF : **le prompt de
   PRODUCTION est celui qui hallucine le plus.** V2CTX est en prod depuis le
   12/08 sur la foi d'un 25-15 ; le banc de 147 photos confirme la préférence
   mais montre le coût. Toute photo taguée à partir de maintenant le paie.
   **Ne pas revenir à V0 sans protocole.** Wagon de 14 : composition d'affichage
   date · lieu · noms depuis `faits`.
4. **Gestes Mike** : `gps_place` ✔ ; renommage appliqué ✔ (7 058) ; nettoyer
   Flo (5 909 photos ; « Corriger » ~0.2 ou « Nettoyer (référence) ») ;
   re-rejeter Caline une fois.
5. **Correctifs d'audit** : I4–I8, O7–O9, O11–O15. O1 clos partout ; O15 (purge
   de `photo_thumbs/`) gagne en poids.
6. **Navigation par similarité et par date** : « Semblables » et « même jour »
   livrés et observés. Reste : doublons proches bridés (>0,98 + même journée →
   quarantaine réversible, 50 paires jugées avant tout geste). ±1 j non décidé.
7. **Extraction `ui/`** : décision nette à prendre — session dédiée `bundle.py`
   ou parcage explicite (item zombie ; préparatoire fait, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nouveau nom d'animal sort en `personne:`.
9. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).**
   HDBSCAN/Chinese Whispers/AdaFace inévaluables à 0,8 %. La barrière reste.
10. **Données / finitions.** Trois chantiers, dans cet ordre :
    (a) **Compter ce que le scan OUBLIE — INSTRUMENT LIVRÉ (18/08), À
    OBSERVER.** Reste : lire `/reglages` après quelques cycles. Un « (non
    declare) » ou un écart inexpliqué non nul EST la piste ; zéro partout ferme
    le sujet. Rien à décider avant d'avoir vu un chiffre en réel.
    (b) **Dates de scan : mesurées (72), correction NON décidée.** Corriger
    `taken` en base touche le pipeline de dates (`monolith-surgery`) et demande
    un backfill ; 72 photos mal triées en sont l'enjeu, contre 1 369 dates
    antérieures à ne surtout pas emporter avec. Deux sous-chantiers moins chers
    et indépendants : garder l'étape 2 du repli (le NOM, 1 cas) et rendre au
    plan de renommage les 15 noms périmés. Rien n'est fait tant que ce n'est pas
    observé en réel.
    (c) Réglages éditables depuis `/reglages` (wagon : pause globale des
    workers) ; 2ᵉ passe des 945 illisibles + `recuperees/` → NAS ; purge des
    undo > 30 j (I12) ; deux images TRONQUÉES (`Sanetsch/DSC00550.JPG`,
    `France & Belgique/DSC00795.JPG`) en attente d'encodage à chaque démarrage,
    visibles dans `erreurs_images`.
11. **UI — harmonisation des vues (demandé 12/08, skill `photo-ui`)** :
    (a) clic sur l'image d'une personne → sa démo aléatoire ; (b) lieux : texte
    sous l'image en tooltip ; (c) harmoniser visages/lieux/animaux — mêmes
    fonctions partout, **sauf** l'effacement, réservé à Classification ;
    (d) zoom pinch + molette — `maximum-scale=1` retiré ✔ (WCAG 1.4.4) ;
    (e) wagons : bandeau `#pending`, libellé `/pets`, et le bouton qui dit
    « Meme jour (14 aout) » là où la page dit « 14 août ».
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** Test « PC mort
    lundi, tout revit vendredi » : restaurer le snapshot NAS sur un dossier
    vierge, chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`). Tant qu'il n'a pas tourné, la sauvegarde
    « vérifiée » est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08).** Recherche,
    fiches et `faits` sourcés en outils MCP locaux (JSON-RPC stdio, zéro
    dépendance — skill `mcp-builder`). Écriture plus tard. Briques de 14a.
14. **Recherche IA locale contextuelle.** (a) **Déterministe — LIVRÉ ET OBSERVÉ**,
    vecteurs orphelins purgés. Manques : les `faits` ne filtrent pas encore (le
    lieu passe par `gps_places` + chemin) ; pas de filtre espèce ni fiche ; le
    tri sans mot-clé reste `_best_time` (donc `mtime`) là où la sélection
    l'exclut. (b) ensuite seulement, **escalade ponctuelle** vers un modèle
    chargé à la demande (bail GpuArbiter, déchargé après) — `vision-eval`,
    jamais câblé sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger. **Parqué** faute
    d'hypothèse — le banc 3b a montré que les faits en contexte n'achètent pas
    la description.

### Résiduels faible valeur (ne pas prioriser)
**MESURÉ le 15/08, et c'est pourquoi on n'y touche pas** : `meme_jour.ANNEE_MIN`
coûte **0 photo**, mais seulement parce que `_fname_time` refuse déjà une année
< 1990 lue dans le NOM DE FICHIER, ce qui coûte **7 photos**. **Couplés** : qui
touche l'un touche l'autre. Chiffrés et non traités (14/08) : (a) le plancher
1990 subsiste dans `plan_rangement.py`, `recensement_doublons.py`,
`diagnostic_dates.py` — sans effet tant qu'aucun dossier d'avant 1990 n'y passe ;
(b) `/files?dir=1&rec=1` (racine NAS) ne répond pas en 6 min, cause non cherchée.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Stockage** : SQLite local WAL (**43 064 entrées**), embeddings BLOB, backup
  NAS snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers/Rangement** : `/browse` réversible, dédoublonnage appliqué
  (8,4 Go), rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles ; **7 058 renommages
  appliqués et observés** (0 sauté, noms humains intacts) ; `gps_place` actif
  dans les noms (1 175 en portent un) ; garde-fou date de SCAN
  (`date_de_scan_presumee`, asymétrique, toléré à un an).
- **UI** : design system « chambre noire » (tokens, plancher a11y), planche
  contact, `/reglages`, `/people`, `/sujets` guichet unique (Classification,
  files « À vérifier », clavier Espace/X/Z/lettre).
- **Correction** : faux positifs « Corriger »/« Nettoyer (référence) », retrait
  SÛR (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
- **Perf** : scoring vectorisé (156 s → qq s) ; `/api/thumb` (−98 % octets NAS) ;
  `_send_file` Range/streaming ; workers sous ordonnanceur ; GpuArbiter 27/27.
- **Tagging** : `qwen3-vl:2b`, prompt v2ctx ; Knowledge Builder : faits
  noms/date/lieu structurés et sourcés (`faits`), noms JAMAIS via le prompt ;
  `TAGGING_PIPELINE_VERSION` estampillée (`pipe`) ; 1 lecture exiftool/photo.
- **Index/vecteurs** : cascade `forget_everywhere` au scan ; **2 374 vecteurs
  orphelins purgés et observés** (0 muet sur 1 600 résultats, contre 2,6 %),
  quarantaine réversible `_corbeille_vecteurs/`.
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, trois tâches de
  fond EXIF (dates, noms, GPS) — état, avancement et « fichiers muets » dans
  `/reglages` ; comptes de l'index au goulot (`comptes_index.py`, à observer).
- **Mesure** : `mesure_dates_scan.py` — dates de scan en base, lecture seule sur
  copie, deux chemins indépendants.
- **Hygiène** : nettoyage réversible (bat 29), commit guidé `SESSION_COMMIT.txt`
  (27), fusion fast-forward serveur allumé (28), purge des branches fusionnées
  (30). Ordre **27 → 0 → 28** : on ne fusionne qu'après observation en réel.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — avec un **déclencheur nommé** : un « mode Flo » minimal
  (file de nommage des visages qu'elle seule sait nommer), à ouvrir quand l'outil
  est à ~90 %. C'est lui qui débloque la vérité terrain.
- **Vidéo → audio** — coût élevé, valeur incertaine, aucun déclencheur en vue.
- **Bibliothèque Figma** — le design system vit déjà dans le code ; un miroir
  serait de la doc à double entretien sans consommateur.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).
