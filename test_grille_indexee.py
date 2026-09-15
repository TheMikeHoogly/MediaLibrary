#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La grille RECURSIVE sort de l'index, plus de la marche sur le NAS.

CE QUI A CHANGE, ET POURQUOI

`/files?dir=1&rec=1` marchait sur le partage SMB pour retrouver les 44 483
fichiers du fonds : 16,8 s d'horloge pour 1,1 s de CPU -- 94 % d'attente
pure. L'index connait les MEMES photos et repond en 0,31 s. Le controle qui
a ouvert le chantier (`mesure_ecart_index_marche.py`, 13/09 22 h 32) a
compare les deux cote a cote : 44 483 clefs, 44 483 fichiers, zero d'un cote,
zero de l'autre.

CE QUE CES BANCS TIENNENT

Le risque de ce changement n'est pas la vitesse, c'est le NOM AFFICHE. Le
parcours l'obtenait par `f.relative_to(folder)` ; une clef d'index ne peut pas
emprunter ce chemin -- elle garde la casse du NAS (`\\\\NAS-Bremblens\\...`)
quand `folder` sort d'un `resolve()` qui MINUSCULE le nom d'hote SMB.
`relative_to` comparerait des segments differents et leverait, ou pire, la
comparaison se ferait sur `_pkey` et la page afficherait des noms de fichiers
tout en minuscules. `_nom_relatif` compare sur `_pkey` et DECOUPE sur la
chaine d'origine : ces bancs l'executent pour de vrai.

POURQUOI `PureWindowsPath` EST INJECTE

`Path(r'\\\\NAS\\x.jpg').is_absolute()` est FAUX sous Linux : un banc qui
laisse `Path` tel quel mesure la PLATEFORME au lieu de la regle (le meme
piege que `test_galerie_enrichissement.py`). Les fonctions extraites recoivent
donc un `Path` qui est toujours celui de Windows.

`server.py` n'est pas importe : cela ouvrirait `photos.db`, dont le serveur est
l'ecrivain unique.

USAGE
    python test_grille_indexee.py
