# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; l'éphémère (état de
session, choses à observer) dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md` (I1–I17, O1–O15, A–F),
`docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (13/08/2026, session 10)

**Deux livraisons observées bonnes en réel, dans l'ordre.** (1) Purge des
doublons : total = **43 067 pile** (43 086 − 19), plus aucune clé absolue
`\\NAS…\_Uploads` (file « À vérifier » incluse). (2) **Navigation par
similarité VALIDÉE en réel (13/08)** : bouton « Semblables » de la lightbox →
page de résultats, navigation de proche en proche. `feat/similar` **committée
et fusionnée** (bat 27/28/29 passés, `_tmp_obs/` supprimé). Reste un test
d'occasion : au prochain upload téléphone, une photo = UNE entrée.

**Session 11 à commiter** (`SESSION_COMMIT.txt` prêt, `fix/lieux-thumb`) :
**résidu O1 confirmé PUIS corrigé** — la section Lieux de `/sujets` était la
dernière grille à charger des originaux (mesuré sur le serveur en marche :
25 cartes via `/media/…`, 0 via `/api/thumb`). `places_list()` rend désormais
`/api/thumb?key=…&s=512`. Mesuré sur une clé de lieu réelle (antislashs +
espaces) : **41 Ko contre 2 435 Ko, −98 %** — soit ~60 Mo de NAS épargnés à
chaque ouverture de `/sujets`. Veille v2ctx inchangée (n=2 : astre/objet,
date en prose).

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
2. **Observer en réel ce qui est livré** : v2ctx/Knowledge Builder **fait ✔**,
   purge des 19 doublons **fait ✔**, bouton « Semblables » **fait ✔** (13/08) ;
   reste : vignettes Lieux (session 11, après redémarrage), re-upload = une
   entrée, seek vidéo mobile, test du Z. Veille v2ctx sur un lot plus grand :
   identifications astre/objet, fuite de la date en prose — tout geste de
   prompt passe par `vision-eval`.
3. **Knowledge Builder + version de pipeline : CÂBLÉS (s8) et OBSERVÉS (s9)** —
   suite naturelle : composition d'affichage date · lieu · noms depuis `faits`
   (choix tranché : structuré d'abord, affichage plus tard) ; re-tagging
   opt-in des entrées v0 si la qualité observée le justifie (~51 h GPU,
   jamais automatique).
4. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos sur sa fiche,
   outillage livré : « Corriger » seuil ~0.2 ou « Nettoyer (référence) ») ;
   re-rejeter le groupe Caline une fois ; activer `gps_place`
   (`18 - …gazetteer.bat` → `enrichir_lieux.py` → `--ecrire` → redémarrer) ;
   lots de renommage **débloqués** (éval V2 faite ; plan = 2114). NB : après
   renommage, le banc `eval/tagging_v1.json` (keyé par chemin) devient
   partiellement caduc — attendu, décision déjà écrite.
5. **Correctifs d'audit restants** : I4–I8, O7–O9, O11–O15 (dont purge de
   `photo_thumbs/` — le cache croît sans borne ; il est **gitignoré depuis le
   12/08**, il ne pollue plus `git status`). **Résidu O1 : SOLDÉ (s11)** —
   Lieux de `/sujets` passé à `/api/thumb`, −98 % mesuré ; O1 est désormais
   clos partout. Le wagon naturel de O15 (purge du cache `photo_thumbs/`)
   gagne en poids maintenant que toutes les grilles l'alimentent.
6. **Navigation par similarité** : `/api/similar` + page `/files?sim=` +
   bouton « Semblables » **livrés et OBSERVÉS BONS (13/08)** ; restent :
   doublons proches bridés (>0,98 + même journée → quarantaine réversible,
   50 paires jugées par Mike avant tout geste) ; rangée « même jour, autres
   années » (requête date, zéro IA). Les deux tranches restantes réutilisent
   `similar_by_key` tel quel — aucune brique nouvelle à écrire.
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
12. **Assurance-vie : restauration à blanc (PROMU de la Réserve le 12/08).**
    Le test de la vision « PC mort lundi, tout revit vendredi » : restaurer
    depuis le snapshot NAS sur une machine/un dossier vierge, chronométrer,
    noter chaque manque (dont copie hors-site de `journal_jugements.jsonl`,
    aujourd'hui locale et gitignorée). Faible effort, grande valeur : tant que
    ce drill n'a pas tourné une fois, la sauvegarde « vérifiée » n'est qu'une
    promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU — son prérequis
    « Knowledge Builder » est soldé et observé le 12/08).** Exposer recherche
    (sémantique + tags), fiches personnes/animaux et `faits` sourcés comme
    outils MCP locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).
    Interroger la bibliothèque depuis une conversation Claude = premier fruit
    concret de la provenance. Écriture (nommer, corriger) : plus tard,
    seulement après usage réel en lecture.
14. **Recherche IA locale intelligente et contextuelle (demandé 12/08).**
    Le champ de recherche (« filtrer par nom ») comprend une demande en
    langage naturel et la décompose. Ordre de construction : (a) d'abord le
    **déterministe** — parser la requête en filtres structurés depuis ce qui
    existe déjà (noms = fiches, dates, lieux = `gps_place`/`faits`, tags,
    reste → recherche sémantique SigLIP) : zéro GPU, couvre l'essentiel ;
    (b) ensuite seulement, **escalade ponctuelle** vers un modèle plus
    intelligent chargé à la demande (bail GpuArbiter, VRAM 4 Go — le modèle
    est déchargé après) ou itérations multiples selon la complexité de la
    demande. Choix du modèle et seuil d'escalade = éval `vision-eval` (jamais
    câblé sans mesure). Synergie : mêmes briques que le serveur MCP (13) —
    l'un sert l'humain dans l'UI, l'autre sert Claude en conversation.
15. **À évaluer (discipline `vision-eval`)** : Florence-2 léger.

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
