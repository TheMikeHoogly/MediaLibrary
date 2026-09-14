#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La page `/arbitrage` : deux versions d une meme photo, cote a cote.

POURQUOI ELLE EXISTE

Depuis le 14/09, les outils laissent `_A TRIER\\Google porte mieux` tranquille
(`rangement_annee.est_arbitrage`). C etait le but -- un outil ne tranche pas un
arbitrage -- mais la consequence est que **rien n en sort tant qu un humain n a
pas regarde**. Une protection sans regard est une salle qui se remplit.

CE QUE CES BANCS TIENNENT

  - l APPARIEMENT : chaque fichier de la salle doit retrouver son jumeau du
    fonds par NOM DE FICHIER, la meme regle que le bat 36 (le bat 33 ne
    renomme pas ce qu il rapatrie) -- et une salle SANS jumeau ne doit pas
    faire un cadre vide, elle doit le DIRE ;
  - le fait que la route ne touche NI au disque NI a exiftool pour ses
    chiffres : la duree d une video est deja dans l index, le scan l ecrit a
    l indexation. Le seul aller-retour NAS admis est le `exists()` ;
  - la page elle-meme : elle ne porte aucun bouton. Un bouton qui ne peut
    jamais aboutir est une promesse que l interface ne tiendra pas
    (CLAUDE.md n. 9), et le geste « la version de Google devient la
    canonique » n existe pas encore.

`server.py` n est pas importe (cela ouvrirait `photos.db`) : la fonction est
lue sur l ARBRE.

USAGE
    python test_arbitrage_page.py
