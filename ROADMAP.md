# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; l'éphémère dans
`PROMPT_NOUVELLE_SESSION.md`. Audits : `docs/AUDIT_INTERNE_2026-08.md`
(I1–I17, O1–O15, A–F), `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (14/08/2026, session 14)

**Session 13 observée en réel, tout passe** : casse des clés SMB et « même jour »
(115 photos sur 11 années, référence exclue, bouton caché sans date précise) ;
chaîne complète vérifiée sur une clé NAS (`similar`, `thumb`, `jour`).

**Plancher 1990 des années du CHEMIN → 1900, nom de fichier exclu — livré ET
observé.** Un dossier « 1985 » ne rendait aucune année : `_best_time` tombait sur
`mtime` et le garde-fou anti-scan de `date_fiable` se désarmait. Observé : **716
photos de 1982-1989 rendues à leur dossier** (elles affichaient avril 2026), 38
photos tirées en arrière par un numéro de scanner corrigées, **0 régression sur
20 239 fichiers**. Restent 15 photos à date PRÉCISE fausse (numérisation du
16/11/2006) : cas REJETÉ. Chiffres : `eval/DECISIONS.md`.
→ **Régénérer `docs/plan_renommage.json`** : le plan est antérieur, les années 80
y sont en « sans date ».

**ExifTool disparu en silence — corrigé et observé.** Les `mkdir` de `DATA_DIR` /
`UPLOAD_DIR` s'exécutaient au NIVEAU MODULE, donc à l'import : sous POSIX
l'antislash n'est pas un séparateur, et deux répertoires nommés
`\\NAS-Bremblens\home\…` (04 et 31/07, vides) sont nés à la racine. Windows les
relit comme des chemins UNC → le `rglob` de `ensure_exiftool` partait sur le NAS,
l'`except OSError` était muet, seul restait le 404 du téléchargement de secours ;
`EXIFTOOL = None`, les trois tâches de fond sortaient et les noms repassaient en
plan B `piexif` (JPEG, sans XMP). Correctifs : `_creer_dossier_si_absolu` (refuse
et le DIT), emplacements probables d'abord, parcours de secours élagué et bavard ;
fantômes dans `_to_delete\faux_dossiers_unc\`. Vérifié au redémarrage.

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine — au fil de l'eau, PAS un blocage.** ~0,8 % de
   confirmations (91/12 072) ; files garnies. **Cadrage Mike (12/08)** : le stock
   est limité par la CONNAISSANCE, pas par l'outillage — Flo nommera ce que Mike
   ne sait pas nommer, quand l'outil sera à ~90 % ; 300 personnes déjà reconnues.
   Métrique = erreurs découvertes. Le point 9 reste parqué.
2. **Observer en réel ce qui est livré** — le gros est **fait ✔**. Reste :
   re-upload = une entrée, seek vidéo mobile, test du Z. Veille v2ctx sur un lot
   plus grand (astre/objet, fuite de la date en prose).
3. **Chaîne « noms → descriptions → recherche » (demandé par Mike, 14/08).**
   Knowledge Builder et `TAGGING_PIPELINE_VERSION` sont câblés (s8) et observés
   (s9) ; le stock de visages nommés (300 personnes) rend enfin une passe de
   re-tagging discutable. L'ordre est imposé par le COÛT — la passe complète
   vaut ~51 h GPU, on ne la paie qu'une fois :
   (a) **Mesurer d'abord ce qu'elle rapporterait** : combien d'entrées sont
   encore en `pipe` v0, et surtout combien portent aujourd'hui des `faits`
   (noms · date · lieu) qu'elles n'avaient pas quand elles ont été taguées —
   les backfills du 13-14/08 ont ajouté 32 822 dates et 5 394 GPS, c'est CE qui
   a changé. Sans ce chiffre, les 51 h sont un pari.
   (b) **Trancher le modèle AVANT la passe** (`vision-eval` : protocole avant
   mesure) : plafond DUR de 4 Go de VRAM — `qwen3-vl:4b` déborde déjà, « plus
   gros » n'est pas une variable libre. Candidats : Florence-2 léger, un
   `qwen3-vl:2b` mieux prompté. Question au banc : un modèle plus gros apporte-t-il
   encore quelque chose QUAND les faits sont déjà donnés en contexte (v2ctx) ?
   Si non, le gain est dans les faits, pas dans le modèle.
   (c) **Puis la passe unique** : opt-in, jamais automatique, estampillée `pipe`,
   reprenable. **Les noms ne repassent PAS par le prompt** (REJETÉ 31/07 : ignoré
   84 % du temps, coût ×2,6) — fusion programmatique, comme aujourd'hui.
   (d) **La recherche (14) ne dépend PAS de (c)** : sa couche déterministe
   (fiches, dates, lieux, tags) est à zéro GPU et avance en parallèle. Le
   re-tagging n'améliore que la traîne sémantique.
   Wagon : composition d'affichage date · lieu · noms depuis `faits`.
4. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos ; « Corriger »
   ~0.2 ou « Nettoyer (référence) ») ; re-rejeter Caline une fois ; activer
   `gps_place` (bat 18 → `enrichir_lieux.py` → `--ecrire` → redémarrer) ; lots de
   renommage **débloqués** (plan = 2114 ; **régénérer le plan d'abord**, cf. le
   plancher 1990 ; le banc `eval/tagging_v1.json` en deviendra partiellement
   caduc — attendu).
5. **Correctifs d'audit restants** : I4–I8, O7–O9, O11–O15. **O1 clos partout** ;
   O15 (purge de `photo_thumbs/`) gagne en poids.
6. **Navigation par similarité et par date** : « Semblables » et « même jour »
   **livrés et observés** (un 14 août bruité au passage : bloc 2010 en triple,
   14 captures sur 115). Reste : doublons proches bridés (>0,98 + même journée →
   quarantaine réversible, 50 paires jugées avant tout geste). Élargir « même
   jour » à ±1 j n'est PAS décidé — seulement si la moisson stricte est maigre.
7. **Extraction `ui/` — décision nette à prendre** : session dédiée `bundle.py`
   ou parcage explicite (item zombie ; préparatoire fait, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nouveau nom d'animal sort en `personne:`.
9. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).**
   HDBSCAN/Chinese Whispers/AdaFace inévaluables à 0,8 %. La barrière reste.
10. **Données / finitions** : édition des réglages depuis `/reglages` (wagon :
    Pause globale des workers) ; 2ᵉ passe des 945 illisibles + `recuperees/` →
    NAS ; `docs/journaux/` gitignoré + purge des undo > 30 j (I12).
11. **UI — harmonisation des vues (demandé 12/08, skill `photo-ui`)** :
    (a) clic sur l'image d'une personne → sa démo aléatoire ; (b) lieux : texte
    sous l'image en tooltip ; (c) harmoniser visages/lieux/animaux — mêmes
    fonctions partout, **sauf** l'effacement, réservé à Classification ;
    (d) zoom pinch + molette (démos et plein écran) ; (e) wagons : retrait du
    bandeau `#pending`, libellé `/pets` « empreintes calculées ».
    Wagon 14/08 : le bouton dit « Meme jour (14 aout) » là où la page dit
    « 14 août » (`MOIS_JOUR` ASCII dans le JS, sur un commentaire faux).
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** Test « PC mort
    lundi, tout revit vendredi » : restaurer le snapshot NAS sur un dossier
    vierge, chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`, locale et gitignorée). Tant qu'il n'a pas tourné,
    la sauvegarde « vérifiée » est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08).** Recherche
    (sémantique + tags), fiches personnes/animaux et `faits` sourcés en outils
    MCP locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`) :
    interroger la bibliothèque depuis une conversation Claude, premier fruit de
    la provenance. Écriture plus tard. Mêmes briques que 14a.
