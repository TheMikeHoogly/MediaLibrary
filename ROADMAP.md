# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; l'éphémère dans
`PROMPT_NOUVELLE_SESSION.md`. Audits : `docs/AUDIT_INTERNE_2026-08.md`
(I1–I17, O1–O15, A–F), `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (14/08/2026, session 15)

**Mesure 3a faite — re-passe de tagging PARKÉE, pas rejetée.** `mesure_repasse.py`
(copie de la base, zéro GPU, zéro NAS ; 18 tests verts, recoupée par un second
chemin de code ; détail `mesure_repasse.txt`, `eval/mesure_repasse.json`) :
**42 060 des 42 078 entrées taguées sont en `pipe` v0**, taguées jusqu'au 11/08
donc **toutes au prompt V0 = image seule** — aucun fait en contexte, par
construction du prompt et non par défaut d'enregistrement. Elles recevraient
aujourd'hui : date 41 818 (78 % EXIF au jour près) · nom 18 886 · **lieu 12 459**
· espèce 4 753 ; 58 photos resteraient sans rien. **Mais ces faits sont déjà dans
l'index** : la re-passe n'achète que la DESCRIPTION, et son seul fondement est
l'A/B 25-15 sur 40 photos — **p = 0,15**.

**`gps_place` ACTIVÉ et observé.** 6 614 photos GPS → 221 amas → **6 595
nommées** ; `lieux.txt` +151 lieux (bloc marqué, backup). Les faits « lieu »
passent de **5 814 à 12 459** et les photos à GPS sans lieu de **6 317 à 18**
(3 amas hors des 25 km — le garde-fou tient). Corrigé au passage : le gazetteer
s'arrête à 1 000 habitants, donc le domicile (1 257 photos, le plus gros amas)
sortait « Bussigny ». **`lieux_locaux.txt`** — lieux locaux prioritaires + alias
— reprend la main (`eval/DECISIONS.md`). Tests 52/52 et 30/30.
→ **Ordre** : **3b**, banc de 150 paires = **25 min GPU** · la passe seulement
s'il tranche (strate « nom » 19 608 = 23,2 h ; tout = 49,8 h).

## Sessions 13-14 — livrées et observées en réel (récit : git)

Casse des clés SMB · « même jour » (115 photos sur 11 années) · **plancher des
années du CHEMIN 1990 → 1900, nom de fichier exclu** (716 photos de 1982-1989
rendues à leur décennie, 38 corrigées d'un numéro de scanner, 0 régression sur
20 239 fichiers ; restent 15 dates PRÉCISES fausses, cas REJETÉ) · **ExifTool
disparu en silence** (deux dossiers fantômes UNC nés d'un `mkdir` au niveau
module, `OSError` muet ; `_creer_dossier_si_absolu` refuse et le DIT).
Raisons et chiffres : `eval/DECISIONS.md`.
→ **Régénérer `docs/plan_renommage.json`** : le plan est antérieur au plancher,
les années 80 y sont en « sans date ».

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine — au fil de l'eau, PAS un blocage.** ~0,8 % de
   confirmations (91/12 072) ; files garnies. **Cadrage Mike (12/08)** : le stock
   est limité par la CONNAISSANCE, pas par l'outillage — Flo nommera ce que Mike
   ne sait pas nommer, quand l'outil sera à ~90 %. Métrique = erreurs
   découvertes. Le point 9 reste parqué.
2. **Observer en réel ce qui est livré** — le gros est **fait ✔**. Reste :
   re-upload = une entrée, seek vidéo mobile, test du Z.
3. **Chaîne « noms → descriptions → recherche » (demandé par Mike, 14/08).**
   L'ordre est imposé par le COÛT : la passe complète vaut ~50 h GPU.
   (a) **Mesurer ce qu'elle rapporterait — FAIT** (État ci-dessus). Le contexte
   serait riche, mais les faits sont **déjà** dans l'index : elle n'achète que la
   description. Suspendue à (b) — ne rien lancer avant.
   (b) **Le banc qui tranche — protocole écrit et figé, outil prêt** :
   `docs/PROTOCOLE_3B_TAGGING.md` (hypothèse, strates, critère de décision AVANT
   la mesure : ≥ 88 préférences sur 150). `eval_tagging.py` recâblé sur la prod
   (prompt `V2CTX`, vraies dates, vrais lieux), 150 paires notées au lieu de 40,
   `--depouiller` applique le critère. **25 min GPU contre 50 h.** À lancer
   **après le bat 18** et **avant** les lots de renommage.
   (c) **Passe unique seulement si (b) la justifie** : opt-in, estampillée `pipe`,
   reprenable. Menu : strate « nom » 19 608 = 23,2 h · +espèce 22 520 = 26,6 h ·
   +lieu 26 027 = 30,8 h · tout 42 078 = 49,8 h. Commencer par « nom ».
   **Les noms ne repassent PAS par le prompt** (REJETÉ 31/07 : ignoré 84 % du
   temps, coût ×2,6) — fusion programmatique.
   (d) **La recherche (14) ne dépend PAS de (c)** : couche déterministe à zéro
   GPU, elle avance en parallèle. Wagon : composition d'affichage
   date · lieu · noms depuis `faits`.
4. **Gestes Mike** : `gps_place` **fait ✔** ; nettoyer Flo (5 909 photos ;
   « Corriger » ~0.2 ou « Nettoyer (référence) ») ; re-rejeter Caline une fois ;
   lots de renommage **débloqués** (plan = 2114 ; **régénérer le plan d'abord**,
   cf. le plancher 1990, et **après le banc 3b** que le renommage rendrait
   partiellement caduc).
5. **Correctifs d'audit restants** : I4–I8, O7–O9, O11–O15. **O1 clos partout** ;
   O15 (purge de `photo_thumbs/`) gagne en poids.
6. **Navigation par similarité et par date** : « Semblables » et « même jour »
   **livrés et observés**. Reste : doublons proches bridés (>0,98 + même journée
   → quarantaine réversible, 50 paires jugées avant tout geste). Élargir « même
   jour » à ±1 j n'est PAS décidé — seulement si la moisson stricte est maigre.
7. **Extraction `ui/` — décision nette à prendre** : session dédiée `bundle.py`
   ou parcage explicite (item zombie ; préparatoire fait, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nouveau nom d'animal sort en `personne:`.
9. **Reconnaissance — algo (BARRIÈRE : vérité terrain ≥ ~5 %).**
   HDBSCAN/Chinese Whispers/AdaFace inévaluables à 0,8 %. La barrière reste.
10. **Données / finitions** : réglages éditables depuis `/reglages` (wagon :
    pause globale des workers) ; 2ᵉ passe des 945 illisibles + `recuperees/` →
    NAS ; purge des undo > 30 j (I12).
11. **UI — harmonisation des vues (demandé 12/08, skill `photo-ui`)** :
    (a) clic sur l'image d'une personne → sa démo aléatoire ; (b) lieux : texte
    sous l'image en tooltip ; (c) harmoniser visages/lieux/animaux — mêmes
    fonctions partout, **sauf** l'effacement, réservé à Classification ;
    (d) zoom pinch + molette ; (e) wagons : bandeau `#pending`, libellé `/pets`.
    Wagon 14/08 : le bouton dit « Meme jour (14 aout) » là où la page dit
    « 14 août » (`MOIS_JOUR` ASCII dans le JS, sur un commentaire faux).
