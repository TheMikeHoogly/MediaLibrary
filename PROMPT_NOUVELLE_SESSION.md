# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

> ⚠ **NE REDÉMARRE PAS LE SERVEUR tant que `/api/maint/status` →
> `queues.personnes` n'est pas à 0.** La fusion Flo → Florine y a laissé
> ~11 800 écritures XMP, et la file n'existe QU'EN MÉMOIRE : un redémarrage la
> jette sans trace, et des milliers de photos garderaient `personne:Flo` dans
> leurs métadonnées alors que l'index dit `Florine` — c'est ainsi que naît un
> nom fantôme. **Débit réel mesuré : 0,28 op/s, soit ~11 h** (départ 08:31 le
> 23/08 ; la ROADMAP de la session 39 annonçait 0,95 op/s, c'était faux). La
> file est vide ? Alors le protocole normal reprend.

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (23/08/2026, fin de session 40)

**La fusion Flo → Florine est FAITE et VÉRIFIÉE** (23/08, 08:31) : un seul nom,
`Florine`, 5 909 photos, plus aucun `Flo` ; règle 2 tenue (143 → 143
confirmations, 1 215 → 1 215 exclusions, 84 → 84 visages) ; un seul journal,
`fusion_20260823_083124.jsonl`, annulable. **Avant d'annuler, savoir que 5 724
des 5 725 photos portaient DÉJÀ `Florine`** (séquelle de la passe morte du 22) :
annuler rendrait `Flo` sans retirer `Florine`.

**La question ouverte de la 39 est répondue : personne ne met de verrou dans une
fiche — la fiche EST le verrou.** Une fiche vivante est un `TrackedEntry`
(sous-classe de `dict` avec `__slots__`), et `deepcopy` d'une sous-classe de
dict copie aussi l'état d'instance : il suit `_store` jusqu'au `SqliteStore` et
bute sur son `lock`, un RLock délibéré. Donc **toute fiche de tout index** était
indeepcopyable, et **la ligne console de `_fiche_pour_journal` ne nommera jamais
rien**. Parade livrée : `__deepcopy__`/`__copy__`/`__reduce__` sur
`TrackedEntry` et `TrackedDict` rendent un **dict nu**. 4 rouges sur l'ancien
code, 52/52 sur le nouveau — dont une vérification qui deepcopy le store
lui-même, pour que le test ne soit pas vide.

**Deux branches livrées en `commit` avec `force=`, `main` intacte** :
`fix/la-fiche-est-le-verrou` et `feat/ce-que-la-file-xmp-doit-encore`. Le
contrôle 5 exige un serveur démarré APRÈS le fichier, et redémarrer aurait jeté
la file XMP ; les tests, eux, ont tourné au BANC sous Windows — 52/52 et 29/29.
**À la fin de la file : redémarrer, observer, puis fusionner ces deux
branches.**

> Le contrôle 5 de l'agent git traite tout `.py` hors `test_`/`mesure_` comme du
> code de serveur — donc aussi les bancs `verifier_*`, que le serveur n'importe
> jamais. L'en-tête de `git_agent.py` assume ce faux positif (« le redémarrage
> coûte douze secondes »). Aujourd'hui il coûtait onze heures : **à rouvrir avec
> Mike, pas à trancher seul.**

## Prochain pas

1. **La MOITIÉ manquante de la réparation.** Mesurer l'écart est fait
   (`verifier_xmp_personnes.py`, 29 tests, tourné au banc : 19 photos sur 200
   portent `Florine` dans leur fichier, 119 portent encore `Flo`). Le REFAIRE
   reste : soit un `appliquer_xmp_personnes.py` (geste de Mike, jamais de
   l'agent), soit une route qui remet en file les clés du `--json`. **Ne jamais
   écrire pendant que `person_writer` tourne** : deux écrivains sur les mêmes
   fichiers, c'est la bagarre du 22/08 en pire.
2. **Accélérer l'écriture XMP** : un processus exiftool par opération, en série,
   ~3,5 s par tag. Grouper le `-Ancien` et le `+Nouveau` d'une même photo en UNE
   invocation (÷2), puis le mode `-stay_open`. Touche `server.py`.
3. **Copie HORS SITE (12 bis)** — le seul manque qui reste à l'assurance-vie ;
   demande une décision de Mike avant du code.
4. **Suite de `ui/`** : le CSS commun (chaque page porte encore son `<style>`)
   puis le redesign — deux chantiers SÉPARÉS, exprès (`photo-ui`).
5. **Reste d'audit** : O7–O9, O11–O15 ; **I1** est VISIBLE dans `/reglages`
   (`tours: visages 0, animaux 0`). **MCP lecture seule (13)** : recherche,
   fiches et `faits` en outils MCP locaux (skill `mcp-builder`).

**Rien n'attend Mike dans `QUESTIONS_MIKE.md`.**
