#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Les depots d'Uploads : quand ils sont arrives, et ce qui attend une decision.

`Uploads` est ne comme un outil de TRANSFERT, pas comme une antichambre de la
phototheque : un depot attend donc une decision, et rien ne bouge tout seul.
Il n'y a PAS d'etat « deja trie » a tenir -- decider fait SORTIR le fichier
d'Uploads, donc ce qui reste est ce qui attend. Ces bancs tiennent cette
propriete autant que les calculs.

La date de depot est notee a l'arrivee depuis le 12/09. Pour les 248 depots
anterieurs elle se relit sur le fichier -- sa date de CREATION, jamais son
`mtime` : jusqu'au 12/09 le tagueur le reecrivait (les 213 images d'`_Uploads`
etaient toutes au 05/09, jour du debut de la campagne).

`server.py` n'est pas importe : les fonctions sont extraites par l'arbre
syntaxique, et le listage est remplace par un bouchon -- il a ses 20 bancs a
lui, ce banc-ci mesure les depots.
"""

import ast
import io
import json
import os
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
LIGNES = SOURCE.splitlines()

FONCTIONS = ('charger_depots', 'sauver_depots', 'depot_noter',
             '_arrivee_de_stat', '_date_arrivee_du_fichier',
             'depot_le', 'depots_a_trier',
             'depots_vue', 'depots_vue_invalider', 'depots_vue_retirer',
             'cible_a_trier')
CONSTANTES = ('DEPOT_MUR_S', '_DEPOTS', '_DEPOTS_LOCK', '_DEPOTS_VUE',
              'DEPOTS_VUE_TTL_S', 'DOSSIER_A_TRIER')


def source_de(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return '\n'.join(LIGNES[n.lineno - 1:n.end_lineno])
    raise AssertionError(nom + ' introuvable dans server.py')


def module(dossier, racines=()):
    m = types.ModuleType('depots')
    m.__dict__.update({
        'os': os, 'io': io, 'json': json, 'time': time,
        'threading': threading, 'Path': Path,
        'SCRIPT_DIR': dossier, 'UPLOAD_DIR': dossier,
        'media_roots': lambda: list(racines),
    })

    def lister(d, rec=False):
        """Bouchon : ce que `_lister_dossier_frais` rendrait."""
        out = []
        for r, dirs, noms in os.walk(d):
            for n in noms:
                out.append(Path(r) / n)
            if not rec:
                break
        return out, []

    m.__dict__['_lister_dossier_frais'] = lister
    m.__dict__['DEPOTS_FILE'] = dossier / '_depots_uploads.json'
    # `ARBRE.body` et pas `ast.walk` : au premier jet, la marche attrapait
    # aussi les affectations INTERIEURES aux fonctions (`_DEPOTS = ...` dans
    # `charger_depots`) et les executait hors de leur indentation.
    for n in ARBRE.body:
        if isinstance(n, ast.FunctionDef) and n.name in FONCTIONS:
            exec(source_de(n.name), m.__dict__)                      # noqa: S102
        elif isinstance(n, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id in CONSTANTES
                for c in n.targets):
            exec('\n'.join(LIGNES[n.lineno - 1:n.end_lineno]),        # noqa: S102
                 m.__dict__)
    m.__dict__['DEPOTS_FILE'] = dossier / '_depots_uploads.json'
    manque = [x for x in FONCTIONS + CONSTANTES if x not in m.__dict__]
    if manque:
        raise AssertionError('introuvable : %r' % manque)
    return m


class Socle(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.m = module(self.d)
        self.m._DEPOTS.clear()
        self.m.depots_vue_invalider()

    def tearDown(self):
        self.tmp.cleanup()

    def poser(self, nom, age_jours=0):
        p = self.d / nom
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x')
        if age_jours:
            t = time.time() - age_jours * 86400
            os.utime(p, (t, t))
        return p


class LaDateDeDepot(Socle):

    def test_le_carnet_l_emporte_sur_le_fichier(self):
        p = self.poser('a.jpg')
        vieux = time.time() - 30 * 86400
        self.m._DEPOTS['a.jpg'] = {'le': vieux, 'par': 'Mike'}
        le, source = self.m.depot_le('a.jpg', p)
        self.assertEqual(source, 'carnet')
        self.assertAlmostEqual(le, vieux, delta=2)

    def test_sans_carnet_on_relit_le_FICHIER(self):
        p = self.poser('b.jpg')
        le, source = self.m.depot_le('b.jpg', p)
        if os.name == 'nt':
            self.assertEqual(source, 'fichier')
            self.assertIsNotNone(le)
        else:
            # Hors Windows, `st_ctime` n'est pas une date de creation : la
            # fonction doit le DIRE en ne rendant rien, pas deviner.
            self.assertEqual(source, 'inconnu')

    def test_un_fichier_disparu_ne_fait_pas_tomber(self):
        le, source = self.m.depot_le('fantome.jpg', self.d / 'fantome.jpg')
        self.assertIsNone(le)
        self.assertEqual(source, 'inconnu')

    def test_noter_puis_oublier(self):
        self.m.depot_noter('c.jpg', 'Flo')
        self.assertIn('c.jpg', self.m._DEPOTS)
        self.assertEqual(self.m._DEPOTS['c.jpg']['par'], 'Flo')
        # Le carnet est ECRIT tout de suite : une coupure ne doit pas
        # emporter ce qui vient d'arriver.
        self.assertTrue((self.d / '_depots_uploads.json').is_file())

    def test_le_carnet_n_est_PAS_purge_par_une_decision(self):
        """Il enregistre une ARRIVEE, pas une attente. Retirer l'entree au
        moment de la decision parait propre et casse l'annulation : observe
        le 12/09 sur un fichier temoin -- apres `garder` puis `undo`, le
        depot revenait dans Uploads mais disparaissait de la liste."""
        src = source_de('_api_tri_decider')
        self.assertNotIn('depot_oublier', src)
        self.assertIn('depots_vue_retirer(cle)', src)
        self.assertNotIn('def depot_oublier', SOURCE)

    def test_le_carnet_se_reprend(self):
        self.m.depot_noter('d.jpg', 'Mike')
        autre = module(self.d)
        autre._DEPOTS.clear()
        autre.__dict__['DEPOTS_FILE'] = self.d / '_depots_uploads.json'
        self.assertTrue(autre.charger_depots())
        self.assertIn('d.jpg', autre._DEPOTS)


class CeQuiAttendUneDecision(Socle):

    def test_seuls_les_depots_PLUS_VIEUX_que_le_mur(self):
        self.poser('vieux.jpg')
        self.poser('neuf.jpg')
        self.m._DEPOTS['vieux.jpg'] = {'le': time.time() - 20 * 86400, 'par': None}
        self.m._DEPOTS['neuf.jpg'] = {'le': time.time() - 3600, 'par': None}
        cles = [d['cle'] for d in self.m.depots_a_trier()]
        self.assertEqual(cles, ['vieux.jpg'])

    def test_du_plus_ANCIEN_au_plus_recent(self):
        for n, j in (('a.jpg', 9), ('b.jpg', 30), ('c.jpg', 15)):
            self.poser(n)
            self.m._DEPOTS[n] = {'le': time.time() - j * 86400, 'par': None}
        self.assertEqual([d['cle'] for d in self.m.depots_a_trier()],
                         ['b.jpg', 'c.jpg', 'a.jpg'])

    def test_le_mur_est_de_SEPT_jours(self):
        self.assertEqual(self.m.DEPOT_MUR_S, 7 * 86400)

    def test_les_jours_sont_comptes_juste(self):
        self.poser('x.jpg')
        self.m._DEPOTS['x.jpg'] = {'le': time.time() - 11.5 * 86400, 'par': None}
        self.assertEqual(self.m.depots_a_trier()[0]['jours'], 11)

    def test_un_depot_sans_date_connue_n_est_PAS_invente(self):
        """Hors Windows la date d'arrivee est inconnue : mieux vaut ne rien
        proposer que proposer une date fausse."""
        self.poser('muet.jpg')
        liste = self.m.depots_a_trier()
        if os.name != 'nt':
            self.assertEqual(liste, [])


class LaVueEnCache(Socle):

    def test_la_vue_est_gardee_puis_invalidee(self):
        self.poser('a.jpg')
        self.m._DEPOTS['a.jpg'] = {'le': time.time() - 20 * 86400, 'par': None}
        self.assertEqual(len(self.m.depots_vue()), 1)
        # Un second depot n'apparait pas tant que la vue n'est pas invalidee...
        self.poser('b.jpg')
        self.m._DEPOTS['b.jpg'] = {'le': time.time() - 20 * 86400, 'par': None}
        self.assertEqual(len(self.m.depots_vue()), 1)
        # ...et un geste l'invalide, sinon la lampe mentirait apres le clic
        # qui vient de l'eteindre.
        self.m.depots_vue_invalider()
        self.assertEqual(len(self.m.depots_vue()), 2)


    def test_une_decision_RETIRE_le_depot_au_lieu_de_tout_refaire(self):
        """Invalider ne suffit pas : la vue se refait depuis le listage, qui
        vient de son propre cache, et le client SMB de Windows garde les
        metadonnees d'un dossier quelques secondes. Mesure le 12/09 sur un
        fichier temoin : apres `effacer`, la liste le portait encore une
        minute -- la lampe comptait un geste qu'on venait de faire."""
        for n in ('a.jpg', 'b.jpg'):
            self.poser(n)
            self.m._DEPOTS[n] = {'le': time.time() - 20 * 86400, 'par': None}
        self.assertEqual(len(self.m.depots_vue()), 2)
        self.m.depots_vue_retirer('a.jpg')
        # La vue n'est PAS refaite : on ne redemande pas au disque ce qu'on
        # vient de lui dire.
        self.assertEqual([d['cle'] for d in self.m.depots_vue()], ['b.jpg'])

    def test_retirer_sur_une_vue_absente_ne_leve_pas(self):
        self.m.depots_vue_invalider()
        self.m.depots_vue_retirer('peu importe')