"""

import ast
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
SOURCE = (ICI / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
PAGE = (ICI / 'ui' / 'pages' / 'arbitrage.html').read_text(encoding='utf-8')


def methode(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError('absente de server.py : ' + nom)


def code_sans_prose(nom):
    """Le CODE d une methode, docstring et commentaires retires.

    Le premier jet de ce banc lisait le texte brut, docstring comprise -- et
    il est tombe sur sa propre prose : la docstring dit « aucun exiftool » et
    nomme « Google porte mieux », les deux mots que les bancs ci-dessous
    interdisent. C est exactement la regle n. 6 de CLAUDE.md, ecrire
    l histoire d une erreur la refait. `ast.unparse` ne rend que le code.
    """
    fn = methode(nom)
    corps = list(fn.body)
    if (corps and isinstance(corps[0], ast.Expr)
            and isinstance(corps[0].value, ast.Constant)
            and isinstance(corps[0].value.value, str)):
        corps = corps[1:]
    return '\n'.join(ast.unparse(n) for n in corps)


SRC = code_sans_prose('_serve_arbitrage_list')


class LaRouteEstBranchee(unittest.TestCase):

    def test_la_page_et_son_api_sont_servies(self):
        self.assertIn("path == '/arbitrage'", SOURCE)
        self.assertIn("ui_page('arbitrage')", SOURCE)
        self.assertIn("path == '/api/arbitrage/list'", SOURCE)
        self.assertIn('self._serve_arbitrage_list()', SOURCE)

    def test_le_gabarit_existe_et_porte_la_barre_de_l_application(self):
        self.assertIn('<!--APPNAV-->', PAGE)
        self.assertIn('<!--UI:components-->', PAGE)


class ElleLitLINDEXPasLeDISQUE(unittest.TestCase):
    """Tout le prix d une page qui s ouvre vite : la duree d une video est
    DEJA dans l index (`{video: True, duree, taken}`, ecrit par le scan).
    Aller la redemander a exiftool couterait une lecture de media par ligne."""

    def test_la_duree_vient_de_l_entree(self):
        self.assertIn("e.get('duree')", SRC)

    def test_ni_exiftool_ni_lecture_de_media(self):
        for mot in ('exiftool', 'subprocess', 'ImageDataHash', 'open(',
                    'read()', 'empreinte_flux'):
            self.assertNotIn(mot, SRC, mot)

    def test_le_SEUL_acces_disque_est_un_exists(self):
        """Un `stat` par fichier serait deja trop : ici on demande seulement
        si le fichier est encore la, et il y en a une poignee."""
        appels = []
        for n in ast.walk(ast.parse(SRC.strip())):
            if isinstance(n, ast.Call):
                f = n.func
                appels.append(f.attr if isinstance(f, ast.Attribute)
                              else getattr(f, 'id', ''))
        for interdit in ('stat', 'scandir', 'walk', 'iterdir', 'glob',
                         'read_bytes', 'read_text'):
            self.assertNotIn(interdit, appels, interdit)
        self.assertIn('exists', appels)


class ElleAPPARIEParLeNOM(unittest.TestCase):

    def test_l_appariement_passe_par_la_regle_partagee(self):
        """`est_arbitrage` vit dans `rangement_annee` et personne ne la
        recopie -- c est la lecon des 68 photos du 13/09."""
        self.assertIn('_ra.est_arbitrage(', SRC)
        self.assertNotIn('Google porte mieux', SRC)

    def test_le_nom_est_normalise_avant_d_etre_compare(self):
        """`Path(k).name` brut ferait dependre l appariement de la CASSE, et
        les cles du NAS gardent la leur."""
        self.assertIn('_pkey(Path(cle).name)', SRC)
        self.assertIn('_pkey(Path(k).name)', SRC)

    def test_une_salle_SANS_jumeau_ne_leve_pas_et_se_DIT(self):
        self.assertIn("'nas': d", SRC)
        self.assertIn('if jumeaux else None', SRC)
        self.assertIn('rien &agrave; comparer', PAGE)

    def test_l_url_est_calculee_par_le_SERVEUR(self):
        """La refaire en JS serait un second assemblage de la meme regle."""
        self.assertIn('_url_for_key(cle, roots)', SRC)
        self.assertNotIn("'/media/'", PAGE)


class ElleNeTrancheRien(unittest.TestCase):
    """Le geste « la version de Google devient la canonique » n existe pas :
    la page ne doit donc porter AUCUN bouton (CLAUDE.md n. 9)."""

    def test_aucun_bouton_sur_la_page(self):
        self.assertNotIn('<button', PAGE)

    def test_la_route_n_ecrit_rien(self):
        for mot in ('STORE.set', 'STORE.save', 'ops.', 'shutil', 'os.remove',
                    'os.rename', 'FileOps'):
            self.assertNotIn(mot, SRC, mot)

    def test_le_verdict_automatique_se_borne_a_une_DUREE(self):
        """Une duree est un fait ; « la meilleure image » est un jugement.
        La page doit renvoyer l image a l oeil, et le dire."""
        self.assertIn("ecart_duree", PAGE)
        self.assertIn("a l oeil", PAGE)


class LePlancherDAccessibilite(unittest.TestCase):

    def test_focus_visible_est_fourni(self):
        self.assertIn(':focus-visible', PAGE)
        self.assertIn('outline: 2px solid var(--veilleuse)', PAGE)

    def test_mouvement_reduit(self):
        self.assertIn('prefers-reduced-motion: reduce', PAGE)

    def test_les_vignettes_sont_de_vrais_liens_avec_un_alt(self):
        self.assertIn('<a class="regard" href="', PAGE)
        self.assertIn('alt="', PAGE)

    def test_la_page_ne_REDECORE_pas_un_composant_canonique(self):
        """`.vue` est la cellule CARREE de la planche contact
        (`components.css` lui pose `aspect-ratio: 1`). Cette page l avait
        reutilisee : une photo en portrait tenait sur un cinquieme de la
        largeur d une boite carree. Un composant canonique se reutilise TEL
        QUEL ou se laisse tranquille."""
        canoniques = [c for c in ('.vue', '.cell', '.tuile', '.piece')
                      if c + ' ' in PAGE or c + ' {' in PAGE]
        self.assertEqual(canoniques, [], canoniques)

    def test_aucune_couleur_en_dur_hors_ombre(self):
        import re
        hex_ = re.findall(r'#[0-9A-Fa-f]{3,8}', PAGE)
        # Seule l ombre portee, comme sur les pages soeurs.
        self.assertEqual([h for h in hex_ if h != '#0008'], [], hex_)

    def test_pas_de_nombre_de_colonnes_en_dur(self):
        self.assertIn('repeat(auto-fit', PAGE)

    def test_l_etat_vide_est_REDIGE(self):
        self.assertIn('La salle est vide', PAGE)
        self.assertIn('n&rsquo;est plus sur le disque', PAGE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