"""

import ast
import unittest
from functools import lru_cache
from pathlib import Path, PureWindowsPath

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
LIGNES = SOURCE.splitlines(True)


def _source_de(nom):
    n = [x for x in ast.walk(ARBRE)
         if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
         and x.name == nom]
    if not n:
        raise AssertionError('fonction absente de server.py : %s' % nom)
    n = n[0]
    return ''.join(LIGNES[n.lineno - 1:n.end_lineno])


def _constante(nom):
    for x in ARBRE.body:
        if isinstance(x, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id == nom for c in x.targets):
            return ast.literal_eval(x.value)
    raise AssertionError('constante absente de server.py : %s' % nom)


def _atelier():
    """Un espace de noms ou les fonctions extraites ont leurs dependances.

    Une fonction de prod arrachee a son module ne tourne que si on lui rend
    ce qu'elle appelle -- quatre bancs sont tombes cette semaine pour l'avoir
    oublie. Les stubs rendent une valeur RECONNAISSABLE : un banc qui passe
    avec `None` partout ne prouve rien."""
    ns = {'Path': PureWindowsPath, 'PurePath': PureWindowsPath,
          'lru_cache': lru_cache}

    @lru_cache(maxsize=None)
    def _pkey_chaine(p):
        return PureWindowsPath(p).as_posix().lower()

    def _pkey(p):
        if type(p) is str:
            return _pkey_chaine(p)
        if isinstance(p, PureWindowsPath):
            return _pkey_chaine(str(p))
        return PureWindowsPath(p).as_posix().lower()

    ns['_pkey'] = _pkey
    ns['_pkey_chaine'] = _pkey_chaine
    ns['human_size'] = lambda o: 'T:%d' % o
    ns['_url_for_key'] = lambda k, roots=None: (
        None if 'SANS_URL' in k else '/media/0/' + _pkey(k))
    ns['_lien_dossier_memo'] = lambda k, roots, memo: ('LBL', 'GURL')
    ns['_epoch_precis'] = lambda k, e: e.get('ep')
    ns['_best_time_depuis'] = lambda k, e, ep: ('BT', k, ep)
    ns['_jour_depuis'] = lambda ep: ('JOUR', ep)
    ns['_faits_pour'] = lambda k, e, ctx: ('FAITS', k, ctx)
    exec(_source_de('_nom_relatif'), ns)
    exec(_source_de('_fiche_depuis_cle'), ns)
    import time as _time
    ns['time'] = _time
    exec(_source_de('_fiche_chronometree'), ns)
    exec(_source_de('_fiche_legere'), ns)
    ns['CHAMPS_DIFFERES'] = _constante('CHAMPS_DIFFERES')
    return ns


ATELIER = _atelier()
NOM = ATELIER['_nom_relatif']
FICHE = ATELIER['_fiche_depuis_cle']
PKEY = ATELIER['_pkey']

RACINE = r'\\NAS-Bremblens\home\Photos'
# Ce que `folder.resolve()` donne : l'hote SMB MINUSCULE. C'est tout le piege.
PREF = PKEY(r'\\nas-bremblens\home\Photos')


class LeNomGardeSaCasse(unittest.TestCase):

    def test_le_chemin_relatif_est_rendu_dans_sa_casse_d_origine(self):
        k = RACINE + r'\Photos Papa\2004\Cumple5MaJose09.jpg'
        self.assertEqual(NOM(k, PREF), 'Photos Papa/2004/Cumple5MaJose09.jpg')

    def test_la_casse_de_l_hote_ne_l_empeche_pas_de_reconnaitre_le_prefixe(self):
        """La clef dit `NAS-Bremblens`, le prefixe dit `nas-bremblens` : sans
        la comparaison sur `_pkey`, la photo perdrait son chemin et 44 000
        fiches s'appelleraient toutes par leur seul nom de fichier."""
        k = RACINE + r'\Photos Mike\2022\IMG_0001.jpg'
        self.assertEqual(NOM(k, PREF), 'Photos Mike/2022/IMG_0001.jpg')
        self.assertNotEqual(NOM(k, PREF), NOM(k, PREF).lower())

    def test_un_sous_dossier_ouvert_coupe_plus_court(self):
        k = RACINE + r'\Photos Papa\2004\x.jpg'
        self.assertEqual(NOM(k, PKEY(RACINE + r'\Photos Papa')), '2004/x.jpg')

    def test_sans_prefixe_c_est_le_nom_nu(self):
        k = RACINE + r'\Photos Papa\2004\x.jpg'
        self.assertEqual(NOM(k, None), 'x.jpg')
        self.assertEqual(NOM(k, ''), 'x.jpg')

    def test_une_clef_hors_du_dossier_rend_le_nom_nu_et_ne_decoupe_PAS(self):
        """Le repli doit etre un nom, jamais une decoupe au hasard : une
        chaine tronquee a un decalage qui ne lui correspond pas donnerait un
        `name` mutile, donc un lien et un tri faux."""
        k = r'\\AUTRE-NAS\home\Photos\a\x.jpg'
        self.assertEqual(NOM(k, PREF), 'x.jpg')

    def test_une_clef_d_uploads_relative_rend_le_nom_nu(self):
        self.assertEqual(NOM('Camera/x.jpg', PREF), 'x.jpg')

    def test_le_prefixe_ne_mord_pas_sur_un_dossier_voisin(self):
        """`Photos Papa` ne doit pas capturer `Photos Papa BIS` : sans le
        `/` ajoute au prefixe, la decoupe partirait au milieu d'un nom."""
        pref = PKEY(RACINE + r'\Photos Papa')
        k = RACINE + r'\Photos Papa BIS\x.jpg'
        self.assertEqual(NOM(k, pref), 'x.jpg')

    def test_une_longueur_qui_change_fait_replier_au_lieu_de_decouper(self):
        """`'I'.lower()` rend DEUX caracteres : le decalage mesure sur la
        forme normalisee ne vaut alors plus sur la chaine d'origine. Aucun nom
        du fonds n'est dans ce cas -- c'est la supposition qu'on verifie au
        lieu de la croire."""
        k = RACINE + '\\Photos \u0130stanbul\\x.jpg'
        self.assertNotEqual(len(PKEY(k)), len(str(k).replace('\\', '/')))
        self.assertEqual(NOM(k, PREF), 'x.jpg')


