# La répétition — « PC mort lundi, tout revit vendredi »

> Chantier 12. L'instrument existe (`verifier_restauration.py`) et la
> sauvegarde des artefacts tourne. **Ce qui n'a jamais eu lieu, c'est la
> restauration elle-même** — et tant qu'elle n'a pas eu lieu, « on a une
> sauvegarde » est une promesse, pas un fait.
>
> Ce document est le geste de Mike, écrit à l'avance pour qu'il se fasse en une
> soirée sans rien inventer en chemin. **Rien ici ne touche au PC vivant** : on
> restaure À CÔTÉ, dans un dossier neuf, et on compare.

## Pourquoi maintenant, et pourquoi pas plus tard

Deux choses ont changé le 22/08 :

1. `docs/undo_*.json` a cessé d'être un historique pour devenir un **actif
   porteur** : c'est par cette carte de 19 331 déplacements que **748 décisions
   humaines** décrochées par le rangement ont retrouvé leur photo. Les perdre,
   c'est perdre la capacité de réparer.
2. En préparant cette répétition, l'inventaire a été pris en flagrant délit :
   il annonçait **« Total exposé : 0 o »** en ne regardant que **trois**
   quarantaines sur les six du disque. Les deux nées le jour même —
   `_corbeille_recalage` (33 rattachements recalés) et `_corbeille_retraits`
   (2 couples retirés) — **n'étaient sauvegardées nulle part**. Corrigé le
   22/08 : les deux côtés découvrent les quarantaines par motif au lieu de les
   lister. *Un zéro parfait est une alarme, encore.*

C'est exactement le mode de panne que la répétition existe pour trouver : rien
n'était cassé, tout était vert, et une pièce manquait.

## Avant de commencer — 2 minutes

1. Le serveur tourne, `/reglages` s'ouvre.
2. Une sauvegarde d'artefacts a eu lieu **depuis le correctif du 22/08** (elle
   part avec le cycle de maintenance, à l'heure). Contrôle : la carte
   « Sauvegarde verifiee » de `/reglages`, ou le banc ci-dessous.
