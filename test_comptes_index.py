"""Banc de `comptes_index.py` — le carnet de comptes de l'index en mémoire.

Ce que ce banc prétend mesurer : qu'un retrait ne peut pas passer inaperçu,
qu'il est attribué au bon motif, que l'absence de motif se VOIT, et que la
réconciliation détecte un écart qu'aucune mutation déclarée n'explique.

Le branchement sur un VRAI `SqliteStore` est vérifié ici aussi
(`TestBranchementStore`) : un registre parfait mais jamais notifié compterait
zéro, et zéro se lit « tout va bien ».

Ce qu'il ne mesure PAS : que `server.py` déclare le bon motif au bon endroit —
seule l'observation en réel le dit.
"""

import threading
import unittest

from comptes_index import MOTIF_NON_DECLARE, RegistreOublis


class TestMotifs(unittest.TestCase):

    def test_retrait_hors_bloc_tombe_dans_non_declare(self):
        r = RegistreOublis()
        r.cle_retiree('a.jpg')
        self.assertEqual(r.retraits, 1)
        self.assertEqual(r.par_motif[MOTIF_NON_DECLARE]['retraits'], 1)
        self.assertEqual(len(r.non_declares), 1)
        self.assertEqual(r.non_declares[0]['cle'], 'a.jpg')

    def test_retrait_dans_un_bloc_est_attribue(self):
        r = RegistreOublis()
        with r.motif('scan:disparus', label='D:/Photos'):
            r.cle_retiree('a.jpg')
            r.cle_retiree('b.jpg')
        self.assertEqual(r.par_motif['scan:disparus']['retraits'], 2)
        self.assertNotIn(MOTIF_NON_DECLARE, r.par_motif)
        self.assertEqual(r.non_declares, [])

    def test_le_bloc_produit_un_evenement_avec_label_et_exemples(self):
        r = RegistreOublis(max_exemples=2)
        with r.motif('scan:disparus', label='D:/Photos'):
            for n in ('a', 'b', 'c'):
                r.cle_retiree(n)
        self.assertEqual(len(r.evenements), 1)
        ev = r.evenements[0]
        self.assertEqual(ev['motif'], 'scan:disparus')
        self.assertEqual(ev['label'], 'D:/Photos')
        self.assertEqual(ev['retraits'], 3)
        self.assertEqual(ev['n'], 1)
        self.assertEqual(ev['exemples'], ['a', 'b'])       # borné

    def test_bloc_sans_mouvement_ne_produit_pas_devenement(self):
        # Un instrument bavard finit ignoré : 288 scans par jour ne doivent pas
        # remplir la liste d'événements vides.
        r = RegistreOublis()
        with r.motif('scan:disparus'):
            pass
        self.assertEqual(r.evenements, [])

    def test_imbrication_le_plus_interne_gagne_mais_les_deux_totalisent(self):
        r = RegistreOublis()
        with r.motif('scan') as ext:
            r.cle_retiree('a')
            with r.motif('purge:fantomes') as inte:
                r.cle_retiree('b')
        self.assertEqual(r.par_motif['scan']['retraits'], 1)
        self.assertEqual(r.par_motif['purge:fantomes']['retraits'], 1)
        self.assertEqual(ext.retraits, 2)                 # englobant : total
        self.assertEqual(inte.retraits, 1)

    def test_ajout_compte_aussi(self):
        r = RegistreOublis()
        with r.motif('tagging'):
            r.cle_ajoutee('a.jpg')
        self.assertEqual(r.ajouts, 1)
        self.assertEqual(r.par_motif['tagging']['ajouts'], 1)
        self.assertEqual(r.par_motif['tagging']['retraits'], 0)

    def test_rekey_est_neutre_en_taille_mais_visible(self):
        # Un déplacement/renommage = 1 retrait + 1 ajout : la taille de l'index
        # ne bouge pas, et pourtant l'opération reste lisible.
        r = RegistreOublis()
        with r.motif('rekey'):
            r.cle_retiree('vieux.jpg')
            r.cle_ajoutee('neuf.jpg')
        self.assertEqual(r.ajouts - r.retraits, 0)
        self.assertEqual(r.par_motif['rekey'], {'ajouts': 1, 'retraits': 1})

    def test_cles_retirees_declare_un_lot(self):
        r = RegistreOublis()
        with r.motif('reset:animaux'):
            r.cles_retirees(['a', 'b', 'c'])
        self.assertEqual(r.par_motif['reset:animaux']['retraits'], 3)
        self.assertEqual(r.non_declares, [])


