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

- **29/08 — Google : il ne manque QU'UNE vérification avant d'effacer.** Les
  **297 fichiers que Google portait mieux que le NAS sont rapatriés** (100 au
  seuil de 100 Ko, puis 197 au seuil de 1 octet), 0 grief, sous
  `_A TRIER\Google porte mieux\<année>`. Au dernier relevé complet il ne
  restait plus aucun déficit supérieur à 100 Ko — les neuf vidéos à −73, −40,
  −22 Mo ont disparu du problème.

  **La vérification finale n'a jamais rendu** : la machine s'est coupée une
  minute après son lancement. *Ma recommandation : la relancer d'abord —
  `verifier_photos_google.py --takeout b64:QzpcR09PR0xFIFBIT1RPU1xleHRyYWl0`.
  Si elle ne compte plus aucun « NAS plus petit », l'effacement GLOBAL chez
  Google devient sûr, et c'est le seul chemin praticable : sélectionner 4 300
  fichiers à la main dans l'interface web ne l'est pas.* Le geste d'effacement
  reste le tien — je ne supprime rien chez un tiers.

  **Un piège de critère, qui vaut d'être retenu** : ne pas attendre que « tout
  soit CERTAIN ». Notre propre tagging ajoute un bloc XMP (~4 Ko) à chaque
  photo et fait donc RECULER ce compte en permanence. Le critère qui se tient
  est **« le NAS n'est jamais plus petit »**.

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
