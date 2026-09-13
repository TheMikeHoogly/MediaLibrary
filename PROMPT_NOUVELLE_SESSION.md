# Reprise — MediaLibrary, après la session du 13 septembre 2026

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`, les chiffres de
> performance dans `PERFORMANCE.md`.

---

## 0. L'état, en dix lignes

**La campagne de retag est FINIE** (nuit du 12 au 13). 40 525 photos portent
`qwen3.5:4b|v3fr|kb1`, 1 abandon, **100 % de vignettes**, pas une photo sans
mots-clés ni description. Le GPU est rendu, la RAM aussi (5,2 Go libres contre
0,5 pendant), **le prompt redevient touchable**.

Trois contraintes sont tombées d'un coup : la difficulté n'est plus d'attendre,
c'est de **choisir**. `ROADMAP.md` section B est réorganisée pour ça.

**Ce qui n'a pas bougé** : les **248 dépôts d'`Uploads`** attendent Mike depuis
31 jours. C'est le seul point que rien de ce que je fais ne débloque.

---

## 1. L'analyse qui doit gouverner la prochaine session

**Ce ne sont pas huit chantiers, c'est UNE décision et trois travaux.**

- **UNE décision, qui appartient à Mike** : « faut-il une prochaine campagne,
  et avec quoi ? ». Le modèle de vision, la question des documents sensibles,
  le bilan, l'abandon — tout converge là. Une campagne coûte **~8 h de GPU**,
  réécrit 40 000 XMP et **efface l'état d'avant** : ce qui doit changer dans le
  pipeline change en même temps, ou pas du tout. `ROADMAP.md` § B liste les
  quatre choses à poser sur la table avant d'en parler à Mike. **Ne rien
  proposer tant qu'elles n'y sont pas.**
- **TROIS travaux qui ne dépendent de personne** : la grille à la demande
  (§ C3), la fenêtre du recensement (§ B7), et les mesures qui demandaient le
  serveur arrêté ou le GPU (§ B5, B6).

Par où commencer, si rien d'autre n'est demandé : **§ C3**, mais en lisant
d'abord le paragraphe suivant — la mesure du 13/09 au soir a changé ce qu'il
faut construire.

---

## 2. La grille à la demande : ce que la dernière mesure a changé

Mike a tranché (13/09) : chargement à la demande. J'avais justifié ça par
« `envoi` est devenu le plus gros poste » — **vrai pour un dossier, faux pour
le pire cas**. Sur la page du fonds ENTIER (`dir=1&rec=1`, ~46 000 photos,
33,7 Mo) :

| | dossier de 2 519 | fonds ENTIER |
|---|---:|---:|
| total | ~0,6 s | **25 s** (112 s à froid) |
| `parcours` (marche SMB) | 50 ms | **18,2 s — 72 %** |
| `envoi` | 93 ms | 1,1 s — 4 % |
| `index` (mêmes photos) | 45 ms | **0,48 s** |

**Paginer le RENDU seul laisserait le premier écran attendre 18 s.** Et
l'index connaît les mêmes photos **38 fois plus vite**. La question à trancher
AVANT de coder n'est donc pas « combien de fiches par page » mais **« une
grille récursive doit-elle encore marcher sur le NAS ? »** — la marche sert à
voir ce que l'index ignore encore. Trois réponses possibles dans `ROADMAP.md`
§ C3.

**Ces chiffres ont été pris pendant qu'un recensement tenait le NAS** : ils
donnent la FORME du problème, pas des valeurs à citer. Les reprendre au calme.

---

## 3. Deux garde-fous qui ont tenu — et qu'il ne faut pas casser

- **`dico_fr_en.json` est la seule matière de l'élargissement FR→EN.** Le retag
  FR seul a vidé `kw_en` (**0 sur 40 525**, mesuré) ; le dictionnaire appris
  est tombé à `appris: 0`, et seul le GEL du 05/09 fait encore vivre la
  recherche élargie (**3 862 paires**, `source: gelé`). **Ne jamais « nettoyer »
  ce fichier.**
- **`exiftool -P`** : 40 000 XMP réécrits dans la nuit, aucune date de fichier
  détruite.

---

## 4. Ce que j'ai livré le 13/09 (détail : git)

Quatre livraisons, `5533353` → `bf09366`.

- **La roadmap réorganisée** autour de la fin de campagne, et l'amorce réécrite.
- **Une étape lourde dit sa FIN, sa durée et son verdict** — y compris quand
  elle lève. Avant : le recensement annonçait son départ et **plus rien pendant
  40 minutes**, et un échec emportait le plan de rangement **en silence**.
  `/api/maint/status` porte maintenant `maint.lourde` (ce qui tourne, et depuis
  quand).
- **Un échec gardé en base nomme sa cause** (`_motif_lisible`) : type,
  message, fichier:ligne. L'unique abandon de la campagne ne disait que
  « another row available » — un message de SQLite, impossible à situer.
- **Trois corrections de roadmap**, toutes trouvées en vérifiant au lieu de
  recopier : B7 était déjà fait des deux côtés, la copie de 283 Mo n'existait
  plus, et ma propre conclusion sur la concurrence SMB était fausse.

---

## 5. Les pièges

- **Le recensement ne se termine plus depuis le 06/09.** Il dure **40 min à
  froid, 8 min à chaud** (cache SMB), et **chaque redémarrage du serveur le
  tue** — or le protocole en impose un à chaque changement de `server.py`.
  Avant de livrer en rafale, regarder `maint.lourde` : si une étape lourde
  tourne depuis 20 minutes, elle mourra pour rien.
- **Deux balayages SMB simultanés coûtent très cher** : l'énumération du NAS
  passe de **305 s à 2 100 s**. Mesuré deux fois.
- **Windows : KB5124008 casse Plan9**, donc `device_bash`. UBR **9278**, Windows
  Update **en pause jusqu'au 17.10**. `Get-HotFix` MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **La VM n'atteint pas le LAN** : tout ce qui interroge le serveur passe par
  l'agent de banc ou par Chrome. Le NAS, lui, est monté sous `$HOME/mnt/Photos`.
- **Canaux** : écrire `rien`, puis l'ordre UNE fois, puis ATTENDRE le retour à
  `rien`. `_banc_sortie.txt` porte un EN-TÊTE qui dit de quel banc vient la
  sortie : c'est lui qui fait foi.
- **Chrome, jamais le navigateur intégré.** `/files` prend `dir=<index>/<sous-
  chemin>` ; la racine du NAS est `dir=1`.
- **Un `livrer` qui touche `server.py` lance ~73 bancs et dure ~6 minutes** :
  c'est voulu. Ne pas conclure à un blocage avant d'avoir attendu.
- **Un banc qui EXÉCUTE une fonction extraite de `server.py` doit recevoir ses
  dépendances** : quatre bancs sont tombés cette semaine parce qu'une fonction
  de prod avait gagné un appel. Et **un banc qui lit le source par le TEXTE
  mesure une orthographe** — écrire sur l'ARBRE (`ast`).
- `server.py` : skill `monolith-surgery` ; UI : `photo-ui`.

---

## 6. Protocole (inchangé)

Éditer → redémarrer (`uptime_s` > 60 d'abord) → **observer en réel** →
`SESSION_COMMIT.txt` → `livrer` → **vérifier dans `.git/logs/refs/heads/main`**.

Et, après toute analyse : **la contre-vérifier** (règle 11). Trois fois cette
semaine elle a attrapé une conclusion fausse **que je venais d'écrire** — dont
deux dans la roadmap elle-même. Une ligne recopiée d'une doc n'est pas une
mesure.