class OuPartUnDepotQuOnGarde(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.uploads = self.racine / '_Uploads'
        self.uploads.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_absent_la_cible_est_None(self):
        """Un bouton qui ne peut JAMAIS aboutir est une promesse que
        l'interface ne tiendra pas (CLAUDE.md n. 9) : la cible absente doit se
        voir AVANT le clic."""
        m = module(self.uploads, racines=[('Photos', self.racine)])
        self.assertIsNone(m.cible_a_trier())

    def test_presente_elle_est_rendue_relative_a_sa_racine(self):
        (self.racine / '_A TRIER').mkdir()
        m = module(self.uploads, racines=[('Photos', self.racine)])
        cible = m.cible_a_trier()
        self.assertIsNotNone(cible)
        idx, rel, chemin = cible
        self.assertEqual(idx, 0)
        self.assertEqual(rel, '_A TRIER')
        self.assertTrue(chemin.is_dir())

    def test_hors_de_toute_racine_connue_la_cible_est_None(self):
        (self.racine / '_A TRIER').mkdir()
        ailleurs = Path(self.tmp.name) / 'ailleurs'
        ailleurs.mkdir()
        m = module(self.uploads, racines=[('Autre', ailleurs)])
        self.assertIsNone(m.cible_a_trier())


class LaVignetteDUnDepotEnSOUSDOSSIER(unittest.TestCase):
    """Trouve en regardant la page : 193 des 248 depots arrivaient SANS
    vignette. Tous venaient d'un telephone, donc de `Camera/`, et
    `_url_for_key` prenait toute cle contenant un separateur pour un chemin
    NAS. La galerie ne pouvait pas le voir : elle calcule son URL elle-meme.

    La regle qui decide est celle de `_resolve_key` : une cle d'Uploads est
    RELATIVE, une cle de dossier supplementaire est ABSOLUE."""

    def module(self):
        import urllib
        import urllib.parse                                    # noqa: F401
        from functools import lru_cache
        from pathlib import PurePath
        m = types.ModuleType('urls')
        m.__dict__.update({
            'urllib': urllib, 'Path': Path, 'PurePath': PurePath,
            'lru_cache': lru_cache, 'PKEY_MEMO_MAX': 1 << 17,
            'media_roots': lambda: [('NAS', Path('/nas/Photos'))]})
        for nom in ('_pkey_chaine', '_pkey', '_url_for_key'):
            exec(source_de(nom), m.__dict__)                    # noqa: S102
        return m

    def test_une_cle_relative_AVEC_sous_dossier_a_une_url(self):
        m = self.module()
        self.assertEqual(m._url_for_key('Camera/20260531_222739.jpg'),
                         '/uploads/Camera/20260531_222739.jpg')

    def test_une_cle_relative_simple_n_a_pas_change(self):
        m = self.module()
        self.assertEqual(m._url_for_key('photo.jpg'), '/uploads/photo.jpg')

    def test_les_caracteres_sont_echappes(self):
        m = self.module()
        self.assertEqual(m._url_for_key('Mes photos/a b.jpg'),
                         '/uploads/Mes%20photos/a%20b.jpg')


class LaChaineEstBRANCHEE(unittest.TestCase):
    """Trois raccordements qu'un banc de calcul ne verrait pas -- et c'est par
    la que le 10/09 une correction posee sur deux chemins d'ecriture sur trois
    etait passee verte."""

    def test_l_upload_note_le_depot(self):
        src = source_de('_do_post') if False else SOURCE
        self.assertIn('depot_noter(key, utilisateur_vu())', src)

    def test_api_moi_porte_le_compte(self):
        self.assertIn('"depots": {"a_trier": len(attente)', SOURCE)

    def test_la_lampe_lit_la_MEME_reponse_que_le_nom(self):
        js = (HERE / 'ui' / 'global.js').read_text(encoding='utf-8')
        self.assertIn('allumerLampe(d)', js)
        self.assertIn('d.depots.a_trier', js.replace('\n', ' ')
                      .replace('d && d.depots && d.depots.a_trier',
                               'd.depots.a_trier'))

    def test_la_lampe_ne_dit_pas_QUE_par_le_clignotement(self):
        """Le plancher n. 4 : le mouvement peut etre coupe. Ce qui reste --
        un nombre et un libelle -- doit porter tout le message."""
        self.assertIn('lampe__n', SOURCE)
        self.assertIn("l.setAttribute('aria-label'",
                      (HERE / 'ui' / 'global.js').read_text(encoding='utf-8'))

    def test_la_page_de_tri_existe_et_porte_la_barre(self):
        page = (HERE / 'ui' / 'pages' / 'tri.html').read_text(encoding='utf-8')
        self.assertIn('<!--APPNAV-->', page)
        self.assertIn('<!--UI:components-->', page)
        self.assertIn('/api/tri/decider', page)
        # Cibles et semantique : des <button>, pas des <div> cliquables.
        self.assertNotIn('onclick=', page)


if __name__ == '__main__':
    unittest.main(verbosity=2)
