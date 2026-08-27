# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

- **27/08 — `.fchip` : une seule classe pour deux choses qui ne sont pas de la
  même nature.** Les cinq autres familles de boutons de `gallery` sont passées
  au `.btn` canonique. `.fchip` résiste, parce qu'elle habille à la fois des
  **`<a>` de navigation** (« ⬆️ Dossiers », un dossier voisin) et des
  **`<span>` d'information** (« Cette photo n'a pas encore été analysée »,
  « 📅 14 août », « 🔍 Semblables à… »). Les convertir en bloc donnerait des
  étiquettes qui ressemblent à des boutons — et le plancher n° 5 dit
  l'inverse : `<button>` pour agir, `<a>` pour naviguer, et rien qui fasse
  semblant. *Ma recommandation : les `<a>` prennent `.btn` (cible 44 px, un
  seul vocabulaire) ; les `<span>` gardent une classe à eux, renommée
  `.fetiquette`, sans bordure ni curseur — pour qu'on ne puisse plus les
  confondre en les lisant. Deux noms, deux natures.* Ça vit dans `server.py`,
  donc ça demandera un redémarrage : je ne l'ai pas fait pendant ton rangement.

- **27/08 — Google Photos : le rapatriement est OUTILLÉ, une seule question
  reste, et elle est en amont.** Tu as dit « mets-les dans A_TRIER et laisse
  faire la magie » : c'est fait côté outil —
  **`32 - Copier les absentes de Google.bat`** copie les **3 776 ABSENTES**
  (12,6 Go) sous `_A TRIER\Takeout Google\<année>`, à blanc d'abord, rien
  n'est jamais écrasé, journal d'annulation dans `_corbeille_copies/`. Le
  plan a été vérifié sur les 3 776 réelles : une année pour chacune, aucune
  collision. **Lance-le, puis `26 - Ranger par annee.bat`.** Rien ne s'efface
  chez Google avant que la vérification ne compte ZÉRO absente.

  **La question qui reste : la photothèque coupe-t-elle le trailer des photos
  qu'elle tague ?** Les 99 « même image » ont, côté Google, un bloc **Samsung
  SEF** de ~2 Ko après le JPEG (`Image_UTC_Data`, `PhotoEditor_Re_Edit_Data`)
  — et **côté NAS, ce trailer fait 0 octet sur les 99**. Le seul écrivain de
  ces fichiers est notre écriture XMP à l'exiftool. Si c'est bien elle, ce
  n'est pas 99 photos : c'est **tout ce que la photothèque tague depuis le
  début**. *Ma recommandation : le mesurer avant d'accuser — prendre dix
  photos Samsung non encore taguées, relever leur trailer, les taguer, le
  relever à nouveau. Une demi-heure, et on saura. Je ne rapatrie pas les 99 :
  leur pixel est déjà là, les copier ferait 99 doublons, et écraser par la
  version Google détruirait les XMP — donc les noms. La cause d'abord.*

  **Mesuré le 27/08 au soir (banc `croiser`, 3 000 tirés hors Takeout,
  975 Samsung jugés)** : la corrélation n'est pas là — nommées **86,9 %**
  avec SEF (Wilson 83,4–89,8), non nommées **83,9 %** (80,5–86,7). Rien
  n'accuse notre écriture ; les 99 paires étaient un sous-ensemble biaisé.
  La preuve de CAUSE reste l'avant/après armé (`--comparer`), qui parlera
  quand des noms seront posés — l'expérience de dix photos que je proposais
  n'est plus le seul chemin, mais elle reste la plus rapide si tu veux
  fermer la question aujourd'hui.

  **Reste indéterminé** : 95 paires (74 dont le trailer contient lui-même un
  `FF D9`, 21 qui ne sont pas des JPEG des deux côtés) et 21 vraiment
  différentes. Listées nommément dans `_reprise_google.json`. À regarder une
  fois les ABSENTES rapatriées, pas avant.

- **26/08 — multi-utilisateurs : DEUX questions restent, et elles bloquent
  l'écriture partagée.** Les six premières sont tranchées (spécification
  complète : `ROADMAP.md`, point 17).

  **(1) Deux jugements contradictoires, qui gagne ?** Florine dit « ce visage
  est Ellie », quelqu'un d'autre dit « non ». Aujourd'hui la dernière écriture
  gagne, en silence — c'était sans conséquence avec un seul utilisateur. À
  vingt, c'est une règle manquante. *Ma recommandation : le dernier jugement
  gagne MAIS les deux sont conservés et la fiche dit qu'il y a désaccord ; toi
  seul tranches. Aucune décision humaine ne s'écrase silencieusement — c'est
  la règle 2 du projet étendue à « les noms de QUI ».*

  **(2) Le renommage par un non-admin, sur « ses propres photos ».** Tu as dit
  : renommage réservé à l'admin, ou autorisé sur ses propres photos si la
  personne n'apparaissait jamais avant. Le cas limite : Florine nomme
  quelqu'un sur SES photos, puis cette personne apparaît sur les tiennes.
  *Ma recommandation : le nom devient commun dès qu'il touche les photos d'un
  deuxième propriétaire, et son renommage repasse alors par toi. Le
  basculement est automatique et se dit dans la fiche.*

