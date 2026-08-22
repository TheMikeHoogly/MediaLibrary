#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la greffe du recalage dans `server.py` — SUR LE CODE DE PROD.

Pourquoi ce fichier
───────────────────
La REGLE du recalage est testee ailleurs (`test_recale_rattachements`, 27 cas).
Ce qui reste est la COURROIE : ce que le serveur donne a lire a la regle. Une
courroie muette est le pire des defauts ici — si `_scores_des_visages` rendait
un dictionnaire vide, la reparation ne ferait rien et le message dirait
tranquillement « 0 rattachement a recaler », ce qui se lit comme « tout va
bien ». Le 22/08 a deja montre ce mode de panne deux fois : `store.rekey` qui
renvoie faux sans un mot, et un croisement a 100 % qui ne croisait rien.

Comme `test_gallery_placeholders` et `test_tranche_jugements`, ce module lit
`server.py` sans l'importer (`import server` ouvre `photos.db`, dont le serveur
est l'ecrivain unique) : il extrait la fonction de l'AST et l'execute dans un
espace de noms a elle.

Les tests n'impriment rien (l'agent git capture la sortie, 22/08).
"""

import ast
import unittest

import numpy as np

SERVER = __import__('pathlib').Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(f"{nom} introuvable dans server.py — la greffe du "
                         "recalage a bouge, ce test doit etre relu.")


class FauxStore:
    def __init__(self, data):
        self.data = data


def espace(faces, protos):
    """`_scores_des_visages` de la prod, avec un magasin et une signature a nous."""
    def _emb(s):
        v = np.asarray(s, dtype=np.float32)
        n = float(np.linalg.norm(v))
        return v / n if n else v

    ns = {'FACE_STORE': FauxStore(faces),
          'person_prototypes': lambda pe: protos,
          '_emb_from_b64': _emb}
    exec(compile(ast.Module([_noeud('_scores_des_visages')], []),
                 str(SERVER), 'exec'), ns)
    return ns['_scores_des_visages']


PROTO = np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32)


class TestScoresDesVisages(unittest.TestCase):

    def test_note_chaque_visage_de_la_photo(self):
        f = espace({'a.jpg': {"faces": [{"emb": [1, 0, 0]}, {"emb": [0, 1, 0]}]}},
                   PROTO)
        s = f({}, ['a.jpg'])
        self.assertEqual(len(s['a.jpg']), 2)
        self.assertAlmostEqual(s['a.jpg'][0], 1.0, 3)
        self.assertAlmostEqual(s['a.jpg'][1], 0.0, 3)

    def test_un_visage_sans_vecteur_vaut_None_et_non_zero(self):
        """Zero voudrait dire « ressemble un peu » ; None veut dire « on ne
        sait pas ». La regle traite les deux differemment."""
        f = espace({'a.jpg': {"faces": [{}, {"emb": [1, 0, 0]}]}}, PROTO)
        self.assertIsNone(f({}, ['a.jpg'])['a.jpg'][0])

    def test_une_photo_absente_du_magasin_n_entre_PAS_dans_le_resultat(self):
        """C'est le garde-fou : la regle ne touche jamais une photo qu'elle ne
        trouve pas dans les scores. Y mettre une liste vide ferait croire que
        la photo n'a aucun visage, et un recalage se deciderait sur du vide."""
        f = espace({'a.jpg': {"faces": [{"emb": [1, 0, 0]}]}}, PROTO)
        self.assertEqual(f({}, ['fantome.jpg']), {})

    def test_une_fiche_en_echec_est_ecartee(self):
        f = espace({'a.jpg': {"failed": 1, "faces": [{"emb": [1, 0, 0]}]}}, PROTO)
        self.assertEqual(f({}, ['a.jpg']), {})

    def test_sans_signature_aucun_score(self):
        """Une fiche sans empreinte de reference ne peut rien juger : rendre
        des scores ici reviendrait a recaler d'apres rien."""
        f = espace({'a.jpg': {"faces": [{"emb": [1, 0, 0]}]}}, None)
        self.assertEqual(f({}, ['a.jpg']), {})

    def test_une_photo_sans_visage_rend_une_liste_vide(self):
        """Elle DOIT figurer : la regle saura qu'il n'y a rien a viser, alors
        qu'une photo absente veut dire « on ne sait pas »."""
        f = espace({'a.jpg': {"faces": []}}, PROTO)
        self.assertEqual(f({}, ['a.jpg']), {'a.jpg': []})


class TestGreffe(unittest.TestCase):

    def test_le_recalage_passe_par_la_regle_partagee(self):
        """S'il recalculait sa propre regle, l'apercu et le banc pourraient
        diverger sans que rien ne le dise."""
        src = ast.get_source_segment(SOURCE, _noeud('recaler_rattachements')) or ''
        self.assertIn('import recale_rattachements as recale', src)
        self.assertIn('recale.recaler_fiche(', src)

    def test_l_apercu_et_l_application_sont_le_meme_appel(self):
        src = ast.get_source_segment(SOURCE, _noeud('recaler_rattachements')) or ''
        self.assertEqual(src.count('recale.recaler_fiche('), 1)

    def test_l_apercu_n_ecrit_rien(self):
        """`dry=True` ne doit toucher ni la fiche, ni le store, ni le disque."""
        src = ast.get_source_segment(SOURCE, _noeud('recaler_rattachements')) or ''
        avant_ecriture = src.split('if dry or not plan:')[0]
        for interdit in ('PEOPLE_STORE.save()', 'write_text'):
            self.assertNotIn(interdit, avant_ecriture)
        self.assertIn('if not dry:', avant_ecriture)

    def test_l_application_est_journalisee_avant_apres(self):
        src = ast.get_source_segment(SOURCE, _noeud('recaler_rattachements')) or ''
        self.assertIn('CORBEILLE_RECALAGE', src)
        self.assertIn("'avant'", src)
        self.assertIn("'apres'", src)

    def test_l_annulation_refuse_d_ecraser_un_jugement_posterieur(self):
        src = ast.get_source_segment(SOURCE, _noeud('annuler_recalage')) or ''
        self.assertIn('fiches_modifiees_depuis', src)
        self.assertIn("op.get('apres')", src)

    def test_les_animaux_ne_sont_pas_touches(self):
        """PETS porte des empreintes DINOv2 et n'a pas ete mesure : reparer un
        magasin qu'on n'a pas mesure serait un pari."""
        src = ast.get_source_segment(SOURCE, _noeud('recaler_rattachements')) or ''
        self.assertNotIn('PETS_STORE', src)
        src = ast.get_source_segment(SOURCE, _noeud('annuler_recalage')) or ''
        self.assertNotIn('PETS_STORE', src)


if __name__ == '__main__':
    unittest.main()
