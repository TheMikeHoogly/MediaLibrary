#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_fusion` — les deux promesses, et le piège des passes.

Pourquoi ce fichier
───────────────────
Une fusion promet deux choses, et les deux se perdent en silence :

1. **Aucune décision humaine perdue.** Le défaut réel du 22/08 —
   `SubjectStore.rename` transportait `refs` mais pas `confirmed` — n'a été vu
   qu'en LISANT la fonction, par chance, en préparant autre chose. 143
   confirmations seraient parties sans un message, sans un compteur, sans une
   trace. Ces tests fabriquent exactement ce défaut et exigent que
   l'instrument le NOMME.

2. **Le geste se défait.** La boucle de `rename` met une heure sans rendre la
   main : un deuxième clic lance une deuxième passe. `annuler_fusion` prend le
   DERNIER journal, or le dernier a vu le fonds déjà tagué par le premier — il
   croit que les photos « portaient déjà » le nom d'arrivée, et annuler ne le
   leur retirerait pas. Le test `test_passes_multiples` tient ce piège.

Aucun test n'appelle un serveur ni n'ouvre une base : chacun fabrique ses
journaux, qui sont des fichiers inertes.
"""

import json
import tempfile
import unittest
from pathlib import Path

import verifier_fusion as V


def fiche(nom, confirmed=(), exclude=(), nomerge=(), faces=(), refs=(),
          avatar=None, at=None):
    f = {'name': nom, 'confirmed': list(confirmed), 'exclude': list(exclude),
         'nomerge': list(nomerge), 'faces': [list(x) for x in faces],
         'refs': list(refs)}
    if avatar is not None:
        f['avatar'] = avatar
    if at is not None:
        f['at'] = at
    return f


def ecrire_journal(dossier, nom, ancien, nouveau, photos, anc, avant, apres):
    """Un journal au format exact de `_journal_fusion` : entête + une ligne
    par photo, `deja` = portait déjà le nom d'arrivée."""
    lignes = [json.dumps({'at': 1787433600.0, 'prefix': 'personne',
                          'ancien': ancien, 'nouveau': nouveau,
                          'photos': len(photos), 'fiche_ancienne': anc,
                          'fiche_cible_avant': avant,
                          'fiche_cible_apres': apres}, ensure_ascii=False)]
    for k, deja in photos:
        lignes.append(json.dumps({'k': k, 'deja': deja}))
    p = Path(dossier) / nom
    p.write_text("\n".join(lignes) + "\n", encoding='utf-8')
    return p


