# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md` puis `eval/DECISIONS.md`, débrief
en 2–3 lignes, puis on attaque.

## Où on en est (14/08/2026, fin de session 13)

- `fix/backfills-silencieux` **fusionné**. Les trois tâches de fond ont fini leur
  passe complète ; elles ne repasseront qu'en rattrapage (quelques fichiers).
- **Livré en session 13, branche `feat/meme-jour-et-casse`, PAS ENCORE OBSERVÉ
  EN RÉEL** (le serveur n'a pas de hot-reload : il faut le redémarrer) :
  1. **Correctif de casse.** `_serve_gallery` et `_serve_random` retrouvent
     l'entrée d'index par `_index_key_for_path` (index secondaire
     `{chemin normalisé: clé}`, `fichiers.build_key_index`) au lieu de
     `STORE.get(str(f))`. Ils rendent aussi la clé d'index EXACTE au client.
  2. **Chantier 6a « même jour, autres années ».** `meme_jour.py` (pur, testé :
     `python test_meme_jour.py`, 40 vérifications), `/api/jour`,
     `/files?jour=<clé|MM-JJ>`, bouton « Même jour » dans la visionneuse.
     Dates **précises uniquement** ; toutes les années, groupées, référence
     exclue.
- Témoin vérifié en bac à sable : sur le code d'avant, la même photo sort sans
  tags et au 1ᵉʳ janvier ; sur le code d'après, 20 tags et sa vraie date.

## Prochain pas — par valeur

1. **Observer en réel, c'est la seule chose qui compte maintenant** (192.168.0.13:8080,
   après `0 - Démarrer le serveur.bat`) :
   (a) ouvrir un dossier ancien du NAS → tags, description, GPS et date de prise
   de vue doivent apparaître ; (b) ouvrir une photo → bouton « Même jour
   (14 août) », cliquer → la journée, toutes années, groupée par millésime ;
   (c) une photo sans date précise ne doit PAS montrer le bouton ;
   (d) diaporama aléatoire sur le NAS → tags et description présents.
2. **Gestes Mike, dans cet ordre** : nettoyer Flo (5 909 photos) ; re-rejeter
   Caline une fois ; activer `gps_place` (bat 18 → `enrichir_lieux.py` →
   `--ecrire` → redémarrer) ; lots de renommage (plan = 2114).
3. **Le reste inchangé** (détail : `ROADMAP.md`) : file « À vérifier » ;
   doublons proches bridés ; UI — harmonisation (11) ; restauration à blanc
   (12) ; serveur MCP lecture (13).
