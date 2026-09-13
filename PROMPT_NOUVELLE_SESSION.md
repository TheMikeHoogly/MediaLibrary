# Reprise — MediaLibrary, après la session du 13 septembre 2026 (soir)

> **Ce fichier est ÉPHÉMÈRE.** Il décrit un état, pas des règles. Les règles
> vivent dans `CLAUDE.md`, le plan dans `ROADMAP.md`, les verdicts dans
> `eval/DECISIONS.md` et `docs/DECISIONS_OUTILLAGE.md`, les chiffres de
> performance dans `PERFORMANCE.md`.

---

## 0. L'état, en dix lignes

**La campagne de retag est FINIE** (nuit du 12 au 13). 40 525 photos portent
`qwen3.5:4b|v3fr|kb1`, 1 abandon, 100 % de vignettes. Le GPU est rendu, la RAM
aussi, **le prompt redevient touchable**.

**Les 248 dépôts d'`Uploads` sont TRIÉS** (13/09, par Mike). `_Uploads` est
vide ; la racine de `_A TRIER` est passée de **174 à 22 entrées** après les
bats 36 puis 26. Ce que le tri a laissé derrière lui est dans `ROADMAP.md` § A7
— dont **une décision qui expire vers le 13/10**.

**Le recensement est allé au bout** pour la première fois depuis le 06/09 :
**1 h 09**, 44 666 fichiers, 274,7 Go.

Index au 13/09 21 h 30 : **44 511 entrées**, 40 370 taguées, file de retag 63,
0 cycle inexpliqué, 0 anomalie. `main` à **`1664c50`** + la livraison de ce
soir.

---

## 1. Par où commencer

Si rien d'autre n'est demandé : **§ 2 ci-dessous**, dans cet ordre, parce que
la mesure du 13/09 au soir en a fixé l'ordre.

Le tableau de priorités vit dans `ROADMAP.md` § B. Ce qu'il faut en retenir :

- **UNE décision appartient à Mike** — « faut-il une prochaine campagne, et
  avec quoi ? ». Une campagne coûte ~8 h de GPU, réécrit 40 000 XMP et
  **efface l'état d'avant** : tout ce qui doit changer dans le pipeline change
  en même temps, ou pas du tout. § B liste les **quatre** choses à poser sur la
  table avant d'en parler. **Ne rien proposer tant qu'elles n'y sont pas.**
- **Le reste ne dépend de personne** : la marche du NAS et la grille à la
  demande (§ C3), `_A TRIER` par propriétaire (§ B8), et les mesures qui
  demandaient le serveur arrêté (§ B5, B6).

---

## 2. La performance : la mesure a tranché l'ORDRE

Reprise au calme le 13/09 à 19 h 22, NAS libre (le recensement venait de
finir). Page du fonds ENTIER, `dir=1&rec=1`, ~46 000 photos, 33,7 Mo :

| | NAS occupé | **NAS libre** |
|---|---:|---:|
| total | 25,2 s | **23,4 s** |
| `parcours` (marche SMB) | 18,2 s | **16,8 s — 72 %** |
| `enrichir` | 3,5 s | 3,4 s — 15 % |
| `envoi` | 1,1 s | 1,0 s — 4 % |
| `index` (les mêmes photos) | 0,48 s | **0,31 s** |

**La contention n'expliquait que 1,4 s sur 18.** Et sur ces 16,8 s de marche,
le CPU n'en consomme que **1,1 s** : **94 % d'attente pure**. Aucune
optimisation de code ne touchera ça.

**D'où l'ordre, qui est la vraie conclusion :**

1. **couper la marche** — servir la grille récursive depuis l'index, marche
   réduite au dossier courant ou reléguée au scan de fond : 23,4 s → **~7 s** ;
2. **le chargement à la demande ENSUITE** (décidé par Mike), qui attaque alors
   `enrichir` : ~7 s → **~1 s**.

Dans l'autre ordre, le chargement à la demande seul ne gagne que ~2 s sur 23.

**Le contrôle qui ouvre le chantier, et le premier quart d'heure de la
séance** : l'index porte 44 665 clés, la marche a trouvé 44 666 fichiers —
**un écart d'UN fichier**, payé 16,8 s à chaque page. Trouver ce fichier, et
dire ce que la marche apporte que l'index n'a pas (présence, `mtime`/taille
pour les dates). `ROADMAP.md` § C3 donne les trois réponses candidates.

