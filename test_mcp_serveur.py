"""Vérifications du serveur MCP en lecture seule.

Aucune ne touche le réseau, le NAS ni `photos.db` : le client HTTP est injecté.
Un banc qui exige le LAN ne tourne que chez Mike, et un banc qui ne tourne pas
n'est pas un banc.

Tout ce qui est IMPRIMÉ ici reste en ASCII : le banc lance les tests avec
PYTHONUTF8=1, l'agent git SANS, et le 22/08 un seul caractere hors cp1252 a fait
tomber 11 tests sur la console de Mike.
"""

import io
import json
import unittest

import mcp_serveur as M


# ───────────────────────────── le faux serveur ───────────────────────────────

class _Reponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def faux_client(reponses, base='http://test:8080'):
    """Un `ClientLecture` dont l'ouverture est simulee.

    `reponses` : chemin -> objet JSON, ou une exception a lever."""
    vues = []

    def ouvrir(requete, timeout=None):
        vues.append(requete)
        chemin = requete.full_url.split(base, 1)[-1].split('?')[0]
        valeur = reponses.get(chemin)
        if isinstance(valeur, Exception):
            raise valeur
        if valeur is None:
            raise AssertionError('le faux serveur ne connait pas ' + chemin)
        if isinstance(valeur, bytes):
            return _Reponse(valeur)
        return _Reponse(json.dumps(valeur).encode('utf-8'))

    c = M.ClientLecture(base=base, ouvrir=ouvrir)
    c.requetes_vues = vues
    return c


def _photos(n, prefixe='p'):
    return [{'key': '\\\\NAS\\%s%d.jpg' % (prefixe, i),
             'name': '%s%d.jpg' % (prefixe, i),
             'url': '/media/1/%s%d.jpg' % (prefixe, i),
             'crop_url': '/api/facecrop?k=%d' % i,
             'gurl': '/browse?dir=1',
             'folder': '2025',
             'i': i, 'sim': 0.5,
             'taken': 1700000000 + i,
             'desc': 'description %d' % i,
             'kw': ['mot%d' % j for j in range(20)]}
            for i in range(n)]


# ──────────────────────────────── protocole ──────────────────────────────────

