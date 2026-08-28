# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux, à la livraison ou au MCP. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (29/08/2026, fin de session 63)

**Le PC de Mike a été redémarré à la fin de la session.** Premier geste :
vérifier que les trois fenêtres du bat 0 tournent (`_agent_*_vu.txt` de moins
de 30 s) et que le serveur répond.

### La journée en quatre morceaux, tous livrés et fusionnés

1. **Le tagueur ne meurt plus d'avoir voulu noter sa mort.** Le 27/08 à
   23:42:50, `STORE.set` échoue sur `database is locked`, le gestionnaire
   d'erreur réécrit dans la MÊME base verrouillée, et cette seconde erreur tue
   le fil. Huit heures perdues. `store_sqlite._ecrire` réessaie (5 essais,
   0,4 → 3,2 s), `_flush_rapide` ré-arme `_dirty`, et `server._marquer_echec`
   avale un second échec. **Règle : un rattrapage ne dépend jamais de la
   ressource qui vient de tomber.**
2. **Les vingt fils de `main()` ont un filet** (décision de Mike) : le fil mort
   SE RELANCE, cinq morts consécutives ALERTENT. `fil_surveille` + registre
   `FILS` + `/sante` qui affiche les fils AVANT les fichiers. Qui boucle et
   qui rend a été MESURÉ (balayage AST des `while True:`).
3. **`.fchip` est mort** : les `<a>` prennent `.btn btn--nav` (44 px, vus sur
   le serveur vivant), les `<span>` deviennent `.fetiquette` (sans bordure ni
   curseur). Zéro `.fchip` dans le DOM rendu.
4. **Le serveur prend sa température** (idée de Mike). `hw_state` porte
   `temp_c`, horloges, watts et deux drapeaux de bridage thermique ;
   `thermique_loop` les écrit au journal, à côté des durées de tagging.

### Google — il ne manque QU'UNE vérification

**ABSENT = 0** : le NAS porte tout ce que Google détient. Les **297 fichiers
que Google portait mieux ont été rapatriés** (100 le premier soir, seuil
100 Ko ; puis 197 au seuil 1 octet) sous `_A TRIER\Google porte mieux\<année>`,
0 grief. Au dernier relevé complet (21:01) il ne restait que ces 197, tous
sous 100 Ko de déficit ; ils sont maintenant sur le NAS.

**MAIS la vérification finale n'a jamais rendu** : la machine s'est coupée une
minute après son lancement. **Premier geste utile de la session** :

    verifier_photos_google.py --takeout b64:QzpcR09PR0xFIFBIT1RPU1xleHRyYWl0 --json=_rapport_google_final.json

Si elle ne compte plus AUCUN « NAS plus petit », **Mike peut effacer chez
Google** — son geste, sur `photos.google.com`, jamais depuis l'app du
téléphone ; le quota ne bouge qu'après vidage de la corbeille (60 j).

**Le bon critère n'est PAS « tout en CERTAIN »** : notre propre tagging
grossit les fichiers (un bloc XMP, ~4 Ko) et fait donc RECULER le compte de
CERTAIN en permanence. Le critère qui se tient, c'est **« le NAS n'est jamais
plus petit »**.

### La machine s'est coupée, et la cause n'est pas tranchée

Le 28/08 à 23:10:15, coupure franche sous charge : `Kernel-Power 41`, **aucun
minidump**, aucun `1074`, `_journal_serveur_crash.log` vide. Ce n'est ni un
écran bleu, ni une mise à jour, ni un plantage de la photothèque. Le BIOS
date de **juillet 2023** — jamais flashé, l'hypothèse MSI tombe.

Le seul indice est le **rythme de tagging** : la session qui est morte taguait
à **27,2 s de moyenne** contre 9,7 à 22,8 s pour les autres du jour, et 14,0 s
après un redémarrage à froid sur le même travail. Reste ouvert : thermique,
alimentation, ou poussière/pâte thermique sur un portable de trois ans.
**Le thermomètre est maintenant dans le journal** pour trancher la prochaine
fois.