3. Un dossier de destination **vide**, sur un disque qui a la place :
   `C:\temp\essai-restauration` dans la suite (276 Mo pour la base + ~20 Mo
   d'artefacts).

Contrôle de départ, à lancer par le canal des bancs
(`_commande_banc.txt`) ou en console :

```
python verifier_restauration.py --vivant copie.db
```

Attendu : **« Total exposé : 0 o »** — et cette fois il parle de TOUTES les
quarantaines. Si une ligne dit `AUCUNE COPIE` en face d'un `IRRECUPERABLE`,
**arrête-toi là** : la sauvegarde a un trou, la répétition mesurerait ce trou
au lieu de mesurer la procédure.

## Le raccourci : `30 - Repetition de restauration.bat`

Tout ce qui suit tient dans un double-clic. Le lanceur enchaîne clone,
copie de la base, copie des artefacts, chronométrage, puis la comparaison — et
s'arrête avec un message clair à la première étape qui échoue.

Ce qu'il ne fait **pas**, exprès : il ne touche ni à la base vivante, ni au NAS,
ni au dossier du projet ; il ne supprime rien (sauf la base d'un essai
PRÉCÉDENT, dans le dossier d'essai, pour pouvoir être relancé) ; et il ne
télécharge pas les modèles YOLO ni le gazetteer — re-téléchargeables, ils ne
mettent aucune décision humaine en jeu et fausseraient le chrono.

Le dossier d'essai se passe **en argument** — `"30 - Repetition de
restauration.bat" E:\ailleurs` — ou se change en tête du fichier
(`set "CIBLE=…"`), tout comme l'adresse du NAS. Le lanceur refuse d'avancer si
le lecteur n'existe pas, plutôt que d'échouer trois étapes plus loin en
accusant la mauvaise cause (c'est ce qu'il a fait au premier essai, 22/08 :
`D:` n'existait pas et le message parlait d'un dossier non vide). La suite de ce document décrit **les mêmes gestes à la
main** — utile si le lanceur cale, ou pour comprendre ce qu'il fait.

## À la main — chronométrer du début à la fin

**Démarre le chrono maintenant.** Le chiffre qui compte n'est pas « ça marche »
mais « combien de temps entre un PC mort et une médiathèque qui répond ».

### 1. Le disque neuf (simulé)

Crée `C:\temp\essai-restauration`. Rien d'autre. C'est le PC neuf : tout ce qui n'y
arrivera pas par la sauvegarde n'existe pas.

### 2. Ce que le NAS rend

Depuis `\\nas-bremblens\home\Uploads` :

| Depuis le NAS | Vers le dossier d'essai | Ce que c'est |
|---|---|---|
| `photos.db.bak` | `photos.db` | l'index, les vecteurs, **toutes les décisions humaines** |
| `journal_jugements.jsonl` | `journal_jugements.jsonl` | l'historique des gestes humains |
| `artefacts\*` (tout l'arbre) | à la racine, même arborescence | réglages, `docs/undo_*`, quarantaines |

Le contenu de `artefacts\` se remet **à plat** : `artefacts\lieux.txt` →
`lieux.txt`, `artefacts\docs\undo_*.json` → `docs\undo_*.json`,
`artefacts\_corbeille_detections\…` → `_corbeille_detections\…`.

### 3. Ce que git rend

```
git clone https://github.com/TheMikeHoogly/MediaLibrary.git
```

`server.py`, les scripts, `requirements.txt`. **Ne pas écraser** les fichiers
de réglages venus du NAS (`dossiers_a_taguer.txt` & co. sont ignorés par git,
donc pas de conflit — mais vérifie qu'ils sont bien là après le clone).

### 4. Ce qui se re-télécharge

`yolo11s.pt`, `yolo11n.pt` (ultralytics), `cities1000.txt` (bat 18). À faire,
mais **note le temps à part** : ce n'est pas de la restauration, c'est du
téléchargement, et ça ne met aucune décision humaine en jeu.

### 5. La comparaison — le seul juge

De retour sur le PC vivant, base fraîche d'abord, puis la comparaison :

```
python mesure_copie_base.py
python verifier_restauration.py --vivant copie.db --restaure C:/temp/essai-restauration
```

**Arrête le chrono ici** et note le temps total.

> **Ne lance pas la comparaison avant d'avoir restauré.** Le 22/08, l'essai a
> été fait sur un dossier encore vide : l'instrument a répondu « Total exposé :
> 0 o » (il ne comptait que ce qui est PRÉSENT sans copie) puis s'est tué sur
> un refus de garde-fou. Les deux sont corrigés — il dit maintenant « RIEN N'A
> ÉTÉ RESTAURÉ ICI » et « COMPARAISON IMPOSSIBLE » — mais l'ordre reste : les
> étapes 1 à 4, PUIS l'étape 5.

## Comment lire le verdict

L'instrument compare les décisions humaines **nom par nom** — rattachements,
exclusions, confirmations. C'est le point entier de l'exercice :

> Un total identique ne prouve rien : deux erreurs qui se compensent donnent le
> même total.

Trois issues, et une seule est bonne :

- **« RÉPÉTITION RÉUSSIE »** — le rapport ne l'écrit que si l'intégrité, les
  tables, le nombre de noms ET chaque nom concordent. Note le temps
  dans `ROADMAP.md` et le chantier 12 se ferme.
- **Un écart sur un ou deux noms** → ce n'est pas un détail. Chaque nom est une
  décision qu'un humain a prise et que la sauvegarde n'a pas rendue. Ne
  corrige rien à la main : note lesquels, c'est la matière du correctif.
- **Un artefact absent** → la liste des manques est le résultat, pas un
  incident. C'est précisément ce que cette répétition doit produire tant
  qu'elle n'a pas eu lieu.

## Ce que la répétition ne dit pas

- Elle ne teste pas le NAS lui-même (les photos). Le fonds vit sur le NAS, la
  sauvegarde ne le duplique pas — c'est un choix, pas un oubli.
- Elle ne mesure pas le temps de re-calcul des vignettes ni des empreintes :
  ceux-là sont *recalculables*, ils coûtent des heures de machine, pas des
  décisions.
- Elle ne remplace pas une copie **hors site**. Un dégât qui emporte le PC ET
  le NAS emporte tout. Ça, c'est un choix qui t'appartient, et il n'est pas
  encore fait.
