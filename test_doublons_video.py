#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le bat 36 sait enfin comparer une VIDEO.

POURQUOI

`verifier_doublons_atrier.py` compare par `exiftool -ImageDataHash` : les
PIXELS. Une video n'en a pas, donc elle etait invisible a l'outil -- et les 19
doublons video de la racine de `_A TRIER` etaient increvables (ROADMAP A7).
Qualifies a la main le 13/09 : 14 ont la meme taille que leur homonyme du
fonds, tete et milieu identiques, seule la remorque de metadonnees differe ;
les 5 autres ont le fonds PLUS LONG (+4 ms a +1,43 s), la copie d'`_A TRIER`
est tronquee. Ce banc tient la regle qui reproduit ces deux verdicts.

CE QU'IL TIENT, ET CE QU'IL REFUSE DE LAISSER PASSER

  - la remorque de metadonnees ne doit PAS empecher de reconnaitre un
    doublon (c'est tout le motif de l'empreinte tete+milieu) ;
  - un flux DIFFERENT ne doit jamais devenir un doublon ;
  - « le fonds est plus long » n'est pas applique tout seul : c'est un
    jugement sur laquelle des deux copies vaut, et un outil qui tranche un
    arbitrage a coute 68 photos le 13/09 ;
  - la regle des noms humains tient aussi sur les videos (CLAUDE.md n. 2).

`exiftool` n'est pas lance : les durees sont injectees. Ce banc mesure la
REGLE, pas la capacite d'exiftool a lire un mp4 -- qu'aucun fichier fabrique
ici ne serait de toute facon.

USAGE
    python test_doublons_video.py
"""

import io
import os
import tempfile
import unittest
from pathlib import Path

import verifier_doublons_atrier as V


def ecrire(chemin, debut, milieu, queue, taille):
    """Un fichier de `taille` octets : un debut, un milieu, une queue."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    corps = bytearray(b'\0' * taille)
    corps[0:len(debut)] = debut
    m = taille // 2
    corps[m:m + len(milieu)] = milieu
    if queue:
        corps[taille - len(queue):] = queue
    chemin.write_bytes(bytes(corps))
    return str(chemin)