class TestMotifDuThread(unittest.TestCase):

    def test_motif_permanent_attribue_tout_le_travail_du_thread(self):
        r = RegistreOublis()
        r.motif_du_thread('tagging')
        r.cle_ajoutee('a.jpg')
        r.cle_ajoutee('b.jpg')
        self.assertEqual(r.par_motif['tagging']['ajouts'], 2)
        self.assertNotIn(MOTIF_NON_DECLARE, r.par_motif)

    def test_motif_permanent_est_idempotent(self):
        r = RegistreOublis()
        r.motif_du_thread('tagging')
        r.motif_du_thread('tagging')
        r.cle_ajoutee('a.jpg')
        self.assertEqual(r.par_motif['tagging']['ajouts'], 1)
        self.assertEqual(len(r._pile()), 1)

    def test_un_bloc_explicite_lemporte_sur_le_motif_permanent(self):
        r = RegistreOublis()
        r.motif_du_thread('tagging')
        with r.motif('scan:disparus'):
            r.cle_retiree('a.jpg')
        r.cle_retiree('b.jpg')
        self.assertEqual(r.par_motif['scan:disparus']['retraits'], 1)
        self.assertEqual(r.par_motif['tagging']['retraits'], 1)

    def test_motif_permanent_ne_deborde_pas_sur_les_autres_threads(self):
        r = RegistreOublis()
        r.motif_du_thread('maintenance')
        fait = []

        def worker():
            r.motif_du_thread('tagging')
            r.cle_ajoutee('w.jpg')
            fait.append(True)

        t = threading.Thread(target=worker)
        t.start()
        t.join(5)
        r.cle_ajoutee('m.jpg')
        self.assertEqual(fait, [True])
        self.assertEqual(r.par_motif['tagging']['ajouts'], 1)
        self.assertEqual(r.par_motif['maintenance']['ajouts'], 1)


