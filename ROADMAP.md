# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; l'éphémère (état de
session, choses à observer) dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md` (I1–I17, O1–O15, A–F),
`docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (13/08/2026, session 12)

**Résidu O1 : soldé et OBSERVÉ BON en réel** — `/sujets` section Lieux,
25 cartes sur 25 en `/api/thumb`, **1 007 Ko et 315 ms pour les 25** (contre
~60 Mo d'originaux). `fix/lieux-thumb` committée et fusionnée. Avant :
purge des doublons (43 067 pile) et bouton « Semblables », observés bons
aussi. Reste un test d'occasion : au prochain upload téléphone, une photo =
UNE entrée.

**Session 12 — TROIS tâches de fond mortes en silence depuis toujours**
(`fix/backfills-silencieux`, à commiter). Parti pour le chantier 6a, on a
mesuré la matière première : **12 407 photos (29 %) sans date au jour près**,
**42 060 entrées sur 43 067 jamais lues**. Cause (`diagnostic_dates.py`) :
garde `if not EXIFTOOL: return` placée AVANT le `sleep`, alors que `EXIFTOOL`
est affecté par `maintenance_loop` lancé dans le même souffle — `backfill_dates`,
`backfill_gps` et surtout `reimport_name_tags` (rapatriement des noms XMP,
invariant n° 2 : **jamais** tournée, aucun `namechk`) renonçaient en
microsecondes, à chaque démarrage. Corrigé + trois garde-fous nés de la
relecture : aucune écriture pour un fichier dont ExifTool n'a pas parlé ; la
date de SCAN ne passe plus pour la prise de vue ; passes sérialisées
(dates → noms → GPS) et comptes rendus dans `/reglages`. **Rien n'est observé
en réel : tout se joue au prochain bat 0** — premier démarrage long.

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine — au fil de l'eau, ce n'est PAS un blocage.**
   ~0,8 % de confirmations (91/12 072) ; instrumentation livrée, files garnies
   (18 personnes + 120 animaux). **Cadrage tranché par Mike (12/08)** : le
   stock est limité par la **connaissance**, pas par l'outillage ni la volonté
   — beaucoup de groupes portent des visages que Mike ne sait pas nommer, et
   **Flo les nommera** quand l'outil sera à ~90 %. **300 personnes déjà
   reconnues** : l'essentiel du travail humain est fait. On juge donc **quand
   l'occasion se présente**. Métrique = erreurs découvertes, pas l'accord
   modèle-humain. Conséquence : le point 9 (algo) reste parqué — ordre de
   travaux, pas dette.
2. **Observer en réel ce qui est livré** : v2ctx/Knowledge Builder **fait ✔**,
   purge des 19 doublons **fait ✔**, bouton « Semblables » **fait ✔**,
   vignettes Lieux **fait ✔** (13/08) ; **à observer en tête de la prochaine
   session : les trois tâches de fond réparées** (`/reglages` → trois cartes ;
   puis relancer `diagnostic_dates.py` : les 12 407 sans date doivent
   s'effondrer, `taken absent` tomber près de 0, et `namechk` exister). Reste :
   re-upload = une entrée, seek vidéo mobile, test du Z. Veille v2ctx sur un
   lot plus grand : identifications astre/objet, fuite de la date en prose —
   tout geste de prompt passe par `vision-eval`.
3. **Knowledge Builder + version de pipeline : CÂBLÉS (s8) et OBSERVÉS (s9)** —
   suite naturelle : composition d'affichage date · lieu · noms depuis `faits`
   (choix tranché : structuré d'abord, affichage plus tard) ; re-tagging
   opt-in des entrées v0 si la qualité observée le justifie (~51 h GPU,
   jamais automatique).
4. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos ; « Corriger »
   seuil ~0.2 ou « Nettoyer (référence) ») ; re-rejeter Caline une fois ;
   activer `gps_place` (`18 - …gazetteer.bat` → `enrichir_lieux.py` →
   `--ecrire` → redémarrer) — profite du backfill GPS enfin réparé ; lots de
   renommage **débloqués** (plan = 2114 ; le banc `eval/tagging_v1.json`, keyé
   par chemin, en deviendra partiellement caduc — attendu).
5. **Correctifs d'audit restants** : I4–I8, O7–O9, O11–O15. **O1 clos
   partout** (s11, observé s12). O15 (purge de `photo_thumbs/`, cache sans
   borne, gitignoré depuis le 12/08) gagne en poids : toutes les grilles
   l'alimentent désormais.
6. **Navigation par similarité** : `/api/similar` + page `/files?sim=` +
   bouton « Semblables » **livrés et OBSERVÉS BONS (13/08)** ; restent :
   doublons proches bridés (>0,98 + même journée → quarantaine réversible,
   50 paires jugées avant tout geste) ; rangée « même jour, autres années »
   — **bloquée tant que le backfill des dates n'est pas observé** : sur la base
   d'aujourd'hui elle rassemblerait des milliers de photos sous un 1er janvier
   qui n'a jamais existé. À bâtir sur les dates PRÉCISES uniquement, jamais sur
   le repli « année du dossier ». Aucune brique nouvelle (`similar_by_key`).
7. **Extraction `ui/` — décision nette à prendre** : session dédiée `bundle.py`
   ou parcage explicite (item zombie ; préparatoire fait et vérifié, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets) ; seule piste : re-mesurer sur découpes SANS marge.
   Relancer si un nouveau nom d'animal apparaît en `personne:`.
9. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).**
   HDBSCAN/Chinese Whispers/AdaFace inévaluables à 0,8 % ; écrire les tags
   SigLIP = mutation XMP → la version de pipeline tagging existe désormais
   (session 8), la barrière vérité terrain reste.
10. **Données / finitions** : édition des réglages depuis `/reglages` (wagon :
    Pause globale des workers, résiduel rattaché le 12/08) ; 2ᵉ passe des 945
    illisibles + `recuperees/` → NAS ; `docs/journaux/` gitignoré + purge des
    undo appliqués > 30 j (I12).
11. **UI — harmonisation des vues (demandé 12/08, skill `photo-ui`)** :
    (a) personnes : clic sur l'image d'une personne → lancer sa démo aléatoire ;
    (b) lieux : le texte sous chaque image d'un dossier lieu passe en tooltip
    (gain de place dans la grille) ; (c) harmoniser les possibilités
    d'affichage visages/lieux/animaux — le maximum de fonctionnalités pour
    tous, **sauf** l'effacement d'image, réservé à l'onglet Classification ;
    (d) zoom/redimensionnement des images aux doigts (pinch) et à la souris
    (molette) dans les démos et l'affichage plein écran ; (e) wagons résiduels
    rattachés le 12/08 : retrait de l'ancien bandeau `#pending`, libellé
    `/pets` « empreintes calculées » (affiche 0 après redémarrage).
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** Le test « PC mort
    lundi, tout revit vendredi » : restaurer le snapshot NAS sur un dossier
    vierge, chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`, aujourd'hui locale et gitignorée). Tant que ce
    drill n'a pas tourné une fois, la sauvegarde « vérifiée » est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08, prérequis
    soldé).** Recherche (sémantique + tags), fiches personnes/animaux et
    `faits` sourcés en outils MCP locaux (JSON-RPC stdio, zéro dépendance —
    skill `mcp-builder`) : interroger la bibliothèque depuis une conversation
    Claude, premier fruit concret de la provenance. Écriture : plus tard, après
    usage réel en lecture.
14. **Recherche IA locale contextuelle (demandé 12/08).** Le champ de
    recherche comprend une demande en langage naturel et la décompose. Ordre :
    (a) **déterministe** d'abord — parser en filtres structurés depuis
    l'existant (noms = fiches, dates, lieux = `gps_place`/`faits`, tags, reste
    → SigLIP) : zéro GPU, couvre l'essentiel ; (b) ensuite seulement,
    **escalade ponctuelle** vers un modèle chargé à la demande (bail
    GpuArbiter, 4 Go, déchargé après). Modèle et seuil = éval `vision-eval`,
    jamais câblé sans mesure. Mêmes briques que le MCP (13).
15. **À évaluer (`vision-eval`)** : Florence-2 léger.

### Résiduels faible valeur (ne pas prioriser)
Vidé le 12/08 : les trois résiduels sont rattachés en wagons aux chantiers 10
(Pause globale des workers) et 11e (bandeau `#pending`, libellé `/pets`).

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
- **Tagging** : `qwen3-vl:2b`, prompt v2ctx (assertions en contexte, sans
  impératif — éval 12/08) ; Knowledge Builder : faits noms/date/lieu structurés
  et sourcés (`faits`), noms JAMAIS via le prompt (fusion `_noms_attendus`,
  exclude = autorité) ; `TAGGING_PIPELINE_VERSION` estampillée (`pipe`) ;
  1 lecture exiftool/photo (élargie à la date de prise de vue).
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, et depuis le
  13/08 les **trois tâches de fond EXIF** (dates, noms, GPS) — état, avancement
  et « fichiers muets » dans `/reglages`. Leçon acquise : *un travail de fond
  qui ne rend pas de comptes finit par ne plus travailler du tout*, et personne
  ne le voit. Trois l'ont fait pendant des mois.
- **Hygiène** : nettoyage de session réversible (bat 29) ; commit guidé
  `SESSION_COMMIT.txt` (bat 27) ; fusion fast-forward sans checkout, serveur
  allumé (bat 28) ; **suppression des branches déjà fusionnées (bat 30)** —
  `git branch -d` refuse tout ce qui n'est pas dans `main`, donc sans risque.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — reste en réserve, mais avec un **déclencheur nommé** :
  la première marche utile est un « mode Flo » minimal (file de nommage des
  visages qu'elle seule sait nommer, rien d'autre), à ouvrir quand l'outil est
  à ~90 % (cadrage du point 1). C'est le multi-utilisateur qui débloque la
  vérité terrain, pas l'inverse.
- **Vidéo → audio** — inchangé : coût élevé, valeur incertaine, aucun
  déclencheur en vue.
- **Bibliothèque Figma** — inchangé : le design system « chambre noire » vit
  déjà dans le code ; une bibliothèque miroir serait de la doc à double
  entretien sans consommateur.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).
