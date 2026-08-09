# Direction tagging — vers une base de connaissances multimodale

Cap : **orchestration > modèle**. Réduire le rôle du LLM (lent, coûteux, hallucine) :
lui donner ce que les autres modèles (SigLIP, InsightFace, DINOv2, YOLO, NAS, XMP) ont
compris, **pas les pixels**. LLM = moteur de raisonnement, pas de vision. Rien ne se
bâtit avant mesure.

## Séquencement
1. Mesurer `assertions vs pixels` (`eval/PLAN_assertions_vs_pixels.md`, `eval_tagging.py`) :
   assertions seules vs assertions+image vs image seule. Pari : l'hybride gagne
   (déjà préféré 2 contre 1 en notation humaine — cf. `DECISIONS.md`).
2. Selon le verdict : couche d'assertions **à provenance** (valeur + confiance + source +
   confirmé_humain). Généralise le Knowledge Builder ; protège la vérité humaine (0,8 %)
   de la circularité par auto-attribution.
3. Puis : cache de raisonnement (pendant des versions de pipeline), versionnement des
   corrections (ex. Luna→Inti), à terme mémoire globale interrogeable.

## Points de vigilance
- Scene Graph : porter la provenance **dès le jour 1**, sinon ré-import de la circularité.
- Modèle : mesurer le pic VRAM (4 Go partagés + Ollama `keep_alive 30m` ; `qwen3-vl:4b`
  déjà rejeté pour débordement). Si le LLM devient texte-only, un petit LLM texte libère
  la VRAM (au prix de l'« attrape-tout » du VLM).
