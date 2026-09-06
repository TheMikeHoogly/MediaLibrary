# Marche à suivre — Mike, 06/09/2026 au soir

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

Pour ces 44, la question n'est PAS « cette photo compte-t-elle ? » (elles
comptent toutes — ce sont des chats, des mariages, le Léman) mais « existe-t-elle
encore ailleurs dans le fonds ? ». Ça se prouve, ça ne se juge pas à l'œil.

- [ ] Lire le verdict de `verifier_corbeille_dernieres_copies.py` — voir
      `docs/corbeille_dernieres_copies.json`. Deux tas : **dernière copie**
      (à restaurer) et **doublon confirmé** (purgeable).
- [ ] Les planches-contact sont dans `_planches_corbeille\` si tu veux voir de
      quoi il s'agit — mais elles ne tranchent pas la question.
- [ ] **Supprimer `_planches_corbeille\`** ensuite.

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

## F. Ce que je te dois encore

Rien de tout ceci n'attend un geste de ta part — c'est ma liste, pas la tienne.
Elle est là pour que tu saches où on en est.

1. **Remplir la file de retag AVANT le travail de démarrage** — pour supprimer
   les 15 min de GPU perdu à chaque redémarrage.
2. **Mesurer en réel le chargement paresseux des vignettes** sur
   `Photos Mike/2022`, le dossier qui avait tout bloqué. Le code est écrit et
   vérifié, mais pas encore observé.
3. **Empêcher deux balayages NAS simultanés** — la maintenance se met en retrait
   quand tu navigues, mais pas quand un scan tourne. C'est la cause directe des
   85 minutes du 06/09 à midi.
4. **Reprendre la mesure des photos sensibles sur `qwen3.5:4b`** (l'ancienne
   portait sur `qwen3-vl:2b`), avec les 24 verdicts humains comme vérité terrain.

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
