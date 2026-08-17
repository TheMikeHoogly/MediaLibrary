# Feuille de route — MediaLibrary

Carte des **priorités**, rien d'autre. Les récits de travaux terminés vivent
dans **git** ; les rejets dans `eval/DECISIONS.md` ; les invariants de méthode
dans `eval/METHODE.md` ; l'éphémère dans `PROMPT_NOUVELLE_SESSION.md`. Audits : `docs/AUDIT_INTERNE_2026-08.md`
(I1–I17, O1–O15, A–F), `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`.

## État (17/08/2026, session 17)

**Vecteurs orphelins PURGÉS ET OBSERVÉS EN RÉEL.** Les 2 374 vecteurs `photo`
sans ligne `tags` rendaient des résultats MUETS (2,6 % sur huit requêtes).
`purger_vecteurs_orphelins.py` (44 vérifications, hors du monolithe : la fuite
est colmatée à la source depuis le 08/08) les met en **quarantaine JSONL**
— vecteur en base64, `--restaurer` les remet — puis les supprime. Après
redémarrage : **0 muet sur 1 600 résultats**, et 0 orphelin base contre base.
Deux chemins, même chiffre. Ventilation : **2 143 ARZOPA** (1 072 clés
absolues + 1 071 relatives), **138** = les 69 clés malformées comptées deux
fois, **91** dans `.corbeille-rangement`, 2 disparus de `Photos/2018`.
**Neuf, et c'est la vraie leçon** : « le fichier existe » ne veut pas dire
« il sera re-tagué ». Les 91 sont bien sur le disque mais **hors portée** du
scan (composant caché) : muets à vie. La règle de sélection du scan est
répliquée dans `sera_re_tague()`, pas devinée.

**Banc 3b tranché — la re-passe de tagging est CLOSE.** V2CTX préféré
**94/147 (63,9 %, p = 0,0009)**, au-dessus du seuil pré-enregistré — mais
**hallucinations doublées** (24 contre 13 ; apparié 15 contre 4, p = 0,019), et
**hors des 30 pièges 69/117 (59,0 %, p = 0,064), sous le seuil**. Le critère
écrit d'avance est un ET. Le gain était dans les faits, pas dans la
description — et les faits sont déjà dans l'index. **~50 h GPU économisées.**
Protocole : `docs/PROTOCOLE_3B_TAGGING.md`. Conséquences : `eval/DECISIONS.md`.

**14a livré ET OBSERVÉ EN RÉEL.** `recherche.py` (pur, 48 tests) décompose :
noms → lieux → **période** → reste à SigLIP. « années 80 » rend **752 photos** ;
« avant 2000 » et « depuis 2000 » sont **disjoints** ; le lieu GÉOCODÉ multiplie
la matière (**Lausanne 120 → 1 031**, Bremblens 303 → >1 500). Deux précisions
jamais mélangées, et le filtre **compte** ce qu'il écarte : `sans_date` = **3 824**
(aucune date au jour près) ou **260** (aucune année fiable), les deux confirmés
par un second chemin de code sur une COPIE de la base.

**À régénérer avant tout lot** : `docs/plan_renommage.json` est antérieur au
plancher 1900 et aux lieux GPS.

## À faire — par ordre de valeur (réordonné au triple audit du 11/08)

1. **Vérité terrain humaine — au fil de l'eau, PAS un blocage.** ~0,8 % de
   confirmations (91/12 072). **Cadrage Mike (12/08)** : le stock est limité par
   la CONNAISSANCE, pas par l'outillage — Flo nommera ce que Mike ne sait pas
   nommer, quand l'outil sera à ~90 %. Métrique = erreurs découvertes.
2. **Observer en réel ce qui est livré** — **fait ✔** (14a et la purge des
   vecteurs compris). Reste : re-upload = une entrée, seek vidéo mobile, test du Z.
3. **Chaîne « noms → descriptions → recherche » — 3a, 3b, 3c CLOS le 16/08.**
   La re-passe ne se fera pas (État ci-dessus, `eval/DECISIONS.md`). Reste
   ouvert, et c'est NEUF : **le prompt de PRODUCTION est celui qui hallucine
   le plus.** V2CTX est en prod depuis le 12/08 sur la foi d'un 25-15 ; le banc
   de 147 photos confirme la préférence mais montre le coût. Toute photo taguée
   à partir de maintenant le paie. **Ne pas revenir à V0 sans protocole** — le
   même piège qu'on vient d'éviter. Wagon de 14 : composition d'affichage
   date · lieu · noms depuis `faits`.
