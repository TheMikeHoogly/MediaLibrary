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

### Dédoublonnage : 10 noms recopiés sur la canonique que le serveur a re-retirés (30/08, session 68)

**Le fait.** Bat 40 a recopié 19 noms des copies vers leurs canoniques (règle 2).
Au démarrage suivant, le serveur a re-retiré ceux dont la canonique portait une
**exclusion humaine** de cette même personne (« 🩹 Faux positifs : 3 » à 12:32 =
exactement les 3 manquants du lot 1 ; « 25 » à 16:13). Sur les mêmes pixels, la
copie disait « c'est Mike », la canonique disait « ce n'est PAS Mike » — deux de
tes jugements, contradictoires, et l'exclusion du propriétaire a gagné (règle du
29/08). **Rien n'est perdu** : le nom vit dans le XMP de la copie en corbeille
(`.corbeille-rangement\dedup_image_*`) et dans `docs/undo_doublons_*.json`. Mais
la fiche ne DIT pas le désaccord, contrairement à la règle.

| Canonique (`Photos Mike`) | Nom re-retiré | Ce que la fiche affiche |
|---|---|---|
| `Voyage Indonésie (294).jpg` | **Mike** | [] |
| `Voyage Indonésie (457).jpg` | **Mike** | Florine |
| `20171028_125245.jpg` | **Florine** | Lola |
| `11122010350.jpg` | **Gaétan** | [] |
| `20250922_152638.jpg` | **Florine** | [] |
| `20251013_221514(0).jpg` | **Florine** | [] |
| `20251013_221514.jpg` | **Florine** | [] |
| `20251031_184042.jpg` | **Sarah** | Lyne, Valérian |
| `20251221_154958.jpg` | **Fabien** | Béa, Didier, Florine, Laura, Quentin, Rafa, Val |
| `20251221_155000.jpg` | **Quentin** | Didier, Fabien, Florine, Laura, Liam Guhl, Rafa, Val |

**Ma recommandation.** Dix photos, un coup d'œil chacune : là où le nom est
juste, le rattacher (un clic dans la fiche lève l'exclusion) ; là où il est
faux, ne rien faire — la corbeille garde la preuve six mois. Et, côté code,
faire DIRE le désaccord : quand `fusionner_fiche` apporte un nom que la
canonique exclut, l'écrire dans `contestes` plutôt que de laisser le démarrage
le retirer en silence — c'est la règle du 29/08 (« rien ne s'efface, la fiche
dit le désaccord »).

**En attendant** : rien ne bouge ; 9 des 19 noms sont bien sur leur canonique.

