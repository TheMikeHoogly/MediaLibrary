# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».
>
> **Vidée le 28/08** : les dix-neuf entrées réglées entre le 19 et le 28/08
> ont été retirées — leur verdict vit dans les fichiers de décisions, leur
> récit dans git. Un carnet de questions qui garde ses réponses cesse d'être
> lisible, et c'est le premier endroit qu'on lit en reprenant.

## En attente

### 1. Les 2 929 doublons identiques : on passe à l'applicateur ? (30/08 nuit)
Mesuré (`docs/doublons_image.json`) : 2 757 groupes aux mêmes pixels, 10,45 Go
à rendre, canonique par ta règle (Mike ; sinon la copie rangée par année),
18 noms à recopier avant retrait, 233 groupes différents laissés tels quels.
**Recommandation** : un `appliquer_doublons_image.py` à blanc d'abord
(aperçu : qui part, qui reste, ce qui est recopié), puis quarantaine
réversible dans `.corbeille-rangement` avec manifeste (la purge à 30 j
existante s'applique), serveur ARRÊTÉ comme bat 26, journal d'undo. Commencer
par les 833 groupes Flo+Mike (Indonésie, Calinous) : c'est là que ta règle
tranche. En attendant : rien ne bouge.

### 2. Recherche IA : élargir la requête française par l'anglais ? (30/08 nuit)
Mesuré : EN bat FR sur 33 paires sur 40 (+17 % de rappel), FR+EN rattrape
80 % de l'écart, et le gabarit « une photo de … » fait perdre 3 points.
**Recommandation** : (a) retirer le gabarit ; (b) dictionnaire FR→EN tiré
des paires `kw_fr`/`kw_en` de l'index (co-occurrence, aucune dépendance),
requête élargie = moyenne des vecteurs FR et EN, mot par mot et sur la
phrase entière ; (c) re-mesurer avec le même banc AVANT/APRÈS. Coût : un
dictionnaire recalculé au démarrage (secondes). Ce que ça ne règle pas :
« ours en peluche » n'est pas un tag fréquent — la phrase entière passe
alors telle quelle, comme aujourd'hui.

