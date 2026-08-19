# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`,
`docs/RANGEMENT_2026.md`.

## État (19/08/2026, session 23)

**10a et 10b CLOS, observés.** Le registre des comptes de l'index tient (12
cycles à zéro + contrôle positif) ; les **15** renommages périmés sont appliqués,
0 date de scan réinscrite, noms intacts, plan régénéré à **0**. Portée honnête
du registre : les −250 du 17/08 sont apparus SOUS CHARGE — les zéros disent
« rien ne fuit », pas « rien ne peut fuir ». Reste NON DÉCIDÉ : corriger `taken`
en base (**72** photos contre **1 369** dates antérieures).

**14a — le `mtime` ne classe plus rien, et c'est OBSERVÉ.** Le FILTRE le
refusait depuis le 15/08 ; le TRI le gardait, dans les trois vues. Mesuré sur
COPIE (43 064 entrées, `mesure_tri_recherche.py`) : **259** photos sans aucune
date sûre, **257** datées de 2026 par leur propre tagging, en tête de **56 des
364 noms** et de **31 dossiers sur 665** (`Photos\Nikola` : 43 sur 54, deux
dossiers entièrement muets). **32** n'ont pas même un `mtime` : l'ancienne clé
(`… or ''`) mélangeait `float` et `str` et **l'ancien tri ne s'exécutait pas**
sur l'index entier (TypeError → 500), sans qu'aucun NOM ne le déclenche (0/364 ;
chemin par LIEU non mesuré — plancher, pas total).

Corrigé par `recherche.trier_chronologique` (pur) : date précise, sinon année du
DOSSIER, jamais `mtime` ; sans-date en FIN et **comptées**. `/files?q=`, qui se
taisait là où `/api/search` parlait, reçoit le même `detail`. **En réel** :
`sans_date_tri` = **53 · 43 · 29 · 29 · 21** (Véronique, Nikola, Mike, Marie,
Sandra), au chiffre près la mesure ; et sur `dir=1/Nikola`, **20 des 20
premières** étaient muettes en décroissant, **0 sur 11** désormais.

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
   (18 % faux rejets). Relancer si un nouveau nom d'animal sort en `personne:`.
9. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).** HDBSCAN /
   Chinese Whispers / AdaFace inévaluables à 0,8 %. La barrière reste.
10. **Données / finitions.** Trois chantiers, dans cet ordre :
    (a) **Compter ce que le scan OUBLIE — CLOS (18/08).** Trois constats
    mineurs, non traités : un ajout découvert PAR LE SCAN est étiqueté
    `tagging` (c'est la mise en file qui crée la clé) — juste pour « qui
    retire », trompeur pour « qui ajoute » ; `dict.__ior__` n'est pas redéfini
    dans `TrackedDict` (seul chemin qui contredit « aucune clé n'échappe » —
    aucun usage, vérifié) ; `cycles_vus` est la longueur d'un anneau de 10, pas
    un compteur : il affiche « 10 » à vie.
    (b) **Garde-fou du repli sur le NOM + reprise des noms périmés — CLOS
    (19/08), observé.** Reste : **correction de `taken` en base NON décidée**
    — elle touche le pipeline de dates (`monolith-surgery`) et exige un
    backfill, pour 72 photos, contre 1 369 dates antérieures à ne pas emporter.
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
    ET trier, partout (19/08). **Le manque suivant n'est PAS le filtre, c'est la
    MATIÈRE — compté le 19/08** : `faits` ne couvre que **81** entrées sur
    43 064 (**0,19 %**), exactement les 81 estampillées `v2ctx|kb1` ; les 42 983
    autres n'ont aucun `pipe`. Filtrer dessus rendrait presque rien EN AYANT
    L'AIR DE MARCHER. Or le matériau est déjà en base pour **37 999** photos
    (18 863 `personne:`, 32 838 dates, 6 614 GPS, 935 animaux) : un **backfill
    DÉTERMINISTE**, sans GPU ni VLM, est le préalable — chaque fait y portant sa
    VRAIE source (« index »), pas celle d'un tagging qui n'a pas eu lieu.
    `espece` dépend en plus des détections : à traiter à part. Ensuite
    seulement : filtre par espèce, par fiche.
    (b) ensuite seulement, **escalade ponctuelle** vers un modèle
    chargé à la demande (bail GpuArbiter, déchargé après) — `vision-eval`,
    jamais câblé sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger. **Parqué** faute
    d'hypothèse — le banc 3b a montré que les faits en contexte n'achètent pas
    la description.

### Résiduels faible valeur (ne pas prioriser)
**MESURÉ le 15/08, et c'est pourquoi on n'y touche pas** : `meme_jour.ANNEE_MIN`
coûte **0 photo**, mais seulement parce que `_fname_time` refuse déjà une année
< 1990 lue dans le NOM, ce qui coûte **7 photos** — **couplés**. Chiffrés et non
traités : (a) le plancher 1990 subsiste dans `plan_rangement.py`,
`recensement_doublons.py`, `diagnostic_dates.py`, sans effet tant qu'aucun
dossier d'avant 1990 n'y passe ; (b) `/files?dir=1&rec=1` (racine NAS) ne répond
pas en 6 min, cause non cherchée ; (c) **plafond 2100 de la date lue dans un
NOM** (`_fname_time`, `fname_datetime`) : `22082010141.jpg` (DDMMYYYY +
séquence) se lit « 2082-01-01 ». **72** en base, **coût 0** — mais uniquement
parce que les 72 portent un `taken` et que `_best_time` prend `min()` ; une
seule sans `taken` serait datée du futur.

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
- **Mesure** : `mesure_dates_scan.py`, `mesure_tri_recherche.py` — lecture seule
  sur COPIE, jamais sur `photos.db`.
- **Hygiène** : nettoyage réversible (29), commit guidé (27), fusion
  fast-forward (28), purge des branches fusionnées (30). Ordre **27 → 0 → 28** :
  on ne fusionne qu'après observation en réel.

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