class LaFicheSortDeLEntree(unittest.TestCase):

    def setUp(self):
        self.k = RACINE + r'\Photos Papa\2004\x.jpg'
        self.e = {'size': 1234, 'mtime': 42.0, 'ep': 99,
                  'kw_fr': ['fete', 'chien'], 'kw_en': ['dog', 'fete'],
                  'gps': [1.0, 2.0], 'desc': 'une description'}

    def test_elle_porte_ce_que_la_page_attend(self):
        f = FICHE(self.k, self.e, 'CTX', ['r'], {}, PREF)
        self.assertEqual(f['name'], 'Photos Papa/2004/x.jpg')
        self.assertEqual(f['key'], self.k)
        self.assertEqual(f['size'], 'T:1234')
        self.assertEqual(f['mtime'], 42.0)
        self.assertEqual(f['_ep'], 99)
        self.assertEqual(f['taken'], ('BT', self.k, 99))
        self.assertEqual(f['jour'], ('JOUR', 99))
        self.assertEqual(f['faits'], ('FAITS', self.k, 'CTX'))
        self.assertEqual(f['gps'], [1.0, 2.0])
        self.assertEqual(f['desc'], 'une description')
        self.assertEqual(f['folder'], 'LBL')
        self.assertEqual(f['gurl'], 'GURL')

    def test_les_champs_sont_EXACTEMENT_ceux_du_chemin_du_NAS(self):
        """Le client rend les deux grilles avec le meme code : un champ en
        moins ici, et c'est une colonne vide qu'aucune erreur n'annonce."""
        attendus = {'name', 'key', 'url', 'size', 'mtime', 'taken', 'jour',
                    '_ep', 'faits', 'kw', 'gps', 'desc', 'folder', 'gurl'}
        self.assertEqual(set(FICHE(self.k, self.e, 'C', [], {}, PREF)),
                         attendus)

    def test_les_mots_cles_sont_dedoublonnes_en_gardant_l_ordre(self):
        f = FICHE(self.k, self.e, 'C', [], {}, PREF)
        self.assertEqual(f['kw'], ['fete', 'chien', 'dog'])

    def test_une_entree_vide_ne_leve_pas_et_ne_ment_pas(self):
        """Une photo indexee par le scan mais pas encore taguee n'a ni
        `size`, ni `kw`, ni `desc`. Elle doit s'afficher quand meme."""
        f = FICHE(self.k, {}, 'C', [], {}, PREF)
        self.assertEqual(f['size'], 'T:0')
        self.assertEqual(f['mtime'], 0)
        self.assertEqual(f['kw'], [])
        self.assertEqual(f['desc'], '')
        self.assertIsNone(f['gps'])

    def test_une_clef_sans_URL_servable_est_ECARTEE(self):
        """Une racine retiree de `dossiers_a_taguer.txt` laisse ses clefs dans
        l'index. Les afficher donnerait des vignettes cassees."""
        self.assertIsNone(
            FICHE(RACINE + r'\SANS_URL\x.jpg', self.e, 'C', [], {}, PREF))

    def test_le_lien_de_dossier_est_demande_par_DOSSIER(self):
        """Le memo appartient a la page : deux photos d'un meme dossier
        doivent partager UN appel. 44 483 appels pour quelques centaines de
        reponses, c'est la redite que le 12/09 avait deja payee ailleurs."""
        recus = []
        ns = dict(ATELIER)
        ns['_lien_dossier_memo'] = lambda k, roots, memo: (
            recus.append(memo) or ('LBL', 'GURL'))
        exec(_source_de('_fiche_depuis_cle'), ns)
        memo = {}
        for i in range(5):
            ns['_fiche_depuis_cle'](
                RACINE + r'\Photos Papa\2004\x%d.jpg' % i,
                self.e, 'C', [], memo, PREF)
        self.assertEqual(len(recus), 5)
        # Le meme objet a chaque fois : une fiche qui fabriquerait son propre
        # memo en rendrait un NEUF, et la memoisation ne servirait jamais --
        # une panne muette, qui ne se verrait que sur l'horloge.
        self.assertTrue(all(m is memo for m in recus),
                        'la fiche ne transmet pas le memo de la page')


