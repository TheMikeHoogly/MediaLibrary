#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — la file d'écriture XMP : une invocation par PHOTO, et elle survit.

Pourquoi ce fichier
───────────────────
Le 23/08, la fusion Flo → Florine a mis **11 814 écritures XMP** dans
`PERSON_QUEUE` pour 5 907 photos, à **0,38 op/s** — onze heures. Deux défauts
tenaient ces heures en otage, et ce sont deux défauts distincts :

1. **Le prix était payé deux fois.** `person_writer` lançait un processus
   ExifTool par GESTE. Or renommer une personne en pose deux par photo — retirer
   l'ancien nom, ajouter le nouveau — coup sur coup. Le coût dominant est le
   DÉMARRAGE du processus (~2,6 s sur SMB), pas l'écriture : une invocation par
   photo au lieu d'une par geste divise la facture par deux.
2. **La file n'existait qu'en mémoire.** `queue.Queue()`, sans trace disque. Un
   redémarrage, une coupure, un plantage, et le travail restant partait **sans
   rien pour le retrouver** : des milliers de photos auraient gardé
   `personne:Flo` dans leur fichier quand l'index dit `Florine`. C'est ainsi que
   naît un nom fantôme — et c'est la règle 2 qui tombe.

Ces tests lisent `server.py` **sans l'importer** (`import server` ouvre
`photos.db`, dont le serveur est l'écrivain unique) : les fonctions sont
extraites de l'AST et exécutées avec des faux à nous — faux ExifTool, faux
index, vrais fichiers dans un dossier temporaire.