---

## 3. `_A TRIER` par propriétaire — décidé, pas construit

Mike a validé le 13/09. **La moitié existe déjà** :
`rangement_annee.base_du_fonds()` range ce qui sort de `Photos Flo/_A TRIER`
dans `Photos Flo/<année>` — vérifié en exécutant la fonction. Le chemin EST le
propriétaire.

Ce qui manque est du côté DÉPÔT : `cible_a_trier()` code en dur la racine, qui
retombe sur le propriétaire du fonds. **Si Flo garde un dépôt, il finit chez
Mike, en silence.** L'identité est pourtant déjà captée (`noter_depot()` écrit
`par`).

Trois défauts voisins à corriger dans le même aller-retour — `Google porte
mieux` échappe au plan d'année ET au bat 36, et le bat 36 apprend à comparer
une vidéo. Le détail, avec ses raisons, est dans `ROADMAP.md` § B8.

**Deux nuances à ne pas perdre** : le découpage n'est pas « par compte » mais
« par dossier propriétaire » (`Photos Papa` n'a pas de compte), et **le
déposant est un défaut, jamais un verdict**.

---

## 4. Deux garde-fous qui ont tenu — et qu'il ne faut pas casser

- **`dico_fr_en.json` est la seule matière de l'élargissement FR→EN.** Le retag
  FR seul a vidé `kw_en` (**0 sur 40 525**, mesuré) ; le dictionnaire appris
  est tombé à `appris: 0`, et seul le GEL du 05/09 fait encore vivre la
  recherche élargie (**3 862 paires**, `source: gelé`). **Ne jamais « nettoyer »
  ce fichier.**
- **`exiftool -P`** : 40 000 XMP réécrits dans la nuit, aucune date de fichier
  détruite.

---

## 5. Les pièges

- **Le recensement dure 1 h 09** (mesuré le 13/09, complet, NAS à lui seul) et
  **chaque redémarrage du serveur le tue** — or le protocole en impose un à
  chaque changement de `server.py`. Avant de livrer en rafale, regarder
  `maint.lourde` dans `/api/maint/status` : si une étape lourde tourne depuis
  20 minutes, elle mourra pour rien.
- **Deux balayages SMB simultanés coûtent très cher** : l'énumération du NAS
  passe de **305 s à 2 100 s**. Mesuré deux fois.
- **Un outil qui descend récursivement dans `_A TRIER` traverse la salle
  d'arbitrage.** C'est comme ça que le bat 36 a résolu tout seul l'arbitrage
  Google de 68 photos (§ A7). Avant d'écrire un outil qui parcourt `_A TRIER`,
  se demander ce qu'il fera des sous-dossiers.
- **Windows : KB5124008 casse Plan9**, donc `device_bash`. UBR **9278**, Windows
  Update **en pause jusqu'au 17.10**. `Get-HotFix` MENT ; la vérité est
  `(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR`.
  **Vers le 16.10** : masquer le KB s'il est reproposé.
- **La VM n'atteint pas le LAN** : `curl` depuis `device_bash` ne voit pas le
  serveur, même par l'IP. Tout ce qui interroge le serveur passe par l'agent de
  banc ou par **Chrome** (`http://192.168.0.13:8080`). Le NAS, lui, est monté
  sous `$HOME/mnt/Photos`.
- **Chrome, jamais le navigateur intégré** (demande de Mike, 13/09). `/files`
  prend `dir=<index>/<sous-chemin>` ; la racine du NAS est `dir=1`.
- **Canaux** : écrire `rien`, puis l'ordre UNE fois, puis ATTENDRE le retour à
  `rien`. `_banc_sortie.txt` porte un EN-TÊTE qui dit de quel banc vient la
  sortie : c'est lui qui fait foi.
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

Et, après toute analyse : **la contre-vérifier** (règle 11). Elle a encore
attrapé deux conclusions fausses le 13/09 au soir — dont une de mes propres
mesures, lue sur un manifeste que j'avais mal analysé. Une ligne recopiée d'une
doc n'est pas une mesure ; un compte tiré d'un parseur qui rend 4 noms sur
2 409 non plus.
