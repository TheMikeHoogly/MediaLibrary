# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

- **25/08 — la copie HORS SITE (12 bis) : deux tiers, pas un.** Un sinistre
  qui emporte le PC ET le NAS emporte tout. Avant de choisir un support, il
  faut voir que le fonds n'est PAS homogène :

  - **Ce qui est irremplaçable et minuscule** : les décisions humaines. Les
    fiches (`people.json`, `pets.json`), les index de visages et d'animaux,
    les journaux de quarantaine (`_corbeille_*`), `photos.db`. Quelques
    centaines de Mo. Rien ne les régénère — un rattachement jugé à la main
    est perdu pour de bon.
  - **Ce qui est irremplaçable et lourd** : les photos elles-mêmes. Des
    centaines de Go. Et comme les noms vivent dans leurs XMP (règle 2), les
    sauver sauve aussi les noms : `photos.db` se reconstruit à partir des
    fichiers, lentement mais sûrement.

  **Ma recommandation : traiter les deux tiers séparément.** Le petit tiers
  part CHAQUE JOUR, chiffré côté client, chez un hébergeur d'objets — quelques
  centaines de Mo coûtent des centimes et l'automatisme est le seul qui tienne
  dans la durée. Le gros tiers part sur un disque externe chiffré, rafraîchi
  à la main et rangé AILLEURS (famille, bureau) — la bande passante d'une
  ligne domestique ne fait pas mieux, et un disque chez quelqu'un d'autre est
  une vraie copie hors site.

  **Ce qu'il me manque pour aller plus loin** : la taille réelle du fonds en
  Go, et ce que tu acceptes — un abonnement mensuel ? un chiffrement dont TU
  gardes la clé (donc que tu peux perdre) ? quelle perte maximale acceptable
  en cas de sinistre : un jour, une semaine, un mois ?

  **En attendant** : rien n'est exposé, et rien n'est protégé non plus.

- **24/08 — l'ordre `reparation_xmp` au canal des bancs : sa raison d'être a
  expiré vingt minutes après ton accord.** Tu as dit oui pour qu'une mort à
  3 h ne coûte pas la nuit — mais la passe a fini toute seule à 03:07. Ce
  qu'il coûterait maintenant : le PREMIER geste qui ÉCRIT dans un canal dont
  le contrat est « ce qui MESURE seulement », et une exception au plafond de
  30 min (une réparation dure des heures). Ce qu'il rapporterait : relancer
  une passe longue sans toi — besoin qui ne se représentera que si un nouvel
  arriéré apparaît. **Ma recommandation : ne pas le construire maintenant**,
  et le reprendre le jour où une seconde passe longue est nécessaire.
  **Fait quand même, parce que c'était la moitié SÛRE de ton accord** : le
  verrou d'écriture. `appliquer_xmp_personnes.py` ne tenait « jamais deux
  écrivains » que contre le SERVEUR ; deux passes lancées à la main, ou une
  passe et un `--nom`, s'ignoraient. Elles se voient désormais (preuve par
  fraîcheur, reprise automatique après 10 min sans signe de vie).

## Réglées

- **24/08 — 21 fantômes `_exiftool_tmp`, et la fuite chronique derrière.**
  Effacés par Mike ; les 13 échecs repris dans la foulée. `inventaire_fantomes.py`
  en trouve **0** sur les deux racines. Et le script sait désormais balayer
  lui-même — `--balayer-fantomes`, **jamais par défaut** : il n'efface que le
  temporaire de la photo qu'il vient de lire, et réessaie UNE fois.

- **24/08 — le rattrapage de `Val` : 3 photos, pas 1 205.** Fait. Mesuré nom
  par nom, fichiers relus en entier : Val 1 091/1 094 puis conforme, Yann
  Mamin 13/13 (24/24 depuis). Des deux noms sautés par la passe de 21:38, un
  seul avait besoin d'être repris.

- **23/08 — ~5 700 photos dont le fichier ignore un nom que l'index porte.**
  **FAIT le 24/08 à 03:07** : `--tous --appliquer`, deux passes, **18 828
  photos balayées, 3 128 réécrites, 13 échecs, aucun nom sauté**. La première
  passe (21:38) est morte à 4 800 sur un auto-ajout du curateur ; la seconde,
  qui ATTEND la file au lieu d'abandonner, est allée au bout en 4 h 29. Reste
  à prendre le seul chiffre qui compte : `verifier_xmp_toutes_personnes.py`.

