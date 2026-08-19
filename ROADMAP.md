# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (19/08/2026, session 26)

**Le lieu n'a plus qu'UNE règle — et c'est celle qu'on voit.** `places_list` et
`_cles_du_lieu` (`/sujets` + recherche) testaient une sous-chaîne ; elles
délèguent à `faits_vue.lieux_du_chemin`. **Observé après redémarrage** :
« Ins » **493 → 5**, recherche **499 → 11 dont 0** venant de
« Cousins&Cousines » (32 sur 80 avant), page **2 119 → 1 539 ms**.

`mesure_lieu_visible.py` a corrigé la règle elle-même : **les 876 « collés »
n'étaient pas tous faux**. « Yani2004 » (219), « AchumaniAlto » (48),
« CuevaMarkusIrpavi » (6) sont de VRAIS lieux collés à l'année ou au sujet —
~330 que les segments entiers auraient emportés avec les 546 faux. La règle
découpe donc les mots sur les frontières de CASSE et de CHIFFRES (« Vallorbe »
reste entier, « Cousins&Cousines » ne rend jamais « Ins »), essaie les groupes
de mots contigus et garde le trait d'union. Gains nets : **Sud France 315,
San Borja 82, Vallée d'Aoste 81, Rurrenabaque 55** (libellé ajouté à
`lieux.txt`) ; « France & Belgique » compte pour **les deux** (574 · 157). Le
nom de FICHIER compte aussi : 52 vrais contre 9 faux qu'aucune règle
syntaxique n'attrapera (« Grupo en la Laguna »). Coût tenu par mémoïsation des
segments — les noms de fichiers, uniques, restent hors cache.

**`taken` en base : REJETÉ ; le garde-fou passe à la LECTURE.** 72 dates de
scan contre **1 347** antérieures légitimes — et `taken` est une LECTURE de
l'EXIF : la réécrire lui ôterait sa provenance. `faits_vue.date_credible` est
injecté dans `meme_jour.epoch_precis` : **70 photos** perdent une date précise
fausse et retombent sur l'année du dossier. `_best_time` en était une COPIE —
la galerie datait de 2006 ce que la recherche datait déjà de 1985. Observé :
`Photos Papa\1983\20150810_…` a quitté le « 10 août ».

**Pas encore observé** : la branche KB de `faits_vue` (`pending` = 0, aucun
tagging depuis) — le premier tagging sera son observation.

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
   **Pas de retour à V0 sans protocole.** Wagon de 14 : affichage
   date · lieu · noms depuis `faits`.
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
    Reste, dans cet ordre : **(iii) brancher la vue** là où le point 3 l'attend
    (affichage date · lieu · noms), index inversé des noms construit UNE fois
    par balayage ; **(iv) le filtre**, mesuré sur **69,14 %** (photos avec un
    fait NON-date), jamais sur 99,79 %.
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
  contact, `/reglages`, `/people`, `/sujets` guichet unique.
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
- **Hygiène** : nettoyage réversible (29) ; **tout git dans `27 - Git.bat`**,
  guichet unique — état dépôt + serveur, commit guidé, redémarrage, fusion
  fast-forward sans checkout, purge des branches, GitHub. Ordre **1 → 7 → 2** :
  on ne fusionne qu'après observation en réel.

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
