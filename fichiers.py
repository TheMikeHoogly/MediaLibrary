#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operations de fichiers sures pour la vue Dossiers (/browse) : renommer,
deplacer, creer un dossier, supprimer (quarantaine reversible), annuler.

Ce module est PUR et testable hors serveur : il ne connait ni STORE ni la vraie
base. La re-cle de l'index est INJECTEE (callback `rekey`) : dans le serveur
c'est `rekey_everywhere` ; en test, un espion. Il fournit le confinement de
chemin, la derivation de cle (meme convention que `scan_uploads`), la
quarantaine reversible (JAMAIS de `rm`) et un journal d'annulation.

Invariants (voir CLAUDE.md / monolith-surgery) :
  - Aucun nom humain perdu : tout deplacement/renommage re-cle l'index via le
    callback (tags + visages/personnes/animaux/chats + vecteur semantique). La
    cle EXACTE stockee est retrouvee par lookup NORMALISE (robuste au format
    backslash/slash/casse), jamais reconstruite a l'aveugle.
  - Jamais de suppression definitive : « supprimer » = deplacer vers
    `.corbeille-rangement/` (reversible), comme appliquer_plan.py.
  - Confinement strict aux racines : ni « .. », ni echappement hors racine.

Convention de cle (identique a scan_uploads, a NE PAS diverger) :
  - fichier a la RACINE d'Uploads          -> nom simple (« photo.jpg »)
  - fichier dans un SOUS-DOSSIER d'Uploads  -> relatif posix (« Album/x.jpg »)
  - fichier d'un dossier NAS supplementaire -> chemin absolu str() (backslashes)
"""

import json
import re
import shutil
import time
from pathlib import Path


class FileOpError(Exception):
    """Erreur d'operation previsible (message montrable a l'utilisateur)."""


class FileOpRefus(FileOpError):
    """Le geste est REFUSE a cet utilisateur (chantier 17, etape 5) : `code`
    HTTP a rendre — 403 sur une photo partagee qui n'est pas a lui, 404 sur
    une photo qu'il ne voit pas (dire « interdit » dirait « ca existe »)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = int(code)


def norm(p):
    """Cle de correspondance insensible au separateur et a la casse.
    Miroir EXACT de server._pkey : Path(p).as_posix().lower()."""
    return Path(p).as_posix().lower()


def sanitize_name(name):
    """Nom de fichier/dossier sur : un seul composant, sans separateur, sans
    « .. », sans caractere interdit Windows ni caractere de controle."""
    raw = (name or '').strip().replace('\\', '/')
    raw = raw.split('/')[-1]                       # jamais de chemin
    if raw in ('', '.', '..'):
        raise FileOpError('Nom invalide.')
    cleaned = re.sub(r'[<>:"|?*\x00-\x1f]', '_', raw).rstrip(' .')
    if not cleaned or cleaned in ('.', '..'):
        raise FileOpError('Nom invalide.')
    return cleaned


def resolve_target(roots, idx, rel):
    """(root, target) confines. `roots` = [(label, Path), ...] (media_roots()).
    Rejette un index hors bornes, un « .. » ou tout echappement hors racine."""
    try:
        root = Path(roots[int(idx)][1]).resolve()
    except (IndexError, ValueError, TypeError):
        raise FileOpError('Racine inconnue.')
    rel = (rel or '').replace('\\', '/').strip('/')
    parts = [seg for seg in rel.split('/') if seg not in ('', '.')]
    if any(seg == '..' for seg in parts):
        raise FileOpError('Chemin invalide.')
    target = (root.joinpath(*parts)).resolve() if parts else root
    if target != root and root not in target.parents:
        raise FileOpError('Cible hors de la racine.')
    return root, target


def key_for_new_path(upload_dir, root, abspath):
    """Cle que le scan attribuerait a `abspath` sous `root` (meme convention que
    scan_uploads : nom simple / relatif posix sous Uploads, chemin absolu sinon)."""
    upload_dir = Path(upload_dir).resolve()
    root = Path(root).resolve()
    abspath = Path(abspath)
    if norm(root) == norm(upload_dir):
        try:
            rel = abspath.resolve().relative_to(upload_dir)
        except ValueError:
            return abspath.name
        return abspath.name if len(rel.parts) == 1 else rel.as_posix()
    return str(abspath)


def build_key_index(store_keys, resolve_key):
    """{chemin_normalise: cle_stockee} pour retrouver la cle EXACTE d'un fichier.
    `store_keys` : iterable des cles du STORE. `resolve_key` : cle -> chemin
    absolu (server._resolve_key)."""
    index = {}
    for k in store_keys:
        try:
            index[norm(resolve_key(k))] = k
        except Exception:
            pass
    return index


