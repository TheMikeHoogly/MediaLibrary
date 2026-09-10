# Marche à suivre — Mike

> Mis à jour le **10/09/2026 au matin**. Ce qui est ici est ce que la prochaine
> session n'aura pas à te redemander. Rien n'est urgent ; rien ne se perd si tu
> t'arrêtes en cours de route.
>
> **La règle qui vaut pour tout le document** : ne lance jamais deux gros
> travaux NAS en même temps. Un bat qui lit le NAS + le serveur qui scanne +
> une galerie ouverte = le disque à genoux. C'est ce qui a coûté deux heures de
> GPU le 06/09. **Un travail à la fois.**

---

## Ce qu'il te reste à faire — la liste courte

- [ ] **Relancer le `50 - Grand menage du depot.bat`** quand tu passes par là.
      Il propose maintenant **47 fichiers / 34,8 Mo** : 34 journaux
      d'annulation de plus de 30 jours (ils marchent enfin, voir plus bas),
      7 rapports périmés, 6 reliquats. Réponds **2** à l'étape 3.
- [ ] **Vider `_corbeille_menage\` à la main**, dans quelques jours. Le bat ne
      le fait pas exprès : *un ménage qui efface le jour même n'est pas un
      ménage, c'est un pari.* Elle contient les 506 fichiers du 09/09.
- [ ] **Lancer le `43 - Purger les originaux Motion Photo (apres verif).bat`**
      — il met les 2 409 `*.jpg_original` en quarantaine, il ne supprime rien.
      Attendu : ~9,27 Go déplacés. Puis le **bat 24** pour purger réellement.
      **Je n'ai pas revérifié qu'ils sont encore là** : si le bat annonce
      « 0 fait », c'est qu'il a déjà tourné, et ce n'est pas un échec.
- [ ] **Une fois par jour** : `/reglages` → `config.retag`. `reste` doit
      baisser, `abandons` doit rester à **0**. Si `en_file` reste à 0
      longtemps, le GPU jeûne : dis-le-moi.
- [ ] **Lire la page `/aide`** — ce n'est pas une tâche, c'est un jugement :
      c'est ta famille qui lira ce texte.

C'est tout. Le reste de ce document dit ce qui est FAIT, pour que tu n'aies pas
à te demander.

---

## A. Les trois fenêtres — le seul point vraiment nécessaire

Le 06/09 à 13h17, les trois fenêtres du bat 0 se sont arrêtées ensemble sans
prévenir : le serveur photo est resté éteint 25 minutes sans que rien ne le
dise. Sans elles, je ne peux **ni mesurer, ni livrer**.

- [x] **Vérifié le 10/09 à 07:45** : les deux agents voyaient leur canal, et le
      serveur a redémarré proprement sur le nouveau code.
- [ ] Doute ? `http://192.168.0.13:8080/reglages` répond → le serveur vit.
      Si une fenêtre manque, relance le bat 0 : il les rouvre toutes.

---

## B. Les photos sensibles — TERMINÉ

**L'onglet est à zéro.** Les 6 de l'échantillon tranchées le 07/09, les 213
candidates triées par toi le 09/09 (60 documents à la corbeille, 7 rangés en
privé, le reste rendu à la galerie), et **la dernière le 10/09**.

Trois défauts trouvés en te regardant faire, tous corrigés et observés en réel :

| Ce qui clochait | Ce que c'était |
|---|---|
| l'onglet se rechargeait depuis le haut après chaque verdict | invivable sur 213 photos — la fiche est maintenant retirée, pas la liste rechargée |
| 68 photos annoncées là où il y en avait **1** | le drapeau `sensible` survit au déménagement : 67 dossiers déjà clos revenaient avec leurs vignettes et leurs chemins |
| « Rendre privée » refusait avec *« Fichier introuvable »* | la photo était à **Flo** : le geste écrit dans `Photos Flo\PRIVE`, fermé même à l'admin. **Tu pouvais l'effacer sans pouvoir la protéger.** Tranché par toi le 10/09 : l'admin dépose partout, il ne fouille nulle part |

