# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 32)

**Le chantier des décisions humaines est CLOS** (session 31 : 787 décisions
re-clées, 0 sans contrepartie, résidu gardé par choix de Mike). Cette session a
attaqué le **point 1 du prochain pas** — juger la tranche 0,35–0,40 — et elle
s'arrête là où il fallait qu'elle s'arrête : **l'instrument est prêt, le
jugement appartient à Mike.**

**Ce qui est LIVRÉ.** `mesure_tranche_seuil.py` (25 tests) n'a pas de règle à
lui : il importe celle de `mesure_propagation_noms` — seuils lus dans
`server.py`, stores de prod, facettes, et `noter_visages()` extraite pour être
partagée — et n'y ajoute que des BORNES. Tirage **uniforme** sur la tranche,
graine fixe : prendre les 30 meilleurs mesurerait le haut et conclurait sur
tout, l'erreur exacte du 20/08. La page **`/tranche`** (15 tests) donne
l'échantillon à juger et **n'attribue RIEN** — ni tag, ni fiche, ni XMP. C'est
la condition du chiffre : mesurer un seuil avec des rattachements qu'on vient
soi-même de poser ne mesure rien. Le serveur COLLECTE, le banc CONCLUT.

**Ce qui est MESURÉ.** Dans la tranche, après les garde-fous humains :
**1 190 candidates** (685 écartées « déjà dit », 64 par une exclusion),
**22 clés fantômes** retirées, **1 168 vivantes**, **30 tirées**. Observé en
réel sur le serveur : 30 items servis, vignettes en 200, verdict écrit,
verdict inconnu refusé en 400.

**Ce qui n'est PAS mesuré, et c'est le point** : le taux. Aucun jugement n'a
été posé. Le banc le dit lui-même — « un banc sans verdict n'est pas un banc ».

**Et la page a fait tomber plus gros qu'elle.** Mike a vu, à l'œil, une planche
« visages déjà confirmés de Didier » contenant Laura Waller, une de Mathieu
contenant Mathilde. Un rattachement est un couple `[photo, index du visage]` ;
`reembed_one_batch` REMPLACE `e['faces']` quand il ré-analyse une photo, donc
l'index finit par désigner quelqu'un d'autre **de la même photo**. Mesuré :
**42 décalés sur 1 194** (3,5 %), minimum **−0,13**, et le croisement nomme la
cause — **5,4 %** sur les photos réellement re-détectées contre **0,4 %**
ailleurs, 41 sur 42. Le premier croisement, bâti sur le drapeau `reemb`, rendait
**100 %** : instrument mort (le drapeau est aussi posé sur les photos seulement
EXAMINÉES) ; `reemb_ms` discrimine.

**Réparation LIVRÉE et vérifiée à blanc** : `recale_rattachements.py` (règle
pure, 27 tests) + trois boutons `/reglages`, quarantaine `_corbeille_recalage/`.
Aperçu sur le serveur vivant : **32 à recaler, 34 « ambigu », 1 « déjà pris »**
— mêmes nombres que le banc, deux chemins. La règle refuse plus qu'elle ne
répare, volontairement : une PERMUTATION entre deux personnes d'une même photo
se refuse des deux côtés.

## Prochain pas

0. **`/reglages` → « Rattachements qui désignent le mauvais visage » →
   2 · Appliquer.** Ça passe avant tout le reste : juger la tranche contre une
   planche de référence fausse ne mesurerait rien. Puis relancer
   `mesure_rattachements.py --base copie.db` pour l'observer.
1. **Juger les 30 sur `http://192.168.0.13:8080/tranche`** (clavier `1` / `2` /
   `3`, `Z` pour revenir), puis `mesure_tranche_seuil.py --bilan` dans
   `_commande_banc.txt`. Le bilan rend le taux **avec son intervalle de
   Wilson** — 30 tirages ne sont pas un pourcentage — et dit ce que
   l'intervalle autorise à conclure. Si la tranche tient, abaisser
   `CUR_ADD_SIM` ne demande **aucun code** : une ligne dans `seuils.txt`.
   *(Une entrée d'essai `__essai_claude__` traîne dans
   `journal_jugements.jsonl` — la vérification du chemin d'écriture. Elle n'est
   pas dans `_tranche_jugements.json`, donc elle ne fausse aucun compte.)*
1bis. **Le résidu du recalage : 34 « ambigu » + 1 « déjà pris ».** Le score ne
   les départage pas — soit la personne est vraiment détectée deux fois, soit
   l'index égaré désigne son voisin. Ils se jugent à l'œil, sur une page, comme
   la tranche. Et **`PETS` n'a jamais été mesuré** : son magasin porte des
   empreintes DINOv2 et `assigned_keys` ne le lit pas.
2. **Chantier 12 — la répétition** (choix de Mike : ordre 1-4-3-2). Restaurer
   POUR DE VRAI sur un dossier vierge, chronométrer, puis
   `verifier_restauration.py --restaure <dossier>` : il compare les décisions
   humaines **nom par nom** — un total identique ne prouve rien.
3. **Correctifs d'audit I4–I8.** Dont **I7**, un vrai défaut produit : la casse
   des tags nommés n'est normalisée qu'à trois endroits, donc un
   `personne:nom` importé n'est **jamais** auto-guéri. Puis I4 (code mort
   rejeté), I5/I6 (`/reglages` ment sur le GPU), I8 (routes orphelines).
4. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Une décision à cinq secondes qui traîne depuis quatre sessions** :
l'extraction `ui/` (point 7) — lui donner une session ou la parquer.

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

**Un échantillon se tire UNIFORMÉMENT**, jamais par le haut : le 20/08, deux
échantillons choisis ont porté une conclusion que le banc complet a réfutée.
Et **un verdict ne se mélange jamais au geste qu'il gouverne** — c'est pour ça
que `/tranche` n'attribue rien.

**Un croisement à 100 % ne croise rien.** Le 22/08, le premier croisement du
banc des rattachements a rendu « 100 % du fonds est re-embarqué » : ce n'était
pas un résultat, c'était un drapeau que tout le monde porte. Avant de conclure
d'un croisement, regarder son DÉNOMINATEUR.

**Un test ne doit rien imprimer.** L'agent git CAPTURE la sortie ; sous Windows
un `print` part alors dans un tuyau, l'encodage local reprend la main, et le
premier « é » tue le test par `UnicodeEncodeError`. Deux refus de livraison le
22/08, pour ça exactement.

**La sandbox ne peut pas écrire sur le fonds.** `POST` de renommage,
d'attribution ou d'application est refusé côté Claude. Tout ce qui MODIFIE
l'archive se termine donc par un bouton dans `/reglages` ou un geste de Mike —
prévois-le dans la conception, sinon le chantier finit en cul-de-sac.
