# Marche à suivre — Mike

> Mis à jour le 07/09/2026 au matin. Ce qui est coché ici est ce que la
> prochaine session n'aura pas à te redemander.

> Tout ce que j'attends de toi, dans l'ordre, avec le résultat à voir à chaque
> étape. Coche au fur et à mesure. Rien ici n'est urgent ; rien ici ne se perd
> si tu t'arrêtes en cours de route.
>
> **Une règle qui vaut pour tout ce document** : ne lance jamais deux gros
> travaux NAS en même temps. Un bat qui lit le NAS + le serveur qui scanne + une
> galerie ouverte = le disque à genoux, et c'est exactement ce qui a coûté deux
> heures de GPU aujourd'hui. Un travail à la fois.

---

## A. Les trois fenêtres — à vérifier avant tout

Le 06/09 à 13h17 les trois fenêtres du bat 0 se sont arrêtées ensemble, sans
prévenir. Le serveur photo était éteint pendant 25 minutes sans que rien ne le
dise.

- [x] **Les trois fenêtres du `0 - Démarrer le serveur.bat` sont ouvertes**
      (Serveur, Git, Bancs). **Vérifié le 07/09 à 07:12** : les deux agents
      avaient vu le canal depuis moins de 5 s, et le serveur écrivait au
      journal. Si l'une manque un jour, relance le bat 0 : il les rouvre
      toutes.
- [ ] Doute ? `http://192.168.0.13:8080/reglages` répond → le serveur vit.

---

## B. Les 6 photos sensibles — FAIT