class FileOps:
    """Orchestre les operations sur le systeme de fichiers + la re-cle de l'index.

    Dependances injectees :
      roots_fn()      -> [(label, Path)]           (server.media_roots)
      resolve_key(k)  -> Path absolu               (server._resolve_key)
      store_keys()    -> iterable des cles STORE   (lambda: list(STORE.data))
      rekey(old,new,mtime=None) -> bool            (server.rekey_everywhere)
      journal_path : Path du journal JSON d'annulation
      trash_dir    : Path de .corbeille-rangement/ (creee au besoin)
      garde(abs)   -> None | (code, message)   (etape 5 : l'utilisateur courant
                      peut-il toucher ce chemin ? None = permis ; facultatif,
                      sans garde tout est permis, comme avant)

    Le garde est UN goulot : chaque geste le consulte sur le chemin absolu
    qu'il va toucher (source, et destination pour deplacer/creer) AVANT de
    toucher au disque ; `undo` le consulte sur le journal AVANT de le depiler
    — une annulation refusee ne perd pas l'entree.
    """

    def __init__(self, roots_fn, resolve_key, store_keys, rekey,
                 journal_path, trash_dir, garde=None):
        self.roots_fn = roots_fn
        self.resolve_key = resolve_key
        self.store_keys = store_keys
        self.rekey = rekey
        self.journal_path = Path(journal_path)
        self.trash_dir = Path(trash_dir)
        self.garde = garde

    def _permis(self, *chemins):
        """Leve FileOpRefus si l'utilisateur courant n'a pas la main sur l'un
        des chemins (le premier refus parle)."""
        if self.garde is None:
            return
        for c in chemins:
            verdict = self.garde(str(c))
            if verdict:
                code, message = verdict
                raise FileOpRefus(code, message)

    # ----- journal d'annulation -----
    def _load_journal(self):
        try:
            return json.loads(self.journal_path.read_text(encoding='utf-8'))
        except Exception:
            return []

    def _append(self, rec):
        j = self._load_journal()
        j.append(rec)
        tmp = self.journal_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(j, ensure_ascii=False, indent=1),
                       encoding='utf-8')
        tmp.replace(self.journal_path)

    def _pop(self):
        j = self._load_journal()
        if not j:
            return None
        rec = j.pop()
        tmp = self.journal_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(j, ensure_ascii=False, indent=1),
                       encoding='utf-8')
        tmp.replace(self.journal_path)
        return rec

    # ----- re-cle d'un fichier ou d'un arbre -----
    def _affected(self, src_abs):
        """[(cle_stockee, chemin_absolu)] pour src_abs (fichier) ou tout son
        arbre (dossier). Utilise l'index normalise (une passe sur le STORE)."""
        index = build_key_index(self.store_keys(), self.resolve_key)
        s = norm(src_abs)
        out = []
        if Path(src_abs).is_dir():
            pref = s.rstrip('/') + '/'
            for nk, k in index.items():
                if nk.startswith(pref):
                    out.append((k, self.resolve_key(k)))
        else:
            k = index.get(s)
            if k is not None:
                out.append((k, self.resolve_key(k)))
        return out

    def _rekey_tree(self, affected, src_abs, dst_abs, dst_root, upload_dir):
        """Re-cle chaque fichier affecte : traduit son chemin src->dst puis
        appelle rekey(old, new). Renvoie la liste [old, new] pour l'annulation."""
        src_abs, dst_abs = Path(src_abs), Path(dst_abs)
        pairs = []
        for old_key, old_path in affected:
            old_path = Path(old_path)
            if norm(old_path) == norm(src_abs):
                new_path = dst_abs                       # le fichier lui-meme
            else:
                rel = old_path.relative_to(src_abs)      # sous un dossier deplace
                new_path = dst_abs / rel
            new_key = key_for_new_path(upload_dir, dst_root, new_path)
            if old_key != new_key:
                try:
                    self.rekey(old_key, new_key)
                except Exception as e:
                    raise FileOpError(f"Re-cle de l'index echouee : {e}")
            pairs.append([old_key, new_key])
        return pairs

    # ----- operations -----
    def rename(self, idx, rel, new_name, upload_dir):
        roots = self.roots_fn()
        root, src = resolve_target(roots, idx, rel)
        if src == root:
            raise FileOpError('On ne renomme pas la racine.')
        self._permis(src)
        if not src.exists():
            raise FileOpError('Fichier introuvable.')
        dst = src.with_name(sanitize_name(new_name))
        if norm(dst) == norm(src):
            return {'op': 'rename', 'changed': False}
        if dst.exists():
            raise FileOpError('Un element porte deja ce nom.')
        affected = self._affected(src)
        shutil.move(str(src), str(dst))
        pairs = self._rekey_tree(affected, src, dst, root, upload_dir)
        rec = {'op': 'rename', 'src': str(src), 'dst': str(dst),
               'idx': int(idx), 'keys': pairs, 'ts': time.time()}
        self._append(rec)
        return {'op': 'rename', 'changed': True, 'dst_name': dst.name,
                'rekeyed': len(pairs)}

    def move(self, idx, rel, dst_idx, dst_rel, upload_dir):
        roots = self.roots_fn()
        root, src = resolve_target(roots, idx, rel)
        droot, ddir = resolve_target(roots, dst_idx, dst_rel)
        if src == root:
            raise FileOpError('On ne deplace pas la racine.')
        self._permis(src, ddir / src.name)
        if not src.exists():
            raise FileOpError('Fichier introuvable.')
        if not ddir.is_dir():
            raise FileOpError('Destination invalide.')
        if norm(ddir) == norm(src.parent):
            return {'op': 'move', 'changed': False}
        if Path(src).is_dir() and norm(ddir).startswith(norm(src).rstrip('/') + '/'):
            raise FileOpError('On ne deplace pas un dossier dans lui-meme.')
        dst = ddir / src.name
        if dst.exists():
            raise FileOpError('La destination contient deja cet element.')
        affected = self._affected(src)
        shutil.move(str(src), str(dst))
        pairs = self._rekey_tree(affected, src, dst, droot, upload_dir)
        rec = {'op': 'move', 'src': str(src), 'dst': str(dst),
               'idx': int(idx), 'dst_idx': int(dst_idx), 'keys': pairs,
               'ts': time.time()}
        self._append(rec)
        return {'op': 'move', 'changed': True, 'rekeyed': len(pairs)}

    def mkdir(self, idx, rel, name):
        roots = self.roots_fn()
        root, parent = resolve_target(roots, idx, rel)
        new = parent / sanitize_name(name)
        self._permis(new)
        if not parent.is_dir():
            raise FileOpError('Dossier parent invalide.')
        if new.exists():
            raise FileOpError('Ce dossier existe deja.')
        new.mkdir(parents=False)
        # Pas de re-cle : un dossier vide n'a aucune entree d'index.
        self._append({'op': 'mkdir', 'dir': str(new), 'ts': time.time()})
        return {'op': 'mkdir', 'name': new.name}

    def delete(self, idx, rel, upload_dir):
        """Supprime = deplace vers .corbeille-rangement/<horodatage>/<nom>.
        JAMAIS de rm. Reversible (les cles suivent vers la corbeille)."""
        roots = self.roots_fn()
        root, src = resolve_target(roots, idx, rel)
        if src == root:
            raise FileOpError('On ne supprime pas la racine.')
        self._permis(src)
        if not src.exists():
            raise FileOpError('Fichier introuvable.')
        stamp = time.strftime('%Y%m%d-%H%M%S') + f"-{int(time.time() * 1000) % 1000:03d}"
        bucket = self.trash_dir / stamp
        bucket.mkdir(parents=True, exist_ok=True)
        dst = bucket / src.name
        affected = self._affected(src)
        shutil.move(str(src), str(dst))
        # re-cle vers la corbeille (dst_root = corbeille : cle = chemin absolu)
        pairs = self._rekey_tree(affected, src, dst, self.trash_dir, upload_dir)
        rec = {'op': 'delete', 'src': str(src), 'dst': str(dst),
               'idx': int(idx), 'keys': pairs, 'ts': time.time()}
        self._append(rec)
        return {'op': 'delete', 'name': src.name, 'rekeyed': len(pairs),
                'trash': str(dst)}

    def undo(self, upload_dir):
        """Annule la derniere operation (deplace en sens inverse + re-cle).
        Le garde est consulte sur le journal AVANT de le depiler : un refus
        laisse l'entree a celui qui a la main (l'auteur du geste, ou l'admin)."""
        j = self._load_journal()
        rec = j[-1] if j else None
        if not rec:
            raise FileOpError('Rien a annuler.')
        if rec.get('op') == 'mkdir':
            self._permis(rec['dir'])
        elif rec.get('op') == 'delete':
            self._permis(rec['src'])          # `dst` est la corbeille : a personne
        else:
            self._permis(rec['src'], rec['dst'])
        rec = self._pop()
        op = rec.get('op')
        if op == 'mkdir':
            d = Path(rec['dir'])
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                raise FileOpError('Dossier non vide : suppression annulee.')
            return {'undone': 'mkdir', 'name': d.name}
        # rename / move / delete : remettre dst -> src, re-cle new -> old
        src, dst = Path(rec['src']), Path(rec['dst'])
        if not dst.exists():
            raise FileOpError('Element deja deplace ailleurs : annulation refusee.')
        if src.exists():
            raise FileOpError('La source existe de nouveau : annulation refusee.')
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        for old_key, new_key in rec.get('keys', []):
            if old_key != new_key:
                try:
                    self.rekey(new_key, old_key)
                except Exception as e:
                    raise FileOpError(f"Re-cle d'annulation echouee : {e}")
        return {'undone': op, 'name': src.name, 'rekeyed': len(rec.get('keys', []))}