class TestBornes(unittest.TestCase):

    def test_liste_des_non_declares_est_bornee_mais_pas_le_compte(self):
        # Le piege exact : plafonner les exemples ET le compte ferait afficher
        # « 20 retraits sans motif » un jour ou 250 cles seraient parties.
        r = RegistreOublis(max_non_declares=5)
        for i in range(50):
            r.cle_retiree(f'{i}.jpg')
        self.assertEqual(r.retraits, 50)                  # le COMPTE est exact
        self.assertEqual(len(r.non_declares), 5)          # les exemples sont bornés
        self.assertEqual(r.resume()['non_declares'], 50)  # et le resume dit 50

    def test_evenements_consecutifs_de_meme_motif_sont_fusionnes(self):
        # Un lot de renommage ouvre un bloc `rekey` PAR FICHIER : sans
        # coalescence, 200 fichiers chassent tous les autres motifs de l'anneau
        # -- l'instrument s'efface lui-meme au moment ou il servirait.
        r = RegistreOublis(max_evenements=5)
        with r.motif('scan:disparus', label='D:/Photos'):
            r.cle_retiree('vieux.jpg')
        for i in range(200):
            with r.motif('rekey'):
                r.cle_retiree(f'{i}')
                r.cle_ajoutee(f'{i}-neuf')
        self.assertEqual(len(r.evenements), 2)
        tete = r.evenements[0]
        self.assertEqual((tete['motif'], tete['n']), ('rekey', 200))
        self.assertEqual((tete['ajouts'], tete['retraits']), (200, 200))
        self.assertEqual(len(tete['exemples']), r.max_exemples)
        # et surtout : l'evenement d'origine a SURVECU
        self.assertEqual(r.evenements[1]['motif'], 'scan:disparus')

    def test_un_motif_different_rouvre_un_evenement(self):
        r = RegistreOublis()
        with r.motif('rekey'):
            r.cle_retiree('a')
        with r.motif('scan:disparus'):
            r.cle_retiree('b')
        with r.motif('rekey'):
            r.cle_retiree('c')
        self.assertEqual([e['motif'] for e in r.evenements],
                         ['rekey', 'scan:disparus', 'rekey'])

    def test_meme_motif_labels_differents_ne_fusionne_pas(self):
        r = RegistreOublis()
        for lab in ('D:/A', 'D:/B'):
            with r.motif('scan:disparus', label=lab):
                r.cle_retiree('x')
        self.assertEqual(len(r.evenements), 2)

    def test_liste_des_evenements_est_bornee_et_recente_en_tete(self):
        r = RegistreOublis(max_evenements=3)
        for i in range(10):
            with r.motif(f'm{i}'):
                r.cle_retiree('x')
        self.assertEqual(len(r.evenements), 3)
        self.assertEqual(r.evenements[0]['motif'], 'm9')

    def test_cle_tres_longue_est_tronquee(self):
        r = RegistreOublis()
        r.cle_retiree('Z' * 500)
        self.assertLessEqual(len(r.non_declares[0]['cle']), 160)

    def test_resume_est_json_able_et_borne(self):
        import json
        r = RegistreOublis(max_evenements=2, max_non_declares=2)
        for i in range(20):
            r.cle_retiree(f'{i}.jpg')
            with r.motif('scan:disparus'):
                r.cle_retiree(f'{i}b.jpg')
        r.debut_cycle(100)
        r.fin_cycle(60)
        s = r.resume()
        json.dumps(s)                                     # ne lève pas
        self.assertEqual(s['retraits'], 40)
        # Le COMPTE est exact ; seuls les EXEMPLES sont bornés. Confondre les
        # deux ferait afficher « 2 » là où 20 clés sont parties.
        self.assertEqual(s['non_declares'], 20)
        self.assertEqual(len(s['non_declares_exemples']), 2)
        # 20 blocs consécutifs de même motif : coalescés en un seul événement.
        self.assertEqual(len(s['evenements']), 1)
        self.assertEqual(s['evenements'][0]['n'], 20)


class TestReconciliation(unittest.TestCase):

    def test_cycle_coherent_ne_signale_rien(self):
        r = RegistreOublis()
        r.debut_cycle(1000)
        with r.motif('scan:disparus'):
            r.cles_retirees([f'{i}' for i in range(10)])
        for i in range(4):
            r.cle_ajoutee(f'n{i}')
        res = r.fin_cycle(1000 - 10 + 4)
        self.assertEqual(res['inexplique'], 0)
        self.assertEqual(res['retraits'], 10)
        self.assertEqual(res['ajouts'], 4)
        self.assertEqual(r.cycles_inexpliques, 0)
        self.assertEqual(r.anomalies, [])
        self.assertEqual(r.ligne_cycle(res), 'index 1000 -> 994 (+4 / -10)')

    def test_disparition_hors_goulot_est_detectee(self):
        # LE cas des -250 : l'index rétrécit sans qu'aucune mutation déclarée
        # ne l'explique. Avant cet instrument, ce chiffre n'existait pas.
        r = RegistreOublis()
        r.debut_cycle(43064)
        res = r.fin_cycle(42814)
        self.assertEqual(res['inexplique'], -250)
        self.assertEqual(r.inexplique_cumul, -250)
        self.assertEqual(r.cycles_inexpliques, 1)
        self.assertEqual(len(r.anomalies), 1)
        self.assertIn('ECART INEXPLIQUE -250', r.ligne_cycle(res))

    def test_apparition_hors_goulot_est_detectee_aussi(self):
        r = RegistreOublis()
        r.debut_cycle(100)
        res = r.fin_cycle(107)
        self.assertEqual(res['inexplique'], 7)

    def test_un_retrait_declare_nest_pas_une_anomalie(self):
        # Le piège symétrique : un scan qui retire 4 000 clés d'un dossier vidé
        # est NORMAL. L'instrument ne doit pas crier au loup.
        r = RegistreOublis()
        r.debut_cycle(43064)
        with r.motif('scan:disparus', label='D:/Photos'):
            r.cles_retirees([f'{i}' for i in range(4000)])
        res = r.fin_cycle(43064 - 4000)
        self.assertEqual(res['inexplique'], 0)
        self.assertEqual(r.anomalies, [])

    def test_fin_sans_debut_ne_leve_pas(self):
        r = RegistreOublis()
        self.assertIsNone(r.fin_cycle(10))
        self.assertEqual(r.ligne_cycle(None), '')

    def test_cycle_sans_mouvement_ne_produit_pas_de_ligne(self):
        r = RegistreOublis()
        r.debut_cycle(500)
        self.assertEqual(r.ligne_cycle(r.fin_cycle(500)), '')

    def test_cycles_sont_bornes_et_recents_en_tete(self):
        r = RegistreOublis(max_cycles=3)
        for i in range(10):
            r.debut_cycle(i)
            r.fin_cycle(i)
        self.assertEqual(len(r.cycles), 3)
        self.assertEqual(r.cycles[0]['debut'], 9)

    def test_ecarts_successifs_se_cumulent_en_signe(self):
        r = RegistreOublis()
        r.debut_cycle(100); r.fin_cycle(90)      # -10
        r.debut_cycle(90);  r.fin_cycle(95)      # +5
        self.assertEqual(r.inexplique_cumul, -5)
        self.assertEqual(r.cycles_inexpliques, 2)


