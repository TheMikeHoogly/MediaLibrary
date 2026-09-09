#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `copier_absentes.py` — sans NAS, sans Google, sans reseau.

Ce que ces tests tiennent
-------------------------
1. **Rien n'est jamais ECRASE.** Un homonyme de meme taille est saute (le
   script est reprenable) ; d'une autre taille, la copie prend un nom
   suffixe et se DIT. C'est la regle 2 du projet appliquee a une copie :
   aucun octet du fonds existant ne se perd.
2. **L'annee ne vient JAMAIS du `mtime`.** Un fichier copie aujourd'hui a le
   `mtime` d'aujourd'hui : s'en servir ferait passer tout l'export pour 2026.
   Le `.json` de Takeout d'abord, le dossier `Photos from YYYY` ensuite.
3. **La cible doit etre sous `_A TRIER`,** parce que c'est la que la chaine
   reprend. Ecrire 12 Go ailleurs sur un NAS ne se rattrape pas.
4. **Chaque copie est RELUE.** Une taille qui ne correspond pas est un
   grief, pas un succes.
5. **Sans `--copier`, le disque reste intact.**

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import copier_absentes as C  # noqa: E402


def export(base, fichiers, sidecars=None):
    """Un mini-export Takeout : {chemin relatif: octets}."""
    base = Path(base)
    for rel, n in fichiers.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x' * n)
    for rel, epoch in (sidecars or {}).items():
        p = base / (rel + '.json')
        p.write_text(json.dumps({'title': os.path.basename(rel),
                                 'photoTakenTime': {'timestamp': str(epoch)}}),
                     encoding='utf-8')
    return base


def rapport_google(chemin, medias):
    Path(chemin).write_text(json.dumps(
        {'par_verdict': {'ABSENT': medias}}), encoding='utf-8')
    return str(chemin)


class LAnnee(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="test_cop_"))

    def test_le_sidecar_de_Takeout_fait_foi(self):
        export(self.d, {'Photos from 2026/a.jpg': 10},
               {'Photos from 2026/a.jpg': 1104537600})     # 2005
        an = C.annee_du_media(str(self.d / 'Photos from 2026/a.jpg'))
        self.assertEqual(an, 2005)          # le sidecar gagne sur le dossier

    def test_a_defaut_le_dossier_Photos_from_YYYY(self):
        export(self.d, {'Photos from 2019/b.jpg': 10})
        self.assertEqual(
            C.annee_du_media(str(self.d / 'Photos from 2019/b.jpg')), 2019)

    def test_sans_rien_l_annee_est_INCONNUE_pas_celle_du_mtime(self):
        # Le piege : un fichier copie aujourd'hui a le mtime d'aujourd'hui.
        export(self.d, {'Album de Carl/c.jpg': 10})
        self.assertIsNone(C.annee_du_media(str(self.d / 'Album de Carl/c.jpg')))


class RienNEstEcrase(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="test_cop2_"))
        self.cible = self.d / '_A TRIER' / 'Takeout Google'

    def test_un_homonyme_de_MEME_taille_est_saute(self):
        (self.cible / '2019').mkdir(parents=True)
        (self.cible / '2019' / 'a.jpg').write_bytes(b'x' * 10)
        export(self.d, {'Photos from 2019/a.jpg': 10})
        t = C.plan([{'chemin_google': str(self.d / 'Photos from 2019/a.jpg'),
                     'octets': 10}], self.cible)
        self.assertEqual(t[0][2], 'deja')

    def test_un_homonyme_d_une_AUTRE_taille_prend_un_suffixe(self):
        (self.cible / '2019').mkdir(parents=True)
        (self.cible / '2019' / 'a.jpg').write_bytes(b'x' * 7)
        export(self.d, {'Photos from 2019/a.jpg': 10})
        t = C.plan([{'chemin_google': str(self.d / 'Photos from 2019/a.jpg'),
                     'octets': 10}], self.cible)
        self.assertEqual(t[0][2], 'suffixe')
        self.assertTrue(t[0][1].endswith('a (2).jpg'), t[0][1])
        # ... et l'original est INTACT.
        self.assertEqual((self.cible / '2019' / 'a.jpg').stat().st_size, 7)

    def test_la_copie_reprend_sans_tout_refaire(self):
        export(self.d, {'Photos from 2019/a.jpg': 10,
                        'Photos from 2019/b.jpg': 20})
        medias = [{'chemin_google': str(self.d / 'Photos from 2019' / n),
                   'octets': o} for n, o in (('a.jpg', 10), ('b.jpg', 20))]
        C.copier(C.plan(medias, self.cible), ecrire=lambda *x: None)
        compte, _g, ecrits = C.copier(C.plan(medias, self.cible),
                                      ecrire=lambda *x: None)
        self.assertEqual(compte['copie'], 0)
        self.assertEqual(compte['deja'], 2)
        self.assertEqual(ecrits, [])


