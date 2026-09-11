# Reprise — MediaLibrary, après la session du 11 septembre 2026 au soir

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`. **Les chiffres du
> chantier performance sont dans `PERFORMANCE.md`** (§ 3.4, 3.10, 3.11, § 5).

---

## 0. La consigne de Mike

> « concentre toi sur la performance (toujours en attendant la fin du
> tagging). fais une analyse en profondeur, des tests utiles et intelligents »
> — « sois le plus autonome possible, fais les tests, tu as accès aux folders
> et à Chrome ».

La campagne de retag commande toujours tout : GPU pris, **prompt
intouchable**, fin attendue vers le **14/09**.

---

## 1. Livré le 11/09 au soir — sur `main`

| Commit | Quoi | Observé |
|---|---|---|
| `2d40c26` | `/api/maint/status` : trois balayages → une passe ; sondes GC/GIL (`/api/serveur` → `sondes`) ; CPU du fil et défauts de page par phase (`/api/perf` → `derniers`) ; bancs `mesure_memoire`, `mesure_cpu`, `diagnostic_ollama_memoire`, `mesure_citations_cachees` | 280–560 → 200–460 ms |
| `3c88b9e` | **correction** de la vue par utilisateur : une fiche réécrite garde ce que l'écrivain ne voyait pas (`restaurer_fiche`), `pop` sur la vue, `values`/`items` filtrés | listes Personnes/Animaux identiques octet pour octet ; exposition réelle 0 fiche |
| `fix/vue-rapide` | prédicat de visibilité réécrit à l'identique, `filter()` natif, `mesure_vue.py` | sur les vraies clés : `len` ×1,66, `values` ×1,67, `items` ×1,44 ; comptes identiques |
| `fix/rename-garde-les-auteurs` | `rename` transporte `auteurs` de la fiche absorbée : les jugements de Flo passaient au nom de celui qui renomme | bancs sur le vrai `SubjectStore` ; ancien code, 3 rouges |
| `fix/gel-du-gc` | `gc.freeze()` des 505 000 objets permanents **et** `threshold2` à 100 | temps de collecte ÷3,8 (3,43 → 0,91 ms par seconde de service), pire pause 509 → 210 ms |
| `feat/http-1-1` | `Content-Length` partout (instrument par l'arbre : 4 réponses nues corrigées), puis `protocol_version` et `timeout` | 120 vignettes : **120 connexions TCP → 4 puis 0**, médiane 14–20 → 11–13 ms ; 416 et plages vérifiés |
| `feat/last-modified` | `Last-Modified` + 304 sur les médias, `no-cache` (les écritures XMP changent les fichiers) | photo de 1,6 Mo : **1 599 130 octets → 0**, 334 → 41 ms ; une plage reste un 206 |

---

## 2. Ce que la session a appris

1. **Le temps perdu n'était pas dans les routes.** Trois `len()` à 47 ms de
   CPU : c'est la **vue par utilisateur**, ~3 µs par clé sur chaque lecture
   agrégée dès qu'un compte est connecté.
2. **La machine pagine** : 0,5 Go de RAM libre, `llama-server` à **13,5 Go
   privés** (modèle déclaré 3,47 Go). `ollama stop` rend la place, elle est
   reprise en vingt minutes : réservation, pas fuite lente.
3. **Le GC complet gelait tout 348 ms toutes les ~100 s** — corrigé le 12/09
   (§ 3.12) : il fallait le gel ET le seuil, le gel seul déplaçait le coût.
4. **Le modèle de tagging n'a que 1,2–1,7 Go en VRAM** : le reste tourne sur
   le CPU. La VRAM libre au chargement décide.

---

## 3. Ce que la session suivante doit faire, dans l'ordre

0. **Vérifier l'état réel** : `.git/logs/refs/heads/main` doit finir sur le
   dernier commit du tableau § 1 — une doc décrit une intention, git dit ce
   qui est fusionné.
1. **`device_bash` remarche** (Mike a retiré la mise à jour Windows le 11/09
   au soir) — mais il tourne dans une VM **Linux** : il ne voit ni les
   processus Windows, ni `localhost:11434`. Ollama, la RAM, le CPU : par
   l'agent de banc. Et le pont écrit encore parfois une version périmée
   (vu deux fois ce soir) : **vérifier par `sha1sum` en `device_bash`**.
2. **Les 13,5 Go d'Ollama** : ni fuite lente (13,5 Go après 20 min), ni
   mémoire épinglée par CUDA (`GGML_CUDA_NO_PINNED=1` essayé, 13,33 Go).
   Le chiffre qui compte : **7,8 Go résidents** pour un modèle de 3,47 Go.
   Rien à faire pendant la campagne — après, un modèle qui tient dans les
   4 Go de VRAM (`vision-eval`). Tant que ça tient, la machine pagine.
3. **La planche entière** (§ 3.7) : le seul gros morceau qui reste, et il ne
   se rouvre qu'avec une mesure côté NAVIGATEUR (ce que coûte l'analyse de
   1,7 million de caractères de JSON avant la première vignette).

---

## 4. Les pièges

- **`device_bash`** : hors service depuis la mise à jour Windows du 08/09 ;
  Mike l'a désinstallée le 11/09 au soir — **à revérifier**. Sans lui : éditer
  dans la sandbox, écrire par le pont, **vérifier par `sha1`** après re-staging.
- **Canaux** : un ordre écrit DEUX fois relance le banc deux fois (vu le 11/09) ;
  pour un banc, écrire `rien`, puis l'ordre UNE fois, puis re-stager et
  comparer la taille.
- **Chrome** : un onglet resté inactif gèle (`Runtime.evaluate` 45 s) — en
  ouvrir un neuf ; scripts de moins de 20 s. `crypto.subtle` absent (http).
- **Comparer phase par phase**, et maintenant **CPU contre temps écoulé** :
  c'est ce qui a départagé calcul, attente du disque et attente du GIL.
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 5. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.