- **22/08 — `personne:Florine` : 153 photos, aucune fiche. Qui est-ce ?**
  Réponse de Mike : **c'est Flo.** « Il faut remplacer tous les Flo par Florine
  dans toute la médiathèque. » Ce que ça explique rétroactivement : le résidu
  que le curateur n'arrivait pas à trancher (`server.py` : « les visages qu'une
  deuxième personne dispute — Florine/Flo »), et les scores séparés à 0,03 sur
  les MÊMES visages notés dans `classifier.py`. Deux noms, une personne : les
  signatures se partageaient les visages.
  **Fait avant le geste** : `rename` réparée (elle perdait 143 confirmations),
  et la fusion rendue réversible (`_corbeille_fusions/`, bouton dans
  `/reglages`). **Le geste reste à Mike** : `/people` → Flo → Renommer →
  `Florine` (11 814 opérations XMP sur 5 907 photos, en tâche de fond).

- **22/08 — appliquer le re-clé des 748 décisions ?** Recommandation suivie :
  **appliqué**. Résultat : **787 décisions sur 685 clés, 97 fiches**. Observé —
  décisions posées sur une clé hors index **928 → 140**. L'audit de la
  quarantaine dit le reste : 788 sorties, **734 arrivées appariées** (même type,
  même index, autre chemin), **54 fusions** de doublons, **0 sans
  contrepartie** — aucune décision humaine perdue, règle 2 tenue.

- **22/08 — que faire du résidu ?** Recommandation suivie : **le garder**. Il
  reste **140 décisions** (117 rattachements, 13 exclusions, 10 confirmations)
  sur des clés dont aucun journal ne connaît la destination, et les **120 clés**
  protégées de la purge du 21/08. Rien n'est purgé : le résidu ne coûte plus
  rien de mesurable, et le jour même, 787 décisions déclarées « déjà perdues »
  se sont révélées récupérables dès qu'une source de preuve nouvelle est
  apparue.

- **21/08 — après le sauvetage : purger, ou chercher la cause d'abord ?**
  Recommandation suivie : **la CAUSE d'abord**. 787 décisions pointant déjà
  dans le vide, c'est une fuite active, pas un résidu — purger avant, c'est
  effacer la scène. La cause a été trouvée le soir même (la cascade suit
  l'index, qui a déjà oublié la clé) et l'angle mort de l'instrument est bouché.

- **21/08 — les 2 374 fiches de visages orphelines, dont 125 portent une
  décision humaine.** Recommandation suivie : **sauver d'abord, purger
  ensuite**. Un instrument cherche, pour chacune des 125, si la photo vit sous
  une autre clé, et nomme celles qui n'ont pas de jumeau ; la purge en
  quarantaine réversible ne vient qu'après. Mike a aussi retenu qu'il faut
  chercher la CAUSE — le 17/08 avait purgé un magasin sur deux sans que ça se
  voie.

- **21/08 — le réservoir de visages sous le seuil de 0,40.** Recommandation
  suivie : **juger 30 propositions de la tranche 0,35–0,40 avant de toucher un
  seuil**. 28 684 visages sous le seuil, mais un meilleur voisin médian à 0,21 :
  le seuil n'est pas ce qui les retient. Abaisser sans jugement serait un pari
  sur des noms.

- **21/08 — la barre de recherche mentait sur une page de résultats.**
  Recommandation suivie : elle cesse de chercher à chaque frappe et attend
  **Entrée**, qui relance la requête côté serveur ; un indice « ↵ Entrée pour
  relancer » paraît tant que le texte diffère. Observé — `montagne` tapé sur la
  page des chats ne touche plus au compte, `Entrée` rend 1 500 photos.

- **20/08 — `eval/DECISIONS.md` à saturation, deuxième fois en deux jours.**
  Recommandation suivie : découpage par DOMAINE, l'outillage part dans
  `docs/DECISIONS_OUTILLAGE.md`. Mike a en plus porté le budget à **50 000**.
  La marge retrouvée a d'abord servi à RENDRE la précision rognée le jour même
  — comme le 19/08.
- **20/08 — l'ESPÈCE comme 5ᵉ axe.** Mike a demandé un CHIFFRE plutôt qu'un
  principe, et le chiffre a tranché contre ma recommandation : **A**, une
  puce explicite. Mais le banc complet, lancé par lui, a aussi réfuté le
  critère que je proposais (voir `eval/DECISIONS.md`, `det_score`).
- **20/08 — `commit` ne poussait rien.** Recommandation suivie : l'agent
  pousse la branche dans les DEUX modes, `main` reste intacte. Observé —
  `refs/remotes/origin/feat/…` créée par l'agent lui-même.
- **19/08 — noms affichés deux fois dans la visionneuse.** Recommandation
  suivie : les tags `personne:` / `animal:` sont retirés de la ligne de tags,
  la ligne de faits les porte seule. Le filtre de la planche les garde.
- **19/08 — `eval/DECISIONS.md` à saturation.** Mike a tranché CONTRE ma
  recommandation d'archive : budget porté de 9 000 à 12 000 octets. Deux
  fichiers à consulter valent moins qu'un seul complet. La marge retrouvée a
  d'abord servi à RENDRE la précision rognée le matin même.
