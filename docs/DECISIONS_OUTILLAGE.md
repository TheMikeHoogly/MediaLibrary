# Décisions tranchées — OUTILLAGE

> **Comment la sandbox agit sur la machine de Mike** : les trois canaux, le
> pilotage du serveur, la livraison git, les superviseurs. Chaque piste, son
> verdict, pour ne rien re-proposer.
>
> **Pourquoi ce fichier existe** (20/08, choix de Mike). `eval/DECISIONS.md`
> débordait pour la deuxième fois en deux jours. L'archive PAR STATUT avait été
> rejetée le 19/08, et à raison : elle coupait un même domaine en deux selon
> l'âge, donc il fallait relire les deux fichiers pour ne rien re-proposer.
> Le découpage par DOMAINE n'a pas ce défaut — le réflexe est lui-même par
> domaine. Qui travaille la recherche n'a jamais besoin de savoir pourquoi
> `taskkill` a échoué ; qui touche aux canaux n'a que faire du gazetteer.
> Précédent : `eval/METHODE.md`, sorti le 16/08.
>
> Le détail des travaux vit dans **git** ; la méthode dans `eval/METHODE.md` ;
> ce qui concerne la PHOTOTHÈQUE elle-même dans `eval/DECISIONS.md`.

## Pilotage du serveur

| Idée / piste | Verdict | Raison |
|---|---|---|
| Route HTTP, ou serveur qui se relance seul | **REJETÉ** (19/08) | Il ne peut garantir que son port est libéré, et s'il rate son réveil la sandbox reste dehors. |
| `arret` coupe aussi le superviseur | **REJETÉ** (19/08) | Un arrêt sans retour est un piège, Mike absent : `arret` met le superviseur en ATTENTE. Illisible → `marche`. |
| Libérer le port PUIS les préparatifs lents | **CORRIGÉ** (19/08) | 40 s de `pip` entre le kill et le démarrage : un orphelin reprenait le port. Le lent passe AVANT ; port tenu après 10 essais → on ne lance RIEN. |
| `taskkill` par TITRE DE FENÊTRE retire l'ancien superviseur | **FAUX** (20/08) | Il ne retrouve pas fiablement les fenêtres console : il n'a RIEN tué. L'ancien superviseur a survécu, a pris pour un plantage le kill par PID de son serveur, et en a relancé un second — **deux fenêtres « MediaLibrary - Serveur »**, le verrou de port passé pourtant. Remplacé par une GÉNÉRATION : le bat 0 écrit un jeton neuf, chaque superviseur le relit à chaque tour et se retire s'il a changé. Un titre se devine, un fichier se lit. |

## Livraison git

| Idée / piste | Verdict | Raison |
|---|---|---|
| **Livrer dans git depuis la sandbox** | **ADOPTÉ, OBSERVÉ** (19/08) | `git` lancé depuis la VM laisse un `.git/index.lock` qu'elle ne sait pas supprimer (elle écrit, elle n'efface pas) : jamais un principe, une impossibilité. Un agent WINDOWS lance le vrai git. Premier acte observé : il s'est commité lui-même (`a43f9d0`, 10 fichiers), push et fast-forward de main compris. |
| L'agent est un bouton déporté | **REJETÉ** (19/08) | Il est la **porte** : refus tant que le serveur ne tourne pas le code visé, qu'un test est rouge, qu'un `.bat` n'est pas ASCII ou que le lint crie. D'où l'ordre **inversé**. |
| **`commit` = branche + push** | **CORRIGÉ, OBSERVÉ** (20/08, choix de Mike) | `CLAUDE.md` l'annonçait, le code s'arrêtait au commit LOCAL — vérifié dans `.git`, pas dans le rapport de l'agent : `refs/remotes/origin/feat/…` n'existait pas. Une traite autonome ne vivait donc que sur le disque de Mike, le scénario même du chantier 12 (« PC mort lundi »). Les deux modes poussent désormais ; `main` reste intacte, car c'est elle que la convention protège, pas l'absence de copie. Le banc tournait « sans distant » : il VALIDAIT le défaut — il tourne maintenant contre un dépôt bare local. |
| `force=` lève tous les contrôles | **REJETÉ** (19/08) | Il lève les NÉGOCIABLES — serveur à jour, tests, `.bat`, lint — et sa raison part dans le journal. Jamais le verrou `.git/*.lock`, jamais `main`, jamais un binaire (`photos.db` fait 290 Mo), jamais un `checkout` vers une branche EXISTANTE, qui réécrirait `server.py` sous le serveur qui tourne. Six tests vérifient exactement ce qu'il n'ouvre pas. Premier usage réel le 20/08 : budget de doc dépassé, arbitrage rendu à Mike. |
| Loger l'agent dans le serveur | **REJETÉ** (19/08) | Le serveur est l'OBJET du commit ; un git qui bloque bloquerait une requête ; et un serveur du LAN qui lance git est une surface qu'on ne veut pas. |

## Les trois canaux

| Idée / piste | Verdict | Raison |
|---|---|---|
| Une fenêtre d'agent minimisée | **REJETÉ** (19/08) | Elle s'est fermée sans que personne le voie : une fenêtre morte-née était indiscernable d'une fenêtre en écoute, et rien ne se livrait sans que rien ne le dise. Fenêtre VISIBLE, `_agent_*_vu.txt` touché à chaque tour, commande `ping` inerte, contrôle du bat 0 après 6 s. |
| **Un troisième canal : lancer un BANC sous Windows** | **ADOPTÉ, OBSERVÉ** (20/08) | La sandbox n'atteint pas le LAN (`X-Proxy-Error: blocked-by-allowlist`) : un banc qui interroge le serveur — c'est lui qui détient SigLIP — ne peut pas tourner chez elle. Livré NON TOURNÉ, il a fallu le clavier de Mike, et sa sortie a RÉFUTÉ une conclusion tirée de deux échantillons. `banc_agent` ne lance QUE les familles qui MESURENT (`mesure_ verifier_ diagnostic_ comptes_ inventaire_ test_ eval_`), sans shell (`subprocess.run` reçoit une liste : `&&` n'est pas filtré, il est sans effet), sans chemin, sans `force=`. Observé : `verifier_bat.py` rendu en 0,1 s accents intacts, `purger_corbeille.py` refusé pour sa famille, `mesure_faits_vue.py --base photos.db` refusé par le banc lui-même. |
| Loger les bancs chez l'agent git | **REJETÉ** (20/08) | Un banc de dix minutes bloquerait le canal de livraison pendant tout ce temps — c'est-à-dire exactement au moment où l'on veut livrer ce qu'on vient de mesurer. Troisième fenêtre, à contrecœur : elle coûte à Mike, le blocage coûterait plus. |
| Trois canaux, trois lecteurs de fichier | **CORRIGÉ** (20/08) | La lecture tolérante (BOM, CRLF, LF nu) et l'écriture atomique en CRLF explicite étaient recopiées DEUX fois à l'identique ; une troisième copie et la règle cessait d'exister. `canal.py` les porte ; chaque agent garde son VOCABULAIRE et sa porte. `lire_ligne` ne met rien en minuscules — un canal transporte un chemin, et `Copie.db` n'est pas `copie.db`. |

> **Méthode : `eval/METHODE.md`** — ici *ce qui a été tranché sur l'outillage*,
> là *comment on tranche*. La photothèque : `eval/DECISIONS.md`.