4. **Gestes Mike** : `gps_place` **fait ✔** ; nettoyer Flo (5 909 photos ;
   « Corriger » ~0.2 ou « Nettoyer (référence) ») ; re-rejeter Caline une fois ;
   lots de renommage **débloqués sans réserve** — le banc 3b est passé, plus
   rien n'attend. **Régénérer `docs/plan_renommage.json` d'abord.**
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
10. **Données / finitions** : réglages éditables depuis `/reglages` (wagon :
    pause globale des workers) ; 2ᵉ passe des 945 illisibles + `recuperees/` →
    NAS ; purge des undo > 30 j (I12). Wagon 17/08 : deux images TRONQUÉES
    (`Sanetsch/DSC00550.JPG`, `France & Belgique/DSC00795.JPG`) restent en
    attente d'encodage à chaque démarrage — visibles dans `erreurs_images`.
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
14. **Recherche IA locale contextuelle (demandé 12/08).** (a) **Déterministe —
    LIVRÉ ET OBSERVÉ 15/08**, vecteurs orphelins purgés le 17/08 (État).
    Manques : les `faits` ne filtrent pas encore (le lieu passe par `gps_places`
    + chemin) ; pas de filtre espèce ni fiche ; le tri sans mot-clé reste
    `_best_time` (donc `mtime`) là où la sélection l'exclut. (b) ensuite
    seulement, **escalade ponctuelle** vers un modèle chargé à la demande (bail
    GpuArbiter, déchargé après) — `vision-eval`, jamais câblé sans mesure.
15. **À évaluer (`vision-eval`)** : Florence-2 léger. Le banc 3b a montré que
    les faits en contexte n'achètent pas la description — un modèle plus gros a
    d'autant moins de raisons d'être testé. **Parqué** faute d'hypothèse.

### Résiduels faible valeur (ne pas prioriser)
Vidé le 12/08 ; corrigés le 15/08 : `sys.argv[1]` pris pour `UPLOAD_DIR`, et
l'import qui MOURAIT quand sa sortie est un tuyau (`UnicodeEncodeError` en
cp1252 : `python outil.py > log.txt` était mortel).
**MESURÉ le 15/08, et c'est pourquoi on n'y touche pas** : deux planchers 1990
subsistent dans le chemin des dates PRÉCISES. `meme_jour.ANNEE_MIN` coûte
**0 photo** — mais seulement parce que `_fname_time` refuse déjà une année
< 1990 lue dans le NOM DE FICHIER, ce qui coûte **7 photos**. Les deux sont
**couplés** : descendre l'un sans l'autre ne rend rien. 7 photos ne valent pas
un redémarrage ; si quelqu'un touche un plancher, qu'il touche les deux.
14/08, chiffrés et non traités : (a) le plancher 1990 subsiste dans
`plan_rangement.py`, `recensement_doublons.py`, `diagnostic_dates.py` — sans
effet tant qu'aucun dossier d'avant 1990 n'y passe ; (b) `/files?dir=1&rec=1`
(racine NAS) ne répond pas en 6 min, cause non cherchée.

## Acquis — ne pas reproposer (détail : git + `eval/DECISIONS.md`)

- **Stockage** : SQLite local WAL (**43 064 entrées** au 17/08), embeddings
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
- **Index/vecteurs** : cascade de suppression `forget_everywhere` (tags +
  visages/animaux + vecteur) au scan ; purge réversible des orphelins hérités
  (`purger_vecteurs_orphelins.py`, quarantaine `_corbeille_vecteurs/`).
- **Observabilité** : boucle scan/backup (O5), `backup_verify`, trois tâches de
  fond EXIF (dates, noms, GPS) — état, avancement et « fichiers muets » dans
  `/reglages`. Leçon : *un travail de fond qui ne rend pas de comptes finit par
  ne plus travailler du tout* — vraie deux fois (13/08, 14/08).
- **Hygiène** : nettoyage réversible (bat 29), commit guidé `SESSION_COMMIT.txt`
  (27), fusion fast-forward serveur allumé (28), purge des branches fusionnées
  (30). Ordre **27 → 0 → 28** : on ne fusionne qu'après observation en réel.

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
