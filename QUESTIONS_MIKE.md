# Questions en attente de Mike

> Carnet des choix qui lui appartiennent, accumulés pendant une traite
> autonome. Une entrée = une question, ma recommandation, et ce que je fais
> en attendant. **Vidée dès qu'elle est répondue** — la réponse part dans
> `eval/DECISIONS.md` si elle tranche, dans `docs/DECISIONS_OUTILLAGE.md` si
> elle touche l'outillage, dans `ROADMAP.md` si elle priorise.
> Protocole : `CLAUDE.md`, « Traite autonome ».

## En attente

### 1. Le timeout d'ExifTool empoisonne la photo, et ça grossit (07/09 au soir)

**Ce qui se passe, mesuré ce soir dans le journal.** Quand l'écriture XMP
d'une photo dépasse le délai (`_run_exiftool`, 180 s par défaut), Python TUE
le processus — mais ExifTool a déjà créé son `<photo>.jpg_exiftool_tmp` sur le
NAS, et le `finally` de `_run_exiftool` ne ramasse que son argfile. Le tmp
reste. **Toute écriture ultérieure sur cette photo échoue alors pour
toujours** : « Error: Temporary file already exists ». La réparation de
dernier recours échoue de la même façon, et la photo est abandonnée
(« listé sur /sante »).

**La chaîne, sur un cas complet** (`Photos Flo/Sista/20200122_chat-tabby-allonge.jpg`) :

- 21:34:52 → mise en re-tagging ;
- 21:39:08 → `⚠ ExifTool: Command […] timed out` — le processus est tué, le
  tmp reste sur le NAS ;
- 21:39:28 → la photo est quand même « taguée en 276 s » : **les mots-clés
  sont dans l'index, c'est le XMP du FICHIER qui n'a pas été écrit** ;
- 22:13:00 puis 22:18:07 → « Temporary file already exists », réparation
  échouée, **abandon**.

**L'ampleur, comptée** : **13 photos** touchées depuis 14:05 aujourd'hui, dans
trois dossiers de `Photos Flo` (Mumi 6, Sandra 5, Sista 2), **29 échecs**
« Temporary file already exists ». Les tmp datent tous d'AUJOURD'HUI, entre
13:23 et 21:44 — un toutes les 30 à 60 minutes, soit environ 0,5 % des photos
re-taguées. **Aucune photo n'est abîmée** : vérifié fichier par fichier, la
photo d'origine est présente à côté de chaque tmp, plus grosse que lui (le tmp
est une copie tronquée), et sa date de modification remonte à AOÛT — le
fichier n'a pas été touché.

À ce rythme, les ~5 jours qu'il reste à la campagne coûteraient **60 à 80
photos** abandonnées, chacune définitivement fermée à toute écriture XMP.

**Deux gestes, et les deux t'appartiennent :**

**(a) Effacer les 13 `_exiftool_tmp` déjà là.** C'est une suppression dans ton
archive, et `CLAUDE.md` dit « un `_exiftool_tmp` condamne sa photo — balayage
jamais par défaut ». → **Ma recommandation : oui, mais fichier par fichier et
sur preuve**, comme le fait le strip Motion Photo : ne retirer un tmp que si la
photo d'origine existe, est plus grosse, et s'ouvre. J'écris l'outil, tu le
lances par un bat. Les 13 photos redeviennent alors écrivables et la campagne
les reprendra.

**(b) Ramasser le tmp quand NOTRE appel vient de le laisser.** Dans le
`except TimeoutExpired` de `_run_exiftool` : effacer le
`<photo>_exiftool_tmp` que cet appel-là vient d'orpheliner — pas un balayage du
disque, un nettoyage derrière notre propre processus tué, sur un chemin qu'on
connaît, et seulement si le tmp est plus récent que le début de l'appel.
→ **Ma recommandation : oui.** Sans ça, (a) se refera tous les jours.

**Ce que je fais en attendant** : rien sur tes fichiers. Le défaut est écrit
ici et dans `ROADMAP.md` ; les 13 photos restent listées sur `/sante`, et la
campagne continue normalement sur tout le reste.

**Question ouverte que je ne sais pas trancher seul** : *pourquoi* l'écriture
dépasse 180 s. Le NAS occupé ? Une photo lourde ? Un `-stay_open` qui
manque ? Ça se mesure, mais pas la même nuit que la correction — et la
correction (b) vaut de toute façon, quelle que soit la cause.
