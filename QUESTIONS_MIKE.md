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

- **28/08 — Google Photos : 55,6 Go peuvent partir, ~106 fichiers ne le
  peuvent PAS, et il faut choisir dans quel ordre.** La vérification d'après
  rapatriement est nette : **ABSENT = 0** — tout ce que Google détient existe
  sur le NAS. Sur 13 905 médias : **4 293 CERTAIN** (même nom, même taille au
  bit près, 55,6 Go) et 9 612 « même nom, taille différente ».

  **Ces 9 612 se lisent en deux paquets, et un seul pose problème.** Le NAS
  est plus GROS dans 9 315 cas, d'un écart médian de **4 101 octets** — c'est
  la taille d'un bloc XMP, donc nos propres tags écrits dans le fichier :
  bénin, le NAS porte la photo de Google PLUS nos noms. Mais dans **297 cas
  le NAS est plus PETIT**, dont **89 de plus d'un mégaoctet**. Ceux-là ne
  s'expliquent pas par des métadonnées.

  **Les vidéos, précisément** (ta question) : **3 114 vidéos, dont 3 104
  CERTAIN** — identiques au bit près sur le NAS. Les **10 autres sont plus
  petites côté NAS**, et lourdement : −73 Mo, −40 Mo, −22 Mo… Exemples :
  `20250510_213701.mp4` (204 Mo chez Google, 131 sur le NAS),
  `20250814_222300.mp4` (150 → 110 Mo). Une seule est plus grosse sur le NAS
  (`20260724_201256.mp4`, 8 → 39 Mo). Et côté photos, des cas comme
  `Luzarches 2016 (33).jpg` : **8,5 Mo chez Google, 0,6 Mo sur le NAS**.

  *Ma recommandation, dans cet ordre : (1) libérer les 55,6 Go CERTAINS —
  ça ramène le compte de 96 % à ~41 Go et règle le problème Gmail ; (2) NE
  PAS toucher aux ~106 fichiers où Google porte plus que le NAS, et les
  rapatrier d'abord — c'est le même outil que pour les absentes ; (3)
  relancer la vérification, et alors seulement effacer le reste.* Le geste
  d'effacement chez Google reste le tien : je ne supprime rien chez un tiers.
  Note pratique : sélectionner 4 293 fichiers à la main dans l'interface web
  est irréaliste — **rapatrier les ~106 d'abord rend l'effacement GLOBAL sûr**,
  et c'est probablement le chemin le plus court.

- **27/08 — Google : 116 paires restent indéterminées.** 95 (74 dont le
  trailer contient lui-même un `FF D9`, 21 qui ne sont pas des JPEG des deux
  côtés) et 21 vraiment différentes, listées nommément dans
  `_reprise_google.json`. Sans effet sur ce qui précède ; à regarder quand le
  reste sera fait.

- **27/08 — le trailer Samsung : la corrélation est morte, la CAUSE ne l'est
  pas.** Mesuré le 27/08 (3 000 tirés hors Takeout, 975 Samsung jugés) :
  nommées **86,9 %** avec SEF (Wilson 83,4–89,8), non nommées **83,9 %**
  (80,5–86,7) — rien n'accuse notre écriture XMP. La preuve de cause reste
  l'avant/après du MÊME fichier, **armé** (`_rapport_sef_avant.json`, à ne pas
  supprimer : il n'est pas dans git). *Ma recommandation : laisser le curateur
  nommer, puis relancer `--comparer`. Aucune action d'ici là.*
