# Amorce de reprise — MediaLibrary

> Colle ce bloc dans une nouvelle conversation Cowork, après avoir connecté
> `C:\Prog\Claude\MediaLibrary`. L'état vit dans les fichiers, pas dans l'historique.
> Règles + protocole = `CLAUDE.md` (chargé auto). Ici : juste l'état et le prochain pas.

Tu reprends **MediaLibrary** — photothèque familiale locale à IA (~30 000 photos NAS,
serveur Python stdlib pur, pipelines Ollama/InsightFace/YOLO/DINOv2, RTX 3050 4 Go).

## Ordre de lecture

1. `CLAUDE.md` (auto) — règles absolues, protocole, architecture.
2. `ROADMAP.md` — état détaillé + priorités par valeur.
3. `eval/DECISIONS.md` — pistes déjà tranchées (ne rien reproposer).
4. Selon le sujet : `docs/RANGEMENT_2026.md`, `docs/AUDIT_EXTERNE_2026.md` ; skills
   `monolith-surgery` (avant tout edit de `server.py`), `photo-ui` (dès qu'on touche l'UI).

## Où on en est (11/08/2026, fin de journée)

Tout le 11/08 est **vérifié en réel**, mais **PAS commité** (`27 - Commit de session.bat`) :
- **Matin** : Lieux vérifiés (25, 0,8 s ; commit `fd1f805`) ; fixes clusters, perf `/sujets`
  (>45 s → 0,8 s), page résultats `/files?q=` ; **fix racine faux positifs** (`attribuer_visage`).
- **Après-midi** : **fix FP confirmé en réel** (rebuild complet du curateur → 0 carte, aucun
  des 5 FP corrigés ne revient) ; **fusion `/sujets`** (entrée unique : onglets
  Personnes/Animaux retirés de la nav, Sujets actif sur `/people`/`/pets`, rangée « Files de
  travail ») ; **passe DESIGN PEOPLE+PETS** (~128 valeurs hors échelle → tokens, lint 0 interdit).

⚠ `/pets` signale « moteur d'empreintes absent (**installe timm**) », empreintes 0, vignettes
groupes vides : le `.venv` du serveur a perdu `timm` — geste Mike.

## Prochain pas — par valeur

1. **Vérité terrain (priorité n°1)** : confirmer ~100 propositions dans `/people`
   (page filtrable, tri clavier Espace=oui / X=non / Z=annuler).
2. **Passe DESIGN — pages restantes** : GALLERY/BROWSE/MAP/HTML/FACES (mêmes mappings que
   PEOPLE/PETS, page par page + vérif visuelle) ; puis extraction physique vers `ui/` (`bundle.py`).
3. Gestes Mike : commit de session ; `pip install timm` (`.venv`) ; lots de renommage +
   activer `gps_place` ; nettoyer Flo/Caline.

## Rappels opérationnels

- Tester en réel : **192.168.0.13:8080** via Claude-in-Chrome. **Pas de hot-reload** →
  redémarrer (`0 - Démarrer le serveur.bat`) après toute modif de `server.py`. Captures =
  onglet au premier plan ; état par `fetch` GET (marche onglet caché).
- Livraison sandbox → disque : `SendUserFile` puis `device_commit_files`. **Git + redémarrage
  = gestes Mike.** Ne pas ouvrir `photos.db` depuis le sandbox (le serveur est l'écrivain unique).