class TestConcurrence(unittest.TestCase):

    def test_les_motifs_ne_fuient_pas_entre_threads(self):
        # La pile de motifs est thread-locale : le worker de tagging qui ajoute
        # une entrée pendant un `with motif('scan:disparus')` du thread de
        # maintenance ne doit PAS être attribué au scan.
        r = RegistreOublis()
        depart = threading.Event()
        dedans = threading.Event()

        def autre():
            depart.wait(5)
            r.cle_retiree('worker.jpg')
            dedans.set()

        t = threading.Thread(target=autre)
        t.start()
        with r.motif('scan:disparus'):
            depart.set()
            dedans.wait(5)
            r.cle_retiree('scan.jpg')
        t.join(5)
        self.assertEqual(r.par_motif['scan:disparus']['retraits'], 1)
        self.assertEqual(r.par_motif[MOTIF_NON_DECLARE]['retraits'], 1)

    def test_le_compte_total_survit_a_la_concurrence(self):
        r = RegistreOublis(max_non_declares=1)
        n_threads, par_thread = 8, 500

        def bosse(i):
            for j in range(par_thread):
                r.cle_retiree(f'{i}-{j}')
                r.cle_ajoutee(f'{i}-{j}')

        ts = [threading.Thread(target=bosse, args=(i,)) for i in range(n_threads)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        self.assertEqual(r.retraits, n_threads * par_thread)
        self.assertEqual(r.ajouts, n_threads * par_thread)

    def test_reconciliation_compte_les_mutations_des_autres_threads(self):
        # Un ajout concurrent du worker de tagging pendant le cycle doit ENTRER
        # dans la réconciliation, sinon tout scan concurrent serait « inexpliqué ».
        r = RegistreOublis()
        r.debut_cycle(100)
        t = threading.Thread(target=lambda: [r.cle_ajoutee(f'w{i}') for i in range(7)])
        t.start()
        t.join(5)
        res = r.fin_cycle(107)
        self.assertEqual(res['ajouts'], 7)
        self.assertEqual(res['inexplique'], 0)


class TestLignes(unittest.TestCase):

    def test_ligne_motifs_liste_les_retraits_par_motif(self):
        r = RegistreOublis()
        with r.motif('scan:disparus'):
            r.cles_retirees(['a', 'b'])
        with r.motif('purge:fantomes'):
            r.cle_retiree('c')
        with r.motif('tagging'):
            r.cle_ajoutee('d')                  # ajout seul : pas dans la ligne
        self.assertEqual(r.ligne_motifs(), 'purge:fantomes 1, scan:disparus 2')

    def test_ligne_motifs_vide_au_demarrage(self):
        self.assertEqual(RegistreOublis().ligne_motifs(), '')


class TestBranchementStore(unittest.TestCase):
    """Le goulot tient-il vraiment ? On branche le registre sur un VRAI
    SqliteStore et on vérifie qu'aucune porte ne laisse passer une clé.

    C'est le test qui compte : le registre peut être parfait, s'il n'est pas
    notifié il compte zéro — et zéro se lit « tout va bien »."""

    def setUp(self):
        import shutil
        import sqlite3
        import tempfile
        from store_sqlite import SqliteStore
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        db = f'{self.dir}/photos.db'
        sqlite3.connect(db).close()
        self.st = SqliteStore(db, 'tags')
        self.addCleanup(self.st.close)
        self.reg = RegistreOublis()
        self.st.brancher_registre(self.reg)

    def test_set_dune_cle_neuve_compte_un_ajout(self):
        self.st.set('a.jpg', {'kw_fr': ['chat']})
        self.assertEqual(self.reg.ajouts, 1)
        self.assertEqual(self.reg.retraits, 0)

    def test_reecrire_une_cle_existante_ne_compte_rien(self):
        self.st.set('a.jpg', {'kw_fr': ['chat']})
        self.st.set('a.jpg', {'kw_fr': ['chien']})
        self.assertEqual(self.reg.ajouts, 1)          # et non 2
        self.assertEqual(self.reg.retraits, 0)

    def test_remove_many_compte_et_attribue(self):
        for n in ('a', 'b', 'c'):
            self.st.set(n, {})
        with self.reg.motif('scan:disparus', label='D:/Photos'):
            n = self.st.remove_many(['a', 'b', 'absente'])
        self.assertEqual(n, 2)
        self.assertEqual(self.reg.par_motif['scan:disparus']['retraits'], 2)
        self.assertEqual(self.reg.retraits, 2)        # 'absente' ne compte pas

    def test_rekey_est_neutre_en_taille(self):
        self.st.set('vieux.jpg', {'kw_fr': ['x']})
        self.reg.debut_cycle(len(self.st.data))
        with self.reg.motif('rekey'):
            self.assertTrue(self.st.rekey('vieux.jpg', 'neuf.jpg'))
        res = self.reg.fin_cycle(len(self.st.data))
        self.assertEqual((res['ajouts'], res['retraits']), (1, 1))
        self.assertEqual(res['inexplique'], 0)

    def test_del_direct_sur_data_tombe_dans_non_declare(self):
        # Le cas qu'on veut voir venir : quelqu'un retire une entrée sans le
        # dire. Ce n'est pas « inexpliqué » (le goulot l'a vu) mais c'est
        # NOMMÉ comme non déclaré, avec la clé en exemple.
        self.st.set('a.jpg', {})
        del self.st.data['a.jpg']
        self.assertEqual(self.reg.par_motif[MOTIF_NON_DECLARE]['retraits'], 1)
        self.assertEqual(self.reg.non_declares[0]['cle'], 'a.jpg')

    def test_remplacement_global_de_data_est_declare(self):
        for n in ('a', 'b', 'c'):
            self.st.set(n, {})
        self.reg.debut_cycle(len(self.st.data))
        with self.reg.motif('reset'):
            self.st.data = {}
        res = self.reg.fin_cycle(len(self.st.data))
        self.assertEqual(res['retraits'], 3)
        self.assertEqual(res['inexplique'], 0)        # pas un faux positif

    def test_un_cycle_complet_se_reconcilie_a_zero(self):
        for i in range(20):
            self.st.set(f'{i}.jpg', {})
        self.reg.debut_cycle(len(self.st.data))
        with self.reg.motif('scan:disparus'):
            self.st.remove_many([f'{i}.jpg' for i in range(5)])
        for i in range(100, 103):
            self.st.set(f'{i}.jpg', {})
        res = self.reg.fin_cycle(len(self.st.data))
        self.assertEqual((res['debut'], res['fin']), (20, 18))
        self.assertEqual((res['ajouts'], res['retraits']), (3, 5))
        self.assertEqual(res['inexplique'], 0)

    def test_sans_registre_branche_rien_ne_change(self):
        self.st.brancher_registre(None)
        self.st.set('z.jpg', {'kw_fr': ['x']})
        self.st.remove_many(['z.jpg'])
        self.st.save()
        self.assertEqual((self.reg.ajouts, self.reg.retraits), (0, 0))
        self.assertNotIn('z.jpg', self.st.data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
