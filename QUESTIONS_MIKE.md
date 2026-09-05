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

### Le dictionnaire FR→EN meurt avec le bilingue (05/09, session 72)

**La question.** L'élargissement FR→EN de la recherche (1 nonies, +0,075 de
rappel@200 mesuré et observé le 30/08) apprend sa traduction sur les entrées
d'index qui portent À LA FOIS `kw_fr` et `kw_en` — « ours en peluche » et
« teddy bear » sur les mêmes photos. Le serveur le RÉAPPREND toutes les 6 h
(`dico_fr_en()`, TTL 6 h). Le passage au FR seul supprime les `kw_en` photo par
photo : à mesure que la campagne avance, la matière d'apprentissage fond, et à
la fin le dictionnaire serait VIDE. L'élargissement mourrait alors sans erreur,
sans ligne dans le journal, et le rappel retomberait de 0,658 à 0,583 — le
genre de panne muette que le projet a déjà payé cher (backfills, boucle de
maintenance).

**Ma recommandation : le GELER.** Le construire une dernière fois sur l'index
encore bilingue (2 276 paires le 30/08), l'écrire sur disque
(`dico_fr_en.json`), et faire de ce fichier la source ; le réapprentissage ne
sert plus à rien quand l'index n'a plus d'anglais. La traduction d'un tag ne se
périme pas — « chaise → chair » restera vrai. Coût : une écriture, une lecture,
un garde-fou « si l'index donne moins de paires que le fichier, garder le
fichier ». Alternatives : (b) accepter la perte et retirer l'élargissement
(honnête, mais on jette une mesure qui a coûté une nuit) ; (c) garder un
`kw_en` traduit dans l'index sans le demander au modèle (une traduction de
plus à maintenir, pour un usage unique).

**En attendant** : rien n'est fait, et rien ne presse tant que l'étape 6 n'est
pas lancée — le dictionnaire ne s'appauvrit qu'à mesure que la campagne
avance. Mais la réponse doit venir AVANT de poser `retag_actif.txt`.

*(Vidé le 30/08 soir : les 10 noms re-retirés du dédoublonnage tranchés par
Mike photo par photo, verdicts appliqués et observés ; règle gravée dans
`eval/DECISIONS.md`, récit dans git `feat/confirmation-grave`.)*