class LaPageNInterrogePlusLeNAS(unittest.TestCase):
    """Le gain est tout entier la : aucune de ces fonctions ne doit toucher au
    disque. Un `stat()` glisse dans la fiche rendrait, une photo a la fois,
    les 44 483 allers-retours SMB que ce chantier vient de couper."""

    def test_aucune_des_deux_fonctions_ne_touche_au_disque(self):
        interdits = {'stat', 'is_file', 'is_dir', 'exists', 'iterdir',
                     'scandir', 'walk', 'open', 'resolve'}
        for nom in ('_nom_relatif', '_fiche_depuis_cle'):
            arbre = ast.parse(_source_de(nom))
            vus = set()
            for n in ast.walk(arbre):
                if isinstance(n, ast.Call):
                    f = n.func
                    appel = (f.attr if isinstance(f, ast.Attribute)
                             else getattr(f, 'id', ''))
                    if appel in interdits:
                        vus.add(appel)
            self.assertEqual(vus, set(), '%s touche au disque : %r' % (nom, vus))



class LaFicheChronometreeRendLaMemeFiche(unittest.TestCase):
    """Un instrument qui change ce qu'il mesure ment : avec ou sans
    `chrono`, la fiche est la MEME, et les cinq postes sont remplis."""

    def test_meme_fiche_et_postes_remplis(self):
        cas = [(RACINE + r'\Photos Papa\2004\x.jpg',
                {'size': 5, 'ep': 3, 'kw_fr': ['a'], 'kw_en': ['a', 'b']}),
               (RACINE + r'\p.jpg', {}),
               (RACINE + r'\SANS_URL.jpg', {'size': 1})]
        chrono = {}
        for k, e in cas:
            self.assertEqual(FICHE(k, e, 'C', [], {}, PREF, chrono=chrono),
                             FICHE(k, e, 'C', [], {}, PREF))
        self.assertEqual(set(chrono),
                         {'url', 'dossier', 'dates', 'faits', 'reste'})
        self.assertTrue(all(v >= 0 for v in chrono.values()))

    def test_sans_url_seul_le_poste_url_compte(self):
        chrono = {}
        self.assertIsNone(FICHE(RACINE + r'\SANS_URL.jpg', {}, 'C', [], {},
                                PREF, chrono=chrono))
        self.assertEqual(set(chrono), {'url'})


class LaFicheLegerePlusSonComplement(unittest.TestCase):
    """15/09 : la grille du fonds entier envoie des fiches LEGERES, et
    `/api/fiches` rend le reste. Leur union doit etre la fiche entiere --
    un champ oublie des deux cotes serait une colonne vide sans erreur."""

    def setUp(self):
        self.legere = ATELIER['_fiche_legere']
        self.differes = ATELIER['CHAMPS_DIFFERES']

    def test_legere_plus_complement_egale_entiere(self):
        for k, e in ((RACINE + r'\Photos Papa\2004\x.jpg',
                      {'size': 5, 'mtime': 7, 'ep': 3, 'gps': [1, 2],
                       'desc': 'd', 'kw_fr': ['a'], 'kw_en': ['a', 'b']}),
                     (RACINE + r'\p.jpg', {})):
            entiere = FICHE(k, e, 'C', [], {}, PREF)
            union = dict(self.legere(k, e, PREF))
            union.update({c: entiere[c] for c in self.differes})
            self.assertEqual(union, entiere)

    def test_les_deux_parts_ne_se_recouvrent_pas(self):
        leg = set(self.legere(RACINE + r'\p.jpg', {}, PREF))
        self.assertFalse(leg & set(self.differes))

    def test_la_legere_ne_fabrique_ni_url_ni_faits(self):
        """Tout l'interet : ces trois appels pesaient 1,76 s sur 3,09."""
        fn = [n for n in ast.walk(ARBRE) if isinstance(n, ast.FunctionDef)
              and n.name == '_fiche_legere'][0]
        appels = {x.func.id for x in ast.walk(fn)
                  if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)}
        self.assertFalse(appels & {'_url_for_key', '_lien_dossier_memo',
                                   '_faits_pour'})

    def test_une_cle_sans_URL_reste_dans_la_legere(self):
        """Le tri se fait sur la legere : la cle sans URL y est, et c'est
        `/api/fiches` qui la dit `url: null`."""
        k = RACINE + r'\SANS_URL.jpg'
        self.assertIsNone(FICHE(k, {}, 'C', [], {}, PREF))
        self.assertEqual(self.legere(k, {}, PREF)['key'], k)

if __name__ == '__main__':
    unittest.main(verbosity=2)