14. **Recherche IA locale contextuelle (demandé 12/08).** Le champ comprend une
    demande en langage naturel et la décompose. (a) **Déterministe d'abord** —
    filtres structurés depuis l'existant (fiches, dates, `gps_place`/`faits`,
    tags, reste → SigLIP) : zéro GPU, couvre l'essentiel, **indépendant du
    re-tagging (3)** ; (b) ensuite seulement, **escalade ponctuelle** vers un
    modèle chargé à la demande (bail GpuArbiter, 4 Go, déchargé après). Modèle et
    seuil = `vision-eval`, jamais câblé sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger — rattaché au point 3b.

### Résiduels faible valeur (ne pas prioriser)
Vidé le 12/08 : les trois résiduels sont rattachés en wagons aux chantiers 10
(Pause globale des workers) et 11e (bandeau `#pending`, libellé `/pets`).
14/08, chiffrés et volontairement non traités : (a) le plancher 1990 subsiste
dans `plan_rangement.py`, `recensement_doublons.py`, `diagnostic_dates.py` — même
erreur, sans effet tant qu'aucun dossier d'avant 1990 n'y passe ; (b)
`/files?dir=1&rec=1` (racine NAS) ne répond pas en 6 min — galerie récursive
racine inutilisable, cause non cherchée.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Stockage** : SQLite local WAL (**43 067 entrées** au 14/08), embeddings
  BLOB, backup NAS snapshot + `backup_verify`.