Chacun a été vu ROUGE sur le code d'avant : sans ça, ils ne prouveraient rien.
"""

import ast
import json
import queue
import os
import threading
import tempfile
import time
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

FONCTIONS = ('write_person_tags', 'write_person_tag', 'write_person_untag',
             '_file_personnes_note', '_file_personnes_faite',
             '_file_personnes_echec', '_file_personnes_reprise',
             '_ecrire_lot_personne', 'person_writer',
             '_enqueue_person_write')


def _fonction(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(
        f"{nom} introuvable dans server.py — si la file d'ecriture a bouge, "
        "ces tests doivent etre RELUS, pas contournes.")


class FauxRetour:
    def __init__(self, code=0):
        self.returncode = code


class Banc:
    """Les fonctions de la prod, branchées sur un faux monde."""

    def __init__(self, dossier, exiftool='exiftool', code=0):
        self.dossier = Path(dossier)
        self.appels = []            # une entrée par invocation ExifTool
        self.code = code
        self.index = {}
        self.espace = {
            '__builtins__': __builtins__,
            'json': json, 'os': os, 'time': time, 'queue': queue,
            'threading': threading, 'Path': Path,
            'EXIFTOOL': exiftool,
            '_run_exiftool': self._exiftool,
            '_stat_of': self._stat,
            '_resolve_key': lambda cle: self.dossier / str(cle),
            'STORE': self,
            'PERSON_QUEUE': queue.Queue(),
            'PERSON_JOURNAL': self.dossier / '_file_personnes.jsonl',
            'PERSON_JOURNAL_POS': self.dossier / '_file_personnes.pos',
            'PERSON_JOURNAL_ECHECS': self.dossier / '_file_personnes_echecs.jsonl',
            'PERSON_JOURNAL_LOCK': threading.Lock(),
            'PERSON_SEQ': 0,
            'PERSON_LOT_MAX': 16,
        }
        module = ast.Module(body=[_fonction(n) for n in FONCTIONS],
                            type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(SERVER), 'exec'), self.espace)

    # — le faux monde —
    @property
    def data(self):
        return self.index

    def _exiftool(self, args, timeout=180):
        self.appels.append(list(args))
        return FauxRetour(self.code)

    def _stat(self, p):
        try:
            st = Path(p).stat()
            return int(st.st_size), int(st.st_mtime)
        except OSError:
            return None, None

    # — raccourcis —
    def __getitem__(self, nom):
        return self.espace[nom]

    @property
    def file(self):
        return self.espace['PERSON_QUEUE']

    def photo(self, nom):
        p = self.dossier / nom
        p.write_bytes(b'jpeg')
        return p

    def ecrivain(self):
        t = threading.Thread(target=self.espace['person_writer'], daemon=True)
        t.start()
        return t

    def journal(self, fichier='_file_personnes.jsonl'):
        p = self.dossier / fichier
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()
                if l.strip()]


class BancTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.b = Banc(self.tmp)

    def _attendre(self, n=1):
        """La file est vidée ? On ne dort pas au hasard : `join()` rend la main
        quand chaque geste a été compté fait."""
        fini = threading.Event()
        threading.Thread(target=lambda: (self.b.file.join(), fini.set()),
                         daemon=True).start()
        self.assertTrue(fini.wait(10), "la file n'a pas ete videe")


# ═════════════════════════ 1. Une invocation par PHOTO ═══════════════════════

class UneInvocationParPhoto(BancTest):

    def test_les_deux_gestes_d_un_renommage_partent_ENSEMBLE(self):
        """Le cœur du gain : `del ancien` + `add nouveau` sur la même photo,
        posés coup sur coup par `rename`, ne doivent coûter qu'UN processus."""
        p = self.b.photo('a.jpg')
        self.b.ecrivain()
        self.b.file.put((p, 'personne:Flo', 'del', 'a.jpg', 1))
        self.b.file.put((p, 'personne:Florine', 'add', 'a.jpg', 2))
        self._attendre()
        self.assertEqual(len(self.b.appels), 1,
                         "deux processus ExifTool pour une seule photo : "
                         "c'est la facture payee deux fois")

    def test_deux_photos_ne_se_melangent_JAMAIS(self):
        """Le garde-fou du groupement : grouper deux photos écrirait le tag de
        l'une dans le fichier de l'autre."""
        a, b = self.b.photo('a.jpg'), self.b.photo('b.jpg')
        self.b.ecrivain()
        self.b.file.put((a, 'personne:Flo', 'del', 'a.jpg', 1))
        self.b.file.put((b, 'personne:Flo', 'del', 'b.jpg', 2))
        self._attendre()
        self.assertEqual(len(self.b.appels), 2)
        self.assertEqual(self.b.appels[0][-1], str(a))
        self.assertEqual(self.b.appels[1][-1], str(b))

    def test_un_ajout_fait_moins_puis_plus_et_IPTC_suit_XMP(self):
        """Contrat d'origine conservé : `-=` puis `+=` (pas de doublon si le
        tag est déjà là), et IPTC porte toujours ce que porte XMP."""
        p = self.b.photo('a.jpg')
        self.b['write_person_tags'](p, {'personne:Flo': 'add'})
        args = self.b.appels[0]
        self.assertIn('-XMP-dc:Subject-=personne:Flo', args)
        self.assertIn('-XMP-dc:Subject+=personne:Flo', args)
        self.assertIn('-IPTC:Keywords-=personne:Flo', args)
        self.assertIn('-IPTC:Keywords+=personne:Flo', args)
        self.assertLess(args.index('-XMP-dc:Subject-=personne:Flo'),
                        args.index('-XMP-dc:Subject+=personne:Flo'))

    def test_un_retrait_ne_fait_que_moins(self):
        p = self.b.photo('a.jpg')
        self.b['write_person_tags'](p, {'personne:Flo': 'del'})
        args = self.b.appels[0]
        self.assertIn('-XMP-dc:Subject-=personne:Flo', args)
        self.assertNotIn('-XMP-dc:Subject+=personne:Flo', args)
        self.assertIn('-IPTC:Keywords-=personne:Flo', args)
        self.assertNotIn('-IPTC:Keywords+=personne:Flo', args)

    def test_le_dernier_geste_sur_un_tag_l_emporte(self):
        """Deux appels successifs laissaient le second décider. Groupés, ils
        doivent décider PAREIL — sinon le groupement change le résultat."""
        p = self.b.photo('a.jpg')
        self.b.ecrivain()
        self.b.file.put((p, 'personne:Flo', 'add', 'a.jpg', 1))
        self.b.file.put((p, 'personne:Flo', 'del', 'a.jpg', 2))
        self._attendre()
        args = self.b.appels[0]
        self.assertNotIn('-XMP-dc:Subject+=personne:Flo', args,
                         "le retrait est le dernier mot : l'ajout ne doit pas "
                         "ressusciter le nom")

    def test_le_chemin_reste_le_DERNIER_argument(self):
        """ExifTool prend les options AVANT le fichier : un chemin au milieu et
        la moitié des gestes s'appliquent à rien."""
        p = self.b.photo('a.jpg')
        self.b['write_person_tags'](p, {'personne:A': 'add', 'personne:B': 'del'})
        self.assertEqual(self.b.appels[0][-1], str(p))

    def test_les_deux_anciennes_portes_gardent_leur_contrat(self):
        """`write_person_tag` / `write_person_untag` sont appelées ailleurs :
        elles doivent continuer à faire exactement une chose."""
        p = self.b.photo('a.jpg')
        self.assertTrue(self.b['write_person_tag'](p, 'personne:Flo'))
        self.assertIn('-XMP-dc:Subject+=personne:Flo', self.b.appels[-1])
        self.assertTrue(self.b['write_person_untag'](p, 'personne:Flo'))
        self.assertNotIn('-XMP-dc:Subject+=personne:Flo', self.b.appels[-1])

    def test_le_mtime_de_l_index_est_resynchronise_apres_notre_ecriture(self):
        """Sinon le balayage « fichiers modifiés » re-tague la photo et perd le
        nom : c'est l'invariant que portait déjà `person_writer`."""
        p = self.b.photo('a.jpg')
        self.b.index['a.jpg'] = {'mtime': 0, 'size': 0}
        self.b.ecrivain()
        self.b.file.put((p, 'personne:Flo', 'add', 'a.jpg', 1))
        self._attendre()
        self.assertGreater(self.b.index['a.jpg']['mtime'], 0)
        self.assertEqual(self.b.index['a.jpg']['size'], 4)


