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

- **29/08 — Google : la vérification a rendu, le feu vert est à toi.**
  `verifier_photos_google` (session 64, 165 s) : ABSENT 0, CERTAIN 4 280,
  PROBABLE 9 625 dont **199 où le NAS est plus petit — tous sous
  `_A TRIER\Google porte mieux`**, nos propres copies. Mesuré fichier par
  fichier (`diagnostic_trailer_google.py`) : **14 Motion Photos Samsung de
  2024** (−1 à −3,3 Mo) passées par `repair_file`, qui jette le trailer —
  vidéo embarquée et profil ICC — mais le `nom.jpg_original` est à côté,
  14/14 à la taille de Google ; et **185 fichiers à −2…−57 Ko**, trailer
  conservé, **zéro tag présent seulement chez Google** : du padding.
  *Ma recommandation : rien de lisible ne manque au NAS, le critère « jamais
  plus petit » est tenu en substance — tu peux effacer chez Google
  (`photos.google.com`, jamais depuis l'app ; quota libéré après vidage de la
  corbeille, 60 j). Avant : corriger `repair_file` pour qu'il préserve le
  trailer, sinon chaque Motion Photo future subira la même perte silencieuse
  (les originaux de `Photos Mike\2024` l'ont déjà subie).*

- **29/08 — 1 217 photos rangées à la RACINE `Photos\<année>` au lieu de
  `Photos Mike\<année>`.** `rangement_annee.cible()` n'a jamais appris le
  déplacement du 26/08 : bat 26 (27 et 28/08, quatre journaux d'annulation
  dans `docs/`, 20+539+20+638) a posé les « absentes » du Takeout dans 17
  dossiers à la racine — 3,7 Go, comptés par `inventaire_racine_photos.py`.
  *Ma recommandation : corriger `cible()` (constante nommée + test), serveur
  arrêté annuler les quatre applications (`--undo`), régénérer le plan, bat 26
  à nouveau, et SEULEMENT alors un `.bat` en `rd` non récursif sur les 17
  dossiers — sûr par construction, il refuse un dossier non vide. À mesurer
  avant l'undo : les décisions visage/animal accrochées à ces clés (le re-clé
  hors-ligne ne porte que 5 magasins sur 7).* Pas de `.bat` d'effacement tant
  que les dossiers portent des photos.

- **29/08 — `_Uploads` : quel rôle avec le multi-utilisateur ?** Aujourd'hui
  racine « plate » à part (clés = nom nu, `scan_uploads`, `key_for_new_path`)
  et `DATA_DIR` pointe encore sur `\\nas-bremblens\home\Uploads`, disparu.
  *Ma recommandation : l'upload devient la boîte de réception du PROPRIÉTAIRE
  connecté — `Photos <Nom>\_A TRIER\` — et le plan par année range chaque
  `_A TRIER` vers `Photos <Nom>\<année>` : une seule règle pour le téléphone,
  le Takeout et le dépôt à la main ; la clé « nom nu » et la racine spéciale
  disparaissent. S'emboîte dans le point PROPRIÉTAIRE du chantier 17.*

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