- **25/08 — la copie HORS SITE (12 bis). LE FONDS EST MESURÉ : 291 Go.**
  `inventaire_fonds.py` (neuf) : **76 947 fichiers, 290,9 Go** — dont
  **109 Go de photos** (73 079 fichiers, 1,5 Mo en moyenne) et **180 Go de
  vidéos** (2 453 fichiers, 75 Mo en moyenne). **62 % du poids tient dans 3 %
  des fichiers.** Le petit tiers des décisions humaines pèse ~300 Mo
  (`photos.db` 277 Mo + 1,1 Mo de fiches + les quarantaines).

  **Le chiffre corrige ma recommandation de la veille.** Je proposais de
  séparer par SUPPORT — le petit tiers en ligne, le gros sur un disque —
  en supposant des téraoctets. À 291 Go, tout tient en ligne pour quelques
  francs par mois : la séparation utile n'est plus le support mais la
  **CADENCE** (les décisions chaque jour, les photos chaque semaine) et le
  disque hors ligne redevient ce qu'il doit être — la copie que rien de
  connecté ne peut atteindre, pas le gros du plan.

  **Le reste est tranché (25/08)** : NAS **Synology DS224+**, cible
  **Infomaniak Swiss Backup** par **Hyper Backup / Swift** — CHF 4,18 par To
  et par mois + CHF 1,84 pour l'appareil, −10 % à l'année, soit **~CHF 6 TTC
  par mois** pour 1 To, données en Suisse, ×3 copies sur 2 datacentres.

  **LE VRAI OBSTACLE EST LE LIEN MONTANT, ET IL EST BON MARCHÉ À LEVER.**
  Mesuré : **22,4 Mbit/s descendant, 13,8 montant** (Wingo « Internet Start »,
  CHF 34.95). Le premier envoi des 291 Go coûte **~50 h de ligne saturée**,
  60 h en vrai. L'offre Wingo actuelle **Internet Go** est à **CHF 35.95 —
  un franc de plus — pour 100 Mbit/s SYMÉTRIQUES** : le même envoi tombe à
  **~8 h**, une nuit. À vérifier avant de souscrire : l'éligibilité fibre à
  l'adresse (la ligne actuelle se comporte comme du VDSL), la durée de la
  promotion (−45 %, prix normal CHF 66.–), l'engagement 24 mois et les
  CHF 99 d'activation.

  **Vérifié le 25/08** : la ligne PEUT donner **425 / 100 Mbit/s** à
  l'adresse (rue du Pressoir 10) — la fibre, elle, n'arrive qu'entre
  **décembre 2027 et mars 2028**. Les 13,8 Mbit/s mesurés ne sont donc pas une
  limite physique mais le plafond de l'abonnement.

  **Quatre pièges nommés** : (1) la clé de chiffrement Hyper Backup est à
  imprimer et ranger ailleurs — une sauvegarde chiffrée dont on perd la clé
  est perdue ; (2) DSM 7.4.1 était en cours de téléchargement — ne pas lancer
  le premier envoi avant le redémarrage ; (3) le compte Infomaniak vu dans les
  mails est celui d'un club dont Mike ne fait plus partie — ouvrir Swiss
  Backup sur un compte PERSONNEL, et vérifier qu'il n'est plus rattaché à
  celui du club ; (4) **le compte Google est à 96 %** — voir ci-dessous.

- **25/08 — le compte Google est à 3,8 Go de la panne.** `one.google.com` :
  **96,23 Go sur 100**. Google Photos **75,03**, Gmail **12,82**, Drive 1,13,
  divers 7,2. **Quand le quota est plein, Gmail cesse de RECEVOIR** — c'est
  un problème actif, indépendant de la photothèque.
  **Résilier Google One est impossible en l'état** : hors Photos le compte
  pèse déjà 21,2 Go contre 15 Go gratuits.
  **Ma recommandation** : les 75 Go de Google Photos sont un doublon de ce que
  le NAS reçoit déjà (`_Uploads`). Les libérer ramène le compte à ~21 % pour
  le même CHF 2/mois, et rend le palier 100 Go confortable pour des années.
  **Dans cet ordre, sans exception** : (1) vérifier que le NAS porte bien ces
  photos-là ; (2) seulement ensuite effacer chez Google — l'app Photos efface
  AUSSI du téléphone quand la synchro est active. **En attendant** : rien
  n'est touché, et le compte se rapproche de son plafond.

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