class LaCopie(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="test_cop3_"))
        self.cible = self.d / '_A TRIER' / 'Takeout Google'

    def test_les_fichiers_atterrissent_dans_leur_ANNEE(self):
        export(self.d, {'Photos from 2024/a.jpg': 10,
                        'Photos from 2005/b.jpg': 20})
        medias = [{'chemin_google': str(self.d / 'Photos from 2024/a.jpg'),
                   'octets': 10},
                  {'chemin_google': str(self.d / 'Photos from 2005/b.jpg'),
                   'octets': 20}]
        compte, _g, ecrits = C.copier(C.plan(medias, self.cible),
                                      ecrire=lambda *x: None)
        self.assertEqual(compte['copie'], 2)
        self.assertTrue((self.cible / '2024' / 'a.jpg').is_file())
        self.assertTrue((self.cible / '2005' / 'b.jpg').is_file())
        self.assertEqual(len(ecrits), 2)

    def test_sans_annee_le_fichier_va_dans_SANS_DATE(self):
        export(self.d, {'Album/c.jpg': 5})
        C.copier(C.plan([{'chemin_google': str(self.d / 'Album/c.jpg'),
                          'octets': 5}], self.cible),
                 ecrire=lambda *x: None)
        self.assertTrue((self.cible / C.SANS_DATE / 'c.jpg').is_file())

    def test_une_source_disparue_est_un_GRIEF_pas_un_silence(self):
        compte, griefs, _e = C.copier(
            [(str(self.d / 'nexistepas.jpg'),
              str(self.cible / '2024' / 'x.jpg'), 'neuf')],
            ecrire=lambda *x: None)
        self.assertEqual(compte['grief'], 1)
        self.assertTrue(griefs)

    def test_le_journal_d_annulation_liste_ce_qui_a_ete_ecrit(self):
        export(self.d, {'Photos from 2024/a.jpg': 10})
        _c, _g, ecrits = C.copier(
            C.plan([{'chemin_google': str(self.d / 'Photos from 2024/a.jpg'),
                     'octets': 10}], self.cible), ecrire=lambda *x: None)
        p = C.journal(ecrits, dossier=self.d / '_corbeille_copies')
        lignes = Path(p).read_text(encoding='utf-8').strip().splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertIn('destination', json.loads(lignes[0]))

    def test_sans_rien_a_ecrire_il_n_y_a_pas_de_journal(self):
        self.assertIsNone(C.journal([], dossier=self.d / '_c'))


class LesGardeFous(unittest.TestCase):

    def _dit(self, **kw):
        lignes = []
        base = dict(travaux=[('s', 'd', 'neuf')],
                    cible=Path('/nas/_A TRIER/Takeout Google'),
                    octets=100, libre=10 ** 9)
        base.update(kw)
        ok = C.rapport(ecrire=lignes.append, **base)
        return ok, lignes

    def test_une_cible_hors_A_TRIER_ne_passe_PAS(self):
        ok, lignes = self._dit(cible=Path('/nas/Photos/ailleurs'))
        self.assertFalse(ok)
        self.assertTrue(any('N EST PAS SOUS' in l for l in lignes))

    def test_le_garde_fou_se_leve_explicitement(self):
        ok, _l = self._dit(cible=Path('/nas/Photos/ailleurs'),
                           hors_a_trier=True)
        self.assertTrue(ok)

    def test_A_TRIER_est_reconnu_dans_le_chemin(self):
        self.assertTrue(C.sous_a_trier('/nas/home/Photos/_A TRIER/x/2024'))
        self.assertTrue(C.sous_a_trier('/nas/home/Photos/_A_TRIER/x'))
        self.assertFalse(C.sous_a_trier('/nas/home/Photos/Photos Mike'))

    def test_la_place_manquante_ne_passe_pas(self):
        ok, lignes = self._dit(octets=10 ** 9, libre=10)
        self.assertFalse(ok)
        self.assertTrue(any('PAS ASSEZ DE PLACE' in l for l in lignes))

    def test_aucune_absente_ne_rend_PAS_vert(self):
        # Un rapport vide peut vouloir dire << tout est copie >> comme
        # << mauvais rapport >>. On ne conclut pas a la place de l'humain.
        ok, lignes = self._dit(travaux=[])
        self.assertFalse(ok)
        self.assertTrue(any('rien a copier' in l for l in lignes))

    def test_un_grief_de_copie_rend_rouge(self):
        ok, _l = self._dit(compte={'copie': 1, 'deja': 0, 'suffixe': 0,
                                   'grief': 1}, griefs=['x'])
        self.assertFalse(ok)


