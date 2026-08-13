# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (13/08/2026, fin de session 12)

- **Vignettes Lieux : observées bonnes en réel**, `fix/lieux-thumb` fusionnée
  (bat 27/28 passés). 25 cartes sur 25 en `/api/thumb` — 1 007 Ko et 315 ms
  pour les 25.
- **Trois tâches de fond étaient mortes en silence à chaque démarrage** :
  `backfill_dates`, `backfill_gps`, `reimport_name_tags`. Garde
  `if not EXIFTOOL: return` placée AVANT leur `sleep`, alors que `EXIFTOOL` est
  affecté par `maintenance_loop` lancé dans le même souffle. Constat :
  **42 060 entrées sur 43 067 jamais lues**, 12 407 photos (29 %) sans date au
  jour près, `namechk` inexistant. Corrigé sur la branche
  `fix/backfills-silencieux` (à commiter) : attente d'ExifTool, écriture
  interdite pour un fichier dont ExifTool n'a pas parlé, garde-fou des photos
  scannées, sérialisation dates → noms → GPS, et trois cartes d'état dans
  `/reglages`. **Rien n'est encore observé en réel.**

## Prochain pas — par valeur

1. **Gestes Mike, dans l'ordre** : bat 27 (`fix/backfills-silencieux`) → bat 0.
   Le premier démarrage est LONG (trois balayages du NAS, ~42 000 fichiers,
   qui cèdent le passage dès que tu navigues). Puis observer :
   (a) `/reglages` → trois nouvelles cartes (dates / noms / GPS) qui avancent ;
   (b) une fois « terminé », relancer `python diagnostic_dates.py --exif 30` —
   attendu : `taken absent` proche de 0, les 12 407 sans date effondrés ;
   (c) la galerie triée par date sur un dossier ancien (2007/2008) doit enfin
   s'ordonner dans la journée ; (d) aucun nom perdu. Puis bat 28.
2. **Chantier 6a « même jour, autres années »**, débloqué une fois (b) observé :
   moteur date pure (index MM-JJ en mémoire, **dates précises seulement**,
   jamais le repli « année du dossier »), route `/api/jour`, page
   `/files?jour=<clé>` calquée sur le mode `sim=`, bouton « Même jour » dans la
   lightbox. Zéro IA, zéro GPU, zéro accès NAS.
3. **Le reste inchangé** (détail : `ROADMAP.md`) : file « À vérifier » ; lots de
   renommage (plan = 2114) ; nettoyer Flo ; re-rejeter Caline ; activer
   `gps_place` — ce dernier profite directement du backfill GPS enfin réparé.
   Puis doublons proches bridés (50 paires jugées avant tout geste), UI —
   harmonisation (11), restauration à blanc (12), serveur MCP lecture (13).
