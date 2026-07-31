# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.

---

Tu reprends le projet **MediaLibrary** — photothèque familiale locale à IA
(~30 000 photos sur NAS, serveur Python stdlib, pipelines Ollama/InsightFace/
YOLO/DINOv2, RTX 3050 4 Go). Dossier : `C:\Prog\Claude\MediaLibrary`. Tout
l'état vit dans les fichiers, pas dans l'historique.

**Lis d'abord, dans l'ordre :**
1. `CLAUDE.md` — règles absolues.
2. `ROADMAP.md` — état et chantiers par ordre de valeur.
3. `eval/DECISIONS.md` — ce qui a déjà été **rejeté sur mesure** (ne pas
   reproposer : MegaDescriptor, contre-exemples, `sqlite-vec`, injection des
   noms au prompt de tagging).
4. Selon le chantier : `docs/AUDIT_EXTERNE_2026.md`, `docs/RANGEMENT_2026.md`,
   et les skills de `.claude/skills/` — `monolith-surgery` **avant tout edit de
   `server.py`**, `photo-ui` pour l'interface, `vision-eval` pour un
   seuil/modèle.

**Garde-fous à ne jamais oublier :**
- **Ne pas ouvrir `photos.db` (WAL) depuis un sandbox Linux** — le copier en
  `/tmp` en lecture seule. Les passes Ollama/GPU tournent sur la machine de
  Mike, via les `.bat` numérotés (ASCII pur : passer `python verifier_bat.py`
  et **lire sa sortie**).
- **Les noms attribués par un humain (`personne:` / `animal:`) ne se perdent
  jamais.** Ils vivent dans les XMP des fichiers.
- **Un score parfait est une alarme, un proxy n'est pas le juge.** La notation
  humaine a renversé un verdict automatique (« V2 ≈ V0 » était faux). Toujours
  vérifier l'effet réel d'une correction.
- **Zéro dépendance au démarrage** (imports lourds paresseux) ; côté client,
  **zéro build, zéro npm**.

**Outillage (état 31/07) :**
- **Git : accès local en session** — le dossier est un vrai dépôt
  (`origin = TheMikeHoogly/MediaLibrary`), `git` marche dans le shell (diff, log,
  branches, commit). La revue de diff avant de toucher `server.py` ne dépend PAS
  du connecteur GitHub MCP (OAuth non activable depuis la session). Le connecteur
  distant ne sert qu'aux issues/PR en ligne.
- **Figma** — connecteur actif et fonctionnel (testé via `whoami`), prêt pour le
  redesign UI « chambre noire ».
- Les autres connecteurs (Slack, Notion…) exigent un OAuth via les réglages
  claude.ai ; sans effet sur les chantiers en cours.

**Où on en est — trois chantiers ouverts, au choix :**
1. **Éval tagging (tranché, deux pas ciblés restants).** Hybride assertions+image
   adopté ; impératif de noms rejeté (coûteux, VRAM au plafond). (a) Noter/mesurer
   un V2 « assertions en contexte, **sans** impératif » (~4,3 s), puis brancher la
   **fusion programmatique** des noms/date/lieu dans la description. (b) **Comparatif
   de modèles** (veille juillet 2026) : le banc porte `--modele`/`--variantes` —
   lancer `python eval_tagging.py --modele qwen3-vl:2b --variantes V0` puis
   `--modele gemma4:e2b --variantes V0`, comparer pic VRAM (rejeter si frôle 4 Go)
   et qualité. Candidats : `gemma4:e2b` (FR natif, edge), `ministral-3-3b`,
   `moondream3`. Voir `eval/DECISIONS.md` et la « Veille modèles » de `ROADMAP.md`.
2. **Redesign UI/UX « chambre noire »** (ROADMAP, section Interface, points 9-12
   + composants signature). Une page à la fois, extraite puis redessinée, via
   Figma. Commencer par la page d'upload ou « Sujets ».
3. **Rangement & dédoublonnage** (`docs/RANGEMENT_2026.md`) — **le plus avancé.**
   - Phase 0 : `recensement_doublons.py` + `23 - Recenser les doublons.bat`
     **écrits et validés** (lecture seule). **À lancer par Mike sur le NAS** pour
     les vrais chiffres (doublons par contenu, Go récupérables, `_A TRIER`,
     sans-date), qui trancheront les 4 décisions ouvertes.
   - Prérequis Phase 1 : `vectors.rekey_prefix`/`rekey_prefix_all` **faits et
     testés** (`test_rekey_vectors.py` 12/12, `test_vectors` 29/29).
   - **Renommage intelligent** : spec convergée avec Mike (voir RANGEMENT, section
     « Renommage intelligent ») — format `YYYYMMDD_<lieu-ou-type>_<sujet>.ext`,
     tirets + ASCII, **automatique** sur `_Uploads`, entièrement réversible.
   - **Prochain pas serveur (session relue, sur COPIE de la base)** : le point de
     re-clé unique appelé à chaque déplacement/renommage — `STORE.rekey` +
     stores faces/people/animals/pets + `get_photo_vec().rekey_prefix_all` — puis
     brancher renommage et application de plan dessus. Charge `monolith-surgery`.

Cap long terme (voir ROADMAP) : **multimodalité** (images → vidéo → audio) et
**recherche AI** en langage naturel dans le serveur. À garder en tête dans les
décisions d'architecture.

Après lecture, dis-moi par lequel tu commences (ou attaque le plus utile) et
propose un plan court avant d'écrire du code. Astuce : dis simplement **« Go »**
et je te fais le débrief + prochaines étapes (protocole décrit dans `CLAUDE.md`).
