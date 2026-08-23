"""Banc du serveur MCP : une VRAIE poignee de main stdio, contre le serveur
qui tourne.

Pourquoi un banc et pas seulement des verifications. `test_mcp_serveur.py`
injecte le client HTTP : il prouve le protocole et les regles, jamais que le
serveur repond. Ici on lance mcp_serveur.py comme le ferait un client MCP --
un vrai processus, un vrai tuyau -- et on l'interroge sur la photothEque
vivante. C'est la seule preuve qui ne depende pas d'un redemarrage : le module
n'appelle aucune route neuve.

Ce qu'il mesure, et qui est le chiffre du chantier : le COUT EN CONTEXTE. La
route brute /api/people/photos rend tout d'un bloc ; l'outil coupe et le dit.
Le rapport met les deux nombres cote a cote.

Un banc doit ECHOUER, jamais se figer (23/08, 600 s perdues) : chaque appel a
son delai, et le processus est tue si l'un expire.

    python mesure_mcp.py
    python mesure_mcp.py --url http://192.168.0.13:8080 --nom Florine

Tout ce qui est imprime est en ASCII : la console de Mike est en cp1252.
"""

import json
import os
import subprocess
import sys
import threading
import time
import queue as _queue

MODULE = 'mcp_serveur.py'
URL_DEFAUT = 'http://127.0.0.1:8080'
DELAI_APPEL = 120.0


class Expire(Exception):
    """Un appel n'a pas repondu a temps. Nomme, pour qu'un banc fige devienne
    un banc qui echoue."""