12. **Assurance-vie : restauration à blanc (PROMU 12/08).** Test « PC mort
    lundi, tout revit vendredi » : restaurer le snapshot NAS sur un dossier
    vierge, chronométrer, noter chaque manque (dont la copie hors-site de
    `journal_jugements.jsonl`). Tant qu'il n'a pas tourné, la sauvegarde
    « vérifiée » est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08).** Recherche,
    fiches et `faits` sourcés en outils MCP locaux (JSON-RPC stdio, zéro
    dépendance — skill `mcp-builder`). Écriture plus tard. Briques de 14a.
14. **Recherche IA locale contextuelle (demandé 12/08).** Le champ comprend une
    demande en langage naturel et la décompose. (a) **Déterministe d'abord** —
    filtres structurés depuis l'existant (fiches, dates, `gps_place`/`faits`,
    tags, reste → SigLIP) : zéro GPU, **indépendant du re-tagging (3)**, et sa
    matière vient de doubler côté lieux ; (b) ensuite seulement, **escalade
    ponctuelle** vers un modèle chargé à la demande (bail GpuArbiter, déchargé
    après). Modèle et seuil = `vision-eval`, jamais câblé sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger — rattaché au point 3b.

### Résiduels faible valeur (ne pas prioriser)
Vidé le 12/08 : les trois résiduels sont rattachés en wagons aux chantiers 10
(Pause globale des workers) et 11e (bandeau `#pending`, libellé `/pets`).
14/08 : **`server.py` prend `sys.argv[1]` comme `UPLOAD_DIR`** (l. 72) — tout
script qui l'importe avec un drapeau (`--dry`, `--limit`) hérite d'un
`UPLOAD_DIR` faux ; sans effet observé (l'échantillon du banc n'a aucune photo
d'Uploads) et désormais bruyant grâce à `_creer_dossier_si_absolu`. Correctif
d'une ligne : ignorer `argv[1]` s'il commence par `-`. Demande un redémarrage.
14/08, chiffrés et volontairement non traités : (a) le plancher 1990 subsiste
dans `plan_rangement.py`, `recensement_doublons.py`, `diagnostic_dates.py` —
sans effet tant qu'aucun dossier d'avant 1990 n'y passe ; (b)
`/files?dir=1&rec=1` (racine NAS) ne répond pas en 6 min, cause non cherchée.

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
