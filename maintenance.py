#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrateur de MAINTENANCE des medias — nettoyage, dedoublonnage, purge,
renommage, rangement — en UN endroit, cadence par etape, reversible.

PHILOSOPHIE. Un seul cycle `run_cycle(sv)` que le SERVEUR appelle en boucle (un
thread de fond, il tourne donc « tout seul quand le serveur tourne »). Chaque
etape a sa propre cadence (`intervals`) et son niveau d'autonomie (`autonomy`) :
  - `auto`    : executee automatiquement quand elle est due ;
  - `propose` : preparee (plan/rapport) mais PAS appliquee — attend un feu vert ;
  - `off`     : desactivee.
Reglage par defaut (choix de Mike) : AUTO pour le sur et reversible (purge,
dedoublonnage exact), PROPOSE pour le gros (rangement par annee).

CONCURRENCE — la regle qui gouverne le decoupage :
  - Les etapes LECTURE SEULE (recensement, plan) tournent en SOUS-PROCESSUS :
    elles ne touchent pas l'index en ecriture, donc aucun conflit avec le serveur.
  - Les etapes qui MUTENT l'index (dedoublonnage) tournent DANS le processus
    serveur, via `sv.rekey` (= `rekey_everywhere`) et `sv.tags*` : elles partagent
    le cache memoire du serveur, donc pas d'ecrivain concurrent ni de cache
    perime (le piege qui obligeait a arreter le serveur pour `appliquer_plan`).
  - La purge est FS-only (ne touche pas l'index).
Tout ce qui est lourd cede a l'UI : si `sv.is_busy()`, on ne lance pas les etapes
lourdes ce tour-ci.

INTEGRATION. Le serveur fournit un objet `sv` (shim) exposant : paths, autonomy,
intervals, rekey(old,new), tags_get/tags_set/tags_save, is_busy(), log(msg),
run_readonly(args), dry. `make_standalone_sv()` en fournit une version autonome
(serveur ARRETE) pour le lanceur `25 - Maintenance.bat` / un one-shot.

Rien n'est jamais supprime sans reversibilite : le dedoublonnage passe par la
quarantaine (journal undo), la purge respecte le delai de 30 j et le filet
« canonique presente » (voir purger_corbeille).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
DOCS = RACINE / "docs"

# Cadence par defaut (secondes)
JOUR = 86400
INTERVALS = {
    'purge': JOUR,
    'dedup': JOUR,
    'recensement': 7 * JOUR,
    'rename': JOUR,
    'rangement': 7 * JOUR,
}
AUTONOMY = {
    'purge': 'auto',
    'dedup': 'auto',
    # recensement est LECTURE SEULE mais LOURD (~4 h de hash NAS) : par defaut on
    # ne le lance pas tout seul (surprise NAS). Mets 'auto' dans la config si tu
    # veux un recensement hebdomadaire automatique quand la machine est au repos.
    'recensement': 'propose',
    'rename': 'propose',         # application pas encore branchee
    'rangement': 'propose',      # gros deplacements : feu vert humain
}
# Etapes lourdes : sautees si l'UI est active (priorite UI)
LOURDES = {'recensement', 'dedup'}
ORDRE = ['recensement', 'dedup', 'purge', 'rename', 'rangement']


# ── etat / cadence ────────────────────────────────────────────────────────────

def _load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_state(path, state):
    try:
        Path(path).write_text(json.dumps(state, ensure_ascii=False, indent=1),
                              encoding='utf-8')
    except OSError:
        pass


def due(step, state, now, intervals):
    last = state.get(step, 0)
    return (now - last) >= intervals.get(step, JOUR)


# ── dedoublonnage : appliquer les quarantaines EN ATTENTE d'un plan ──────────

def _sha256_resilient(path, buf=1 << 16, tries=3, pause=0.4):
    import hashlib
    last = None
    for attempt in range(tries):
        h = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                while True:
                    b = f.read(buf)
                    if not b:
                        break
                    h.update(b)
            return h.hexdigest()
        except OSError as e:
            last = e
            if attempt + 1 < tries:
                time.sleep(pause * (attempt + 1))
    raise last


def apply_pending_dedup(sv):
    """Applique les operations `quarantine` du plan dont la SOURCE existe encore
    (donc pas deja traitee). In-process : mute l'index via `sv.rekey`. Reversible
    (journal undo). Renvoie un compte."""
    import shutil
    plan_path = Path(sv.paths['plan'])
    if not plan_path.exists():
        sv.log("dedup : pas de plan_rangement.json — rien a appliquer")
        return {'ok': 0, 'skip': 0, 'absent': 0}
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    qs = [o for o in plan.get('operations', []) if o['type'] == 'quarantine']
    journal = {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
               'source': 'maintenance', 'operations': []}
    c = {'ok': 0, 'skip': 0, 'absent': 0}
    for op in qs:
        src, dst = Path(op['src']), Path(op['dst'])
        canon = Path(op['preuve']['canonique'])
        if not src.exists():
            c['absent'] += 1                      # deja quarantine lors d'un run precedent
            continue
        if sv.is_busy():
            sv.log("dedup : UI active, on s'arrete la (repris au prochain tour)")
            break
        if not canon.exists() or dst.exists():
            c['skip'] += 1
            continue
        try:
            if _sha256_resilient(src) != op['preuve']['sha256'] \
               or _sha256_resilient(canon) != op['preuve']['sha256']:
                c['skip'] += 1
                continue
        except OSError:
            c['skip'] += 1
            continue
        if sv.dry:
            c['ok'] += 1
            continue
        # fusion des noms manquants dans la canonique AVANT retrait
        noms = op.get('fusion_noms') or []
        if noms:
            e = sv.tags_get(op['preuve']['canonique'])
            if e is not None:
                kw = list(e.get('kw_fr') or [])
                add = [n for n in noms if n not in kw
                       and n not in (e.get('kw_en') or [])]
                if add:
                    e = dict(e)
                    e['kw_fr'] = kw + add
                    sv.tags_set(op['preuve']['canonique'], e)
        dst.parent.mkdir(parents=True, exist_ok=True)
        (dst.parent / 'manifeste.json').write_text(json.dumps({
            'origine': op['src'], 'canonique': op['preuve']['canonique'],
            'sha256': op['preuve']['sha256'], 'groupe': op['manifeste']['groupe'],
            'date_application': time.strftime('%Y-%m-%d %H:%M:%S')},
            ensure_ascii=False), encoding='utf-8')
        shutil.move(str(src), str(dst))
        sv.rekey(op['src'], op['dst'])
        journal['operations'].append({'src': op['src'], 'dst': op['dst'],
                                      'canonique': op['preuve']['canonique'],
                                      'index_rekey': True})
        c['ok'] += 1
    if not sv.dry and journal['operations']:
        sv.tags_save()
        # 1 sexdecies suite (04/09) : le 7e magasin (gps_places.json) ne suit
        # PAS AP.rekey_stores tout seul -- deplacer_dossiers.py le dit de
        # lui-meme ("Il ignore aussi gps_places.json"). StandaloneSv le
        # transporte desormais (voir rekey/gps_save ci-dessous) ; _MaintSv
        # (le sv du serveur, in-process) n'a pas besoin de ce geste, son
        # rekey() delegue a rekey_everywhere qui sauve gps_places lui-meme --
        # d'ou le hasattr, pour ne rien casser des deux cotes.
        if hasattr(sv, 'gps_save'):
            sv.gps_save()
        jp = DOCS / f"undo_rangement_{time.strftime('%Y%m%d_%H%M%S')}_maint.json"
        jp.write_text(json.dumps(journal, ensure_ascii=False, indent=1),
                      encoding='utf-8')
        sv.log(f"dedup : {c['ok']} quarantaine(s), journal {jp.name}")
    else:
        sv.log(f"dedup : {c}")
    return c


# ── un cycle ──────────────────────────────────────────────────────────────────

def run_cycle(sv, now=None):
    """Execute les etapes DUES, dans l'ordre, selon autonomie et priorite UI.
    Met a jour l'etat et le rapport. Renvoie le resume des etapes lancees."""
    now = now if now is not None else time.time()
    state = _load_state(sv.paths['state'])
    autonomy = sv.autonomy
    intervals = sv.intervals
    lance = {}

    for step in ORDRE:
        mode = autonomy.get(step, 'off')
        if mode == 'off':
            continue
        if not due(step, state, now, intervals):
            continue
        if step in LOURDES and sv.is_busy():
            sv.log(f"{step} : UI active, reporte")
            continue

        if step == 'recensement':
            # lecture seule -> sous-processus (aucun conflit d'index)
            sv.log("recensement + plan (lecture seule)…")
            r1 = sv.run_readonly(['recensement_doublons.py'])
            r2 = sv.run_readonly(['plan_rangement.py']) if r1 == 0 else 1
            lance[step] = {'recensement': r1, 'plan': r2}
        elif step == 'dedup':
            if mode == 'auto':
                lance[step] = apply_pending_dedup(sv)
            else:
                sv.log("dedup : mode propose — plan pret, application non lancee")
                lance[step] = 'propose'
        elif step == 'purge':
            import purger_corbeille as PC
            corb = sv.paths.get('corbeille')
            stats = PC.purge(corb, 30, appliquer=(mode == 'auto' and not sv.dry),
                             verifier_canon=False) if corb else None
            lance[step] = stats
        elif step == 'rename':
            # L'application du renommage _Uploads n'est pas encore branchee ;
            # le coeur (renommage/renommage_facts) et le dry-run existent.
            sv.log("rename _Uploads : preparation seule (application a venir)")
            lance[step] = 'propose'
        elif step == 'rangement':
            sv.log("rangement par annee : PROPOSE (attend inventaire + feu vert)")
            lance[step] = 'propose'

        state[step] = now

    _save_state(sv.paths['state'], state)
    rapport = {'dernier_cycle': time.strftime('%Y-%m-%d %H:%M:%S'),
               'etapes_lancees': lance, 'etat': state}
    try:
        Path(sv.paths['report']).write_text(
            json.dumps(rapport, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass
    return lance


# ── shim autonome (serveur ARRETE) ───────────────────────────────────────────

class StandaloneSv:
    """`sv` pour un one-shot hors serveur : ouvre ses propres stores et re-cle
    via les memes primitives que rekey_everywhere (appliquer_plan)."""

    def __init__(self, db=None, dry=False, autonomy=None, gps=None):
        self.dry = dry
        self.autonomy = dict(AUTONOMY, **(autonomy or {}))
        self.intervals = dict(INTERVALS)
        self.paths = {
            'corbeille': None, 'plan': str(DOCS / 'plan_rangement.json'),
            'recensement': str(DOCS / 'recensement.json'),
            'state': str(DOCS / 'maintenance_state.json'),
            'report': str(DOCS / 'maintenance_report.json'),
            'racine': str(RACINE),
        }
        try:
            plan = json.loads(Path(self.paths['plan']).read_text(encoding='utf-8'))
            self.paths['corbeille'] = plan.get('corbeille')
        except Exception:
            pass
        self._stores = self._sem = None
        self._db = db or str(RACINE / 'photos.db')
        # 1 sexdecies suite (04/09) : le 7e magasin, comme AP.open_stores
        # pour la base -- injectable pour les tests, RACINE/gps_places.json
        # en usage reel (meme defaut qu'appliquer_plan_annee.GPS).
        self._gps_path = gps or str(RACINE / 'gps_places.json')
        self._gps = None
        self._gps_dirty = False

    def _ensure(self):
        if self._stores is None:
            import appliquer_plan as AP
            self._stores, self._sem = AP.open_stores(self._db)
        if self._gps is None:
            import appliquer_plan_annee as APA
            self._gps = APA.charger_gps(self._gps_path)

    def rekey(self, old, new):
        import appliquer_plan as AP
        self._ensure()
        rekeyed = AP.rekey_stores(old, new, self._stores, self._sem)
        if rekeyed:
            import appliquer_plan_annee as APA
            if APA.recler_gps(self._gps, old, new):
                self._gps_dirty = True
        return rekeyed

    def gps_save(self):
        if self._gps_dirty:
            import appliquer_plan_annee as APA
            APA.ecrire_gps(self._gps, self._gps_path)
            self._gps_dirty = False

    def tags_get(self, key):
        self._ensure()
        return self._stores['tags'].data.get(key)

    def tags_set(self, key, entry):
        self._ensure()
        self._stores['tags'].set(key, entry)

    def tags_save(self):
        if self._stores:
            self._stores['tags'].save()

    def is_busy(self):
        return False                       # serveur arrete : rien d'autre n'ecrit

    def log(self, msg):
        line = time.strftime('%H:%M:%S ') + msg
        print("  " + line)
        try:
            with open(DOCS / 'maintenance.log', 'a', encoding='utf-8') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + "\n")
        except OSError:
            pass

    def run_readonly(self, args):
        return subprocess.run([sys.executable] + args, cwd=str(RACINE)).returncode


def make_standalone_sv(dry=False):
    return StandaloneSv(dry=dry)


def main():
    dry = '--dry' in sys.argv
    forcer = '--forcer' in sys.argv
    # 1 sexdecies (03/09, demande de Mike) : ce lanceur MUTE photos.db en
    # ouvrant ses propres stores (StandaloneSv._ensure -> appliquer_plan.
    # open_stores), donc le meme verrou que les autres appliquer_*.py --
    # avant, le bat se contentait de PREVENIR ("serveur suppose ARRETE") et
    # laissait Mike faire confiance a sa propre memoire. Desormais le script
    # le VERIFIE lui-meme (refus_d_ecriture, deja teste et utilise par
    # appliquer_plan_annee.py et consorts) : le dry-run reste toujours permis
    # (rien n'est ecrit), --forcer passe outre a tes risques comme ailleurs.
    import appliquer_plan_annee as APA
    refus = APA.refus_d_ecriture(str(RACINE / 'photos.db'), dry, forcer)
    if refus:
        print(refus)
        return 1
    sv = make_standalone_sv(dry=dry)
    print(f"{'DRY-RUN' if dry else 'MAINTENANCE'} — un cycle "
          "(serveur verifie ARRETE pour les etapes mutantes).")
    lance = run_cycle(sv)
    print("\nEtapes lancees :", json.dumps(lance, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