# ═══════════════════ 2. La file survit à l'arrêt ═════════════════════════════

class LaFileSurvit(BancTest):

    def test_le_geste_est_note_AVANT_d_etre_enfile(self):
        """L'ordre est la garantie : noté puis perdu = refait au démarrage (sans
        effet, l'écriture est idempotente) ; enfilé puis perdu = nom fantôme."""
        self.b.photo('a.jpg')
        vus = []
        self.b.file.put = lambda item: vus.append(self.b.journal())
        self.b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        self.assertEqual(len(vus), 1)
        self.assertEqual([d['tag'] for d in vus[0]], ['personne:Flo'],
                         "le journal doit deja porter le geste au moment ou "
                         "il entre en file")

    def test_l_enfilement_porte_un_numero_d_ordre(self):
        self.b.photo('a.jpg')
        self.b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        item = self.b.file.get_nowait()
        self.assertEqual(len(item), 5)
        self.assertEqual(item[4], 1)

    def test_ce_qui_n_est_pas_un_fichier_n_entre_ni_en_file_ni_au_journal(self):
        self.b['_enqueue_person_write']('fantome.jpg', 'personne:Flo', 'add')
        self.assertTrue(self.b.file.empty())
        self.assertEqual(self.b.journal(), [])

    def test_une_file_interrompue_repart_exactement_ou_elle_en_etait(self):
        """Le cas de la fusion : 3 gestes notés, 1 fait, arrêt. Au redémarrage,
        les 2 qui restent doivent revenir — et le premier ne pas être refait."""
        for n in ('a.jpg', 'b.jpg', 'c.jpg'):
            self.b.photo(n)
            self.b['_enqueue_person_write'](n, 'personne:Florine', 'add')
        premier = self.b.file.get_nowait()
        self.b['_file_personnes_faite']([premier])
        self.b.file.task_done()

        neuf = Banc(self.tmp)                     # un serveur qui redémarre
        self.assertEqual(neuf['_file_personnes_reprise'](), 2)
        restes = [neuf.file.get_nowait() for _ in range(2)]
        self.assertEqual([r[3] for r in restes], ['b.jpg', 'c.jpg'])
        self.assertTrue(neuf.file.empty(),
                        "un geste deja fait a ete refait : la position ne sert "
                        "a rien si elle n'est pas lue")

    def test_sans_journal_la_reprise_ne_reinvente_rien(self):
        self.assertEqual(self.b['_file_personnes_reprise'](), 0)

    def test_une_ligne_tronquee_par_la_coupure_ne_fait_pas_tomber_la_reprise(self):
        """Une coupure franche laisse une demi-ligne : c'est exactement le cas
        que la durabilité doit encaisser, pas celui où elle abandonne."""
        self.b.photo('a.jpg')
        self.b.photo('b.jpg')
        self.b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        j = Path(self.tmp) / '_file_personnes.jsonl'
        with open(j, 'a', encoding='utf-8') as f:
            f.write('{"n": 2, "chemin": "b.jp')
        neuf = Banc(self.tmp)
        self.assertEqual(neuf['_file_personnes_reprise'](), 1)

    def test_la_reprise_suit_la_CLE_quand_la_photo_a_ete_rangee_ailleurs(self):
        """Entre l'arrêt et le redémarrage, le rangement par année a pu bouger
        le fichier. La clé est ce qui survit ; le chemin noté, non."""
        self.b.photo('a.jpg')
        self.b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        j = Path(self.tmp) / '_file_personnes.jsonl'
        d = self.b.journal()[0]
        d['chemin'] = str(Path(self.tmp) / 'ailleurs' / 'a.jpg')
        j.write_text(json.dumps(d) + '\n', encoding='utf-8')
        neuf = Banc(self.tmp)
        self.assertEqual(neuf['_file_personnes_reprise'](), 1)
        self.assertEqual(neuf.file.get_nowait()[0], Path(self.tmp) / 'a.jpg')

    def test_une_photo_disparue_est_sautee_sans_bloquer_le_reste(self):
        self.b.photo('a.jpg')
        self.b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        Path(self.tmp, 'a.jpg').unlink()
        neuf = Banc(self.tmp)
        self.assertEqual(neuf['_file_personnes_reprise'](), 0)

    def test_file_vidée_le_journal_est_remis_a_zero(self):
        """Sans ça, le journal grossirait à chaque nom posé, pour toujours."""
        self.b.photo('a.jpg')
        self.b.ecrivain()
        self.b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        self._attendre()
        self.assertFalse((Path(self.tmp) / '_file_personnes.jsonl').exists())
        self.assertFalse((Path(self.tmp) / '_file_personnes.pos').exists())

    def test_le_journal_n_est_pas_remis_a_zero_s_il_reste_du_travail(self):
        """La course : un producteur note un geste pendant que l'écrivain finit
        le précédent. Effacer là perdrait le geste qui vient d'entrer."""
        a, b = self.b.photo('a.jpg'), self.b.photo('b.jpg')
        self.b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        self.b['_enqueue_person_write']('b.jpg', 'personne:Flo', 'add')
        premier = self.b.file.get_nowait()
        self.b['_file_personnes_faite']([premier])
        self.assertTrue((Path(self.tmp) / '_file_personnes.jsonl').exists())
        self.assertEqual(len(self.b.journal()), 2)