class LeSecondCasGoogleEnPorteePlus(unittest.TestCase):
    """Le NAS porte le NOM, mais un fichier plus PETIT (28/08).

    Sur 9 612 << tailles differentes >>, 9 315 ont le NAS plus GROS d'un ecart
    median de 4 101 octets : c'est un bloc XMP, nos propres tags, et c'est
    benin. Mais 297 fois le NAS est plus PETIT, dont 89 de plus d'un Mo -- dix
    videos a -73, -40, -22 Mo. Effacer chez Google en croyant que le NAS a la
    photo perdrait la bonne version. Ces tests tiennent le TRI, parce que
    c'est lui qui decide ce qui vit et ce qui meurt.
    """

    def rapport(self, entrees):
        d = Path(tempfile.mkdtemp(prefix='test_ecart_'))
        self.addCleanup(lambda: None)
        p = d / 'r.json'
        p.write_text(json.dumps({'par_verdict': entrees}), encoding='utf-8')
        return str(p)

    @staticmethod
    def media(nom, google, nas, verdict_detail=True):
        return {'nom': nom, 'chemin_google': '/g/' + nom, 'octets': google,
                'detail': ('taille %d chez Google, %d sur le NAS'
                           % (google, nas)) if verdict_detail else 'autre chose'}

    def test_par_defaut_seules_les_ABSENTES_sortent(self):
        """Le comportement d'avant ne bouge pas d'un pouce."""
        r = self.rapport({'ABSENT': [self.media('a.jpg', 10, 0)],
                          'PROBABLE': [self.media('b.jpg', 900, 100)]})
        self.assertEqual([m['nom'] for m in C.absentes(r)], ['a.jpg'])

    def test_le_NAS_plus_petit_est_retenu(self):
        r = self.rapport({'PROBABLE': [self.media('v.mp4', 204468711, 131027884)]})
        m = C.absentes(r, ('PROBABLE',), 100000)
        self.assertEqual([x['nom'] for x in m], ['v.mp4'])

    def test_le_NAS_plus_GROS_est_ecarte(self):
        """C'est le cas BENIN : nos XMP. Le rapatrier ferait un doublon pour
        rien, et rien n'est en danger si Google efface sa version."""
        r = self.rapport({'PROBABLE': [self.media('p.jpg', 2614943, 2619031)]})
        self.assertEqual(C.absentes(r, ('PROBABLE',), 100000), [])

    def test_un_ecart_sous_le_seuil_est_ecarte(self):
        """Quelques kilo-octets ne prouvent rien ; un megaoctet, si."""
        r = self.rapport({'PROBABLE': [self.media('p.jpg', 1000000, 999000)]})
        self.assertEqual(C.absentes(r, ('PROBABLE',), 100000), [])
        self.assertEqual(len(C.absentes(r, ('PROBABLE',), 500)), 1)

    def test_un_detail_illisible_est_ECARTE_jamais_devine(self):
        r = self.rapport({'PROBABLE': [self.media('p.jpg', 9, 1,
                                                  verdict_detail=False)]})
        self.assertEqual(C.absentes(r, ('PROBABLE',), 100), [])

    def test_les_deux_verdicts_se_cumulent(self):
        r = self.rapport({'ABSENT': [self.media('a.jpg', 10, 0)],
                          'PROBABLE': [self.media('v.mp4', 900000, 100)]})
        m = C.absentes(r, ('ABSENT', 'PROBABLE'), 100000)
        self.assertEqual(sorted(x['nom'] for x in m), ['a.jpg', 'v.mp4'])