class LectureDesJournaux(unittest.TestCase):

    def test_entete_et_lignes(self):
        with tempfile.TemporaryDirectory() as d:
            p = ecrire_journal(d, 'fusion_20260822_160000.jsonl', 'Flo',
                               'Florine', [('a', 0), ('b', 1), ('c', 0)],
                               fiche('Flo'), fiche('Florine'), fiche('Florine'))
            r = V.lire_journal(p)
        self.assertEqual(r['erreur'], '')
        self.assertEqual(r['photos_lues'], 3)
        self.assertEqual(r['deja'], 1)
        self.assertEqual(r['cles'], 3)
        self.assertEqual(r['doublons'], 0)
        self.assertEqual(r['entete']['ancien'], 'Flo')

    def test_doublon_de_cle_signale(self):
        with tempfile.TemporaryDirectory() as d:
            p = ecrire_journal(d, 'fusion_1.jsonl', 'Flo', 'Florine',
                               [('a', 0), ('a', 0)], fiche('Flo'),
                               fiche('Florine'), fiche('Florine'))
            r = V.lire_journal(p)
        self.assertEqual(r['doublons'], 1)

    def test_journal_vide_ne_leve_pas(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'fusion_vide.jsonl'
            p.write_text("", encoding='utf-8')
            r = V.lire_journal(p)
        self.assertIn('vide', r['erreur'])
        self.assertIsNone(r['entete'])

    def test_journal_absent_ne_leve_pas(self):
        r = V.lire_journal(Path('/inexistant/fusion_x.jsonl'))
        self.assertTrue(r['erreur'])


class RegleDeux(unittest.TestCase):
    """L'union des décisions des deux fiches doit se retrouver après."""

    def test_union_preservee(self):
        anc = fiche('Flo', confirmed=['k1', 'k2'], exclude=['x1'],
                    nomerge=['n1'], faces=[('k1', 0)], avatar=['k1', 0],
                    at=100)
        av = fiche('Florine', confirmed=['k3'], faces=[('k3', 1)], at=200)
        ap = fiche('Florine', confirmed=['k1', 'k2', 'k3'], exclude=['x1'],
                   nomerge=['n1'], faces=[('k1', 0), ('k3', 1)],
                   avatar=['k1', 0], at=100)
        v = V.regle_deux({'fiche_ancienne': anc, 'fiche_cible_avant': av,
                          'fiche_cible_apres': ap})
        self.assertTrue(v['ok'], v['manques'])
        self.assertEqual(v['confirmed_attendus'], 3)
        self.assertEqual(v['at'], 'la plus ancienne')

    def test_le_defaut_du_22_08_est_nomme(self):
        """`rename` transportait `refs` mais pas `confirmed` : 143 « oui, c'est
        bien elle » partaient en silence. L'instrument doit les compter."""
        anc = fiche('Flo', confirmed=[f'k{i}' for i in range(143)],
                    refs=['r1'])
        av = fiche('Florine')
        ap = fiche('Florine', refs=['r1'])          # confirmed non transporté
        v = V.regle_deux({'fiche_ancienne': anc, 'fiche_cible_avant': av,
                          'fiche_cible_apres': ap})
        self.assertFalse(v['ok'])
        self.assertEqual(len(v['manques']['confirmed']), 143)

    def test_exclusions_et_nomerge_aussi(self):
        anc = fiche('Flo', exclude=['x1'], nomerge=['n1'])
        ap = fiche('Florine')
        v = V.regle_deux({'fiche_ancienne': anc, 'fiche_cible_avant': None,
                          'fiche_cible_apres': ap})
        self.assertFalse(v['ok'])
        self.assertIn('exclude', v['manques'])
        self.assertIn('nomerge', v['manques'])

    def test_visage_perdu_vu(self):
        anc = fiche('Flo', faces=[('k1', 0), ('k2', 3)])
        ap = fiche('Florine', faces=[('k1', 0)])
        v = V.regle_deux({'fiche_ancienne': anc, 'fiche_cible_avant': None,
                          'fiche_cible_apres': ap})
        self.assertFalse(v['ok'])
        self.assertEqual(len(v['manques']['faces']), 1)

    def test_avatar_perdu_vu(self):
        anc = fiche('Flo', avatar=['k1', 0])
        ap = fiche('Florine')
        v = V.regle_deux({'fiche_ancienne': anc, 'fiche_cible_avant': None,
                          'fiche_cible_apres': ap})
        self.assertFalse(v['ok'])
        self.assertEqual(v['avatar'], 'PERDU')

    def test_refs_plafonnees_ne_sont_pas_une_violation(self):
        """`rename` plafonne `refs` à 80 : un manque s'y DIT, mais ce ne sont
        pas des décisions humaines — l'instrument ne doit pas crier au loup."""
        anc = fiche('Flo', refs=[f'r{i}' for i in range(60)])
        av = fiche('Florine', refs=[f's{i}' for i in range(40)])
        ap = fiche('Florine', refs=([f'r{i}' for i in range(60)]
                                    + [f's{i}' for i in range(20)]))
        v = V.regle_deux({'fiche_ancienne': anc, 'fiche_cible_avant': av,
                          'fiche_cible_apres': ap})
        self.assertTrue(v['ok'])
        self.assertTrue(v['refs_plafond'])

    def test_fiche_apres_absente_est_un_echec(self):
        v = V.regle_deux({'fiche_ancienne': fiche('Flo'),
                          'fiche_cible_avant': None, 'fiche_cible_apres': None})
        self.assertFalse(v['ok'])


class Annulabilite(unittest.TestCase):

    def _rapports(self, d):
        return [V.lire_journal(p) for p in V.journaux(d)]

    def test_une_seule_passe_le_bouton_a_raison(self):
        with tempfile.TemporaryDirectory() as d:
            ecrire_journal(d, 'fusion_20260822_160000.jsonl', 'Flo', 'Florine',
                           [('a', 0)], fiche('Flo'), fiche('Florine'),
                           fiche('Florine'))
            a = V.annulabilite(self._rapports(d))
        self.assertFalse(a['passes_multiples'])
        self.assertTrue(a['accord'])
        self.assertEqual(a['a_utiliser'], 'fusion_20260822_160000.jsonl')

    def test_passes_multiples(self):
        """Deux passes du même couple : le bouton prendrait la seconde, qui a
        noté « portait déjà Florine » pour des photos taguées par la première.
        Le seul journal qui dit vrai est le premier — et lui seul porte la
        fiche absorbée."""
        with tempfile.TemporaryDirectory() as d:
            ecrire_journal(d, 'fusion_20260822_160000.jsonl', 'Flo', 'Florine',
                           [('a', 0), ('b', 1)], fiche('Flo', confirmed=['k1']),
                           fiche('Florine'), fiche('Florine', confirmed=['k1']))
            ecrire_journal(d, 'fusion_20260822_161000.jsonl', 'Flo', 'Florine',
                           [('a', 1)], None,
                           fiche('Florine', confirmed=['k1']),
                           fiche('Florine', confirmed=['k1']))
            a = V.annulabilite(self._rapports(d))
        self.assertTrue(a['passes_multiples'])
        self.assertEqual(a['pris_par_defaut'], 'fusion_20260822_161000.jsonl')
        self.assertEqual(a['a_utiliser'], 'fusion_20260822_160000.jsonl')
        self.assertFalse(a['accord'])

    def test_aucun_journal_complet(self):
        with tempfile.TemporaryDirectory() as d:
            ecrire_journal(d, 'fusion_1.jsonl', 'Flo', 'Florine', [('a', 1)],
                           None, fiche('Florine'), fiche('Florine'))
            a = V.annulabilite(self._rapports(d))
        self.assertEqual(a['a_utiliser'], '')
        self.assertFalse(a['accord'])


class Serveur(unittest.TestCase):

    def test_sans_serveur_le_banc_le_dit(self):
        s = V.cote_serveur('', 'Flo', 'Florine')
        self.assertFalse(s['joignable'])
        self.assertTrue(s['erreur'])

    def test_serveur_injoignable_ne_leve_pas(self):
        s = V.cote_serveur('http://127.0.0.1:9', 'Flo', 'Florine')
        self.assertFalse(s['joignable'])
        self.assertTrue(s['erreur'])


class Verdict(unittest.TestCase):

    def _rapport(self, journaux_, serveur=None):
        r = {'journaux': journaux_, 'ancien': 'Flo', 'nouveau': 'Florine',
             'annulabilite': V.annulabilite(
                 [x for x in journaux_ if x.get('entete')]),
             'serveur': serveur or {'joignable': False, 'erreur': 'non testé'},
             'ops_attendues': 100}
        r['verdict'] = V.verdict(r)
        return r

    def test_aucun_journal_dit_le_risque_du_redemarrage(self):
        r = self._rapport([])
        self.assertIn('redémarrer', " ".join(r['verdict']))
        self.assertIn('AUCUN journal', V.afficher(r))

    def test_regle2_violee_apparait_dans_le_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            p = ecrire_journal(d, 'fusion_1.jsonl', 'Flo', 'Florine',
                               [('a', 0)], fiche('Flo', confirmed=['k1']),
                               None, fiche('Florine'))
            j = V.lire_journal(p)
            j['regle2'] = V.regle_deux(j['entete'])
        r = self._rapport([j])
        self.assertIn('RÈGLE 2', " ".join(r['verdict']))
        self.assertIn('RÈGLE 2 VIOLÉE', V.afficher(r))

    def test_ancien_nom_vivant_est_signale(self):
        with tempfile.TemporaryDirectory() as d:
            p = ecrire_journal(d, 'fusion_1.jsonl', 'Flo', 'Florine',
                               [('a', 0)], fiche('Flo'), None, fiche('Florine'))
            j = V.lire_journal(p)
            j['regle2'] = V.regle_deux(j['entete'])
        r = self._rapport([j], serveur={
            'joignable': True, 'erreur': '', 'fiche_ancienne': True,
            'fiche_nouvelle': True, 'photos_ancien': 4487,
            'photos_nouveau': 1420, 'file_personnes': 16209})
        texte = V.afficher(r)
        self.assertIn('ENCORE LÀ', texte)
        self.assertIn('plusieurs passes', texte)

    def test_file_vide_se_lit_comme_un_fonds_a_jour(self):
        with tempfile.TemporaryDirectory() as d:
            p = ecrire_journal(d, 'fusion_1.jsonl', 'Flo', 'Florine',
                               [('a', 0)], fiche('Flo'), None, fiche('Florine'))
            j = V.lire_journal(p)
            j['regle2'] = V.regle_deux(j['entete'])
        r = self._rapport([j], serveur={
            'joignable': True, 'erreur': '', 'fiche_ancienne': False,
            'fiche_nouvelle': True, 'photos_ancien': None,
            'photos_nouveau': 5911, 'file_personnes': 0})
        texte = V.afficher(r)
        self.assertIn('vide', texte)
        self.assertIn('un seul nom', " ".join(r['verdict']))


class Main(unittest.TestCase):

    def test_dossier_vide_code_zero(self):
        with tempfile.TemporaryDirectory() as d:
            code = V.main(['--dossier', d, '--serveur', ''])
        self.assertEqual(code, 0)

    def test_json_ecrit(self):
        with tempfile.TemporaryDirectory() as d:
            ecrire_journal(d, 'fusion_1.jsonl', 'Flo', 'Florine', [('a', 0)],
                           fiche('Flo'), None, fiche('Florine'))
            sortie = str(Path(d) / 'r.json')
            V.main(['--dossier', d, '--serveur', '', '--json', sortie])
            r = json.loads(Path(sortie).read_text(encoding='utf-8'))
        self.assertEqual(r['ancien'], 'Flo')
        self.assertEqual(len(r['journaux']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