Les six sont traitées. Deux étaient déjà à la corbeille le 06/09 (le relevé
Migros et la carte d'assurance-maladie) ; **j'ai effacé les quatre autres le
07/09 au soir**, sur ta consigne — « la médiathèque est censée conserver des
photos et vidéos de souvenirs, et non des documents » :

| Effacé | Ce que c'était |
|---|---|
| `Photos Mike\2023\20230326_190923.jpg` | décompte de charges + bulletin de versement (IBAN) |
| `Photos Mike\2022\20220805_200910.jpg` | courrier bancaire avec IBAN — au nom d'un tiers, en Bolivie |
| `Photos Flo\Floufline\20240226_223732.jpg` | document officiel au nom de Florine |
| `Photos Mike\2026\20260201_202623.jpg` | certificat médical d'incapacité de travail |

**Rien n'est perdu** : elles sont dans `Photos\.corbeille-effacements\`, une
par seau horodaté, et la purge automatique les garde **180 jours**. Le décompte
de charges concerne la PPE — si tu en as besoin pour tes comptes, il est encore
là.

- [x] **`_planches\` et `_planches_corbeille\` supprimés** — ils contenaient
      des copies lisibles de ces documents. Note au passage : la « basse
      définition » ne protégeait rien (un IBAN et une date de naissance s'y
      lisaient), c'est écrit dans `eval/METHODE.md`.

Ta consigne change aussi la spec de l'onglet Sensibles : le geste par défaut
devient **Corbeille**, pas « Rendre privée ». Voir `ROADMAP.md` § 3 bis.

---

## C. Motion Photos — le bat 43

Le **bat 42 est terminé depuis le 03/09** : 2 409 photos strippées, 9,27 Go de
vidéo retirés. Le relancer ne fait rien (le passage du 06/09 l'a confirmé :
0 faits, 20 déjà propres). Ne le relance plus.

- [ ] **Lancer le `43 - Purger les originaux Motion Photo (apres verif).bat`** —
      il met les 2 409 `*.jpg_original` en quarantaine, il ne supprime rien.
      Attendu : ~9,27 Go déplacés.
- [ ] Puis le **bat 24** pour purger réellement.

---

## D. La corbeille de rangement — ce qui reste

Le 06/09 : 325 groupes réancrés (bat 46), 364 fichiers purgés (bat 24),
**25,36 Go rendus**. Restent 77 groupes.

- 33 ont moins de 30 jours : **rien à faire**, ils partiront d'eux-mêmes au
  prochain bat 24.
- 44 refusent la purge parce que leur copie gardée est introuvable.

La question n'était PAS « cette photo compte-t-elle ? » (elles comptent
toutes) mais « existe-t-elle encore ailleurs ? ». **Tranché le 06/09 au soir**,
après une première réponse fausse de ma part (voir ROADMAP : le bat 40
dédoublonne par les PIXELS, pas par les octets — mon premier banc cherchait
par empreinte de fichier et rendait 37 « dernières copies » dont 30 n'en
étaient pas) :

- **36 sont des doublons réels** → purgeables sans risque.
- **4 sont des coquilles « Read error in the sector ! »** de la vieille
  récupération de disque, même famille que les 942 → à jeter, elles ne
  contiennent rien.
- **3 seulement sont de vraies photos sans jumeau connu** → à **RESTAURER** :
  Florine à un mariage, un paysage de Bolivie avec un hérisson en peluche, et
  trois personnes sous un arbre en fleurs. Tu les vois dans
  `_planches_corbeille\les_7_a_juger.jpg`.

**L'outil existe depuis le 07/09 : `47 - Restaurer les photos sans jumeau
connu.bat`.** Il ne supprime rien, il n'écrase jamais un fichier existant, et
il s'annule (journal dans `docs/`). Il commence par un aperçu ; tu peux
répondre **N** et rien ne bouge. Je ne l'ai pas lancé moi-même : déplacer des
photos dans ton archive passe par un bat, comme tous les outils qui touchent
aux fichiers.

**Vérifié pour toi le 07/09 avant de te le donner** — les trois photos sont
présentes en quarantaine, leur empreinte correspond à leur manifeste, et leur
dossier d'origine existe et est LIBRE :

| Photo | Retourne dans |
|---|---|
| `IMG-20180527-WA0008.jpg` | `Photos Flo\Floufline\` |
| `IMG-20150729-WA0018.jpg` | `Photos Flo\2015 Bolivie\` |
| `IMG-20210426-WA0002.jpg` | `Photos Flo\Sista\40 ans Val et Thierry\` |

- [ ] **Lancer le bat 47** (aperçu, puis O pour restaurer).
- [ ] Puis le **bat 24** pour purger ce qui reste.
- [ ] **Supprimer `_planches_corbeille\`** et `_planches\` quand tu les as vus
      — dis-le-moi et je peux le faire, tu m'as donné le droit d'effacer dans
      `C:\Prog\Claude\MediaLibrary` ce matin.

---

## E. La campagne de retag

Elle tourne toute seule. Le levier est `retag_actif.txt` — un fichier VIDE à la
racine du projet. **Ne l'efface pas** : l'effacer arrête la campagne au lot
suivant (rien n'est perdu, mais elle s'arrête).

- [ ] **Une fois par jour**, jeter un œil à `/reglages` → `config.retag` :
      `reste` doit baisser, `abandons` doit rester à 0.
- [ ] Si `en_file` reste à 0 longtemps, le GPU jeûne : dis-le-moi.
- [ ] **Le 9 septembre** : redémarrage Patch Tuesday. Après le redémarrage de
      Windows, relance le bat 0 — sinon rien ne repart.

Ce qu'il faut savoir sur son rythme, pour ne pas t'inquiéter à tort :

- **Quand tu navigues dans la photothèque, le tagueur s'efface.** C'est voulu :
  l'interface a la priorité sur le NAS. Une campagne qui ralentit pendant que tu
  regardes des photos n'est pas en panne.
- Un **redémarrage du serveur** ne coûte plus que **9 secondes** de GPU
  inoccupé (corrigé le 07/09 au matin, observé deux fois). Avant, c'était
  entre 1 minute et 81 minutes selon l'humeur du NAS — je disais « ~15 min »,
  c'était une moyenne qui cachait le vrai problème : ça ne dépendait pas du
  code, mais du disque.

---

## E bis. Avant de dire « go ! » à la prochaine session

Rien de tout ceci n'est bloquant — tu peux dire « go » sans, je reprendrai
l'état réel de toute façon. Mais chacun de ces trois points m'évite de te
poser une question et fait gagner du temps :

- [ ] **Les trois fenêtres du bat 0 tournent** (section A). C'est le seul
      point vraiment nécessaire : sans elles je ne peux ni mesurer, ni livrer.
- [ ] **Les 6 photos sensibles sont traitées** (section B). Au 06/09 22h30,
      deux sont déjà à la corbeille (le relevé Migros et la carte
      d'assurance-maladie) ; les quatre autres sont encore en place. Le
      collage est dans `_planches\les_6_sensibles.jpg`.
- [ ] **Tu as jeté un œil aux 3 photos à restaurer** (section D,
      `_planches_corbeille\les_7_a_juger.jpg`). Si elles te vont, tu n'as rien
      à dire : je les restaure et je purge le reste.

Et une chose à me dire seulement si elle a changé : **as-tu touché à
`retag_actif.txt`** ou arrêté la campagne ? Si oui, dis-le en une ligne avec le
« go » — c'est le fait qui commande tout le reste.

## F. Ce que je te dois encore

Rien de tout ceci n'attend un geste de ta part — c'est ma liste, pas la tienne.
Elle est là pour que tu saches où on en est.

1. **L'ONGLET SENSIBLES** — celui que tu as demandé, et le gros morceau de la
   prochaine session. L'application te dit ce qu'elle a trouvé ; la photo est
   masquée sans bouger en attendant ton verdict.
2. ~~Remplir la file de retag AVANT le travail de démarrage.~~ **FAIT le
   07/09**, et mesuré : 9 secondes au lieu de 1 à 81 minutes.
3. ~~Empêcher deux balayages NAS simultanés.~~ **FAIT À MOITIÉ le 07/09** : la
   maintenance se met maintenant en retrait quand un scan tourne — c'est
   l'ordre qui a coûté les 85 minutes du 06/09 à midi. **Reste l'ordre
   inverse** (une maintenance déjà partie, puis le scan qui arrive dessus) ;
   je ne l'ai pas touché parce que la ligne concernée porte un garde-fou posé
   exprès, et que je n'ai pas de mesure pour le remplacer sans risque.
4. ~~L'outil qui restaure les 3 dernières copies de la corbeille.~~ **FAIT
   le 07/09**, et **tu l'as lancé** : les trois photos sont revenues à leur
   dossier d'origine à 08:16.
6. ~~Le `_exiftool_tmp` orphelin qui ferme une photo pour toujours.~~ **TROUVÉ
   ET CORRIGÉ le 07/09 au soir.** Quand une écriture dépassait son délai, le
   fichier de travail d'ExifTool restait sur le NAS et toutes les écritures
   suivantes sur cette photo échouaient — 13 photos en huit heures, et ça
   grossissait. Le serveur le ramasse maintenant sur preuve, et une passe
   unique a rouvert les 22 photos déjà touchées. Zéro tmp restant.
5. **Reprendre la mesure des photos sensibles sur `qwen3.5:4b`** (l'ancienne
   portait sur `qwen3-vl:2b`), avec les 24 verdicts humains comme vérité
   terrain. **Après la campagne** : un banc qui interroge le modèle pendant
   qu'elle tourne lui prend le GPU.

*(Le chargement paresseux des vignettes est fait ET observé : 585 tuiles,
30 chargées, 555 en attente, plafond à 4.)*

---

## Si quelque chose cloche

- **Une page tourne sans fin** → regarde s'il y a un autre onglet de la
  photothèque ouvert sur un gros dossier. Ferme-le. Chrome n'ouvre que six
  connexions par site, et une planche pouvait les prendre toutes.
- **Un bat dit ECHEC** → lis la ligne au-dessus. « Déjà fait » n'est pas un
  échec, et deux bats l'ont déjà crié à tort (45 puis 42) ; les deux sont
  corrigés.
- **Le serveur ne répond plus** → bat 0. Si les fenêtres sont là mais muettes,
  ferme-les et relance le bat 0.
- **Tu veux tout annuler** → chaque outil destructif a son journal dans `docs/`
  (`undo_*.json`) et son option `--annuler`. Rien de ce qui a été fait
  aujourd'hui n'est irréversible, sauf le bat 24, qui ne touche que ce dont
  l'existence d'une autre copie a été prouvée au bit près.
