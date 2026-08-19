# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`,
`docs/RANGEMENT_2026.md`.

## État (19/08/2026, session 24)

**Session 23** : 10a, 10b et 14a CLOS et observés — détail dans git et
`eval/DECISIONS.md`. Reste NON DÉCIDÉ : corriger `taken` en base (**72** photos
contre **1 369** dates antérieures).

**Git : guichet unique.** Les bats 27, 28 et 30 sont fondus dans
`27 - Git.bat` — état du dépôt + geste conseillé, commit de session, fusion
fast-forward sans checkout, purge des branches, ouverture GitHub. Leur code est
repris tel quel ; les trois anciens sont dans `_bat_archive/`, les y reprendre
suffit à revenir en arrière. **Non observé en réel** : Mike ne l'a pas lancé.

**Backfill des `faits` : la matière est MESURÉE** (`mesure_faits_backfill.py`,
lecture seule sur COPIE, 17 tests). `faits` couvre **81** entrées sur 43 064 ;
un backfill déterministe en porterait **42 974 (99,79 %)** — **et ce chiffre
est une alarme, pas un succès** : **12 752 (29,61 %)** n'auraient que la DATE.
Le chiffre honnête est **30 222 (70,18 %)** avec au moins un fait NON-date. Par
type : personne **18 863**, lieu **13 757** (6 595 GPS + 7 162 chemin), espèce
**4 750**, animal **935**, date **42 773** (dont **3 995** par la seule année du
dossier). **90** entrées resteraient muettes.

**Deux constats qui commandent la conception.** (a) `faits` est un
**INSTANTANÉ, pas une vue** : sur les 81 déjà pourvues, **12 divergent** de ce
que dit l'index aujourd'hui — des noms écrits en juin et retirés depuis (Flo).
Un backfill écrit une fois se périmera exactement pareil. (b) **Le lieu ne doit
pas être backfillé par le miroir du renommage** : `resolve_path_place` teste une
SOUS-CHAÎNE — **577** photos reçoivent un lieu collé à l'intérieur d'un mot,
dont **442 « Ins » depuis « Cousins&Cousines »** et 13 « Orbe » depuis
« Vallorbe ». La règle du KB (`server._lieu_pour_cle`) compare des segments
ENTIERS et n'a pas ce défaut. Déjà réalisé dans des noms de fichiers : **6** —
latent, pas encore payé.

## À faire — par ordre de valeur

1. **Vérité terrain humaine — au fil de l'eau, PAS un blocage.** ~0,8 %
   (91/12 072). **Cadrage Mike (12/08)** : le stock est limité par la
   CONNAISSANCE, pas par l'outillage — Flo nommera ce que Mike ne sait pas
   nommer, quand l'outil sera à ~90 %. Métrique = erreurs découvertes.
2. **Observer en réel ce qui est livré** — **fait ✔**. Reste : re-upload = une
   entrée, seek vidéo mobile, test du Z.
3. **Chaîne « noms → descriptions → recherche » — 3a, 3b, 3c CLOS le 16/08.**
   La re-passe ne se fera pas. Reste ouvert : **le prompt de PRODUCTION est
   celui qui hallucine le plus.** V2CTX est en prod depuis le 12/08 sur la foi
   d'un 25-15 ; le banc de 147 photos montre le coût — toute photo taguée le
   paie. **Pas de retour à V0 sans protocole.** Wagon de 14 : affichage
   date · lieu · noms depuis `faits`.
4. **Gestes Mike** : `gps_place` ✔ ; renommage appliqué ✔ (7 058) ; nettoyer
   Flo (5 909 photos ; « Corriger » ~0.2 ou « Nettoyer ») ; re-rejeter Caline.
5. **Correctifs d'audit** : I4–I8, O7–O9, O11–O15. O1 clos ; O15 (purge de
   `photo_thumbs/`) gagne en poids.
6. **Navigation par similarité et par date** : « Semblables » et « même jour »
   livrés et observés. Reste : doublons proches bridés (>0,98 + même journée →
   quarantaine réversible, 50 paires jugées avant tout geste).