class LEmpreinteIgnoreLaRemorque(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.bloc = V.BLOC
        V.BLOC = 64            # meme regle, fichiers de banc

    def tearDown(self):
        V.BLOC = self.bloc
        self.tmp.cleanup()

    def test_le_bloc_de_prod_est_UN_Mo(self):
        """Lire 2 Mo par fichier sur SMB est tenable ; hasher 4 Go ne l'est
        pas. Le banc baisse le bloc, la prod ne doit pas avoir suivi."""
        self.assertEqual(self.bloc, 1 << 20)

    def test_meme_debut_meme_milieu_queue_differente_MEME_empreinte(self):
        a = ecrire(self.d / 'a.mp4', b'DEBUT', b'MILIEU', b'AAAA', 1000)
        b = ecrire(self.d / 'b.mp4', b'DEBUT', b'MILIEU', b'ZZZZ', 1000)
        self.assertEqual(V.empreinte_flux(a), V.empreinte_flux(b))

    def test_un_MILIEU_different_change_l_empreinte(self):
        a = ecrire(self.d / 'a.mp4', b'DEBUT', b'MILIEU', b'AAAA', 1000)
        b = ecrire(self.d / 'b.mp4', b'DEBUT', b'AUTRE.', b'AAAA', 1000)
        self.assertNotEqual(V.empreinte_flux(a), V.empreinte_flux(b))

    def test_une_taille_differente_change_l_empreinte(self):
        """La taille EST dans l'empreinte : c'est elle qui separe « doublon »
        de « tronquee », les deux verdicts du 13/09."""
        a = ecrire(self.d / 'a.mp4', b'DEBUT', b'MILIEU', b'AAAA', 1000)
        b = ecrire(self.d / 'b.mp4', b'DEBUT', b'MILIEU', b'AAAA', 900)
        self.assertNotEqual(V.empreinte_flux(a), V.empreinte_flux(b))

    def test_un_fichier_absent_ne_leve_pas(self):
        self.assertIsNone(V.empreinte_flux(str(self.d / 'pas_la.mp4')))


class LesDeuxVerdicts(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.bloc, V.BLOC = V.BLOC, 64
        self.vraies_durees = V.durees
        self.D = {}
        V.durees = lambda exe, chemins, log=None: {
            V.hkey(c): self.D.get(V.hkey(c), (0.0, '1920x1080'))
            for c in chemins}

    def tearDown(self):
        V.BLOC = self.bloc
        V.durees = self.vraies_durees
        self.tmp.cleanup()

    def duree(self, chemin, secondes):
        self.D[V.hkey(chemin)] = (secondes, '1920x1080')

    def test_le_cas_des_14_meme_flux_remorque_differente(self):
        dup = ecrire(self.d / '_A TRIER' / 'v.mp4', b'D', b'M', b'AAAA', 1000)
        canon = ecrire(self.d / 'Photos Mike' / '2025' / 'v.mp4',
                       b'D', b'M', b'ZZZZ', 1000)
        self.duree(dup, 12.0)
        self.duree(canon, 12.0)
        c, t, g = V.comparer_videos('exiftool', [dup], [canon], {})
        self.assertEqual([e['dup'] for e in c], [dup])
        self.assertEqual(c[0]['canonique'], canon)
        self.assertEqual((t, g), ([], []))

    def test_le_cas_des_5_le_fonds_est_plus_long(self):
        dup = ecrire(self.d / '_A TRIER' / 'v.mp4', b'D', b'M', b'', 600)
        canon = ecrire(self.d / 'Photos Mike' / '2025' / 'v.mp4',
                       b'D', b'M', b'', 1000)
        self.duree(dup, 10.57)
        self.duree(canon, 12.0)
        c, t, g = V.comparer_videos('exiftool', [dup], [canon], {})
        self.assertEqual(c, [])
        self.assertEqual([e['dup'] for e in t], [dup])
        self.assertEqual(t[0]['duree_dup'], 10.57)
        self.assertEqual(t[0]['duree_canonique'], 12.0)

    def test_une_video_PLUS_LONGUE_ici_n_est_JAMAIS_un_doublon(self):
        """Le sens compte : si c'est la copie d'`_A TRIER` qui porte plus de
        video, la retirer perdrait la bonne version."""
        dup = ecrire(self.d / '_A TRIER' / 'v.mp4', b'D', b'M', b'', 1000)
        canon = ecrire(self.d / 'Photos Mike' / '2025' / 'v.mp4',
                       b'D', b'M', b'', 600)
        self.duree(dup, 12.0)
        self.duree(canon, 10.0)
        c, t, g = V.comparer_videos('exiftool', [dup], [canon], {})
        self.assertEqual((c, t), ([], []))
        self.assertEqual(len(g), 1)

    def test_un_flux_different_est_GARDE(self):
        dup = ecrire(self.d / '_A TRIER' / 'v.mp4', b'D', b'M', b'', 1000)
        canon = ecrire(self.d / 'Photos Mike' / '2025' / 'v.mp4',
                       b'X', b'Y', b'', 1000)
        self.duree(dup, 12.0)
        self.duree(canon, 12.0)
        c, t, g = V.comparer_videos('exiftool', [dup], [canon], {})
        self.assertEqual((c, t), ([], []))
        self.assertEqual(g[0]['pourquoi'], 'flux different')

    def test_sans_homonyme_dans_le_fonds_rien_n_est_teste(self):
        dup = ecrire(self.d / '_A TRIER' / 'v.mp4', b'D', b'M', b'', 1000)
        autre = ecrire(self.d / 'Photos Mike' / '2025' / 'w.mp4',
                       b'D', b'M', b'', 1000)
        self.assertEqual(V.comparer_videos('exiftool', [dup], [autre], {}),
                         ([], [], []))

    def test_un_NOM_HUMAIN_absent_de_la_canonique_retient_la_video(self):
        """CLAUDE.md n. 2 : un changement qui risque de perdre un nom est
        faux, quel que soit son gain. La regle valait deja pour les images."""
        dup = ecrire(self.d / '_A TRIER' / 'v.mp4', b'D', b'M', b'AAAA', 1000)
        canon = ecrire(self.d / 'Photos Mike' / '2025' / 'v.mp4',
                       b'D', b'M', b'ZZZZ', 1000)
        self.duree(dup, 12.0)
        self.duree(canon, 12.0)
        noms = {V.hkey(dup): {'personne:Florine'}, V.hkey(canon): set()}
        c, t, g = V.comparer_videos('exiftool', [dup], [canon], noms)
        self.assertEqual(c, [])
        self.assertEqual(g[0]['pourquoi'], 'nom absent de la canonique')

    def test_un_nom_PRESENT_des_deux_cotes_ne_retient_rien(self):
        dup = ecrire(self.d / '_A TRIER' / 'v.mp4', b'D', b'M', b'AAAA', 1000)
        canon = ecrire(self.d / 'Photos Mike' / '2025' / 'v.mp4',
                       b'D', b'M', b'ZZZZ', 1000)
        self.duree(dup, 12.0)
        self.duree(canon, 12.0)
        noms = {V.hkey(dup): {'personne:Florine'},
                V.hkey(canon): {'personne:Florine'}}
        c, _t, _g = V.comparer_videos('exiftool', [dup], [canon], noms)
        self.assertEqual(len(c), 1)


class LesVideosNeSontPasDesImages(unittest.TestCase):

    def test_les_deux_familles_d_extensions_sont_disjointes(self):
        self.assertEqual(V.IMAGE_EXT & V.VIDEO_EXT, set())

    def test_enum_videos_ne_ramasse_pas_les_images(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / 'a.jpg').write_bytes(b'x')
            (d / 'b.mp4').write_bytes(b'x')
            (d / '.cache').mkdir()
            (d / '.cache' / 'c.mp4').write_bytes(b'x')
            vus = [os.path.basename(p) for p in V.enum_videos(str(d))]
            self.assertEqual(vus, ['b.mp4'])


class LesCheminsACCENTUESArriventENTIERS(unittest.TestCase):
    """Le defaut le plus couteux trouve ce jour-la, et il depassait les
    videos.

    Les chemins partaient sur la LIGNE DE COMMANDE. Un chemin accentue y
    arrive mutile : exiftool repond « Error: File not found », le lot rend
    une entree de MOINS, et personne ne le voit. Une photo accentuee n'a donc
    pas d'empreinte, ne trouve jamais sa canonique, et tombe dans
    `homonymes_differents` -- la liste que `--homonymes-differents` peut
    RETIRER. Un fichier qu'on n'a pas su comparer s'y donnait pour un fichier
    compare et juge different.

    MESURE le 14/09, 8 accentues et 8 ascii pris dans l'index :
    ancien appel **0/8** contre **8/8** sur les accentues, **8/8 des deux
    cotes** sur les ascii (`mesure_exiftool_accents.py`). Et 3 714 cles sur
    44 477 -- **8,4 % du fonds** -- portent au moins un caractere hors ASCII.

    Ce banc ne lance pas exiftool : il verifie que les chemins ne passent
    PLUS par la ligne de commande, et qu'ils arrivent entiers dans le fichier
    d'arguments."""

    def setUp(self):
        self.vu = {}
        self.vraie_run = V.subprocess.run

        class Reponse:
            returncode = 0
            stdout = '[]'
            stderr = ''

        def faux_run(args, **kw):
            self.vu['args'] = list(args)
            # Le fichier d'arguments doit exister PENDANT l'appel.
            chemin = args[args.index('-@') + 1]
            self.vu['argfile'] = chemin
            self.vu['contenu'] = io.open(
                chemin, encoding='utf-8').read()
            return Reponse()

        V.subprocess.run = faux_run

    def tearDown(self):
        V.subprocess.run = self.vraie_run

    def test_aucun_chemin_ne_passe_par_la_ligne_de_commande(self):
        V.exiftool_json('exiftool.exe', ['-s3', '-j'],
                        [r'\\NAS\Photos Flo\2014 Grèce\x.jpg'])
        ligne = ' '.join(self.vu['args'])
        self.assertIn('-@', self.vu['args'])
        self.assertNotIn('Grèce', ligne)
        self.assertNotIn('x.jpg', ligne)

    def test_l_accent_arrive_ENTIER_dans_le_fichier_d_arguments(self):
        chemin = r'\\NAS\Photos Flo\2016 Indonésie\Voyage (2).mp4'
        V.exiftool_json('exiftool.exe', ['-s3', '-j'], [chemin])
        self.assertIn(chemin, self.vu['contenu'].splitlines())

    def test_le_charset_est_dit_a_exiftool(self):
        """Sans lui, exiftool relirait le fichier d'arguments dans la page de
        codes du systeme : le chemin serait entier dans le fichier et mutile
        a l'arrivee."""
        V.exiftool_json('exiftool.exe', ['-s3'], ['a.jpg'])
        lignes = self.vu['contenu'].splitlines()
        self.assertIn('-charset', lignes)
        self.assertIn('filename=UTF8', lignes)
        self.assertLess(lignes.index('-charset'), lignes.index('a.jpg'))

    def test_les_options_precedent_les_chemins(self):
        V.exiftool_json('exiftool.exe', ['-Duration#', '-j'], ['a.mp4'])
        lignes = self.vu['contenu'].splitlines()
        self.assertLess(lignes.index('-Duration#'), lignes.index('a.mp4'))

    def test_le_fichier_d_arguments_est_EFFACE_apres(self):
        V.exiftool_json('exiftool.exe', ['-j'], ['a.jpg'])
        self.assertFalse(os.path.exists(self.vu['argfile']))


class UnFichierSansEMPREINTENEstPasUnFichierDIFFERENT(unittest.TestCase):
    """La consequence a ne pas reintroduire : « je n'ai pas pu le comparer »
    et « je l'ai compare et il differe » doivent se distinguer, parce que la
    seconde autorise un retrait."""

    def test_image_hashes_SIGNALE_ce_qu_il_n_a_pas_pu_lire(self):
        vus = []
        vraie = V.exiftool_json
        V.exiftool_json = lambda exe, opts, lot, log=None: []
        try:
            V.image_hashes('exiftool.exe', ['a.jpg', 'b.jpg'], vus.append)
        finally:
            V.exiftool_json = vraie
        self.assertTrue(any('SANS empreinte' in m for m in vus), vus)


if __name__ == '__main__':
    unittest.main(verbosity=2)
