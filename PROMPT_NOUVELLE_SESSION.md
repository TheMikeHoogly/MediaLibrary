# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 38)

**Cinq lots fusionnés dans `main`** : `4de5acc` (I7), `0e46ddd` (I4/I5/I6/I8),
`58bfacd` (quarantaines), `ddf2da5` puis `537791d` (le monolithe s'ouvre).
Tout a été observé en réel, `code_a_jour` vrai à chaque fois.

**Les correctifs d'audit I4 à I8 sont CLOS**, et le premier a réfuté l'audit
avant de le corriger. I7 annonçait « un `personne:nom` importé n'est jamais
auto-guéri » ; le fonds, interrogé pour la première fois
(`mesure_noms_casse.py`), répond : sur **37 707 tags nommés — 0 préfixe non
canonique, 0 doublon, 3 tags en casse divergente** (`animal:luna` / fiche
`Luna`). Défaut LATENT, corrigé quand même — `tagging_meta.parse_tag_nomme`
remplace six lectures divergentes. Preuve en réel : `/api/names` passe Luna de
**207 à 210**, les 351 personnes ne bougent pas d'un compte.
I5/I6 : le moteur des visages se DIT au lieu de s'affirmer, et l'arbitre VRAM
est visible dans `/reglages` (baux, Mo libres, refus, évictions).
I8 : `/api/pets/name` et `/api/hardware` retirés (404 vérifiés).
I4 : 57 lignes rejetées le 30/07 retirées de `classifier.py` — le défaut
n'était pas le code mort mais l'en-tête, qui décrivait depuis 22 jours un
comportement que le logiciel n'avait pas.

**Le monolithe s'est ouvert : les ONZE gabarits vivent dans `ui/pages/`.**
`server.py` passe de **~17 200 à 11 986 lignes**, et **les onze pages sont
identiques au caractère près** (mêmes longueurs, mêmes empreintes avant/après).
`ui_page(nom)` relit un gabarit modifié sans redémarrage, se replie sur ce que
`bundle.py` a CUIT quand `ui/` est absent, et **DIT quel fichier manque** si les
deux manquent. Les quatre bancs qui lisaient les pages dans le source passent
par `ui_gabarits.py`, qui **lève** au lieu de se replier.

## Prochain pas

1. **Chantier 12 — la répétition, et c'est un geste de Mike.** Le protocole est
   écrit : `docs/REPETITION_RESTAURATION.md`, à suivre tel quel (restaurer pour
   de vrai dans un dossier vierge, chronométrer, puis
   `verifier_restauration.py --restaure <dossier>` — il compare les décisions
   humaines **nom par nom**, un total identique ne prouve rien).
2. **Suite de `ui/`** : le CSS commun (chaque page porte encore son `<style>`)
   puis le redesign — deux chantiers SÉPARÉS, exprès (`photo-ui`).
3. **Reste d'audit** : O7–O9, O11–O15 ; **I1** est maintenant VISIBLE dans
   `/reglages` (`tours: visages 0, animaux 0` — les deux boucles les plus
   lourdes ne passent toujours pas par `creneau()`).
4. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Une question attend Mike** (`QUESTIONS_MIKE.md`) : `personne:Florine` vit sur
**153 photos sans aucune fiche**, seul nom du fonds dans ce cas, et **149 de
ces 153 portent aussi `personne:Flo`**. La galerie propose « Florine » comme
puce de filtre, `/api/names` l'ignore : deux autorités divergent. Fusion ou
fiche à créer — jugement humain, geste sur le fonds.

**À VÉRIFIER À LA REPRISE** : la sauvegarde des quarantaines. L'inventaire du
chantier 12 disait « Total exposé : 0 o » en ne regardant que **3 corbeilles
sur 6** ; il dit maintenant **281,2 Ko** (`_corbeille_recalage`,
`_corbeille_retraits`). Les deux côtés découvrent par motif désormais, mais le
trou ne se referme qu'à la première sauvegarde horaire APRÈS le correctif —
relancer `verifier_restauration.py --vivant copie.db` et confirmer le retour à
zéro. *Un zéro parfait est une alarme : c'était le troisième de la journée.*

**Les TROIS canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer ;
`canal.py` les lit tous) : `_commande_serveur.txt` → `redemarrer`, puis
VÉRIFIER `GET /api/serveur` (`code_a_jour` vrai) ; `_commande_git.txt` →
`commit` (traite autonome) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json` ; `_commande_banc.txt` → un banc, puis
LIRE `_banc_sortie.txt`. Trois fenêtres ouvertes — Serveur, Git, Bancs ; un
agent est vivant si son `_agent_*_vu.txt` a moins de 30 s.

**Un fichier de suivi serre** : `eval/DECISIONS.md` **47 029** octets pour
50 000 (`ROADMAP.md` est redescendue à 41 000 le 22/08 en condensant les
sessions 28→35). La prochaine session qui touche aux décisions condense
d'abord — le détail vit dans git, pas dans les docs.

**Mesurer** : jamais sur `photos.db` — `mesure_copie_base.py` d'abord, puis
`--base copie.db`.

**Ne pas rouvrir sans chiffre neuf** : le chantier des rattachements (visages
ET animaux) ; les 15 clés mortes et les 6 espèces ; abaisser `CUR_ADD_SIM` ;
porter le recalage aux animaux ; 16(a) ; `taken` en base ; backfill ÉCRIT de
`faits` ; index des noms en UNE passe ; filtre des noms sur les `kw` bruts ;
`det_score` comme critère d'espèce ; règle d'espèce ÉLARGIE ; re-passe de
tagging en LOT ; agent git dans le serveur ; planchers 1990 ; plafond 2100.

**Deux pistes ouvertes par Mike (22/08)** — détail dans `ROADMAP.md` :
(a) **tirer plus du LLM local à matériel constant** — se renseigner à
l'ouverture de toute session touchant au tagging, à la description ou à la
recherche ; (b) **ouvrir la médiathèque à la famille**, dossiers persos et
contrôle de qui voit quoi.

**Un repli silencieux repéré, non traité, et il est TRIPLE** : `_serve_facecrop`
sert le visage **0** quand l'index est hors bornes, `_serve_animalcrop` fait
pareil, `/people` aussi pour l'avatar. Zéro cas aujourd'hui (mesuré), mais
c'est un mensonge muet à l'endroit exact où un humain juge.

## Ce que cette journée a coûté, et qu'il ne faut pas repayer

**Un ZÉRO parfait est une alarme, exactement comme un score parfait — et il y
en a eu TROIS dans la journée.** « 0 photo taguée » accusait la COLONNE
(`kw` au lieu de `kw_fr`). « 15 clés mortes sans contrepartie » n'a tenu
qu'après un troisième chemin, le disque. Et « Total exposé : 0 o » ne parlait
que des trois quarantaines que l'instrument connaissait, alors que le disque en
portait six.

**Une liste en dur est toujours en retard d'un chantier.** Trois corbeilles
listées quand il y en avait six ; six lectures de tags nommés là où une seule
règle suffisait. Les deux se corrigent pareil : DÉCOUVRIR au lieu d'ÉNUMÉRER,
et faire lever bruyamment ce qui manque.

**Ce que l'audit annonce, le fonds ne le confirme pas forcément.** I7 était un
vrai défaut de code et un défaut à 3 tags. Mesurer d'abord change ce qu'on
écrit ensuite : on livre une robustesse, pas une réparation — et on ne s'en
attribue pas le mérite.

**Un test qui se rabat en silence ne mesure plus rien, il rassure.** En sortant
les gabarits, quatre bancs se seraient tus si `ui_gabarits` s'était replié sur
une copie périmée. Il lève.

**La sandbox ne peut pas écrire sur le fonds.** Tout ce qui MODIFIE l'archive
se termine par un bouton dans `/reglages` ou un geste de Mike — prévois-le dans
la conception, sinon le chantier finit en cul-de-sac.
