#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — fusionner deux fiches ne doit RIEN emporter (règle 2).

Pourquoi ce fichier
───────────────────
Le 22/08, Mike a tranché que « Flo » et « Florine » sont la même personne. En
préparant la fusion, `SubjectStore.rename` s'est révélé transporter `refs`,
`exclude` et `faces` — mais **pas `confirmed`**. La fiche Flo en porte **143** :
143 fois où un humain a dit « oui, c'est bien elle ». Elles seraient parties
en silence, et le même défaut a valu pour **chaque fusion du curateur** depuis
que la fonction existe (`curator_accept`, type « merge »).

Une exclusion et une confirmation sont la même matière : un humain a tranché.
La règle 2 du projet ne dit pas « les tags ne se perdent jamais », elle dit
que les décisions humaines ne se perdent pas.

Ces tests lisent `server.py` sans l'importer (`import server` ouvre
`photos.db`, dont le serveur est l'écrivain unique) : la méthode est extraite
de l'AST et exécutée avec des magasins à nous.
"""

import ast
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _methode(nom):
    """Une méthode de `SubjectStore`, sortie de sa classe."""
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.ClassDef) and n.name == 'SubjectStore':
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and m.name == nom:
                    return m
    raise AssertionError(f"SubjectStore.{nom} introuvable — si la fusion a "
                         "bouge, ce test doit etre relu, pas contourne.")


def _methode_rename():
    """La méthode `rename` de `SubjectStore`, sortie de sa classe."""
    return _methode('rename')


def _fonction(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(f"{nom} introuvable dans server.py")


class FauxMagasin:
    def __init__(self, data):
        self.data = data

    def set(self, k, v, save=True):
        self.data[k] = v

    def save(self):
        pass


class Sujet:
    """`SubjectStore.rename` de la prod, branchée sur des magasins à nous."""

    def __init__(self, fiches, index=None, prefix='personne', species=False):
        self.store = FauxMagasin(fiches)
        self.prefix = prefix
        self.species = species
        self.ecrits = []                       # (clé, tag, sens) mis en file
        self.journaux = []                     # ce que la fusion a NOTÉ
        # Appelé AVANT chaque mise en file : c'est le seul endroit d'où l'on
        # peut observer l'état des fiches PENDANT la boucle — et donc vérifier
        # que la fusion des fiches a bien eu lieu AVANT elle (22/08).
        self.hook = None
        index = index if index is not None else {}
        self.index = FauxMagasin(index)

        def _retire(k, tag):
            e = self.index.data.get(k)
            if isinstance(e, dict):
                e['kw_fr'] = [x for x in (e.get('kw_fr') or [])
                              if str(x).lower() != tag.lower()]

        def _ajoute(k, tag):
            e = self.index.data.get(k)
            if isinstance(e, dict) and tag.lower() not in [
                    str(x).lower() for x in (e.get('kw_fr') or [])]:
                e.setdefault('kw_fr', []).append(tag)

        def _enfile(k, tag, op='add'):
            if self.hook:
                self.hook(k, tag, op)
            self.ecrits.append((k, tag, op))

        ns = {
            'copy': copy,
            'STORE': self.index,
            '_kw_has': lambda e, tag: any(
                str(x).lower() == tag.lower() for x in (e.get('kw_fr') or [])),
            '_index_remove_person': _retire,
            '_index_add_person': _ajoute,
            '_enqueue_person_write': _enfile,
            '_journal_fusion': lambda *a: self.journaux.append(a),
        }
        mod = ast.Module([_fonction('_merge_assigned'), _methode_rename(),
                          _methode('delete')], [])
        exec(compile(mod, str(SERVER), 'exec'), ns)
        self._rename = ns['rename']
        self._delete = ns['delete']

    def _new_entry(self, name, espece=None):
        # Miroir minimal de `SubjectStore._new_entry` : une fiche neuve n'a
        # que son nom et sa date. Si la prod se met à en mettre plus, ce test
        # ne le verra pas — c'est le prix d'un double, et il est assumé ici :
        # ce qu'on mesure, c'est ce qui est TRANSPORTÉ depuis l'ancienne fiche.
        e = {'name': name, 'refs': [], 'at': 5000.0}
        if self.species:
            e['species'] = espece or 'cat'
        return e

    def rename(self, old, new):
        return self._rename(self, old, new)

    def delete(self, name):
        return self._delete(self, name)


FICHE_FLO = {
    'name': 'Flo', 'at': 1000.0,
    'refs': ['r1', 'r2'],
    'exclude': ['x1', 'x2'],
    'confirmed': ['c1', 'c2', 'c3'],
    'nomerge': ['Mathilde'],
    'avatar': ['photo.jpg', 3],
    'faces': [['a.jpg', 0], ['b.jpg', 1]],
}


class TestRienNeSePerd(unittest.TestCase):

    def fusion(self, cible=None):
        fiches = {'flo': dict(FICHE_FLO)}
        if cible is not None:
            fiches['florine'] = cible
        s = Sujet(fiches)
        s.rename('Flo', 'Florine')
        return s.store.data

    def test_les_confirmations_survivent(self):
        # Le défaut du 22/08, en une ligne.
        self.assertEqual(self.fusion()['florine']['confirmed'],
                         ['c1', 'c2', 'c3'])

    def test_les_exclusions_survivent(self):
        self.assertEqual(self.fusion()['florine']['exclude'], ['x1', 'x2'])

    def test_les_refus_de_fusion_survivent(self):
        self.assertEqual(self.fusion()['florine']['nomerge'], ['Mathilde'])

    def test_les_rattachements_survivent(self):
        self.assertEqual(self.fusion()['florine']['faces'],
                         [['a.jpg', 0], ['b.jpg', 1]])

    def test_l_avatar_survit_quand_la_cible_n_en_a_pas(self):
        self.assertEqual(self.fusion()['florine']['avatar'], ['photo.jpg', 3])

    def test_l_ancienne_fiche_disparait_bien(self):
        self.assertNotIn('flo', self.fusion())

    def test_le_nom_est_celui_demande(self):
        self.assertEqual(self.fusion()['florine']['name'], 'Florine')


class TestQuandLaCibleExisteDEJA(unittest.TestCase):
    """Deux fiches vivantes : on ADDITIONNE, on ne remplace pas."""

    def fusion(self):
        s = Sujet({'flo': dict(FICHE_FLO),
                   'florine': {'name': 'Florine', 'at': 2000.0,
                               'refs': ['r9'], 'exclude': ['x9'],
                               'confirmed': ['c9'],
                               'avatar': ['deja.jpg', 1],
                               'faces': [['z.jpg', 5]]}})
        s.rename('Flo', 'Florine')
        return s.store.data['florine']

    def test_les_deux_ensembles_de_decisions_se_cumulent(self):
        f = self.fusion()
        self.assertEqual(f['confirmed'], ['c1', 'c2', 'c3', 'c9'])
        self.assertEqual(f['exclude'], ['x1', 'x2', 'x9'])

    def test_les_rattachements_des_deux_cotes_sont_la(self):
        self.assertEqual(sorted(map(tuple, self.fusion()['faces'])),
                         [('a.jpg', 0), ('b.jpg', 1), ('z.jpg', 5)])

    def test_l_avatar_de_la_CIBLE_n_est_pas_ecrase(self):
        self.assertEqual(self.fusion()['avatar'], ['deja.jpg', 1])

    def test_la_fiche_garde_la_plus_ancienne_date(self):
        self.assertEqual(self.fusion()['at'], 1000.0)

    def test_aucun_doublon_dans_les_ensembles(self):
        s = Sujet({'flo': {'name': 'Flo', 'confirmed': ['c1'], 'exclude': ['x1']},
                   'florine': {'name': 'Florine', 'confirmed': ['c1'],
                               'exclude': ['x1']}})
        s.rename('Flo', 'Florine')
        f = s.store.data['florine']
        self.assertEqual(f['confirmed'], ['c1'])
        self.assertEqual(f['exclude'], ['x1'])


class TestLesFichiersEtLIndex(unittest.TestCase):

    def test_chaque_photo_taguee_donne_un_RETRAIT_et_un_AJOUT(self):
        index = {'p1.jpg': {'kw_fr': ['personne:Flo']},
                 'p2.jpg': {'kw_fr': ['personne:flo', 'personne:Mike']},
                 'p3.jpg': {'kw_fr': ['personne:Mike']}}
        s = Sujet({'flo': dict(FICHE_FLO)}, index)
        n = s.rename('Flo', 'Florine')
        self.assertEqual(n, 2)                       # p3 n'est pas concernée
        self.assertEqual(sorted(s.ecrits), [
            ('p1.jpg', 'personne:Flo', 'del'),
            ('p1.jpg', 'personne:Florine', 'add'),
            ('p2.jpg', 'personne:Flo', 'del'),
            ('p2.jpg', 'personne:Florine', 'add'),
        ])

    def test_la_casse_du_tag_n_empeche_pas_le_renommage(self):
        # « personne:flo » compte comme « personne:Flo » (I7, 22/08).
        s = Sujet({'flo': dict(FICHE_FLO)},
                  {'p.jpg': {'kw_fr': ['PERSONNE:FLO']}})
        self.assertEqual(s.rename('Flo', 'Florine'), 1)

    def test_renommer_vers_le_meme_nom_ne_fait_rien(self):
        s = Sujet({'flo': dict(FICHE_FLO)}, {'p.jpg': {'kw_fr': ['personne:Flo']}})
        self.assertEqual(s.rename('Flo', 'flo'), 0)
        self.assertEqual(s.ecrits, [])

    def test_un_nom_vide_ne_fait_rien(self):
        s = Sujet({'flo': dict(FICHE_FLO)})
        self.assertEqual(s.rename('Flo', '   '), 0)
        self.assertIn('flo', s.store.data)



class TestLaFusionEstREVERSIBLE(unittest.TestCase):
    """Le geste le plus lourd du projet — 5 907 fichiers — doit se défaire.

    Tous les autres gestes destructeurs ont leur quarantaine. Celui-là n'en
    avait aucune jusqu'au 22/08.
    """

    def fusion(self, index):
        s = Sujet({'flo': dict(FICHE_FLO)}, index)
        s.rename('Flo', 'Florine')
        self.assertEqual(len(s.journaux), 1, "la fusion n'a rien journalise")
        return s.journaux[0]

    def test_chaque_photo_touchee_est_notee(self):
        _, _, _, touchees, _, _, _ = self.fusion(
            {'p1.jpg': {'kw_fr': ['personne:Flo']},
             'p2.jpg': {'kw_fr': ['personne:Flo']},
             'p3.jpg': {'kw_fr': ['personne:Mike']}})
        self.assertEqual(sorted(k for k, _ in touchees), ['p1.jpg', 'p2.jpg'])

    def test_une_photo_qui_portait_DEJA_les_deux_noms_est_marquee(self):
        # Le cœur de l'affaire : 149 photos portaient Flo ET Florine. Leur
        # rendre Flo est juste ; leur retirer Florine serait un vol.
        _, _, _, touchees, _, _, _ = self.fusion(
            {'deux.jpg': {'kw_fr': ['personne:Flo', 'personne:Florine']},
             'une.jpg': {'kw_fr': ['personne:Flo']}})
        self.assertEqual(dict(touchees), {'deux.jpg': 1, 'une.jpg': 0})

    def test_la_fiche_absorbee_est_notee_ENTIERE(self):
        _, _, _, _, avant_old, _, _ = self.fusion({})
        self.assertEqual(avant_old['confirmed'], ['c1', 'c2', 'c3'])
        self.assertEqual(avant_old['avatar'], ['photo.jpg', 3])

    def test_les_deux_etats_de_la_CIBLE_sont_notes(self):
        s = Sujet({'flo': dict(FICHE_FLO),
                   'florine': {'name': 'Florine', 'confirmed': ['c9']}})
        s.rename('Flo', 'Florine')
        _, _, _, _, _, avant_new, apres_new = s.journaux[0]
        self.assertEqual(avant_new['confirmed'], ['c9'])       # pour rendre
        self.assertEqual(apres_new['confirmed'],               # pour refuser
                         ['c1', 'c2', 'c3', 'c9'])

    def test_le_journal_note_les_deux_noms_et_le_genre(self):
        prefix, ancien, nouveau = self.fusion({})[:3]
        self.assertEqual((prefix, ancien, nouveau),
                         ('personne', 'Flo', 'Florine'))

    def test_un_renommage_qui_ne_fait_rien_ne_journalise_rien(self):
        s = Sujet({'flo': dict(FICHE_FLO)})
        s.rename('Flo', '   ')
        self.assertEqual(s.journaux, [])


# ────────────────── L'annulation, sur pièces ──────────────────
# `annuler_fusion` est la seule chose qui rende la fusion réversible. Non
# testée, ce serait une promesse — et le projet en a déjà payé deux (deux
# bancs qui ne mesuraient pas ce qu'ils annonçaient).

class Bac:
    """`_journal_fusion` + `annuler_fusion` de la prod, dans un dossier à nous."""

    def __init__(self, dossier, fiches, index, prefix='personne'):
        self.store = FauxMagasin(fiches)
        self.prefix = prefix
        self.ecrits = []
        self.index = FauxMagasin(index)
        sac = self

        class FauxSujet:
            store = self.store

        def add(k, tag):
            e = sac.index.data.get(k)
            if isinstance(e, dict) and tag.lower() not in [
                    str(x).lower() for x in (e.get('kw_fr') or [])]:
                e.setdefault('kw_fr', []).append(tag)

        def rem(k, tag):
            e = sac.index.data.get(k)
            if isinstance(e, dict):
                e['kw_fr'] = [x for x in (e.get('kw_fr') or [])
                              if str(x).lower() != tag.lower()]

        self.ns = {
            'CORBEILLE_FUSIONS': Path(dossier), 'Path': Path,
            'json': __import__('json'), 'time': __import__('time'),
            'STORE': self.index, 'SUBJECTS': {prefix: FauxSujet()},
            '_index_add_person': add, '_index_remove_person': rem,
            '_enqueue_person_write': lambda k, tag, op='add':
                self.ecrits.append((k, tag, op)),
            '_suggest_remove': lambda pred: None,
        }
        mod = ast.Module([_fonction('_journal_fusion'),
                          _fonction('fusions_journalisees'),
                          _fonction('annuler_fusion')], [])
        exec(compile(mod, str(SERVER), 'exec'), self.ns)

    def journaliser(self, *a):
        return self.ns['_journal_fusion'](*a)

    def annuler(self):
        return self.ns['annuler_fusion']()


class TestAnnulerLaFusion(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def bac(self):
        """Une fusion Flo → Florine déjà faite, telle qu'elle l'aurait été."""
        index = {'seule.jpg': {'kw_fr': ['personne:Florine']},
                 'deux.jpg': {'kw_fr': ['personne:Florine']},
                 'une.jpg': {'kw_fr': ['personne:Florine']}}
        cible_apres = {'name': 'Florine', 'confirmed': ['c1', 'c9'],
                       'at': 1000.0}
        b = Bac(self.d, {'florine': dict(cible_apres)}, index)
        b.journaliser('personne', 'Flo', 'Florine',
                      [['deux.jpg', 1], ['une.jpg', 0]],
                      {'name': 'Flo', 'confirmed': ['c1']},
                      {'name': 'Florine', 'confirmed': ['c9'], 'at': 1000.0},
                      dict(cible_apres))
        return b

    def test_l_ancien_nom_revient_sur_les_photos(self):
        b = self.bac()
        b.annuler()
        for k in ('deux.jpg', 'une.jpg'):
            self.assertIn('personne:Flo', b.index.data[k]['kw_fr'], k)

    def test_la_photo_qui_avait_DEJA_les_deux_noms_garde_le_nouveau(self):
        b = self.bac()
        b.annuler()
        self.assertIn('personne:Florine', b.index.data['deux.jpg']['kw_fr'])

    def test_la_photo_qui_ne_l_avait_pas_le_perd(self):
        b = self.bac()
        b.annuler()
        self.assertNotIn('personne:Florine', b.index.data['une.jpg']['kw_fr'])

    def test_une_photo_ETRANGERE_a_la_fusion_n_est_pas_touchee(self):
        b = self.bac()
        b.annuler()
        self.assertEqual(b.index.data['seule.jpg']['kw_fr'],
                         ['personne:Florine'])

    def test_les_fichiers_du_NAS_sont_remis_en_file(self):
        b = self.bac()
        b.annuler()
        self.assertEqual(sorted(b.ecrits), [
            ('deux.jpg', 'personne:Flo', 'add'),
            ('une.jpg', 'personne:Flo', 'add'),
            ('une.jpg', 'personne:Florine', 'del'),
        ])

    def test_les_deux_fiches_reviennent_telles_qu_elles_etaient(self):
        b = self.bac()
        b.annuler()
        self.assertEqual(b.store.data['flo']['confirmed'], ['c1'])
        self.assertEqual(b.store.data['florine']['confirmed'], ['c9'])

    def test_une_cible_qui_N_EXISTAIT_PAS_disparait_a_nouveau(self):
        apres = {'name': 'Florine', 'confirmed': ['c1']}
        b = Bac(self.d, {'florine': dict(apres)},
                {'p.jpg': {'kw_fr': ['personne:Florine']}})
        b.journaliser('personne', 'Flo', 'Florine', [['p.jpg', 0]],
                      {'name': 'Flo', 'confirmed': ['c1']}, None, dict(apres))
        b.annuler()
        self.assertNotIn('florine', b.store.data)
        self.assertEqual(b.store.data['flo']['confirmed'], ['c1'])

    def test_une_fiche_JUGEE_DEPUIS_n_est_pas_ecrasee(self):
        b = self.bac()
        b.store.data['florine']['confirmed'] = ['c1', 'c9', 'cX']   # un humain
        r = b.annuler()
        self.assertEqual(r['fiche_cible_jugee_depuis'], 1)
        self.assertEqual(b.store.data['florine']['confirmed'],
                         ['c1', 'c9', 'cX'])
        # ... et pourtant les tags des photos, eux, sont bien rendus.
        self.assertIn('personne:Flo', b.index.data['une.jpg']['kw_fr'])

    def test_une_photo_disparue_du_fonds_est_comptee_sans_bloquer(self):
        b = self.bac()
        del b.index.data['une.jpg']
        r = b.annuler()
        self.assertEqual(r['photos_disparues'], 1)
        self.assertEqual(r['photos_rendues'], 1)

    def test_le_journal_est_marque_annule_et_ne_repasse_pas(self):
        b = self.bac()
        b.annuler()
        self.assertEqual(b.ns['fusions_journalisees'](), [])
        self.assertTrue(list(self.d.glob('*.annule')))
        self.assertFalse(b.annuler()['ok'])

    def test_sans_journal_l_annulation_le_DIT(self):
        b = Bac(self.d, {}, {})
        r = b.annuler()
        self.assertFalse(r['ok'])
        self.assertIn('aucune fusion', r['error'])

    def test_rien_a_journaliser_ne_cree_pas_de_journal(self):
        b = Bac(self.d, {}, {})
        self.assertIsNone(b.journaliser('personne', 'Flo', 'Florine',
                                        [], None, None, None))
        self.assertEqual(b.ns['fusions_journalisees'](), [])
    def test_deux_fusions_dans_la_meme_seconde_gardent_deux_journaux(self):
        # Le nom du journal est horodaté à la seconde ; le curateur peut
        # accepter deux fusions coup sur coup. La seconde n'efface pas la
        # première — sinon la première fusion devient irréversible en silence.
        b = self.bac()
        b.journaliser('personne', 'Mutz', 'Caline', [['q.jpg', 0]],
                      {'name': 'Mutz'}, None, {'name': 'Caline'})
        self.assertEqual(len(b.ns['fusions_journalisees']()), 2)


class TestCeQueLaFusionECRIT(unittest.TestCase):
    """Une trace qui tue le geste qu'elle raconte.

    Le 22/08, deux livraisons ont été refusées d'affilée sur « FAILED
    (errors=11) » sans que le message nomme sa cause. Le coupable n'était pas
    la fusion : c'était le « ↻ » de sa ligne de journal. L'agent git lance les
    tests SANS `PYTHONUTF8` — console cp1252 — là où le banc le force. Les
    deux portes du projet ne jugeaient pas la même chose, et la plus sévère
    avait raison : du code qui s'imprime ne doit pas dépendre de la console
    qui l'écoute.
    """

    def test_la_ligne_de_journal_est_en_ASCII_PUR(self):
        src = ast.get_source_segment(SOURCE, _fonction('_journal_fusion')) or ''
        ligne = [l for l in src.splitlines()
                 if 'Fusion journalisee' in l and 'print' in l]
        self.assertTrue(ligne, "la ligne de journal a disparu ou change de nom")
        for l in ligne:
            l.encode('ascii')          # lève si un jour un symbole revient

    def test_le_message_survit_a_une_console_cp1252(self):
        # Le test qui aurait évité les deux refus : on écrit vraiment.
        import io as _io
        tampon = _io.TextIOWrapper(_io.BytesIO(), encoding='cp1252',
                                   errors='strict')
        tampon.write("  Fusion journalisee : Flo -> Florine, "
                     "5907 photo(s) - reversible (fusion_20260822.jsonl)\n")
        tampon.flush()


class TestLOrdreDuGeste(unittest.TestCase):
    """L'ordre fiches-puis-photos, et ce qu'il a coûté de l'apprendre.

    Le 22/08, la vraie fusion a été lancée et n'a jamais fini. La boucle met
    une HEURE (un `stat` NAS par photo) et la fiche absorbée ne disparaissait
    qu'À LA FIN : pendant toute cette heure, la signature de Flo restait
    vivante et `AUTO_ADD` la ré-attribuait toutes les 240 s aux photos que la
    fusion venait de lui retirer. Mesuré sur le fonds : `Flo` descend de 5 907
    à 4 487 puis REMONTE à 5 703, 60 auto-ajouts « Flo » en une heure, et
    17 092 écritures en attente pour une fusion qui en demande 11 814.

    Aucun test ne pouvait voir ça : ils regardaient le RÉSULTAT d'une fusion
    qui va au bout. Ceux-ci regardent l'ORDRE et l'INTERRUPTION.
    """

    def _index(self, *cles_et_tags):
        return {k: {'kw_fr': list(tags)} for k, tags in cles_et_tags}

    def test_la_fiche_est_fusionnee_AVANT_la_boucle(self):
        """Au premier fichier mis en file, l'ancienne fiche n'existe déjà
        plus — donc plus de signature, donc plus d'auto-ajout à contre-sens."""
        s = Sujet({'flo': dict(FICHE_FLO)},
                  self._index(('a.jpg', ['personne:Flo']),
                              ('b.jpg', ['personne:Flo'])))
        vus = []
        s.hook = lambda k, tag, op: vus.append(
            ('flo' in s.store.data, 'florine' in s.store.data))
        s.rename('Flo', 'Florine')
        self.assertTrue(vus, "aucune écriture mise en file")
        self.assertEqual(vus[0], (False, True),
                         "la fiche absorbée vit encore pendant la boucle : "
                         "le curateur va remettre l'ancien nom derrière elle")

    def test_une_boucle_interrompue_note_quand_meme_ce_qu_elle_a_fait(self):
        """Sans le `finally`, une boucle qui tombe laisse un fonds à moitié
        renommé et RIEN pour l'annuler. C'est arrivé."""
        s = Sujet({'flo': dict(FICHE_FLO)},
                  self._index(('a.jpg', ['personne:Flo']),
                              ('b.jpg', ['personne:Flo']),
                              ('c.jpg', ['personne:Flo'])))

        def casse(k, tag, op):
            if k == 'b.jpg':
                raise OSError("NAS injoignable")
        s.hook = casse
        with self.assertRaises(OSError):
            s.rename('Flo', 'Florine')
        self.assertEqual(len(s.journaux), 1, "rien n'a été journalisé : la "
                         "fusion interrompue serait inannulable")
        # `b.jpg` en fait partie : son INDEX avait déjà basculé quand
        # l'écriture est tombée. C'est précisément ce qu'il faut noter — la
        # photo est à moitié renommée, et seule cette ligne permet de le rendre.
        touchees = s.journaux[0][3]
        self.assertEqual([t[0] for t in touchees], ['a.jpg', 'b.jpg'])
        self.assertIsInstance(s.journaux[0][4], dict,
                              "la fiche absorbée doit être notée pour être "
                              "rendue")

    def test_relancer_apres_une_interruption_reprend_le_travail(self):
        s = Sujet({'flo': dict(FICHE_FLO)},
                  self._index(('a.jpg', ['personne:Flo']),
                              ('b.jpg', ['personne:Flo']),
                              ('c.jpg', ['personne:Flo'])))
        s.hook = lambda k, tag, op: (_ for _ in ()).throw(
            OSError("NAS")) if k == 'b.jpg' else None
        with self.assertRaises(OSError):
            s.rename('Flo', 'Florine')
        s.ecrits.clear()
        s.hook = None
        n = s.rename('Flo', 'Florine')          # la fiche est déjà fusionnée
        self.assertEqual(n, 1, "la photo restante n'a pas été reprise")
        restants = [k for k, e in s.index.data.items()
                    if 'personne:Flo' in e['kw_fr']]
        self.assertEqual(restants, [])
        # `b.jpg` avait basculé dans l'index sans que son fichier suive : la
        # reprise doit REPASSER dessus, sinon son XMP garde l'ancien nom pour
        # toujours et le fera revenir au prochain balayage.
        self.assertIn(('b.jpg', 'personne:Flo', 'del'), s.ecrits)
        # La deuxième passe ne trouve plus de fiche à absorber : elle ne doit
        # RIEN retirer à celle d'arrivée (règle 2, même dans la reprise).
        self.assertEqual(s.store.data['florine']['confirmed'],
                         ['c1', 'c2', 'c3'])

    def test_le_fichier_qui_porte_deja_le_nouveau_nom_est_reecrit(self):
        """Une photo dont l'index a basculé sans que l'XMP suive garde
        l'ancien nom dans ses métadonnées : au prochain balayage il revient
        dans l'index, sans fiche. C'est ainsi que naît un nom fantôme —
        « personne:Florine, 153 photos, aucune fiche »."""
        s = Sujet({'flo': dict(FICHE_FLO)},
                  self._index(('deja.jpg', ['personne:Florine'])))
        s.rename('Flo', 'Florine')
        self.assertIn(('deja.jpg', 'personne:Flo', 'del'), s.ecrits)
        self.assertIn(('deja.jpg', 'personne:Florine', 'add'), s.ecrits)

    def test_mais_elle_n_entre_pas_dans_ce_qui_s_annule(self):
        """…et elle ne doit PAS être notée comme touchée : elle ne portait pas
        l'ancien nom, annuler ne doit rien lui rendre."""
        s = Sujet({'flo': dict(FICHE_FLO)},
                  self._index(('deja.jpg', ['personne:Florine']),
                              ('vraie.jpg', ['personne:Flo'])))
        s.rename('Flo', 'Florine')
        touchees = s.journaux[0][3]
        self.assertEqual([t[0] for t in touchees], ['vraie.jpg'])

    def test_supprimer_efface_la_fiche_AVANT_de_balayer(self):
        """`delete` avait exactement la même forme que `rename` : la fiche ne
        partait qu'après la boucle. Supprimer un nom très photographié aurait
        donc livré la même bataille contre `AUTO_ADD`, en silence, et sans
        même un journal pour la raconter."""
        s = Sujet({'flo': dict(FICHE_FLO)},
                  self._index(('a.jpg', ['personne:Flo']),
                              ('b.jpg', ['personne:Flo'])))
        vus = []
        s.hook = lambda k, tag, op: vus.append('flo' in s.store.data)
        n = s.delete('Flo')
        self.assertEqual(n, 2)
        self.assertTrue(vus)
        self.assertFalse(vus[0], "la fiche vit encore pendant la boucle : le "
                         "curateur va remettre le nom derrière la suppression")

    def test_une_photo_qui_porte_les_DEUX_noms_est_notee_deja(self):
        """Les 149 photos qui portaient Flo ET Florine : annuler doit leur
        rendre Flo sans leur retirer Florine."""
        s = Sujet({'flo': dict(FICHE_FLO)},
                  self._index(('deux.jpg', ['personne:Flo',
                                            'personne:Florine'])))
        s.rename('Flo', 'Florine')
        self.assertEqual(s.journaux[0][3], [['deux.jpg', 1]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
