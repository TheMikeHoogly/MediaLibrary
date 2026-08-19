# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; la méthode dans
`eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits :
`docs/AUDIT_INTERNE_2026-08.md`, `docs/AUDIT_EXTERNE_2026.md`,
`docs/RANGEMENT_2026.md`.

## État (19/08/2026, session 25)

**Sessions 23–24** : 10a, 10b et 14a CLOS et observés ; `27 - Git.bat` (guichet
unique — état dépôt + serveur, commit, redémarrage, fusion sans checkout,
branches, GitHub) **observé le 19/08**, session 24 commitée et fusionnée par lui.
Reste NON DÉCIDÉ : corriger `taken` en base (**72** photos contre **1 369** dates
antérieures). **Non observé en réel** : Mike ne l'a pas lancé.

**`faits` devient une VUE — le backfill est REJETÉ, rien n'est écrit.**
`faits_vue.py` (pur, 26 tests) calcule les faits à la demande ; `server`
lui délègue la règle de lieu (**0 différence sur 43 064 clés**).
`mesure_faits_vue.py` a tranché sur COPIE :

- **Ce qu'elle rend** : **42 974 (99,79 %)** avec un fait, mais le chiffre
  honnête est **29 775 (69,14 %)** avec un fait NON-date ; 13 199 n'ont que la
  date, 90 sont muettes. Matière : date 42 773 · personne 18 859 · lieu **12 802**
  (6 595 GPS + 6 207 chemin) · espèce 4 750 · animal 935.
- **Pourquoi une vue** : sur les 81 pourvues, elle en corrige **4** — 3 noms
  « Flo » retirés depuis, **1 photo qui a reçu 6 noms APRÈS son tagging**. Un
  backfill aurait gravé les deux erreurs 43 064 fois.
- **Ce qu'elle coûte** : **1,4 ms** par page de 50, **3,8 s** sur l'index entier.
  Prudence : `_noms_attendus` balaie toutes les fiches à chaque appel (13,9 ms
  pour 50 clés) — en balayage complet, index inversé des noms construit UNE fois.

**Et le LIEU n'est prêt pour aucune des deux règles.** Celle du KB évite les
**577** lieux collés dans un mot, mais en RATE **378** en mot entier (207 effacés
au nettoyage, **124 libellés MULTI-MOTS jamais essayés** — « Weekend Vallée
d'Aoste », 47 mots de 4 lettres) et répond AUTREMENT sur **591** (315 fois plus
précise, 119 moins, 157 arbitraires). **1 546** désaccords — l'argument décisif
pour la vue : une règle corrigée vaudra pour les 43 064 sans migration.

## À faire — par ordre de valeur

1. **Vérité terrain humaine — au fil de l'eau, PAS un blocage.** ~0,8 %
   (91/12 072). Le stock est limité par la CONNAISSANCE, pas l'outillage : Flo
   nommera ce que Mike ne sait pas nommer, quand l'outil sera à ~90 %.
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
7. **Extraction `ui/`** : décision à prendre — session dédiée `bundle.py` ou
   parcage explicite (item zombie ; préparatoire fait, détail git).
8. **Cross-pipeline (Mutz/Caline)** : outil livré, réversible. Fix auto REJETÉ
   (18 % faux rejets). Relancer si un nom d'animal sort en `personne:`.
9. **Reconnaissance — algo.** BARRIÈRE : vérité terrain ≥ ~5 %. HDBSCAN /
   Chinese Whispers / AdaFace inévaluables à 0,8 %.
10. **Données / finitions.** Trois chantiers, dans cet ordre :
    (a) **Compter ce que le scan OUBLIE — CLOS (18/08).** Trois constats mineurs
    non traités : un ajout vu PAR LE SCAN est étiqueté `tagging` ; `dict.__ior__`
    non redéfini dans `TrackedDict` (aucun usage) ; `cycles_vus` est la longueur
    d'un anneau de 10 — il affiche « 10 » à vie.
    (b) **Garde-fou du repli sur le NOM + noms périmés — CLOS (19/08), observé.**
    Reste : **`taken` en base NON décidé** — 72 photos contre 1 369 antérieures.
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
    `journal_jugements.jsonl`). Tant qu'il n'a pas tourné, c'est une promesse.
13. **Serveur exposé en MCP, lecture seule d'abord (PROMU 12/08).** Recherche,
    fiches et `faits` en outils MCP locaux (JSON-RPC stdio, zéro dépendance —
    skill `mcp-builder`). Écriture plus tard. Briques de 14a.
14. **Recherche IA locale contextuelle.** (a) **Déterministe — la MATIÈRE est
    tranchée (19/08)** : `faits` est une **VUE** (`faits_vue.py`), pas un champ
    — mesures et raisons dans l'État. Reste, dans cet ordre :
    **(i) brancher la vue** là où le point 3 l'attend (affichage date · lieu ·
    noms) et sur `/api/…`, en construisant l'index inversé des noms UNE fois
    par balayage ; **(ii) corriger la règle de LIEU** — les 124 libellés
    multi-mots sont le plus gros lot et le plus facile (essayer le libellé
    entier dans le segment, pas seulement ses mots), le seuil de 5 lettres en
    coûte 47, et « France & Belgique » demande de trancher : deux lieux ou
    aucun ; **(iii) le filtre**, mesuré sur la couverture réelle (69,14 %),
    jamais sur les 99,79 %.
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
  contact, `/reglages`, `/people`, `/sujets` guichet unique (clavier).
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
  `mesure_faits_backfill.py`, `mesure_faits_vue.py` — lecture seule sur COPIE,
  jamais sur `photos.db`.
- **Hygiène** : nettoyage réversible (29) ; **tout git dans `27 - Git.bat`**,
  guichet unique — état dépôt + serveur, commit guidé, redémarrage, fusion
  fast-forward sans checkout, purge des branches, GitHub. Ordre **1 → 7 → 2** :
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
