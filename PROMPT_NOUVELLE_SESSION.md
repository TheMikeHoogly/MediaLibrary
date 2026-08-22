# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 31)

**Le coupable n'était pas la purge : c'est le RANGEMENT, et il se taisait.**
`rekey_everywhere` transporte sept magasins quand une photo change de chemin, et
quatre « stores de sujets » passent dans la même boucle. Mais `PEOPLE` et `PETS`
sont les seuls keyés par **NOM** : leurs chemins vivent DANS la fiche
(`faces` = [[chemin, index]], `exclude`, `confirmed`, `avatar`).
`store.rekey(ancien_chemin, nouveau_chemin)` y cherche une entrée dont la CLÉ
serait un chemin, n'en trouve jamais, renvoie **faux sans un mot**. La boucle
avait l'air de couvrir quatre magasins ; elle en couvrait deux. Chaque rangement
par année et chacun des **7 058** renommages a pu décrocher un jugement.

**Ce que ça coûtait** : sur **3 364** décisions humaines, **928** pointent vers
une clé absente de l'index (596 rattachements, 249 exclusions, 83
confirmations), sur **804** clés. Le TAG survivait (index + XMP), donc la photo
gardait son nom et la règle 2 tenait : c'est la VÉRITÉ TERRAIN qui partait — et
une exclusion perdue, c'est un faux positif qui revient.

**« 787 décisions déjà perdues » est RÉFUTÉ**, et c'était un défaut de
recherche, pas une mesure : personne ne leur avait cherché de jumeau. Les
**journaux d'annulation** de `docs/` — écrits pour défaire, relus à l'endroit —
donnent **19 331** déplacements et retrouvent **698** des 804 clés. Trois
preuves comparées : journal **685**, nom de fichier **346** (36 homonymes
refusés), vecteur **13** — la purge du 21/08 ayant emporté les détections des
clés mortes. Bilan : **748 décisions se re-clent**, 56 y sont déjà, **124** sont
vraiment perdues. Le « une seule décision à reporter (Luna) » tombe avec.

**LIVRÉ.** `recle_decisions.py` (règle pure, 15 tests) branché dans
`rekey_everywhere` : une photo qui bouge emmène ses jugements, index de vignette
compris. `journaux_deplacements.py` (14 tests) : une seule lecture des journaux,
partagée par le serveur et le banc. Réparation rétroactive dans `/reglages` —
aperçu / appliquer / annuler, quarantaine `_corbeille_decisions/` — qui passe
par **la même fonction** que le préventif. Instruments :
`mesure_report_orphelines.py`, `verifier_recle_decisions.py`.

**Observé sur le serveur vivant** : `POST /api/maint/recle-apercu` rend 804 clés
mortes, **685 à re-clé**, 119 sans destination, **0 hors bornes** — les mêmes
nombres que le banc, deux chemins. Le « 0 hors bornes » est une corroboration :
un jumeau faux ferait déborder les index.

## Prochain pas

1. **UN CLIC DE MIKE, et c'est le plus rentable de la liste** : `/reglages` →
   « Décisions humaines restées sur l'ancien chemin » → **2 · Appliquer**. La
   sandbox n'a pas le droit d'écrire sur le fonds — l'aperçu et l'annulation
   sont là pour encadrer le geste. Pour observer ensuite :
   `mesure_copie_base.py` puis `verifier_recle_decisions.py --base copie.db`,
   qui doit passer de **928** décisions hors index à **~180**.
2. **Ce qui reste vraiment perdu** : **124** décisions sur 106 clés dont aucun
   journal ne connaît la destination, plus **120** clés protégées de la purge du
   21/08 dont les photos n'existent plus. Décider de leur sort — les garder
   coûte un résidu permanent, les purger coûte de la vérité terrain.
3. **Le registre des oublis SURVIT — fait et observé (22/08).**
   `_comptes_index.json`, écrit dès le démarrage puis à chaque cycle ;
   `redemarrages` 0 → 1 sur deux relances, `depuis` conservé. La prochaine
   anomalie de l'index sera donc diagnosticable APRÈS coup, ce qui manquait aux
   −250 du 17/08 comme aux 2 283 du 21/08.
4. **Juger 30 propositions de la tranche 0,35–0,40** (choix de Mike, 21/08)
   avant de toucher `CUR_ADD_SIM`. 1 328 visages, 1 106 photos vivantes.
5. **Chantier 12 — l'instrument est livré, la répétition reste à faire.**
   `verifier_restauration.py` a nommé **9 artefacts irrécupérables présents
   nulle part ailleurs (19,9 Mo)**, dont `docs/undo_*.json` et les trois
   quarantaines ; `backup_artefacts()` les pousse désormais sur le NAS à chaque
   sauvegarde — observé : 61 fichiers, 20,4 Mo, « Total exposé : 0 o ». Reste le geste de Mike : restaurer pour de vrai sur un dossier
   vierge, chronométrer, puis `verifier_restauration.py --restaure <dossier>`.
6. **Finitions UI et plafond de page : FAITES et observées (22/08).** Reste
   l'audit I4–I8 / O7–O15, puis **MCP lecture seule (13)**.

**Une décision à cinq secondes qui traîne depuis trois sessions** : l'extraction
`ui/` (point 7) — lui donner une session ou la parquer.

**Ne pas rouvrir sans chiffre neuf** : 16(a) (mesuré, 17 photos) ; `taken` en
base ; backfill ÉCRIT de `faits` ; index des noms en UNE passe ; filtre des noms
sur les `kw` bruts ; `det_score` comme critère d'espèce ; règle d'espèce
ÉLARGIE ; re-passe de tagging en LOT (50 h GPU — l'incrémental reste ouvert) ;
agent git dans le serveur ; planchers 1990 ; plafond 2100.

**Les TROIS canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer ;
`canal.py` les lit tous) : `_commande_serveur.txt` → `redemarrer`, puis
VÉRIFIER `GET /api/serveur` (`code_a_jour` vrai) ; `_commande_git.txt` →
`commit` (traite autonome) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json` ; `_commande_banc.txt` → un banc, puis
LIRE `_banc_sortie.txt`. Trois fenêtres ouvertes — Serveur, Git, Bancs ; un
agent est vivant si son `_agent_*_vu.txt` a moins de 30 s.

**Mesurer** : jamais sur `photos.db` — `mesure_copie_base.py` d'abord, puis
`--base copie.db`. Et **avant de comparer des noms ou des vecteurs, chercher si
le geste a laissé une TRACE** : les journaux d'annulation de `docs/` ont rendu
685 clés là où le nom en rendait 346 et le vecteur 13.

**La sandbox ne peut pas écrire sur le fonds.** `POST` de renommage,
d'attribution ou d'application est refusé côté Claude. Tout ce qui MODIFIE
l'archive se termine donc par un bouton dans `/reglages` ou un geste de Mike —
prévois-le dans la conception, sinon le chantier finit en cul-de-sac.
