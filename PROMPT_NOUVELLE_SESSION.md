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
clés oubliées vivent des décisions humaines — **141**, portées par **120 clés**
(Alix Baudère, Luna…).

**LA CAUSE, trouvée le soir même.** La cascade de suppression est pilotée par
l'INDEX : `_sync_dir` calcule ses orphelins à partir de `STORE`, donc une clé
**déjà** absente de l'index lui est invisible — `forget_everywhere` ne sera
jamais appelé pour elle. L'autre filet, `purge_cles_fantomes`, exige un
**jumeau vivant** de même nom de fichier : quand les deux jumeaux sont morts
(`ARZOPA/x` et `…\_Uploads\ARZOPA\x`), il ne se déclenche jamais. Classement
des 2 374 : **2 283 « personne ne les voit »**, **91 sous un chemin caché**
(`.corbeille-rangement`), que la purge de démarrage retire de l'index **sans
cascade**. Et l'instrument avait un angle mort exact : il comparait les
détections au DISQUE et les vecteurs à l'INDEX, jamais les détections à
l'index. **Bouché** : `verifier_orphelins.py --sans-disque` (0,7 s, base contre
base) dit `faces` **2 374** hors index, `animals` **2 377**, **120 clés jugées
par un humain**, **0** vecteur orphelin.

**Le sauvetage ne rend presque rien, et c'est le résultat.** Sur les 141
décisions portées par ces clés : **13** ont un jumeau vivant, **12** portent
déjà le nom, il reste **UNE** décision à reporter (Luna). Les **128** autres
n'ont aucun jumeau. Et **787** décisions pointent vers des clés inconnues
PARTOUT — déjà perdues. Vérité terrain réelle : **3 364** décisions (1 576
rattachements — « 1 196 » comptait des CLÉS —, 1 496 exclusions, 292
confirmations).

**LE CORRECTIF EST LIVRÉ ET OBSERVÉ.** La purge de démarrage cascade enfin
(`forget_everywhere` au lieu de `STORE.remove_many` — préventif), et
`purge_detections_hors_index()` balaie au démarrage ce que `_sync_dir` ne peut
plus voir. Deux garde-fous : **jamais** une clé portant une décision humaine, et
**seulement** ce que l'index ne reprendra jamais (fichier absent ou chemin
caché) — une clé dont le fichier existe est en attente de re-tagging et se
COMPTE au lieu de se purger. Quarantaine JSONL avant tout retrait. Le dry-run
(`verifier_orphelins.py --sans-disque --simuler-purge`) annonçait 2 254 + 2 257 ;
la quarantaine en contient **exactement** 2 254 + 2 257. Observé après
redémarrage : `visages` **44 450 → 42 196**, hors index **2 374 → 120** (les
protégées), file du curateur **inchangée** (13/1/24), index intact à 43 065.

## Prochain pas

1. **Reporter la décision de Luna**, la seule des 141 qui se sauve : son
   rattachement sur `…\_Uploads\ARZOPA\KP6XMN-…jpg` va vers
   `…\Photos Flo\Luna & Inti\20260101_Pheno.jpg` (jumeau retrouvé par le
   VISAGE à 1,0000). Puis décider du sort des **120 clés protégées** : leurs
   photos n'existent plus, la décision n'a plus de sujet — les garder coûte un
   résidu permanent, les purger coûte 141 décisions de vérité terrain.
2. **Faire SURVIVRE le registre des oublis.** `comptes_index` vit en mémoire :
   après le redémarrage de 19:31, `par_motif` est vide et la cause des 2 283 ne
   pourra jamais être établie rétrospectivement. Un compteur qui ne survit pas
   au redémarrage ne diagnostique rien.
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