class LaLigneDeCommande(unittest.TestCase):

    def test_sans_copier_le_disque_reste_INTACT(self):
        d = Path(tempfile.mkdtemp(prefix="test_cop4_"))
        export(d, {'Photos from 2024/a.jpg': 10})
        r = rapport_google(d / 'r.json', [
            {'nom': 'a.jpg', 'octets': 10,
             'chemin_google': str(d / 'Photos from 2024/a.jpg')}])
        cible = d / '_A TRIER' / 'T'
        code = C.main(['--rapport', r, '--cible', str(cible)])
        self.assertEqual(code, 0)
        self.assertFalse(cible.exists())

    def test_avec_copier_le_fichier_arrive(self):
        d = Path(tempfile.mkdtemp(prefix="test_cop5_"))
        export(d, {'Photos from 2024/a.jpg': 10})
        r = rapport_google(d / 'r.json', [
            {'nom': 'a.jpg', 'octets': 10,
             'chemin_google': str(d / 'Photos from 2024/a.jpg')}])
        cible = d / '_A TRIER' / 'T'
        code = C.main(['--rapport', r, '--cible', str(cible), '--copier',
                       '--journal', str(d / '_corbeille_copies'),
                       '--json', str(d / 'sortie.json')])
        self.assertEqual(code, 0)
        self.assertTrue((cible / '2024' / 'a.jpg').is_file())
        s = json.loads((d / 'sortie.json').read_text(encoding='utf-8'))
        self.assertEqual(s['compte']['copie'], 1)
        self.assertTrue(s['journal'])

    def test_le_journal_ne_TOMBE_PAS_dans_le_dossier_du_projet(self):
        # Rouge observe le 27/08 : un test a ecrit un journal a la racine du
        # projet, et l'agent git l'a committe. Un test qui touche le projet
        # est un test qui salit.
        d = Path(tempfile.mkdtemp(prefix="test_cop6_"))
        export(d, {'Photos from 2024/a.jpg': 10})
        r = rapport_google(d / 'r.json', [
            {'nom': 'a.jpg', 'octets': 10,
             'chemin_google': str(d / 'Photos from 2024/a.jpg')}])
        C.main(['--rapport', r, '--cible', str(d / '_A TRIER' / 'T'),
                '--copier', '--journal', str(d / '_corbeille_copies')])
        self.assertTrue((d / '_corbeille_copies').is_dir())
        # Le dossier du PROJET n'a rien recu de ce test.
        recus = list((C.RACINE / '_corbeille_copies').glob('*.jsonl')) \
            if (C.RACINE / '_corbeille_copies').is_dir() else []
        for f in recus:
            self.assertLess(f.stat().st_mtime, time.time() - 5, str(f))

    def test_un_rapport_introuvable_ne_tombe_pas(self):
        self.assertEqual(C.main(['--rapport', '/nexistepas.json']), 2)


