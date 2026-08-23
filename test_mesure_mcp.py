"""Verifications du banc MCP.

Elles lancent un VRAI processus et parlent un VRAI protocole, mais ne touchent
ni le serveur de la phototheque ni le NAS : `initialize`, `tools/list` et `ping`
ne passent par aucun appel HTTP. C'est ce qui rend ce banc verifiable partout,
et pas seulement sur la machine de Mike.

Impressions en ASCII : la console de l'agent git est en cp1252.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mesure_mcp as B

ICI = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(ICI, 'mcp_serveur.py')
# Une URL qui ne repond a personne : si une etape « sans HTTP » se met un jour a
# appeler le reseau, elle echouera ici au lieu de passer en silence.
URL_MORTE = 'http://127.0.0.1:9'


class UneVraieSession(unittest.TestCase):

    def setUp(self):
        self.s = B.SessionMCP(module=MODULE, url=URL_MORTE, dossier=ICI)

    def tearDown(self):
        self.s.fermer()

    def test_la_poignee_de_main_passe_par_un_vrai_tuyau(self):
        r = self.s.appeler('initialize', {'protocolVersion': '2025-06-18'}, 20)
        self.assertEqual(r['result']['serverInfo']['name'], 'medialibrary')

    def test_une_notification_ne_ramene_rien(self):
        """Une absence ne se prouve que par une attente : c'est le seul endroit
        du projet ou « rien » est le resultat attendu."""
        self.s.appeler('initialize', {}, 20)
        self.s.envoyer('notifications/initialized', {}, avec_id=False)
        self.assertTrue(self.s.rien_ne_vient(1.0))

    def test_les_outils_annonces_sont_tous_en_lecture_seule(self):
        r = self.s.appeler('tools/list', {}, 20)
        outils = r['result']['tools']
        self.assertTrue(outils)
        for o in outils:
            self.assertTrue(o['annotations']['readOnlyHint'], o['name'])

    def test_stdout_ne_porte_que_du_protocole_meme_en_vrai(self):
        """Le serveur ecrit une banniere au demarrage : si elle partait sur
        stdout, la premiere reponse serait illisible et personne ne saurait
        pourquoi."""
        r = self.s.appeler('initialize', {}, 20)
        self.assertIn('result', r)
        r = self.s.appeler('ping', {}, 20)
        self.assertEqual(r['result'], {})

    def test_un_serveur_injoignable_est_NOMME_pas_masque(self):
        """L'URL morte est ici le sujet : l'outil doit dire que la phototheque
        ne repond pas, et rendre isError plutot que mourir."""
        res = self.s.outil('ml_etat', {}, 30)
        self.assertTrue(res.get('isError'))
        texte = res['content'][0]['text']
        self.assertIn('127.0.0.1:9', texte)

    def test_la_session_survit_a_une_erreur_d_outil(self):
        self.s.outil('ml_effacer_tout', {}, 20)
        r = self.s.appeler('ping', {}, 20)
        self.assertIn('result', r)

    def test_le_serveur_meurt_proprement_quand_on_ferme_l_entree(self):
        self.s.appeler('initialize', {}, 20)
        err = self.s.fermer()
        self.assertEqual(self.s.proc.returncode, 0)
        self.assertIn('medialibrary', err)   # la banniere est bien sur stderr


class LeRapport(unittest.TestCase):

    def test_le_rapport_compte_les_rouges(self):
        lignes = [B.ligne_resultat('a', True, 'x'),
                  B.ligne_resultat('b', False, 'y')]
        t = B.rapport(lignes, 'entete')
        self.assertIn('2 etape(s), 1 rouge(s)', t)
        self.assertIn('RATE', t)

    def test_le_rapport_reste_lisible_sur_une_console_cp1252(self):
        """Le defaut du 22/08 : un caractere hors cp1252 faisait tomber onze
        tests sans nommer sa cause."""
        t = B.rapport([B.ligne_resultat('poignee de main', True, 'ok')], 'x')
        t.encode('cp1252')

    def test_une_description_exotique_ne_tue_pas_le_rapport(self):
        """Le detail vient du FONDS : une description peut porter un emoji, et
        la console de Mike est en cp1252. Le banc doit rapporter, pas mourir."""
        l = B.ligne_resultat('ml_chercher', True, 'desc = "chat \U0001F431 sur \u21bb"')
        t = B.rapport([l], 'entete')
        t.encode('cp1252')
        self.assertIn('ml_chercher', t)

    def test_le_texte_sain_traverse_console_sans_etre_abime(self):
        """Remplacer trop serait aussi un defaut : « ete » et « a cote » doivent
        rester lisibles."""
        clair = 'la phototheque a repondu, periode 2019, espece chat'
        self.assertEqual(B.console(clair), clair)
        accents = 'espece:chat -- 1 371 872 octets'
        self.assertEqual(B.console(accents), accents)

    def test_zero_octet_brut_n_est_pas_un_gain_infini(self):
        """Une mesure ratee ne doit pas se lire comme un succes eclatant."""
        self.assertEqual(B.gain_de_contexte(0, 100), (0.0, 0.0))

    def test_le_gain_se_lit_en_facteur_et_en_part_gardee(self):
        facteur, garde = B.gain_de_contexte(1371872, 6000)
        self.assertGreater(facteur, 200)
        self.assertLess(garde, 1.0)

    def test_texte_prefere_le_contenu_structure(self):
        res = {'structuredContent': {'total': 3},
               'content': [{'type': 'text', 'text': '{"total": 999}'}]}
        self.assertEqual(B._texte(res)['total'], 3)

    def test_texte_sait_encore_lire_un_client_sans_structuredContent(self):
        res = {'content': [{'type': 'text', 'text': json.dumps({'total': 7})}]}
        self.assertEqual(B._texte(res)['total'], 7)


if __name__ == '__main__':
    unittest.main(verbosity=2)
