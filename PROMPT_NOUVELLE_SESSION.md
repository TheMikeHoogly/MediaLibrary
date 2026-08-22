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

**LE CHANTIER 12 EST CLOS : la répétition a eu lieu, et elle est RÉUSSIE
(22/08, 22:51).** Base restaurée depuis le NAS sur un dossier neuf, comparée au
vivant : intégrité ok, six tables identiques, **363 noms des deux côtés, AUCUN
écart de décision nom par nom**. 60 s pour les 250 Mo de la base. Tous les
artefacts IRRÉCUPÉRABLES sont revenus. La sauvegarde a cessé d'être une
promesse. **Reste ouvert, et c'est un choix de Mike : la copie HORS SITE** —
un sinistre qui emporte le PC ET le NAS emporte tout.

**Ce que la répétition a trouvé en chemin — cinq défauts, tous muets** :
l'inventaire ne voyait que 3 quarantaines sur 6 ; le garde-fou « ne jamais
ouvrir photos.db » refusait la base RESTAURÉE (la comparaison nom par nom
n'avait jamais pu tourner) ; un dossier vide se lisait « 0 o exposé » ;
`robocopy` meurt en ERREUR 59 après ~72 s sur 250 Mo et recommence à chaque
essai (`copier_reprise.py` passe en 60 s et REPREND à l'octet) ; et trois
défauts de `.bat`, dont une parenthèse dans un `echo` au sein d'un bloc, que
`verifier_bat.py` sait désormais voir.

**Mike a tranché : Flo et Florine sont la même personne.** La préparation de la
fusion a débusqué un défaut de règle 2 : `SubjectStore.rename` transportait
`refs`/`exclude`/`faces` mais **pas `confirmed`, `avatar`, `nomerge`** — les
**143** confirmations de la fiche Flo seraient parties en silence, et le même
défaut valait pour chaque fusion du curateur depuis l'origine. Corrigé.
**Et la fusion est devenue réversible** : c'était le seul geste destructeur sans
quarantaine, et le plus lourd (**11 814 opérations XMP sur 5 907 photos**).
`_corbeille_fusions/` note les deux fiches et, photo par photo, si elle portait
**déjà** le nom d'arrivée — sans quoi annuler volerait Florine aux 149 photos
qui portaient les deux. Bouton `Annuler la derniere fusion` dans `/reglages`,
35 tests.

## Prochain pas

1. **La fusion Flo → Florine, par Mike** : `/people` → fiche Flo → Renommer →
   `Florine`. Écriture sur le fonds, donc son geste, pas celui de la sandbox.
   Ensuite VÉRIFIER : `/api/names` doit rendre **une** Florine à ~5 911 et plus
   aucun Flo, ses **143** confirmations intactes ; la file XMP se vide en tâche
   de fond (des heures). Si quelque chose cloche : `/reglages` →
   `Annuler la derniere fusion`.
2. **Copie HORS SITE (chantier 12 bis)** — le seul manque qui reste à
   l'assurance-vie, et il demande une décision avant du code.
3. **Suite de `ui/`** : le CSS commun (chaque page porte encore son `<style>`)
   puis le redesign — deux chantiers SÉPARÉS, exprès (`photo-ui`).
4. **Reste d'audit** : O7–O9, O11–O15 ; **I1** est maintenant VISIBLE dans
   `/reglages` (`tours: visages 0, animaux 0` — les deux boucles les plus
   lourdes ne passent toujours pas par `creneau()`).
5. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Rien n'attend Mike dans `QUESTIONS_MIKE.md`** — la question Florine est
répondue, et sa réponse est le point 1 ci-dessus.
