# Décisions tranchées

> Chaque piste, son verdict, pour ne rien re-proposer. Chiffres : git. Les
> adoptés stabilisés vivent dans les Acquis de `ROADMAP.md` ; ici, ce qui a
> été REJETÉ, CORRIGÉ ou reste OUVERT.

## Reconnaissance · triage · stockage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Contre-exemples (exclusions comme négatifs) | **REJETÉ** (30/07) | −8,7 % partout. |
| Garde humain/animal auto (SigLIP zéro-shot) | **REJETÉ** (08/08) | Visages et statues/chats se chevauchent : 18 % faux rejets. Remède humain : « C'est un animal ». |
| Garde visages sur découpes SANS marge · deux signaux | **PARKÉ** | Seules pistes restantes (0,3 de marge embarque le chat voisin). |
| MegaDescriptor plutôt que DINOv2 | **REJETÉ** (31/07) | À armes égales, DINOv2 garde +3,4 pts. |
| Découpes en plus haute résolution | **REJETÉ** (31/07) | Aucun effet (256 px ne touche que l'affichage). Fêtes MOBILES aussi (15/08) : mal placée d'un jour, pire qu'absente. |
| Détecteur ML de rebut / flou auto | **REJETÉ par conception** (03/08) | Rebut évident = règle simple ; subtil non isolable sans risquer une bonne photo. |
| `sqlite-vec` ; embeddings INT8 | **REJETÉ** (11/08) | Cosinus numpy sur BLOB suffit. INT8 : ×2 mais recall@10 0,9685 — « sans perte » réfuté. |

## Tagging / description

| Idée / piste | Verdict | Raison |
|---|---|---|
| V1 — assertions seules, pixels jetés | **REJETÉ** (31/07) | Descriptions « méta » un tiers du temps. |
| Injecter les noms dans le prompt | **REJETÉ** (31/07) | Ignoré 84 % du temps, coût ×2,6. Le LLM décrit, il n'affirme pas l'identité. |
| **Re-passe complète de tagging (~50 h GPU)** | **CLOSE** (16/08, `docs/PROTOCOLE_3B_TAGGING.md`) | 147 paires en aveugle : V2CTX préféré **63,9 %** mais **hallucinations doublées** et **59,0 % hors des 30 pièges**, sous le seuil. Le critère est un ET. |
| V2CTX (prompt de PROD) hallucine plus que V0 | **OUVERT** (16/08) | Le banc mesurait la re-passe ; il a mesuré le prompt EN PROD. Adopté sur un 25-15, il double les hallucinations : chaque photo taguée le paie. **Pas de retour à V0 sans protocole.** |
| Faits en contexte pour DOCUMENTS/reçus/captures | **HYPOTHÈSE** (16/08) | Strate « piège » : **83 %**, la seule qui passe — mais POST-HOC sur 30 photos. |
| Modèle de tagging plus GROS | **PARQUÉ** (16/08) | Plafond DUR (4 Go partagés) ; et le banc 3b a montré que les faits en contexte n'achètent pas la description. |

## Renommage

| Idée / piste | Verdict | Raison |
|---|---|---|
| Appliquer les 7 058 renommages | **FAIT** (17/08) | 36 lots, **0 sauté**, undo complet, noms intacts, plan régénéré à **0 nom brut**. |
| Chercher le mécanisme des −250 sans instrument | **REJETÉ → instrument OBSERVÉ** (18/08) | Rien n'était perdu, et rien ne comptait : `comptes_index.py` compte au GOULOT (`TrackedDict`). **Contrôle positif en réel** : +1 puis −1, `inexpliqué` 0 ; 12 cycles au repos à 0. S'il revient, le registre rendra le chiffre. |
| Le repli sur le NOM est gardé comme `taken` | **CORRIGÉ** (19/08) | Le numériseur écrit l'instant du scan dans `DateTimeOriginal` **et** dans le nom : le garde-fou du 17/08 ne fermait qu'une porte sur deux. **73** noms refusés = **1** vraie date de scan + **72** faux futurs, **0 nom brut** — le geste ferme une porte sans déplacer un fichier. |
| Le plan revient sur ce qu'il a renommé | **CORRIGÉ, OBSERVÉ** (19/08) | `est_nom_annee_seule` rend au plan les `YYYY0000_` qu'il a écrits, **seulement si la date est devenue précise**. **15** moves appliqués : 0 scan réinscrit, noms intacts, plan régénéré à **0**. **376** attendent une date. |

## Lieux · recherche (chantier 14a)

| Idée / piste | Verdict | Raison |
|---|---|---|
| Nommer les lieux au SEUL gazetteer `cities1000` | **CORRIGÉ** (14/08) | Il s'arrête à 1 000 hab. : le domicile (1 257 photos) sortait « Bussigny ». `lieux_locaux.txt` : locaux prioritaires + alias. |
| API de géocodage cloud (TomTom, OSM…) | **REJETÉ** | Vie privée du GPS familial ; clé/quota/réseau au démarrage. Gazetteer LOCAL. |
| Chercher un lieu dans le SEUL chemin | **CORRIGÉ** (15/08) | 6 595 photos ont un `gps_place` que leur dossier ignore. Chemin **OU** géocodé : Lausanne 120 → 1 031. |
| `_best_time` comme source d'année d'un filtre | **REJETÉ** (15/08) | Il retombe sur `mtime` : le tagging de 2026 a réécrit une photo de 1998. Source dédiée : précise, sinon DOSSIER, jamais `mtime`. |
| Une précision de date unique pour tous les filtres | **REJETÉ** (15/08) | Exiger le jour partout cache 3 824 photos ; l'accepter partout invente un mois. |
| Filtrer sans dire combien on écarte | **REJETÉ** (15/08) | « 3 photos » se lit « il n'y en a que 3 ». `sans_date` compté et affiché. |
| Laisser les vecteurs des photos sorties de l'index | **TRAITÉ** (17/08) | 2 374 purgés, quarantaine réversible. Puis **0 muet sur 1 600 résultats** (2,6 % avant). |
| Le `mtime` comme date de repli pour CLASSER | **CORRIGÉ, OBSERVÉ** (19/08) | Le filtre le refusait depuis le 15/08 ; le tri le gardait — recherche, `/files?q=` et galerie. Sur copie : **259** photos sans date sûre, **257** datées de 2026 par leur propre tagging, en tête de **56 des 364 noms**. **32** sans même un `mtime` : l'ancien tri **ne s'exécutait pas** sur l'index entier (TypeError → 500). Une seule règle partout, sans-date en FIN et COMPTÉES. En réel : `sans_date_tri` = 53 · 43 · 29 · 29 · 21, au chiffre près la mesure. Détail : git. |
| La page `/files?q=` se taisait | **CORRIGÉ, OBSERVÉ** (19/08) | `/api/search` disait ce qu'il avait compris et écarté ; la page du champ d'accueil, non. Même producteur (`detail`), une fabrique de libellé. |
| « Fichier absent » comme seul critère de purge | **CORRIGÉ** (17/08) | « Le fichier existe » ne dit pas « il sera re-tagué » : 91 photos vivaient hors de toute racine scannée. Règle du scan répliquée dans `sera_re_tague()`. |

## Dates de prise de vue

| Idée / piste | Verdict | Raison |
|---|---|---|
| Aplatir DateTimeOriginal/CreateDate/ModifyDate en `min()` | **REJETÉ** (13/08) | `ModifyDate` est souvent la date du SCAN : un 1995 numérisé partait en 2005. Cru **seulement** si son année est dans le CHEMIN. |
| Corriger les dates d'un nom de fichier de SCAN | **REJETÉ** (14/08) | 4,0 % contredisent le chemin, mais 139 réveillons et 914 à un an sont légitimes ; les 215 à ≥ 4 ans en sont inséparables. |
| Plancher 1990 des années lues dans un CHEMIN | **CORRIGÉ → 1900** (14/08) | « 1985 » ne rendait aucune année : `_best_time` tombait sur `mtime`. Observé : 716 rendues. |
| Les deux planchers 1990 restants (`_fname_time`, `meme_jour.ANNEE_MIN`) | **PARKÉ chiffré** (15/08) | 0 et 7 photos, **couplés** — détail dans les Résiduels du ROADMAP. |
| `_path_years` lisait le NOM DE FICHIER | **CORRIGÉ** (14/08) | `119-1908_IMG.JPG` sous un dossier 2002 : `min()` reculait 38 photos de 94 ans. |
| `DateTimeOriginal` cru sans condition au RENOMMAGE | **CORRIGÉ** (17/08) | Un scanner qui le remplit passe `date_fiable` : 12 photos de « Photos Papa » recevaient un nom en 2007. `date_de_scan_presumee` : une date précise POSTÉRIEURE de plus d'un an à TOUTES les années du dossier n'est pas crue → `YYYY0000`. Observé : 12 → 0. |
| Le garde-fou est SYMÉTRIQUE | **REJETÉ, le chiffre a grandi** (17/08) | Une date ANTÉRIEURE au dossier est l'EXIF qui corrige un dossier d'import : **1 369** en base. Symétrique, il les aurait détruites pour en sauver 72. |
| Portée des dates de SCAN en base | **MESURÉE : 72** (17/08) | Sur COPIE, confirmé sur le serveur vivant : **72**, presque toutes dans « Photos Papa », +2 à +32 ans. Angles morts : 6 818 sans année de dossier, 10 226 sans `taken`. |
| Corriger `taken` en BASE | **NON DÉCIDÉ** (17/08) | Mesure faite, correction non : backfill du pipeline de dates pour 72 photos, face à 1 369 antérieures à ne pas emporter. Les deux gestes moins chers sont faits (19/08). |
| Écrire `None` pour tout un lot ExifTool | **REJETÉ** (13/08) | Un lot raté (NAS muet) est indiscernable d'un lot vide : on n'écrit que pour les fichiers dont ExifTool a PARLÉ. |
| Plafond 2100 de la date lue dans un NOM | **PARKÉ chiffré** (19/08) | `22082010141.jpg` se lit « 2082 » : **72** en base, **coût 0** — seulement parce qu'elles ont un `taken`. |

> **Méthode : `eval/METHODE.md`.** Ici *ce qui a été tranché* ; là *comment on
> tranche*. Les deux se lisent en début de session.