- **Reconnaissance** : SigLIP 2 (90 % r1) ; animaux 97,4 % r1 ; prototypes
  multiples ; vérif d'espèce.
- **Nommage** : attribution unifiée personnes+animaux (multi-noms, annulation
  10 s), rejets réversibles, reclassement `personne:`→`animal:` réversible.
- **Fichiers/Rangement** : `/browse` réversible, dédoublonnage appliqué
  (8,4 Go), rangement par année, orchestrateur de maintenance.
- **Renommage** : cœur + plan + applicateur réversibles prêts (plan = 2114) ;
  `gps_place` codé (pas activé).
- **UI** : design system « chambre noire » (tokens, plancher a11y dont
  `:focus-visible`), planche contact, `/reglages`, `/people` réorganisé,
  `/sujets` guichet unique (sous-nav, Classification, files « À vérifier »,
  clavier Espace/X/Z/lettre).
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
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, et les trois
  tâches de fond EXIF (dates, noms, GPS) — état, avancement et « fichiers muets »
  dans `/reglages`. Leçon : *un travail de fond qui ne rend pas de comptes finit
  par ne plus travailler du tout* — vraie deux fois (13/08, 14/08).
- **Hygiène** : nettoyage de session réversible (bat 29) ; commit guidé
  `SESSION_COMMIT.txt` (bat 27) ; fusion fast-forward sans checkout, serveur
  allumé (bat 28) ; suppression des branches fusionnées (bat 30). Ordre :
  **27 → 0 → 28** — on ne fusionne qu'après observation en réel.

## Réserve — futur, non prioritaire (triée le 12/08)

- **Multi-utilisateur** — en réserve, avec un **déclencheur nommé** : un « mode
  Flo » minimal (file de nommage des visages qu'elle seule sait nommer), à ouvrir
  quand l'outil est à ~90 %. C'est lui qui débloque la vérité terrain.
- **Vidéo → audio** — inchangé : coût élevé, valeur incertaine, aucun
  déclencheur en vue.
- **Bibliothèque Figma** — le design system vit déjà dans le code ; un miroir
  serait de la doc à double entretien sans consommateur.
- Récits LLM auto : écartés (hallucination).

**Vision** : mémoire familiale à provenance — deux tests : « PC mort lundi,
tout revit vendredi » (**promu** : chantier 12) et « aucun fait affirmé sans
provenance » (en cours : `faits` sourcés livrés, composition d'affichage au
point 3, MCP lecture au point 13).