class LeProtocole(unittest.TestCase):

    def test_initialize_se_nomme_et_annonce_sa_version(self):
        r = M.traiter({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}, None)
        self.assertEqual(r['id'], 1)
        self.assertEqual(r['result']['protocolVersion'], M.PROTOCOLE)
        self.assertEqual(r['result']['serverInfo']['name'], M.NOM_SERVEUR)
        self.assertIn('tools', r['result']['capabilities'])

    def test_une_notification_ne_recoit_AUCUNE_reponse(self):
        """Repondre a une notification casse les clients stricts, et le defaut
        ne se voit qu'a la poignee de main -- jamais dans un test d'outil."""
        r = M.traiter({'jsonrpc': '2.0',
                       'method': 'notifications/initialized'}, None)
        self.assertIsNone(r)

    def test_une_methode_inconnue_NOMME_celles_qui_existent(self):
        r = M.traiter({'jsonrpc': '2.0', 'id': 7, 'method': 'resources/list'},
                      None)
        self.assertEqual(r['error']['code'], -32601)
        self.assertIn('tools/list', r['error']['message'])

    def test_un_message_sans_methode_est_refuse(self):
        r = M.traiter({'jsonrpc': '2.0', 'id': 2}, None)
        self.assertEqual(r['error']['code'], -32600)

    def test_une_ligne_illisible_ne_tue_pas_la_session(self):
        """Un client qui bafouille une ligne doit pouvoir continuer : sinon un
        seul octet de travers coute toute la conversation."""
        entree = io.StringIO('ceci n est pas du json\n'
                             '{"jsonrpc":"2.0","id":9,"method":"ping"}\n')
        sortie = io.StringIO()
        servis = M.boucle(entree, sortie, None)
        self.assertEqual(servis, 2)
        lignes = [json.loads(l) for l in sortie.getvalue().splitlines()]
        self.assertEqual(lignes[0]['error']['code'], -32700)
        self.assertEqual(lignes[1]['id'], 9)

    def test_une_ligne_vide_est_ignoree_sans_reponse(self):
        sortie = io.StringIO()
        servis = M.boucle(io.StringIO('\n\n   \n'), sortie, None)
        self.assertEqual(servis, 0)
        self.assertEqual(sortie.getvalue(), '')

    def test_stdout_ne_porte_QUE_du_protocole(self):
        """Une seule ligne de diagnostic sur stdout casse le cadrage, et le
        client ne dit jamais pourquoi."""
        entree = io.StringIO(
            '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n'
            '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n')
        sortie = io.StringIO()
        M.boucle(entree, sortie, None)
        for ligne in sortie.getvalue().splitlines():
            json.loads(ligne)          # leve si une ligne n'est pas du JSON

    def test_tools_list_ne_fuit_pas_les_fonctions(self):
        """`handler` est un objet Python : le laisser dans la liste ferait lever
        `json.dumps` chez le premier client, et le serveur mourrait muet."""
        r = M.traiter({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'}, None)
        outils = r['result']['tools']
        self.assertEqual(len(outils), len(M.OUTILS))
        for o in outils:
            self.assertNotIn('handler', o)
        json.dumps(r)

    def test_chaque_outil_se_declare_en_LECTURE_seule(self):
        for o in M.OUTILS:
            self.assertTrue(o['name'].startswith('ml_'), o['name'])
            self.assertEqual(o['inputSchema']['type'], 'object', o['name'])
            self.assertTrue(o['annotations']['readOnlyHint'], o['name'])
            self.assertFalse(o['annotations']['destructiveHint'], o['name'])

    def test_un_outil_inconnu_rend_isError_pas_une_erreur_de_protocole(self):
        """La difference compte : une erreur JSON-RPC casse le client, un
        `isError` revient au modele, qui peut corriger son tir."""
        r = M.traiter({'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
                       'params': {'name': 'ml_effacer_tout'}}, None)
        self.assertNotIn('error', r)
        self.assertTrue(r['result']['isError'])
        self.assertIn('ml_chercher', r['result']['content'][0]['text'])

    def test_tools_call_sans_nom_est_une_erreur_de_parametre(self):
        r = M.traiter({'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call',
                       'params': {}}, None)
        self.assertEqual(r['error']['code'], -32602)


# ─────────────────────────────── lecture seule ───────────────────────────────

class LaFrontiere(unittest.TestCase):

    def test_le_client_REFUSE_un_chemin_hors_liste(self):
        c = faux_client({})
        with self.assertRaises(M.RefusDeLecture) as e:
            c.get('/api/people/rename', {'nom': 'x'})
        self.assertIn('lecture seule', str(e.exception))
        self.assertEqual(c.requetes_vues, [])   # rien n'est meme parti

    def test_le_client_n_emet_que_des_GET(self):
        c = faux_client({'/api/serveur': {'pid': 1}})
        c.get('/api/serveur')
        self.assertEqual([r.method for r in c.requetes_vues], ['GET'])

    def test_aucune_route_d_ECRITURE_n_est_permise(self):
        """Garde-fou pour le jour ou quelqu'un ajoutera une route : la liste des
        chemins permis est la frontiere, et elle doit rester lisible."""
        for interdit in ('/api/assign', '/api/undo', '/api/people/rename',
                         '/api/people/delete', '/api/maint/run',
                         '/api/files/delete', '/api/pets/untag'):
            self.assertNotIn(interdit, M.CHEMINS_PERMIS)

    def test_le_client_n_a_aucune_methode_d_ecriture(self):
        for interdit in ('post', 'put', 'delete', 'ecrire', 'requete'):
            self.assertFalse(hasattr(M.ClientLecture, interdit), interdit)


# ────────────────────────────── le plafond se dit ────────────────────────────

class LePlafond(unittest.TestCase):

    def test_tranche_dit_le_total_ce_qu_elle_montre_et_le_reste(self):
        t = M.tranche(list(range(100)), 10, 20)
        self.assertEqual((t['total'], t['debut'], t['montres'], t['reste']),
                         (100, 10, 20, 70))
        self.assertEqual(t['items'][0], 10)

    def test_tranche_borne_la_limite_meme_si_on_demande_l_infini(self):
        t = M.tranche(list(range(10000)), 0, 99999)
        self.assertEqual(t['montres'], M.LIMITE_MAX)
        self.assertEqual(t['total'], 10000)

    def test_photos_de_demande_son_maximum_a_la_route(self):
        """Second plafond muet trouve le 23/08, dans la route cette fois :
        sans `limit`, /api/people/photos rend exactement 2 000 photos pour
        Florine, qui en porte 5 919. Un compte tronque sans un mot."""
        c = faux_client({'/api/people/photos': {'photos': _photos(5919)}})
        out = M._photos_de(c, {'nom': 'Florine'})
        self.assertIn('limit=%d' % M.PLAFOND_PERSONNE, c.appels[0])
        self.assertEqual(out['total'], 5919)
        self.assertFalse(out['total_est_un_plancher'])

    def test_deux_mille_photos_rendent_vingt_items_et_DISENT_deux_mille(self):
        """Le cas mesure le 23/08 : /api/people/photos rend 1 371 872 octets
        d'un coup. Un agent qui recoit 20 photos sans le total croit tenir la
        reponse entiere."""
        c = faux_client({'/api/people/photos': {'photos': _photos(2000)}})
        out = M._photos_de(c, {'nom': 'Mike'})
        self.assertEqual(out['montres'], 20)
        self.assertEqual(out['total'], 2000)
        self.assertEqual(out['reste'], 1980)

    def test_la_reponse_coupee_tient_dans_un_contexte(self):
        """Mesure, pas intention : 20 photos du fonds ne doivent pas peser des
        dizaines de milliers d'octets."""
        c = faux_client({'/api/people/photos': {'photos': _photos(2000)}})
        out = M._photos_de(c, {'nom': 'Mike'})
        octets = len(json.dumps(out, ensure_ascii=False))
        self.assertLess(octets, 8000, 'sortie trop lourde : %d octets' % octets)

    def test_photo_courte_jette_ce_qui_ne_s_adresse_qu_a_une_interface(self):
        p = M.photo_courte(_photos(1)[0])
        for parti in ('crop_url', 'gurl', 'folder', 'i', 'sim', 'url'):
            self.assertNotIn(parti, p)
        self.assertIn('cle', p)
        self.assertIn('desc', p)
        self.assertEqual(len(p['mots']), 8)     # 20 mots-cles coupes a 8

    def test_debut_pagine_vraiment(self):
        c = faux_client({'/api/people/photos': {'photos': _photos(50)}})
        a = M._photos_de(c, {'nom': 'Mike', 'limite': 5})
        b = M._photos_de(c, {'nom': 'Mike', 'limite': 5, 'debut': 5})
        self.assertNotEqual([p['cle'] for p in a['items']],
                            [p['cle'] for p in b['items']])
        self.assertEqual(b['items'][0]['nom'], 'p5.jpg')

    def test_chercher_demande_le_PLAFOND_de_la_route_pas_ce_qu_il_montre(self):
        """Defaut trouve en observant le vrai serveur le 23/08 : en demandant
        `n=5`, l'outil annoncait « 5 trouvees » pour espece:chat, un axe qui en
        porte 2 386. Le compte doit venir du FONDS, la coupe de l'outil."""
        c = faux_client({'/api/search': {'results': _photos(300)}})
        out = M._chercher(c, {'q': 'chat', 'limite': 5})
        self.assertIn('n=%d' % M.PLAFOND_RECHERCHE, c.appels[0])
        self.assertEqual(out['total'], 300)
        self.assertEqual(out['montres'], 5)

    def test_un_total_sous_le_plafond_n_est_PAS_un_plancher(self):
        c = faux_client({'/api/search': {'results': _photos(300)}})
        out = M._chercher(c, {'q': 'chat'})
        self.assertFalse(out['total_est_un_plancher'])
        self.assertNotIn('note', out)

    def test_une_route_qui_plafonne_le_DIT(self):
        """1 500 lignes rendues, c'est peut-etre 1 500 photos, peut-etre
        20 000. Un total qui ne distingue pas les deux se lit comme un
        inventaire."""
        c = faux_client({'/api/search': {'results': _photos(M.PLAFOND_RECHERCHE)}})
        out = M._chercher(c, {'q': 'espece:chat'})
        self.assertTrue(out['total_est_un_plancher'])
        self.assertIn('AU MOINS', out['note'])

    def test_semblables_declare_aussi_son_plafond(self):
        c = faux_client({'/api/similar': {'results': _photos(M.PLAFOND_SEMBLABLES)}})
        out = M._semblables(c, {'cle': 'k'})
        self.assertTrue(out['total_est_un_plancher'])
        self.assertIn('/api/similar', out['note'])


# ──────────────────────────── ce que l'agent doit voir ───────────────────────

class CeQueLAgentDoitVoir(unittest.TestCase):

    def test_chercher_dit_ce_que_le_serveur_a_COMPRIS_de_la_requete(self):
        """Cas reel du 23/08 : `personne:Luna` est reparti en semantique, le
        serveur l'a rendu dans `reste`. Sans ce champ, un agent croit avoir
        filtre alors qu'il a cherche des mots."""
        c = faux_client({'/api/search': {
            'results': _photos(3), 'reste': 'personne:Luna',
            'noms': [], 'lieux': [], 'periode': '', 'especes': []}})
        out = M._chercher(c, {'q': 'personne:Luna'})
        self.assertEqual(out['reste_requete'], 'personne:Luna')
        self.assertEqual(out['axes']['noms'], [])

    def test_chercher_montre_les_axes_reconnus(self):
        c = faux_client({'/api/search': {
            'results': _photos(2), 'reste': '',
            'noms': ['Florine'], 'lieux': ['Bremblens'],
            'periode': '2019', 'especes': ['chat']}})
        out = M._chercher(c, {'q': 'Florine Bremblens 2019 espece:chat'})
        self.assertEqual(out['axes']['especes'], ['chat'])
        self.assertEqual(out['axes']['periode'], '2019')
        self.assertEqual(out['reste_requete'], '')

    def test_un_animal_demande_parmi_les_personnes_est_le_piege_de_Luna(self):
        """Luna est un ANIMAL : demandee en personne, la route rend zero photo
        sans rien expliquer. Le genre choisit la ROUTE, et le dit."""
        c = faux_client({'/api/people/photos': {'photos': []},
                         '/api/pets/photos': {'photos': _photos(80, 'luna')}})
        personne = M._photos_de(c, {'nom': 'Luna'})
        animal = M._photos_de(c, {'nom': 'Luna', 'genre': 'animal'})
        self.assertEqual(personne['total'], 0)
        self.assertEqual(animal['total'], 80)
        self.assertIn('/api/pets/photos', c.appels[1])

    def test_un_genre_inconnu_est_refuse_en_le_NOMMANT(self):
        c = faux_client({})
        with self.assertRaises(M.RefusDeLecture) as e:
            M._photos_de(c, {'nom': 'Luna', 'genre': 'chat'})
        self.assertIn('chat', str(e.exception))

    def test_une_requete_vide_donne_des_EXEMPLES_pas_un_reproche(self):
        with self.assertRaises(M.RefusDeLecture) as e:
            M._chercher(faux_client({}), {'q': '   '})
        self.assertIn('espece:', str(e.exception))

    def test_meme_jour_exige_un_jour_ou_une_cle(self):
        with self.assertRaises(M.RefusDeLecture) as e:
            M._meme_jour(faux_client({}), {})
        self.assertIn('MM-JJ', str(e.exception))

    def test_sujets_filtre_par_prefixe_sans_distinguer_la_casse(self):
        c = faux_client({'/api/sujets/list': {
            'personnes': [{'nom': 'Florine', 'n': 5919},
                          {'nom': 'Mike', 'n': 5566}],
            'animaux': [{'nom': 'Luna', 'n': 210}], 'lieux': []}})
        out = M._sujets(c, {'genre': 'personnes', 'prefixe': 'flor'})
        self.assertEqual(out['personnes']['total'], 1)
        self.assertEqual(out['personnes']['items'][0]['nom'], 'Florine')

    def test_etat_porte_code_a_jour_parce_qu_il_change_le_sens_du_reste(self):
        c = faux_client({'/api/serveur': {'uptime_s': 13306, 'demarre_a': 1.0,
                                          'code_a_jour': False},
                         '/api/maint/status': {'queues': {'personnes': 7530},
                                               'busy': False, 'counts': {}}})
        out = M._etat(c, {})
        self.assertFalse(out['code_a_jour'])
        self.assertEqual(out['files']['personnes'], 7530)


# ──────────────────────────── les pannes se nomment ──────────────────────────

class LesFaits(unittest.TestCase):

    FAITS = {'faits': {'a.jpg': {'date': '2019-07-14', 'date_src': 'exif',
                                 'lieu': 'Bremblens', 'lieu_src': 'gps',
                                 'noms': ['Florine']},
                       'b.jpg': None},
             'inconnues': ['c.jpg'], 'demandees': 3}

    def test_les_cles_partent_REPETEES_pas_en_repr_Python(self):
        """Sans `doseq`, urlencode envoie « key=['a', 'b'] » : le serveur lit
        une seule cle, absurde, et rend « inconnue » sans rien expliquer."""
        c = faux_client({'/api/faits': self.FAITS})
        M._faits(c, {'cles': ['a.jpg', 'b.jpg', 'c.jpg']})
        self.assertIn('key=a.jpg', c.appels[0])
        self.assertIn('key=b.jpg', c.appels[0])
        self.assertNotIn('%5B', c.appels[0])

    def test_les_trois_reponses_traversent_l_outil_intactes(self):
        c = faux_client({'/api/faits': self.FAITS})
        out = M._faits(c, {'cles': ['a.jpg', 'b.jpg', 'c.jpg']})
        self.assertEqual(out['faits']['a.jpg']['lieu_src'], 'gps')
        self.assertIsNone(out['faits']['b.jpg'])
        self.assertEqual(out['inconnues'], ['c.jpg'])

    def test_une_cle_seule_est_acceptee_comme_une_liste(self):
        c = faux_client({'/api/faits': self.FAITS})
        M._faits(c, {'cles': 'a.jpg'})
        self.assertIn('key=a.jpg', c.appels[0])

    def test_sans_cle_l_outil_dit_ou_les_trouver(self):
        with self.assertRaises(M.RefusDeLecture) as e:
            M._faits(faux_client({}), {'cles': []})
        self.assertIn('ml_chercher', str(e.exception))

    def test_au_dela_du_plafond_l_outil_COUPE_et_le_dit(self):
        """Couper ici plutot que de laisser le serveur le faire : c'est le
        meme plafond, mais celui-la est annonce."""
        c = faux_client({'/api/faits': {'faits': {}, 'inconnues': [],
                                        'demandees': M.PLAFOND_FAITS}})
        out = M._faits(c, {'cles': ['p%d.jpg' % i for i in range(250)]})
        self.assertTrue(out['tronque'])
        self.assertEqual(out['non_demandees'], 50)
        self.assertEqual(c.appels[0].count('key='), M.PLAFOND_FAITS)

    def test_sur_un_serveur_qui_n_a_pas_redemarre_l_outil_le_DIT(self):
        """La route est neuve : tant que le serveur tourne l'ancien code, elle
        rend 404. Le message doit envoyer vers la bonne cause, pas vers les
        donnees."""
        import urllib.error
        c = faux_client({'/api/faits': urllib.error.HTTPError(
            'u', 404, 'nope', None, None)})
        r = M.appeler_outil(c, 'ml_faits', {'cles': ['a.jpg']})
        self.assertTrue(r['isError'])
        self.assertIn('TOURNE', r['content'][0]['text'])


class LesPannes(unittest.TestCase):

    def test_un_serveur_muet_nomme_l_URL_et_la_question_a_se_poser(self):
        c = faux_client({'/api/serveur': OSError('connexion refusee')})
        with self.assertRaises(M.RefusDeLecture) as e:
            c.get('/api/serveur')
        msg = str(e.exception)
        self.assertIn('http://test:8080', msg)
        self.assertIn('demarre', msg.replace('é', 'e'))

    def test_un_404_parle_du_code_QUI_TOURNE(self):
        """Le piege du projet : une route ecrite sur le disque n'existe pas
        tant que le serveur n'a pas redemarre."""
        import urllib.error
        c = faux_client({'/api/search': urllib.error.HTTPError(
            'u', 404, 'nope', None, None)})
        with self.assertRaises(M.RefusDeLecture) as e:
            c.get('/api/search', {'q': 'x'})
        self.assertIn('404', str(e.exception))
        self.assertIn('TOURNE', str(e.exception))

    def test_une_page_HTML_d_erreur_ne_passe_pas_pour_du_JSON(self):
        c = faux_client({'/api/search': b'<html>500</html>'})
        with self.assertRaises(M.RefusDeLecture) as e:
            c.get('/api/search', {'q': 'x'})
        self.assertIn('HTML', str(e.exception))

    def test_un_outil_qui_echoue_revient_au_MODELE_pas_au_client(self):
        c = faux_client({'/api/search': OSError('coupure')})
        r = M.appeler_outil(c, 'ml_chercher', {'q': 'chat'})
        self.assertTrue(r['isError'])
        self.assertIn('photo', r['content'][0]['text'])

    def test_un_argument_absurde_ne_fait_pas_tomber_le_serveur(self):
        c = faux_client({'/api/search': {'results': []}})
        r = M.appeler_outil(c, 'ml_chercher', {'q': 'chat', 'limite': 'beaucoup'})
        self.assertTrue(r['isError'])
        texte = r['content'][0]['text']
        self.assertIn('argument invalide', texte)
        self.assertIn('ml_chercher', texte)


# ─────────────────────────────── les dates ───────────────────────────────────

class LesDates(unittest.TestCase):

    def test_la_date_suit_l_heure_LOCALE_de_la_machine(self):
        """Pas une constante : le fuseau est un piege connu (19/08). On compare
        au calcul local, ce qui rend le test vrai partout."""
        import time
        e = 1700000000
        attendu = time.strftime('%Y-%m-%d %H:%M', time.localtime(e))
        self.assertEqual(M._date_lisible(e), attendu)

    def test_une_date_absente_reste_ABSENTE(self):
        """Zero epoch rendrait « 1970-01-01 » : une date fausse est pire qu'une
        date manquante, parce qu'elle se lit comme une date."""
        for rien in (0, None, '', 'bof'):
            self.assertEqual(M._date_lisible(rien), '')

    def test_une_photo_sans_date_ne_porte_pas_de_champ_date(self):
        p = M.photo_courte({'key': 'k', 'name': 'n', 'taken': 0})
        self.assertNotIn('date', p)


if __name__ == '__main__':
    unittest.main(verbosity=2)