**Ta consigne reste la spec** : « la médiathèque conserve des SOUVENIRS, pas des
documents ». Le geste par défaut de l'onglet est la **corbeille**.

Rien n'est perdu : tout part dans `Photos\.corbeille-effacements\`, un seau
horodaté par geste, gardé **180 jours**.

---

## C. Le ménage du dépôt — FAIT, et il reste un dernier passage

Le `50 - Grand menage du depot.bat` a tourné deux fois le 09/09 : **14 fichiers
au premier passage, 506 au second**. L'écart n'est pas un caprice — mon
instrument était aveugle, et il l'était par **cinq portes** différentes. La plus
large : un élagage comparé à un nom NU protégeait la corbeille VIVANTE de la
racine et faisait taire, du même coup, la corbeille MORTE archivée dans
`_to_delete\` — 579 des 800 fichiers.

Deux choses que tu as vues et qui étaient de vrais défauts :

- **L'étape 3 te promettait un choix qu'elle ne pouvait pas tenir.** Tu as
  répondu « 2 » deux fois et lu « Rien à déplacer » : 35 des 44 journaux
  étaient vétotés par construction. Corrigé — pour cette famille, c'est **l'âge
  que tu donnes** qui juge, pas le motif.
- **`_rapport_google_apres2.json`** que tu as déclaré mort : réglé en retirant
  les deux mentions du bat 33, sans liste d'exception. L'instrument est
  d'accord de lui-même.

Tu as effacé la copie de `photos.db` du 08/09 — **283 Mo**, la plus grosse
pièce de `_to_delete\`. Bien vu : c'était le seul fichier que le veto ne
pouvait pas trancher, parce que le code cite `photos.db` partout et qu'aucun
instrument ne distingue la base vivante de sa copie.

---

## D. La corbeille de rangement — FAIT

Le 06/09 : 325 groupes réancrés (bat 46), 364 fichiers purgés (bat 24),
**25,36 Go rendus**. Le 07/09 tu as lancé le bat 47 : les **3 vraies photos
sans jumeau connu** sont revenues à leur dossier d'origine à 08:16 — Florine à
un mariage, un paysage de Bolivie avec un hérisson en peluche, trois personnes
sous un arbre en fleurs.

La question n'était pas « cette photo compte-t-elle ? » (elles comptent toutes)
mais « existe-t-elle encore ailleurs ? ». J'y avais d'abord répondu faux : le
bat 40 dédoublonne par les **pixels**, pas par les octets, et mon premier banc
cherchait par empreinte de fichier — 37 « dernières copies » dont 30 n'en
étaient pas.

---

## E. La chaîne Google — CLOSE

Le bat 49 est passé le 09/09 : les cinq contrôles, l'étape qui a jugé les
**14 absentes jetables** (moitiés vidéo de Motion Photos, deux preuves
chacune), le `EFFACER` écrit en toutes lettres. **C: est passé de 171,2 à
236 Go libres sur 932** — les 96 Go annoncés, à la mesure près.

Plus de Takeout, ni en `.zip` ni en extrait. Le NAS porte tout ce qui devait
l'être.

> Ce que ce bat aura appris, et qui vaut plus que les 96 Go : un garde-fou qui
> ne sait dire que « bloqué » finit par être contourné. Celui-ci a appris à
> **distinguer** — deux preuves pour déclarer une absente jetable, et l'arrêt
> sinon. C'est la différence entre un verrou et un jugement.

**Et le fait qui reste vrai, sans se répéter à chaque session** : depuis cet
effacement, le NAS est le **seul exemplaire** des ~40 600 photos. Un NAS chez
soi ne protège ni du feu, ni du vol, ni d'une fausse manœuvre. Tu as placé la
copie hors site en fin de roadmap le 09/09 — c'est ton choix et il est noté
tel quel.

---

## F. La campagne de retag

Elle tourne toute seule depuis le 05/09. Le levier est `retag_actif.txt`, un
fichier **vide** à la racine. **Ne l'efface pas** : l'effacer arrête la
campagne au lot suivant (rien n'est perdu, mais elle s'arrête).

Fin attendue autour du **14/09** — ~190 photos/heure, comptées dans le journal.

Ce qu'il faut savoir sur son rythme, pour ne pas t'inquiéter à tort :

- **Quand tu navigues dans la photothèque, le tagueur s'efface.** C'est voulu :
  l'interface a la priorité sur le NAS. Une campagne qui ralentit pendant que
  tu regardes des photos n'est pas en panne.
- Un **redémarrage du serveur** ne coûte plus que **9 secondes** de GPU
  inoccupé (corrigé le 07/09, observé trois fois depuis).

---

## G. Ce que je te dois encore — ma liste, pas la tienne

1. **Réviser les fichiers de règles** (`CLAUDE.md`, ce document) — **fait le
   10/09**, et c'était le point le plus important : cinq règles mesurées les
   09 et 10/09 n'existaient que dans un carnet éphémère.
2. **`_reconcilier` re-hashe tout le store à chaque `save()`** (point d'audit
   O14). C'est du chemin de service, pas du calcul IA : réparable pendant que
   le GPU est pris. **C'est le meilleur gain de performance qui reste.**
3. **Reprendre la mesure des photos sensibles sur `qwen3.5:4b`** — l'ancienne
   portait sur `qwen3-vl:2b`, avec tes verdicts comme vérité terrain.
   **Après la campagne** : un banc qui interroge le modèle lui prend le GPU.
4. **La question au tagueur sur les documents** — elle n'est pas reportée par
   prudence, elle est **empêchée** : toucher au prompt rouvrirait les ~12 000
   photos déjà refaites.
5. **Le bilan chiffré de la campagne** : ce que `qwen3.5:4b|v3fr|kb1` a changé,
   mesuré et non supposé. C'est la première passe officielle du fonds.
6. ~~Empêcher deux balayages NAS simultanés.~~ **À MOITIÉ** : la maintenance se
   retire quand un scan tourne. Reste l'ordre inverse — une maintenance déjà
   partie, puis le scan qui arrive dessus. Je n'y ai pas touché : la ligne
   porte un garde-fou posé exprès, et je n'ai pas de mesure pour le remplacer
   sans risque.

---

## Si quelque chose cloche

- **Une page tourne sans fin** → cherche un autre onglet de la photothèque
  ouvert sur un gros dossier, et ferme-le. Chrome n'ouvre que six connexions
  par site, et une planche pouvait les prendre toutes.
- **Un bat dit ECHEC** → lis la ligne au-dessus. « Déjà fait » n'est pas un
  échec, et deux bats l'ont crié à tort (45 puis 42) ; les deux sont corrigés.
- **Un bat semble sauter des étapes** → ne me laisse **jamais** le réécrire
  pendant qu'il tourne. `cmd.exe` relit le fichier par décalage d'octets :
  le 09/09, +70 octets ajoutés pendant le bat 49 lui ont fait exécuter un
  fragment de ligne, d'où un « Python est introuvable » et un message d'arrêt
  entièrement faux.
- **Le serveur ne répond plus** → bat 0. Si les fenêtres sont là mais muettes,
  ferme-les et relance le bat 0.
- **Tu veux tout annuler** → chaque outil destructif a son journal dans `docs/`
  (`undo_*.json`) et son option `--annuler`. Le bat 50 a le sien
  (`_corbeille_menage\<horodatage>\_manifeste.json`). Rien n'est irréversible,
  sauf le bat 24 — et lui ne touche que ce dont l'existence d'une autre copie
  a été prouvée au bit près.
