# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (12/08/2026, fin de session 6)

- **Git sain** : `HEAD = main = origin/main` — tout commité, fusionné, poussé ;
  aucune branche non fusionnée. Le protocole bats 27 → 28 tient. Le **bat 30**
  supprime les étiquettes de branches déjà fusionnées (22 traînaient).
- Vérifié en réel : files Classification garnies (18 personnes, 120 animaux),
  `/api/thumb` 200 (52 Ko vs 4,7 Mo), Range 206.
- **Session 6 — à commiter + redémarrer** : correctif de l'échéance de
  sauvegarde (ci-dessous), `photo_thumbs/` gitignoré, bat 30.
- **Non observé** : effet O6 (`pending = 0`, aucun arriéré → la contention ne
  peut pas se reproduire ; il faut déposer ~30 photos neuves pour la revoir).

## Le vrai risque du moment : la sauvegarde ne partait pas

`backup_verify` n'avait jamais tourné, et la cause n'était pas la vérification :
**l'échéance du backup était un compteur de tours** (`cycle % 12`), variable
locale remise à zéro à chaque démarrage. Il fallait donc **1 h de serveur
ininterrompu** — or il n'y a pas de hot-reload : chaque modif de `server.py`
impose un redémarrage, plusieurs par heure les jours de développement. La base
pouvait n'être **jamais** sauvegardée précisément les jours où des jugements
humains sont produits. Corrigé : l'échéance se lit sur le **mtime du snapshot**
(`_backup_du()`) — sans état, insensible aux redémarrages, et une sauvegarde en
retard part dès le premier tour qui suit le démarrage.

**À observer (réflexe n°2)** : après redémarrage, `/reglages` → la carte
« Sauvegarde vérifiée » doit passer à **ok en quelques minutes**. Si elle reste
« jamais », c'est l'URI UNC de `backup_verify` qui coince (jamais vue passer sur
Windows) — le message est dans la console du serveur.

## Prochain pas — par valeur

1. **Commiter + redémarrer**, puis guetter « Sauvegarde vérifiée : ok ».
2. **Éval tagging V2** avant tout lot de renommage
   (`eval/PLAN_assertions_vs_pixels.md`) ; si confirmée → Knowledge Builder.
3. **Correctifs d'audit restants** (I4–I8, O7–O9, O11–O15) et gestes Mike :
   nettoyer Flo (5 909 photos sur sa fiche), `gps_place`. Ordre : `ROADMAP.md`.
4. **Jugement dans Classification** : au fil de l'eau, sans en faire un
   préalable — cf. cadrage du point 1 de la roadmap (la limite est la
   connaissance des visages, pas l'outil ; Flo nommera le reste).
