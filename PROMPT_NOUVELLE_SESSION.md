# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (21/08/2026, fin de session 30)

**Le chantier 16(a) est CLOS par une mesure, et il n'y avait rien dedans.**
La propagation des noms ne dormait pas : elle a convergé. `build_suggestions()`
repasse sur tout le fonds toutes les 240 s et `AUTO_ADD` moissonne à 0,40 avec
une marge de 0,10. Ce qu'elle rattacherait MAINTENANT, sur 71 461 visages :
**14 en automatique, 24 en file — 33 photos, 38 noms.** Rien n'est caché par le
plafond (38 cartes sur 400). Le cas exact du chantier — une photo nommée qui
garde un visage non couvert — concerne **18 745** photos et en rendrait **17**.

**Ce qui autorise à conclure** : le banc et le serveur VIVANT donnent les trois
mêmes nombres — `remove` **13**, `merge` **1**, `add` **24**. Deux chemins, un
chiffre.

**Le brut mentait d'un facteur 100.** Sans le garde-fou des clés fantômes, le
banc annonçait 3 698 rattachements en attente ; testées une à une contre le
NAS, **3 684** pointent vers un fichier disparu. C'est `--fichiers` qui a fait
tomber 3 698 à 14 — voir `eval/METHODE.md`.

**La trouvaille est ailleurs, et elle vaut plus que la question posée.** Le
magasin de visages garde **2 374** fiches dont la clé n'est plus dans l'index :
**exactement** les 2 374 clés purgées le 17/08 (intersection 2 374 / 2 374
contre `_corbeille_vecteurs/vecteurs_orphelins_20260817_073335.jsonl`). La
purge a emporté leurs vecteurs SigLIP et **laissé leurs visages**. Et sur ces
clés oubliées vivent **125 décisions humaines** — 104 rattachements, 11
exclusions, 10 confirmations (Alix Baudère, Luna…), comptées dans les 2 984.

## Prochain pas

1. **Sauver les 125 avant de purger quoi que ce soit** (choix de Mike, 21/08 —
   la règle 2 impose l'ordre). D'abord l'INSTRUMENT, pas le geste : pour
   chacune des 125, chercher si la photo vit sous une AUTRE clé — les doublons
   `ARZOPA/x` ↔ `…\_Uploads\ARZOPA\x` le suggèrent fortement — et **nommer
   celles qui n'ont pas de jumeau vivant**. Le report des noms et la purge
   (quarantaine réversible, comme le 17/08) viennent après, et seulement après.
2. **Chercher la CAUSE** : pourquoi le scan retire une clé de l'index sans
   retirer sa fiche de visages ? `forget_everywhere` est un acquis du ROADMAP —
   il ne couvre visiblement pas ce chemin-là. Purger sans le savoir reconduit
   l'incident : c'est exactement ce que le 17/08 a fait, sans que ça se voie.
3. **Juger 30 propositions de la tranche 0,35–0,40** (choix de Mike, 21/08)
   avant de toucher `CUR_ADD_SIM`. 1 328 visages, 1 106 photos vivantes. Sans
   ce jugement, abaisser un seuil est un pari sur des noms — et le plafond de
   400 n'en montrerait que 386 de toute façon. Le réservoir entier (28 684
   visages, meilleur voisin **médian 0,21**) n'est PAS un gisement : ce sont
   des gens sans fiche.
4. **Chantier 12 — la restauration à blanc.** Toujours le seul item dont
   l'échec serait irréversible, et il n'a jamais tourné. Partage des rôles
   inchangé : la restauration est un geste de Mike, la sandbox écrit
   l'INSTRUMENT (`verifier_restauration.py`, comparaison du restauré au vivant).
5. **Les finitions, en TRAITE AUTONOME** (`commit`, `main` intacte) : UI (11),
   audit I4–I8 / O7–O15, plafond de page à 1 500 sur `espece:chat`.
6. **MCP lecture seule (13)**, puis le reste de `ROADMAP.md`.

**Une décision à cinq secondes qui traîne depuis deux sessions** : l'extraction
`ui/` (point 7) — lui donner une session ou la parquer.

**Ne pas rouvrir sans chiffre neuf** : 16(a) (mesuré, 17 photos) ; `taken` en
base ; backfill ÉCRIT de `faits` ; index des noms en UNE passe ; filtre des
noms sur les `kw` bruts ; `det_score` comme critère d'espèce ; règle d'espèce
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
`--base copie.db`. Et **répliquer les GARDE-FOUS du producteur, pas seulement
sa règle** : `mesure_propagation_noms.py --fichiers 40000` (76 s, un `stat` par
clé candidate) est ce qui sépare 3 698 d'un chiffre vrai. Ce que le serveur
FAIT ne se lit pas dans un banc : `GET /api/curator/list` a confirmé les trois
nombres.
