# Marche à suivre — Mike

> Mis à jour le 06/09/2026 au soir. Ce qui est coché ici est ce que la
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

- [ ] **Les trois fenêtres du `0 - Démarrer le serveur.bat` sont ouvertes**
      (Serveur, Git, Bancs). Si l'une manque, relance le bat 0 : il les rouvre
      toutes.
- [ ] Doute ? `http://192.168.0.13:8080/reglages` répond → le serveur vit.

---

## B. Les 6 photos sensibles (chantier 18)

Ce sont les seules de l'échantillon qui méritent d'être privées. La liste
détaillée est dans `ROADMAP.md`, section « 3 bis ».

Pour chacune : colle le lien, clique la vignette, puis **🔒 Rendre privée** dans
la visionneuse. Le geste déplace la photo dans le `PRIVE` de son propriétaire,
et il est annulable.

- [ ] `…/browse/1/Photos%20Mike/2026/260531_Samsung_MHU/Camera#voir=20260411_160856.jpg` — relevé bancaire
- [ ] `…/browse/1/Photos%20Mike/2023#voir=20230326_190923.jpg` — décompte de charges + IBAN
- [ ] `…/browse/1/Photos%20Mike/2022#voir=20220805_200910.jpg` — courrier bancaire + IBAN
- [ ] `…/browse/1/Photos%20Mike/2026/260531_Samsung_MHU/Camera#voir=20260502_093501.jpg` — carte d'assurance-maladie
- [ ] `…/browse/1/Photos%20Flo/Floufline#voir=20240226_223732.jpg` — document officiel au nom de Florine → part dans **son** PRIVE
- [ ] `…/browse/1/Photos%20Mike/2026#voir=20260201_202623.jpg` — certificat médical

(Préfixe complet : `http://192.168.0.13:8080`)

- [ ] **Supprimer le dossier `_planches\`** quand c'est fini : il contient des
      copies basse définition de ces six documents.

**Nouveau (06/09 soir) : tu peux en faire plusieurs d'un coup.** Dans
l'onglet **Dossiers**, coche les photos, puis **🔒 Rendre privées** dans la
barre du bas. Utile pour un dossier entier de relevés et d'attestations comme
ton `Camera`. Chaque déplacement reste annulable un par un.

**Et ce n'est qu'un pansement** : l'onglet **Sensibles** que tu as demandé —
l'application qui te DIT ce qu'elle a détecté, photo masquée par défaut en
attendant ton verdict — est spécifié (`eval/DECISIONS.md`, 06/09) et c'est le
prochain vrai chantier.

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
toutes) mais « existe-t-elle encore ailleurs ? ». **C'est mesuré**
(`verifier_corbeille_dernieres_copies.py`, rapport
`docs/corbeille_dernieres_copies.json`) :

- **37 groupes sont la DERNIÈRE copie** (165 Mo) → à **RESTAURER**, surtout pas
  à purger.
- **6 sont des doublons confirmés** (4 Mo) → purgeables sans risque.
- **4 illisibles** → à regarder.

- [ ] Décider quoi faire des 37 : les remettre dans le fonds. **Dis-le-moi**,
      je fais l'outil de restauration (le manifeste garde leur chemin d'origine).
- [ ] **Supprimer `_planches_corbeille\`** — les planches ont servi, mais elles
      ne répondaient pas à la question.

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
- Un **redémarrage du serveur** coûte encore ~15 min de GPU inoccupé (le travail
  de démarrage lit le NAS avant que la file se remplisse). C'est le prochain
  correctif sur ma liste.

---

## E bis. Avant de dire « go ! » à la prochaine session

Rien de tout ceci n'est bloquant — tu peux dire « go » sans, je reprendrai
l'état réel de toute façon. Mais chacun de ces trois points m'évite de te
poser une question et fait gagner du temps :

- [ ] **Les trois fenêtres du bat 0 tournent** (section A). C'est le seul
      point vraiment nécessaire : sans elles je ne peux ni mesurer, ni livrer.
- [ ] **Les 6 photos sensibles sont traitées** (section B) — ou dis-moi que tu
      les laisses pour plus tard. Tant qu'elles y sont, je ne peux pas prendre
      leur cas comme référence pour l'onglet Sensibles.
- [ ] **Tu m'as dit quoi faire des 37 dernières copies** de la corbeille
      (section D) : les restaurer, ou les laisser dormir. C'est un jugement,
      pas une tâche.

Et une chose à me dire seulement si elle a changé : **as-tu touché à
`retag_actif.txt`** ou arrêté la campagne ? Si oui, dis-le en une ligne avec le
« go » — c'est le fait qui commande tout le reste.

## F. Ce que je te dois encore

Rien de tout ceci n'attend un geste de ta part — c'est ma liste, pas la tienne.
Elle est là pour que tu saches où on en est.

1. **L'ONGLET SENSIBLES** — celui que tu as demandé, et le gros morceau de la
   prochaine session. L'application te dit ce qu'elle a trouvé ; la photo est
   masquée sans bouger en attendant ton verdict.
2. **Remplir la file de retag AVANT le travail de démarrage** — pour supprimer
   les 15 min de GPU perdu à chaque redémarrage.
3. **Empêcher deux balayages NAS simultanés** — la maintenance se met en retrait
   quand tu navigues, mais pas quand un scan tourne. C'est la cause directe des
   85 minutes du 06/09 à midi.
4. **L'outil qui restaure les 37 dernières copies** de la corbeille.
5. **Reprendre la mesure des photos sensibles sur `qwen3.5:4b`** (l'ancienne
   portait sur `qwen3-vl:2b`), avec les 24 verdicts humains comme vérité terrain.

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
