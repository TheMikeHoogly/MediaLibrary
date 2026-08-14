# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (14/08/2026, fin de session 12)

- **Trois tâches de fond réparées, observées bonnes en réel** (branche
  `fix/backfills-silencieux`, committée, **pas encore fusionnée**). Elles
  mouraient en silence à chaque démarrage depuis toujours. Résultat de la nuit,
  0 fichier muet et 0 erreur sur les trois : **32 822 dates de prise de vue**
  récupérées sur 42 060 photos lues, **184 tags de noms** rapatriés depuis les
  XMP, **5 394 photos géolocalisées** de plus (carte : 1 220 → 6 614 points).
- **Un second bug est apparu en vérifiant** : la vue « Dossiers »
  (`/files?dir=`) ne trouve aucune entrée d'index pour la racine NAS —
  `Path.resolve()` minuscule le nom d'hôte SMB, `STORE.get(str(f))` est
  sensible à la casse. Elle affiche donc toutes les photos sans tags, sans
  description, sans GPS et sans date. **Antérieur à cette session**, non
  corrigé. C'est le prochain chantier (point 5 de `ROADMAP.md`).

## Prochain pas — par valeur

1. **Geste Mike : bat 28** (fusionner `fix/backfills-silencieux`), puis bat 29.
   Rien d'autre ne bloque : les trois passes ont fini et ne repasseront qu'en
   rattrapage (quelques fichiers) aux prochains démarrages.
2. **Casse des clés dans la vue dossier** — petit correctif, gros effet :
   `_serve_gallery` doit chercher l'entrée via `_pkey` (index secondaire
   `{_pkey: clé}` bâti une fois, comme le fait déjà le reste du code) au lieu
   de `STORE.get(str(f))`. À observer en réel : ouvrir un dossier ancien, les
   tags et la date de prise de vue doivent apparaître.
3. **Chantier 6a « même jour, autres années »**, maintenant débloqué : moteur
   date pure (index MM-JJ en mémoire, **dates précises seulement**, jamais le
   repli « année du dossier »), route `/api/jour`, page `/files?jour=<clé>`
   calquée sur le mode `sim=`, bouton « Même jour » dans la lightbox. Zéro IA,
   zéro GPU, zéro accès NAS.
4. **Le reste inchangé** (détail : `ROADMAP.md`) : file « À vérifier » ; lots de
   renommage (plan = 2114) ; nettoyer Flo ; re-rejeter Caline ; activer
   `gps_place` — d'autant plus intéressant maintenant que la carte a 6 614
   points. Puis doublons proches bridés, UI — harmonisation (11), restauration
   à blanc (12), serveur MCP lecture (13).