# ═════════════════════ 3. Ce qui échoue est NOMMÉ ════════════════════════════

class LesEchecsSontNommes(BancTest):

    def test_un_echec_d_exiftool_est_ecrit_pas_avale(self):
        b = Banc(self.tmp, code=1)
        p = b.photo('a.jpg')
        b.ecrivain()
        b.file.put((p, 'personne:Flo', 'add', 'a.jpg', 1))
        fini = threading.Event()
        threading.Thread(target=lambda: (b.file.join(), fini.set()),
                         daemon=True).start()
        self.assertTrue(fini.wait(10))
        echecs = b.journal('_file_personnes_echecs.jsonl')
        self.assertEqual(len(echecs), 1)
        self.assertEqual(echecs[0]['tag'], 'personne:Flo')
        self.assertTrue(echecs[0]['motif'])

    def test_sans_exiftool_rien_n_est_ecrit_et_l_absence_est_dite(self):
        b = Banc(self.tmp, exiftool=None)
        p = b.photo('a.jpg')
        self.assertFalse(b['write_person_tags'](p, {'personne:Flo': 'add'}))
        self.assertEqual(b.appels, [])
        b.file.put((p, 'personne:Flo', 'add', 'a.jpg', 1))
        b['_ecrire_lot_personne']([b.file.get_nowait()])
        motifs = [d['motif'] for d in b.journal('_file_personnes_echecs.jsonl')]
        self.assertEqual(motifs, ['exiftool absent'])

    def test_la_position_avance_MEME_sur_echec(self):
        """Sinon un fichier illisible serait rejoué à chaque démarrage, pour
        toujours, et la file ne finirait jamais."""
        b = Banc(self.tmp, code=1)
        p = b.photo('a.jpg')
        b.photo('b.jpg')
        b['_enqueue_person_write']('a.jpg', 'personne:Flo', 'add')
        b['_enqueue_person_write']('b.jpg', 'personne:Flo', 'add')
        premier = b.file.get_nowait()
        b['_ecrire_lot_personne']([premier])
        self.assertEqual((Path(self.tmp) / '_file_personnes.pos')
                         .read_text(encoding='utf-8').strip(), '1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