class LaRegleMotionPhoto(unittest.TestCase):
    """Regle PRODUIT du 08/09 : on ne rapatrie pas les videos de Motion Photo.

    Mesuree sur le vrai rapport avant d'etre ecrite : sur 13 905 entrees,
    3 114 videos, dont 1 972 portent la tige d'une photo du meme dossier
    Google. Les 1 142 autres sont de vraies videos et doivent passer."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="test_mp_"))

    def _rapport(self, medias, verdict='ABSENT'):
        c = self.d / 'r.json'
        c.write_text(json.dumps({'par_verdict': {verdict: medias}}),
                     encoding='utf-8')
        return str(c)

    def _m(self, rel, octets=10):
        return {'nom': os.path.basename(rel), 'octets': octets,
                'chemin_google': str(self.d / rel)}

    def test_la_video_jumelle_d_une_photo_est_ecartee(self):
        r = self._rapport([self._m('Photos from 2026/20260722_223506.jpg'),
                           self._m('Photos from 2026/20260722_223506.MP4')])
        ec = []
        gardes = C.absentes(r, ('ABSENT',), 0, ecartees=ec)
        noms = sorted(os.path.basename(x['chemin_google']) for x in gardes)
        self.assertEqual(noms, ['20260722_223506.jpg'])
        self.assertEqual(len(ec), 1)

    def test_une_VRAIE_video_passe(self):
        # Pas de photo de meme tige : ce n'est pas une Motion Photo.
        r = self._rapport([self._m('Photos from 2026/vacances.mp4')])
        ec = []
        gardes = C.absentes(r, ('ABSENT',), 0, ecartees=ec)
        self.assertEqual(len(gardes), 1)
        self.assertEqual(ec, [])

    def test_la_photo_doit_etre_dans_le_MEME_dossier(self):
        # Deux annees differentes : l'homonymie ne prouve pas la paire.
        r = self._rapport([self._m('Photos from 2025/IMG_1.jpg'),
                           self._m('Photos from 2026/IMG_1.mp4')])
        ec = []
        gardes = C.absentes(r, ('ABSENT',), 0, ecartees=ec)
        self.assertEqual(len(gardes), 2)
        self.assertEqual(ec, [])

    def test_la_photo_temoin_peut_vivre_dans_un_AUTRE_verdict(self):
        # Le cas reel : la photo est CERTAIN (le NAS l'a) et seule la video
        # sort en ABSENT. Ne regarder que la recolte la rendrait invisible.
        c = self.d / 'r.json'
        c.write_text(json.dumps({'par_verdict': {
            'CERTAIN': [self._m('Photos from 2026/x.jpg')],
            'ABSENT': [self._m('Photos from 2026/x.MP4')]}}),
            encoding='utf-8')
        ec = []
        gardes = C.absentes(str(c), ('ABSENT',), 0, ecartees=ec)
        self.assertEqual(gardes, [])
        self.assertEqual(len(ec), 1)

    def test_l_option_avec_motion_photo_les_garde(self):
        r = self._rapport([self._m('Photos from 2026/a.jpg'),
                           self._m('Photos from 2026/a.mp4')])
        ec = []
        gardes = C.absentes(r, ('ABSENT',), 0, avec_motion_photo=True,
                            ecartees=ec)
        self.assertEqual(len(gardes), 2)
        self.assertEqual(ec, [])

    def test_ce_que_NOUS_avons_strippe_n_est_pas_rapatrie(self):
        # Le NAS est plus petit parce que le bat 42 lui a retire la video.
        # Google ne porte pas une meilleure IMAGE : il porte la video jetee.
        # Mesure du 09/09 : sur la recolte reelle du bat 33 (1 913 medias),
        # ce filtre rend exactement les 99 gardes et les 1 814 ecartes que
        # Mike avait tries a la main, sans un seul desaccord.
        m = self.d / 'manifeste.json'
        m.write_text(json.dumps({'faits': {
            'N:\\Photos\\2026\\20260722_223506.jpg': {'octets': 1}}}),
            encoding='utf-8')
        r = self._rapport([self._m('Photos from 2026/20260722_223506.jpg'),
                           self._m('Photos from 2026/autre.jpg')])
        ec = []
        st = C.noms_strippes(m)
        gardes = C.absentes(r, ('ABSENT',), 0, ecartees=ec, strippes=st)
        noms = [os.path.basename(x['chemin_google']) for x in gardes]
        self.assertEqual(noms, ['autre.jpg'])
        self.assertEqual(len(ec), 1)

    def test_le_manifeste_se_compare_par_NOM(self):
        # Chemins NAS d'un cote, chemins Google de l'autre : seul le nom de
        # fichier peut les rapprocher. La limite est assumee et documentee.
        m = self.d / 'manifeste.json'
        m.write_text(json.dumps({'faits': {'N:/Photos/2026/X.JPG': 1}}),
                     encoding='utf-8')
        self.assertEqual(C.noms_strippes(m), {'x.jpg'})

    def test_un_manifeste_absent_ou_casse_ne_FILTRE_RIEN(self):
        # Il ne doit jamais ecarter par accident : sans preuve, on rapatrie.
        self.assertEqual(C.noms_strippes(self.d / 'nexistepas.json'), set())
        casse = self.d / 'casse.json'
        casse.write_text('{ pas du json', encoding='utf-8')
        self.assertEqual(C.noms_strippes(casse), set())

    def test_la_regle_n_efface_JAMAIS_rien(self):
        # Elle decide ce qu'on RAPATRIE. Le fichier Google reste ou il est.
        export(self.d, {'Photos from 2026/a.jpg': 10,
                        'Photos from 2026/a.mp4': 10})
        r = self._rapport([self._m('Photos from 2026/a.jpg'),
                           self._m('Photos from 2026/a.mp4')])
        C.main(['--rapport', r, '--cible', str(self.d / '_A TRIER' / 'T'),
                '--copier', '--journal', str(self.d / '_corbeille_copies')])
        self.assertTrue((self.d / 'Photos from 2026/a.mp4').exists())


if __name__ == '__main__':
    unittest.main(verbosity=0)