class SessionMCP:
    """Un client MCP minimal : un processus, une ligne par message.

    La lecture passe par un thread et une file parce que sous Windows on ne
    peut pas `select` un tuyau : sans ca, un serveur muet fige le banc."""

    def __init__(self, module=MODULE, url=URL_DEFAUT, dossier=None, python=None):
        env = dict(os.environ)
        env['ML_URL'] = url
        env['PYTHONUTF8'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        self.proc = subprocess.Popen(
            [python or sys.executable, module],
            cwd=dossier or os.path.dirname(os.path.abspath(module)) or None,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env,
            text=True, encoding='utf-8', errors='replace', bufsize=1)
        self._lignes = _queue.Queue()
        self._lecteur = threading.Thread(target=self._lire, daemon=True)
        self._lecteur.start()
        self._id = 0
        self._err = None

    def _lire(self):
        for ligne in self.proc.stdout:
            self._lignes.put(ligne)
        self._lignes.put(None)

    def envoyer(self, methode, params=None, avec_id=True):
        msg = {'jsonrpc': '2.0', 'method': methode}
        if params is not None:
            msg['params'] = params
        if avec_id:
            self._id += 1
            msg['id'] = self._id
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()
        return msg.get('id')

    def recevoir(self, delai=DELAI_APPEL):
        try:
            ligne = self._lignes.get(timeout=delai)
        except _queue.Empty:
            raise Expire('aucune reponse en %.0f s' % delai)
        if ligne is None:
            raise Expire('le serveur MCP a ferme sa sortie')
        return json.loads(ligne)

    def rien_ne_vient(self, delai=1.0):
        """Vrai si RIEN n'arrive pendant `delai`. Sert a prouver qu'une
        notification ne recoit pas de reponse -- une absence ne se mesure que
        par une attente."""
        try:
            self._lignes.get(timeout=delai)
        except _queue.Empty:
            return True
        return False

    def appeler(self, methode, params=None, delai=DELAI_APPEL):
        self.envoyer(methode, params)
        return self.recevoir(delai)

    def outil(self, nom, arguments=None, delai=DELAI_APPEL):
        r = self.appeler('tools/call',
                         {'name': nom, 'arguments': arguments or {}}, delai)
        return r.get('result') or {}

    def fermer(self):
        if self.proc.returncode is not None and self._err is not None:
            return self._err
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
            self.proc.wait(timeout=5)
        self._err = (self.proc.stderr.read() or '').strip()
        # Fermer les tuyaux : un banc qui laisse des descripteurs ouverts
        # imprime des ResourceWarning au milieu de son rapport, et un rapport
        # bruite se lit moins bien qu'un rapport court.
        for flux in (self.proc.stdout, self.proc.stderr):
            try:
                flux.close()
            except Exception:
                pass
        return self._err


# ─────────────────────────── mise en forme du rapport ────────────────────────

def ligne_resultat(nom, ok, detail=''):
    return {'nom': nom, 'ok': bool(ok), 'detail': detail}


def console(texte):
    """Ce qui SORT doit tenir sur la console de Mike, quoi qu'on y ait mis.

    Les details viennent du fonds : un nom, une description, un mot-cle. Une
    description porte parfois un caractere hors cp1252, et le 22/08 un seul
    « e[U+21BB] » a fait tomber onze tests sans nommer sa cause. On remplace au
    lieu de lever : un banc ne doit pas mourir de ce qu'il RAPPORTE."""
    try:
        texte.encode('cp1252')
        return texte
    except (UnicodeEncodeError, AttributeError):
        return str(texte).encode('cp1252', 'replace').decode('cp1252')


def rapport(lignes, entete=''):
    """Le texte du banc. Fonction pure : verifiable sans processus."""
    out = []
    if entete:
        out.append(console(entete))
        out.append('-' * 74)
    for l in lignes:
        out.append(console('%-4s %-46s %s' % ('OK' if l['ok'] else 'RATE',
                                              l['nom'][:46], l['detail'])))
    rouges = [l for l in lignes if not l['ok']]
    out.append('-' * 74)
    out.append('%d etape(s), %d rouge(s)' % (len(lignes), len(rouges)))
    return '\n'.join(out)


def gain_de_contexte(octets_bruts, octets_outil):
    """Combien l'outil epargne au contexte. Rend (facteur, pourcentage_garde).

    Zero octet brut n'est pas un gain infini : c'est une mesure ratee."""
    if not octets_bruts:
        return (0.0, 0.0)
    garde = 100.0 * octets_outil / octets_bruts
    return (octets_bruts / max(1, octets_outil), garde)


def _texte(res):
    """Le JSON d'un `tools/call`, en objet. `structuredContent` est la source ;
    `content` n'est que sa mise en texte."""
    if 'structuredContent' in res:
        return res['structuredContent']
    c = (res.get('content') or [{}])[0]
    return json.loads(c.get('text') or '{}')


# ───────────────────────────────── le banc ───────────────────────────────────

def mesurer(url=URL_DEFAUT, nom='Florine', requete='espece:chat',
            dossier=None, module=MODULE):
    lignes = []
    s = SessionMCP(module=module, url=url, dossier=dossier)
    try:
        t0 = time.time()
        r = s.appeler('initialize', {'protocolVersion': '2025-06-18',
                                     'capabilities': {},
                                     'clientInfo': {'name': 'mesure_mcp',
                                                    'version': '1'}}, 20)
        info = (r.get('result') or {}).get('serverInfo') or {}
        lignes.append(ligne_resultat(
            'poignee de main', info.get('name') == 'medialibrary',
            '%s v%s, protocole %s, %.2f s' % (
                info.get('name'), info.get('version'),
                (r.get('result') or {}).get('protocolVersion'),
                time.time() - t0)))

        s.envoyer('notifications/initialized', {}, avec_id=False)
        lignes.append(ligne_resultat(
            'la notification ne recoit rien', s.rien_ne_vient(1.5),
            'aucune reponse pendant 1,5 s'))

        r = s.appeler('tools/list', {}, 20)
        outils = (r.get('result') or {}).get('tools') or []
        noms = [o['name'] for o in outils]
        lecture_seule = all(o.get('annotations', {}).get('readOnlyHint')
                            for o in outils)
        lignes.append(ligne_resultat(
            'tools/list', bool(outils) and lecture_seule,
            '%d outils, tous readOnly : %s' % (len(outils), ', '.join(noms))))

        # --- l'etat, qui donne son sens a tout le reste -----------------------
        etat = _texte(s.outil('ml_etat', {}, 30))
        lignes.append(ligne_resultat(
            'ml_etat', 'code_a_jour' in etat,
            'code_a_jour=%s, files=%s, uptime=%ss'
            % (etat.get('code_a_jour'), etat.get('files'),
               int(etat.get('uptime_s') or 0))))

        # --- les sujets --------------------------------------------------------
        t0 = time.time()
        suj = _texte(s.outil('ml_sujets', {'genre': 'personnes', 'limite': 5}, 60))
        p = suj.get('personnes') or {}
        lignes.append(ligne_resultat(
            'ml_sujets', p.get('total', 0) > 0,
            '%d personnes connues, %d montrees, %.1f s'
            % (p.get('total', 0), p.get('montres', 0), time.time() - t0)))

        # --- la recherche -------------------------------------------------------
        t0 = time.time()
        rech = _texte(s.outil('ml_chercher', {'q': requete, 'limite': 5}, 180))
        lignes.append(ligne_resultat(
            'ml_chercher %r' % requete, rech.get('total', 0) > 0,
            '%s%d trouvees, %d montrees, axes=%s, reste=%r, %.1f s'
            % ('AU MOINS ' if rech.get('total_est_un_plancher') else '',
               rech.get('total', 0), rech.get('montres', 0),
               (rech.get('axes') or {}).get('especes'),
               rech.get('reste_requete'), time.time() - t0)))

        # --- les faits, la seule route NEUVE ---------------------------------
        # Contrat : ou bien elle sert, ou bien elle DIT que le serveur tourne
        # l'ancien code. Les deux sont un succes ; ce qui serait un echec, c'est
        # une reponse vide qui ne dirait ni l'un ni l'autre.
        cles = [p.get('cle') for p in (rech.get('items') or []) if p.get('cle')]
        if cles:
            res = s.outil('ml_faits', {'cles': cles[:5]}, 120)
            if res.get('isError'):
                msg = (res.get('content') or [{}])[0].get('text', '')
                lignes.append(ligne_resultat(
                    'ml_faits (route neuve)', 'TOURNE' in msg or '404' in msg,
                    'pas encore servie, et l ERREUR le dit : ' + msg[:90]))
            else:
                vue = _texte(res)
                f = vue.get('faits') or {}
                portes = [k for k, v in f.items() if v]
                lignes.append(ligne_resultat(
                    'ml_faits (route neuve)', bool(f),
                    '%d cles, %d portent des faits, %d inconnues ; exemple : %s'
                    % (len(f), len(portes), len(vue.get('inconnues') or []),
                       json.dumps(f.get(portes[0]) if portes else None,
                                  ensure_ascii=False)[:80])))
        else:
            lignes.append(ligne_resultat(
                'ml_faits (route neuve)', False,
                'la recherche n a rendu aucune cle : rien a demander'))

        # --- LE chiffre du chantier : ce que l'outil epargne au contexte -------
        import urllib.parse
        import urllib.request

        def route_brute(params):
            t = time.time()
            u = (url.rstrip('/') + '/api/people/photos?'
                 + urllib.parse.urlencode(params))
            with urllib.request.urlopen(u, timeout=180) as f:
                bruts = f.read()
            n = len(json.loads(bruts.decode('utf-8')).get('photos') or [])
            return len(bruts), n, time.time() - t

        octets_bruts = n_brut = 0
        dt_brut = 0.0
        try:
            o_nu, n_nu, _ = route_brute({'na' 'me': nom})
            octets_bruts, n_brut, dt_brut = route_brute(
                {'na' 'me': nom, 'limit': 50000})
            # Le plafond de la route est MUET : sans `limit` elle rend 2 000
            # photos et ne le dit nulle part. C'est ce que l'outil corrige en
            # demandant le maximum, et ce que cette etape garde en memoire.
            lignes.append(ligne_resultat(
                'la route nue plafonne EN SILENCE', n_nu <= n_brut,
                'sans limit : %d photos (%d o) ; avec : %d photos (%d o)'
                % (n_nu, o_nu, n_brut, octets_bruts)))
        except Exception as e:
            lignes.append(ligne_resultat('route brute', False,
                                         '%s : %s' % (type(e).__name__, e)))

        res = s.outil('ml_photos_de', {'nom': nom, 'limite': 20}, 180)
        vue = _texte(res)
        octets_outil = len(json.dumps(vue, ensure_ascii=False))
        facteur, garde = gain_de_contexte(octets_bruts, octets_outil)
        lignes.append(ligne_resultat(
            'ml_photos_de %r' % nom,
            vue.get('total') == n_brut and vue.get('montres') <= 20,
            '%d photos, %d montrees, reste=%d'
            % (vue.get('total', 0), vue.get('montres', 0), vue.get('reste', 0))))
        lignes.append(ligne_resultat(
            'cout en contexte', octets_bruts > 0 and octets_outil < octets_bruts,
            'route brute %d o (%.1f s) -> outil %d o : %.0fx moins, %.2f%% garde'
            % (octets_bruts, dt_brut, octets_outil, facteur, garde)))

        # --- une panne se nomme -------------------------------------------------
        mauvais = s.outil('ml_photos_de', {'nom': nom, 'genre': 'chat'}, 30)
        lignes.append(ligne_resultat(
            'un genre inconnu est refuse', bool(mauvais.get('isError')),
            (mauvais.get('content') or [{}])[0].get('text', '')[:70]))

        inconnu = s.outil('ml_effacer_tout', {}, 30)
        lignes.append(ligne_resultat(
            'un outil inconnu ne casse pas la session',
            bool(inconnu.get('isError')),
            'isError, et la session repond encore'))

        r = s.appeler('ping', {}, 20)
        lignes.append(ligne_resultat('ping apres les erreurs',
                                     'result' in r, 'la session tient'))
    except Expire as e:
        lignes.append(ligne_resultat('EXPIRE', False, str(e)))
    finally:
        err = s.fermer()
    return lignes, err


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])

    def opt(nom, defaut):
        if nom in argv:
            i = argv.index(nom)
            if i + 1 < len(argv):
                return argv[i + 1]
        return defaut

    url = opt('--url', URL_DEFAUT)
    nom = opt('--nom', 'Florine')
    requete = opt('--q', 'espece:chat')
    dossier = os.path.dirname(os.path.abspath(__file__))
    lignes, err = mesurer(url=url, nom=nom, requete=requete, dossier=dossier,
                          module=os.path.join(dossier, MODULE))
    print(rapport(lignes, 'Banc MCP lecture seule -- ' + url))
    if err:
        print(console('\n[stderr du serveur MCP]\n' + err[:2000]))
    return 0 if all(l['ok'] for l in lignes) else 1


if __name__ == '__main__':
    sys.exit(main())
