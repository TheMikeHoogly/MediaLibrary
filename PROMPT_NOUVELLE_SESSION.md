# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (18/08/2026, fin de session 21)

**Chantier 10a CLOS — l'instrument a été observé, et prouvé.** Douze cycles de
scan chez Mike : index 43 064 invariant, `ajouts`/`retraits` 0, « (non declare) »
0, `inexpliqué` 0 partout. Puis un **contrôle positif** en deux temps — une
photo-témoin déposée dans `_Uploads`, puis retirée :

```
43 064 → 43 065  (+1)  ajouts 1   motif tagging         inexplique 0
43 065 → 43 064  (−1)  retraits 1 motif scan:disparus   inexplique 0
```

C'est ce geste qui donne leur sens aux zéros : sans lui, « zéro partout » et
« l'instrument est débranché » se lisent pareil. Le sujet des −250 du 17/08 se
ferme : rien n'a été perdu, le mécanisme reste inconnu, et s'il revient le
registre rendra le chiffre. **Portée honnête** : les −250 sont apparus SOUS
CHARGE ; ceci ne prouve pas l'absence de fuite sous charge, seulement qu'elle
serait comptée.

## Prochain pas — par valeur

1. **10b — les deux gestes pas chers, indépendants et réversibles** : garder
   l'étape 2 du repli (le NOM — 1 cas, module pur, sans redémarrage) et rendre
   au plan de renommage les **15 noms périmés**. Ils ne touchent NI le pipeline
   de dates NI les **1 369** dates antérieures. Le troisième geste — corriger
   `taken` en base pour **72** photos (`monolith-surgery` + backfill) — reste
   **non décidé** : c'est lui qui risque d'emporter les 1 369.
2. **Trois constats du registre**, relevés le 18/08, non traités (ROADMAP 10a) :
   ajout étiqueté `tagging` au lieu de `scan:*` ; `dict.__ior__` non redéfini
   dans `TrackedDict` (trou latent du goulot, aucun usage) ; `cycles_vus` =
   longueur d'un anneau de 10, pas un compteur.
3. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Ne pas revenir à V0 sans protocole.**
4. **14a, suites** : les `faits` ne filtrent pas encore ; pas de filtre par
   espèce ni par fiche ; le tri d'un résultat sans mot-clé passe encore par
   `_best_time` (donc `mtime`) là où la sélection l'exclut.
5. **Le reste** (`ROADMAP.md`) : deux images tronquées en attente d'encodage à
   chaque démarrage ; gestes Mike (Flo, Caline) ; doublons proches ; UI (11) ;
   restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : les deux planchers 1990 restants coûtent
7 photos et 0, et ils sont couplés. La strate « piège » du banc 3b (83 %) est
une hypothèse post-hoc sur 30 photos, pas une décision.

**À vider à la main** quand la recherche aura vécu quelques jours :
`_corbeille_vecteurs/` (2 374 lignes, toutes relues) et
`_corbeille_session/plan_avant/`.

**Ordre des gestes git : 27 → 0 → 28.**