7. **Extraction `ui/`** : décision nette à prendre — session dédiée `bundle.py`
   ou parcage explicite (item zombie ; préparatoire fait, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nom d'animal sort en `personne:`.
9. **Reconnaissance — algo.** BARRIÈRE : vérité terrain ≥ ~5 %. HDBSCAN /
   Chinese Whispers / AdaFace inévaluables à 0,8 %.
10. **Données / finitions.** Trois chantiers, dans cet ordre :
    (a) **Compter ce que le scan OUBLIE — CLOS (18/08).** Trois constats
    mineurs, non traités : un ajout découvert PAR LE SCAN est étiqueté
    `tagging` (c'est la mise en file qui crée la clé) ; `dict.__ior__` n'est pas
    redéfini dans `TrackedDict` (aucun usage, vérifié) ; `cycles_vus` est la
    longueur d'un anneau de 10, pas un compteur — il affiche « 10 » à vie.
    (b) **Garde-fou du repli sur le NOM + reprise des noms périmés — CLOS
    (19/08), observé.** Reste : **correction de `taken` en base NON décidée**
    — elle touche le pipeline de dates (`monolith-surgery`) et exige un
    backfill, pour 72 photos, contre 1 369 dates antérieures à ne pas emporter.
    (c) Réglages éditables depuis `/reglages` (wagon : pause globale des
    workers) ; 2ᵉ passe des 945 illisibles + `recuperees/` → NAS ; purge des
    undo > 30 j (I12) ; deux images TRONQUÉES en attente d'encodage à chaque
    démarrage, visibles dans `erreurs_images`.
11. **UI — harmonisation des vues (demandé 12/08, skill `photo-ui`)** :
    (a) clic sur l'image d'une personne → sa démo aléatoire ; (b) lieux : texte
    sous l'image en tooltip ; (c) harmoniser visages/lieux/animaux — mêmes
    fonctions partout, **sauf** l'effacement, réservé à Classification ;
    (d) zoom pinch + molette — `maximum-scale=1` retiré ✔ (WCAG 1.4.4) ;
    (e) wagons : bandeau `#pending`, libellé `/pets`, le bouton qui dit
    « Meme jour (14 aout) » là où la page dit « 14 août », et « Date ↑ » qui
    reste allumé sur `/files?q=` alors que l'ordre affiché est celui du serveur.
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** « PC mort lundi,
    tout revit vendredi » : restaurer le snapshot NAS sur un dossier vierge,
    chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`). Tant qu'il n'a pas tourné, la sauvegarde
    « vérifiée » est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08).** Recherche,
    fiches et `faits` en outils MCP locaux (JSON-RPC stdio, zéro dépendance —
    skill `mcp-builder`). Écriture plus tard. Briques de 14a.
14. **Recherche IA locale contextuelle.** (a) **Déterministe — LIVRÉ ET
    OBSERVÉ** : vecteurs orphelins purgés ; une seule règle de date pour filtrer
    ET trier, partout (19/08). Le manque suivant n'est pas le filtre mais la
    MATIÈRE, et elle est désormais **mesurée** (voir l'État) : `faits` = 81
    entrées ; un backfill déterministe en porterait 42 974, dont seulement
    **30 222 avec un fait NON-date**. Ordre : **backfill d'abord** (pur, sans
    GPU ni VLM ni NAS, chaque fait portant sa VRAIE source — `index` pour les
    noms), **lieu par la règle du KB et non par le miroir du renommage**,
    `espece` à part (elle vient des détections) ; **le filtre ensuite**, mesuré
    sur la couverture réelle. À trancher avant d'écrire : un champ figé se
    périme (12 des 81 divergent déjà) — recalcul à la demande, ou re-backfill
    à chaque correction de nom.
    (b) ensuite seulement, **escalade ponctuelle** vers un modèle
    chargé à la demande (bail GpuArbiter, déchargé après) — `vision-eval`,
    jamais câblé sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger. **Parqué** faute
    d'hypothèse — le banc 3b a montré que les faits en contexte n'achètent pas
    la description.

### Résiduels faible valeur (ne pas prioriser)
**MESURÉ le 15/08, et c'est pourquoi on n'y touche pas** : les deux planchers
1990 (`_fname_time`, `meme_jour.ANNEE_MIN`) coûtent **7** photos et **0**, et
ils sont **couplés** ; le plancher 1990 subsiste aussi dans `plan_rangement.py`,
`recensement_doublons.py`, `diagnostic_dates.py`, sans effet tant qu'aucun
dossier d'avant 1990 n'y passe. Le **plafond 2100** d'une date lue dans un NOM
(`22082010141.jpg` → « 2082 ») : **72** en base, **coût 0** — uniquement parce
qu'elles portent un `taken` et que `_best_time` prend `min()`. Enfin
`/files?dir=1&rec=1` (racine NAS) ne répond pas en 6 min, cause non cherchée.

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
  contact, `/reglages`, `/people`, `/sujets` guichet unique (clavier
  Espace/X/Z/lettre).
- **Correction** : faux positifs « Corriger »/« Nettoyer (référence) », retrait
  SÛR (`untag`→`exclude`), `exclude` autorité partout + auto-guérison.
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
  fond EXIF (dates, noms, GPS) dans `/reglages` ; comptes de l'index au goulot
  (`comptes_index.py`, observé).
- **Recherche** : quatre dimensions (noms · lieux · période · sens) ; une seule
  règle de date pour filtrer ET trier (`recherche.py`, pur).
- **Mesure** : `mesure_dates_scan.py`, `mesure_tri_recherche.py`,
  `mesure_faits_backfill.py` — lecture seule sur COPIE, jamais sur `photos.db`.
- **Hygiène** : nettoyage réversible (29) ; **tout git dans `27 - Git.bat`**,
  guichet unique — état du dépôt + geste conseillé, commit guidé, fusion
  fast-forward sans checkout, purge des branches, GitHub. Ordre **1 → 0 → 2** :
  on ne fusionne qu'après observation en réel.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — avec un **déclencheur nommé** : un « mode Flo » minimal
  (file de nommage des visages qu'elle seule sait nommer), à ouvrir quand l'outil
  est à ~90 %. C'est lui qui débloque la vérité terrain.
- **Vidéo → audio** : coût élevé, valeur incertaine, aucun déclencheur en vue.
- **Bibliothèque Figma** : le design system vit dans le code ; un miroir serait
  de la doc à double entretien sans consommateur.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).