Windows, séparément : **Secure Boot désactivé** par Mike pour pouvoir démarrer
le 28 au matin, et **le « Windows UEFI CA 2023 » est absent du DB**. C'est de
la sécurité, pas de la stabilité — et le correctif manuel est en deux phases
dont la seconde est IRRÉVERSIBLE : ne pas y toucher sans lire la page
Microsoft à jour.

## Prochain pas

1. **La vérification Google** (ci-dessus). Trois minutes, lecture disque, pas
   de GPU. C'est le feu vert pour libérer ~56 Go chez un tiers dont le quota
   est à 96 %.
2. **Ranger les 297 rapatriés.** Ils n'entrent dans le plan qu'une fois
   TAGUÉS — le plan vient de l'index EN MÉMOIRE, pas du disque. Donc :
   attendre que `queues.tag` retombe, régénérer le plan (`POST
   /api/maint/plan-annee`), puis `26 - Ranger par annee.bat`. **Le plan périme
   vite** : le 28/08, bat 26 a rendu `skip: 559` en relisant un plan du 12/08.
3. **Supprimer `_to_delete/`** (43 Mo de corbeilles et journaux d'annulation
   d'avant le 25/08). Geste de Mike ; les journaux de cette semaine ont été
   gardés exprès.
4. **Le 9 septembre au matin** : vérifier que Windows a DEMANDÉ au lieu de
   redémarrer (Patch Tuesday le 8, redémarrage vers 01:30 la nuit suivante).
   `Get-WinEvent -FilterHashtable @{LogName='System'; Id=1074}`.
5. **Le chantier 18 (confidentialité)** : le jeu étiqueté et son banc D'ABORD.
   Illustration involontaire du 28/08 : une photo taguée « facture, chèque,
   paiement, virement, caisse, transaction ». Le verdict ne va PAS dans le XMP.
6. **Le panneau `?` des raccourcis** — et d'abord sa brique : un JS commun
   injecté partout (`_UI_GLOBAL_FILES`, il n'en existe aucun). `server.py`.
7. **La suite du chantier 17** : PROPRIÉTAIRE, puis attribution rétroactive
   des 3 767 décisions. **Les deux questions bloquantes sont TRANCHÉES**
   (28/08, `eval/DECISIONS.md`) : le désaccord se conserve et se dit, un nom
   devient commun dès qu'il touche un deuxième propriétaire.
8. **UNIFIER le re-clé** : la primitive existe TROIS fois
   (`server.rekey_everywhere`, `deplacer_dossiers.recle_une_cle`,
   `appliquer_plan.rekey_stores`). Elle a déjà divergé cinq jours.
9. **Reste d'audit** : O8–O9, O11, O13–O15 ; **I1** dans `/reglages` ;
   `animal:luna` (3) vs `animal:Luna` (355). Puis les **quatre pages sans
   `components.css`** (`browse`, `faces`, `map`, `reglages`) — seul chantier
   UI qui ne demande AUCUN redémarrage (`ui/pages/` est relu à chaud).
   **Attention** : `/map` sert de page TÉMOIN à `verifier_pages_composants` ;
   la convertir ferait perdre son contrôle négatif à l'instrument. Lui trouver
   un remplaçant d'abord, ou la garder témoin.

## En fin de projet

- **La copie hors site (12 bis)** attend la fin du chantier 17 : DS224+ →
  Infomaniak Swiss Backup, ~CHF 6/mois pour 1 To, fonds 291 Go, clé imprimée,
  et une restauration d'épreuve. **La ligne internet ne change pas
  maintenant** (choix de Mike, 28/08).
- **HTTPS : FAIT** — `https://msi-mike.goat-draco.ts.net/`.

## Réflexes

### Mesurer

**La bonne ÉCHELLE, sinon la bonne conclusion sur les mauvaises données.**
J'ai comparé les durées de tagging à l'intérieur d'une session — plates — et
conclu « pas de bridage ». Le signal était ENTRE les sessions : 27,2 s contre
9,7–22,8 s. Avant de conclure « pas de dérive », demander : dérive par rapport
à QUOI.

**Interroger un outil externe CHAMP PAR CHAMP avant de le grouper.**
`power.limit` et `temperature.memory` rendent `[N/A]` sur cette carte, et un
seul champ refusé fait échouer TOUTE la requête `nvidia-smi` — sans dire
lequel. Les demander à l'aveugle aurait aveuglé `hw_state` sur sa propre VRAM.

**Un rouge causé par un NOM manquant ne prouve rien** sur le comportement.
Il faut que l'ancien code s'EXÉCUTE (`hasattr`, pas un accès direct). Et tous
les tests ne peuvent pas rougir : un garde d'un mécanisme NEUF ne le peut pas.

**Un banc qui imprime doit rester lisible par une console cp1252** — c'est
celle de l'agent git. Deux bancs sur ~90 étaient fautifs le 28/08, corrigés,
zéro restant (balayage AST des `print`).

**Ne JAMAIS lancer `unittest discover` depuis la VM** : trois tests ouvrent le
vrai `photos.db`.

**Le canal du banc n'admet que `[A-Za-z0-9_.:/=-]`** (espaces via jeton `b64:`,
en argument SÉPARÉ) et son plafond est **600 s** — échantillonner au-delà.

### Lire

**Le journal du serveur d'abord**, depuis la dernière bannière :

    L=$(grep -n "===== DEMARRAGE" _journal_serveur.log | tail -1 | cut -d: -f1)
    tail -n +$L _journal_serveur.log | grep -n "FIL MORT\|THREAD MORT\|Traceback"

**Savoir d'où vient un chiffre.** `verifier_photos_google` lit le **DISQUE**
(il ne touche jamais `STORE`) : il n'attend pas le tagging. `generer_plan_annee`
lit l'**index en mémoire** : un fichier n'y entre qu'une fois TAGUÉ. J'ai fait
attendre Mike des heures pour rien en confondant les deux.

**Un plan appliqué n'est pas un plan calculé.** `appliquer_plan_annee` relit
`docs/plan_rangement_annee.json` ; s'il date, il rend `skip: N` et ne range
rien.

### Juger

**Un rattrapage ne doit jamais dépendre de la ressource qui vient de tomber.**
Ne pas pouvoir noter un échec est regrettable ; mourir en essayant fait perdre
tout le reste. Vaut aussi pour un `ROLLBACK` qui masque sa cause.

**Une corrélation n'est pas une cause.** Le banc du trailer le dit lui-même.

**Ne pas voir une cible ne la rend pas conforme** — tout rapport dit sa PORTÉE.

**Un banc vert n'est pas un regard.** Les instruments savaient dire que les
règles étaient là ; ils ne pouvaient pas dire que l'étiquette avait cessé de
faire semblant d'être un bouton.

### Toucher

**`ui/pages/` et `ui/*.css` sont relus À CHAUD** ; seul `server.py` exige un
redémarrage — qui interrompt tagging et scan.

**L'ordre de la cascade a QUATRE étages** : `components.css` → page →
`tokens.css` → `base.css`.

**Jamais deux écrivains sur `photos.db`.** Le serveur est l'écrivain unique ;
`26 - Ranger par annee.bat` exige qu'il soit ARRÊTÉ, et le PROUVE deux fois.

**Un `_exiftool_tmp` condamne sa photo** — balayage jamais par défaut.

> **Piège d'horloge** : `device_bash` est en **UTC** (−2 h chez Mike).
>
> **Le dossier monté a un cache** : le `mtime` dit la vérité, `tail` peut
> mentir. Mais un gel SIMULTANÉ de plusieurs fichiers au même instant est
> aussi ce que produit une vraie fermeture — demander à Mike plutôt que de
> conclure.
