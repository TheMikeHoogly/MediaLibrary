"""Serveur MCP local, LECTURE SEULE, sur la photothèque (point 13 de la feuille
de route). JSON-RPC 2.0 sur stdio, stdlib pure : ni npm, ni SDK, ni framework —
règle 3 du projet.

CE QU'IL EST. Un adaptateur, pas une source. Il ne lit ni `photos.db` (règle 4 :
le serveur est l'écrivain unique) ni le NAS ; il interroge en GET le serveur qui
tourne. Conséquence pratique, et c'est ce qui le rend livrable un jour où
`server.py` a changé sous un serveur qui n'a pas redémarré : il ne dépend
d'AUCUNE route neuve. Tout ce qu'il appelle existe déjà.

LECTURE SEULE, ET PAS SEULEMENT PAR CONVENTION. Le client (`ClientLecture`)
n'a pas de méthode pour écrire : il émet des GET, et il REFUSE tout chemin
absent de `CHEMINS_PERMIS`. Ajouter un outil qui écrit demanderait donc de
changer le client, pas seulement d'ajouter une entrée dans `OUTILS` — la
frontière est structurelle, pas déclarative.

LE PLAFOND SE DÉCLARE, TOUJOURS. `/api/people/photos?name=Mike` rend
**1 371 872 octets** (mesuré le 23/08 sur le fonds vivant) : passer une réponse
telle quelle noierait le contexte de n'importe quel agent. Chaque outil de liste
coupe donc, et RÉPOND CE QU'IL A COUPÉ — `total`, `debut`, `montres`. C'est la
leçon déjà payée côté recherche (ROADMAP 14a) : un plafond silencieux se lit
comme une exhaustivité, et un agent qui croit avoir tout vu conclut faux.

LA SEULE ROUTE NEUVE, ET POURQUOI ELLE L'EST. `ml_faits` s'appuie sur
`/api/faits`, ajoutée le 23/08. La ligne de faits n'était calculée que dans
`_serve_browse`, pour la page : rien d'autre ne pouvait la lire. La refaire ici
aurait été un SECOND assemblage — exactement ce que `faits_vue` a été écrit pour
empêcher (« une seule implémentation, deux appelants »). Tant que le serveur qui
tourne n'a pas redémarré, cet outil rend une erreur qui le DIT (« la route
existe-t-elle dans le code qui TOURNE ? ») ; les cinq autres ne dépendent de
rien de neuf.

Usage :
    python mcp_serveur.py            # parle MCP sur stdin/stdout
    ML_URL=http://192.168.0.13:8080 python mcp_serveur.py

stdout ne porte QUE du protocole. Tout le reste va sur stderr : une seule ligne
de diagnostic sur stdout casse le cadrage et le client ne dit jamais pourquoi.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = '1.0'
NOM_SERVEUR = 'medialibrary'
PROTOCOLE = '2025-06-18'

URL_DEFAUT = os.environ.get('ML_URL', 'http://127.0.0.1:8080')
DELAI_S = float(os.environ.get('ML_DELAI', '30'))

# Le serveur peut être lent (le NAS, un worker qui écrit des XMP). Un outil doit
# ÉCHOUER, jamais se figer : la leçon du 23/08, payée 600 s au banc.
CHEMINS_PERMIS = (
    '/api/search',
    '/api/similar',
    '/api/jour',
    '/api/faits',
    '/api/sujets/list',
    '/api/names',
    '/api/people/photos',
    '/api/pets/photos',
    '/api/serveur',
    '/api/maint/status',
)

LIMITE_DEFAUT = 20
LIMITE_MAX = 200

# Ce que les routes elles-mêmes acceptent au maximum. On leur demande ce
# plafond, PAS le nombre qu'on veut montrer : sinon `total` ne compterait que ce
# qu'on a demandé, et l'outil mentirait exactement comme le plafond silencieux
# qu'il est censé rendre visible. Constaté sur le fonds le 23/08 :
# `ml_chercher espece:chat limite=5` annonçait « 5 trouvées » là où le fonds en
# porte 2 386.
PLAFOND_RECHERCHE = 1500
PLAFOND_SEMBLABLES = 500
# `/api/people/photos` plafonne à 2 000 SANS LE DIRE quand on ne lui passe rien :
# Florine, qui porte 5 919 photos, en rendait exactement 2 000 (mesuré le 23/08).
# On lui demande donc son propre maximum, et `total` redevient un compte.
PLAFOND_PERSONNE = 50000
PLAFOND_FAITS = 200


# ───────────────────────────── le monde extérieur ────────────────────────────

class RefusDeLecture(Exception):
    """Le client a refusé : chemin hors de la liste, ou serveur muet.

    Une exception distincte parce que l'agent doit pouvoir DISTINGUER « la
    photothèque ne répond pas » de « cet outil n'existe pas » — deux causes,
    deux gestes."""


class ClientLecture:
    """Des GET, et rien d'autre. Pas de `post`, pas de `requete(methode=...)`.

    `ouvrir` est injectable pour que les vérifications n'aient besoin ni de
    réseau ni de serveur : un banc qui exige le LAN ne tourne que chez Mike."""

    def __init__(self, base=None, ouvrir=None, delai=DELAI_S):
        self.base = (base or URL_DEFAUT).rstrip('/')
        self._ouvrir = ouvrir or urllib.request.urlopen
        self.delai = delai
        self.appels = []          # trace : ce qui a VRAIMENT été demandé

    def get(self, chemin, params=None):
        if chemin not in CHEMINS_PERMIS:
            raise RefusDeLecture(
                "chemin refuse : %s. Ce serveur est en lecture seule et n'appelle "
                "que %s." % (chemin, ', '.join(CHEMINS_PERMIS)))
        url = self.base + chemin
        if params:
            propres = {k: v for k, v in params.items()
                       if v not in (None, '', [])}
            if propres:
                # `doseq` : certains paramètres sont RÉPÉTABLES (`key` de
                # `/api/faits`). Sans lui, une liste part en repr Python et le
                # serveur reçoit « ['a', 'b'] » comme une seule clé.
                url += '?' + urllib.parse.urlencode(propres, doseq=True)
        self.appels.append(url)
        requete = urllib.request.Request(url, method='GET')
        try:
            with self._ouvrir(requete, timeout=self.delai) as reponse:
                brut = reponse.read()
        except urllib.error.HTTPError as e:
            raise RefusDeLecture(
                "la photothèque a répondu %s sur %s. La route existe-t-elle "
                "dans le code qui TOURNE ?" % (e.code, chemin))
        except Exception as e:
            raise RefusDeLecture(
                "la photothèque ne répond pas sur %s (%s : %s). Le serveur "
                "est-il démarré, et l'URL est-elle la bonne ? (ML_URL=%s)"
                % (self.base, type(e).__name__, e, self.base))
        try:
            return json.loads(brut.decode('utf-8'))
        except Exception as e:
            raise RefusDeLecture(
                "réponse illisible de %s (%s). Ce n'est pas du JSON : la route "
                "a peut-être rendu une page HTML d'erreur." % (chemin, e))


# ──────────────────────────── mise en forme ──────────────────────────────────

def tranche(items, debut, limite):
    """Coupe, et DIT ce qu'elle coupe.

    `total` n'est pas décoratif : sans lui, un agent qui reçoit 20 photos sur
    2 000 croit tenir la réponse entière. C'est la panne que le plafond de la
    recherche a déjà produite une fois (ROADMAP 14a)."""
    items = list(items or ())
    debut = max(0, int(debut or 0))
    limite = max(1, min(int(limite or LIMITE_DEFAUT), LIMITE_MAX))
    bout = items[debut:debut + limite]
    return {
        'total': len(items),
        'debut': debut,
        'montres': len(bout),
        'reste': max(0, len(items) - debut - len(bout)),
        'items': bout,
    }


def _plancher(rendus, plafond, route):
    """Dit si `total` est un COMPTE ou seulement un PLANCHER.

    Une route qui plafonne rend exactement `plafond` lignes qu'il y en ait
    autant ou dix fois plus. Sans ce champ, « total: 1500 » se lit comme un
    inventaire ; c'est le défaut que la page de recherche a déjà eu, et qu'elle
    a corrigé en déclarant son plafond (ROADMAP 14a)."""
    if rendus < plafond:
        return {'total_est_un_plancher': False}
    return {
        'total_est_un_plancher': True,
        'note': "%s plafonne a %d resultats : il y en a AU MOINS %d, le compte "
                "exact n'est pas dans cette reponse. Resserrer la requete pour "
                "le connaitre." % (route, plafond, plafond),
    }


def _date_lisible(epoch):
    """Heure LOCALE de la machine, assumée.

    Le fuseau est un piège connu du projet (19/08 : deux « divergences » étaient
    des photos prises à 00h06 sous UTC). Ici le lecteur est Mike, sur sa
    machine : l'heure locale est la bonne, et le champ `taken` garde l'epoch
    pour qui veut recalculer."""
    try:
        e = float(epoch or 0)
    except (TypeError, ValueError):
        return ''
    if e <= 0:
        return ''
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(e))


def photo_courte(p, mots_max=8):
    """Ce qu'un agent peut LIRE d'une photo, pas ce que l'API sait en dire.

    `crop_url`, `gurl`, `folder`, `i`, `sim` sont des affaires d'interface :
    les garder coûterait du contexte sans rien apprendre à personne."""
    if not isinstance(p, dict):
        return {'cle': str(p)}
    mots = [m for m in (p.get('kw') or []) if m][:mots_max]
    court = {
        'cle': p.get('key') or '',
        'nom': p.get('name') or '',
        'desc': p.get('desc') or '',
        'mots': mots,
    }
    if p.get('taken'):
        court['taken'] = p.get('taken')
        court['date'] = _date_lisible(p.get('taken'))
    if p.get('score') is not None:
        court['score'] = p.get('score')
    return court


# ─────────────────────────────── les outils ──────────────────────────────────

def _chercher(client, args):
    q = (args.get('q') or '').strip()
    if not q:
        raise RefusDeLecture(
            "`q` est vide. Exemples : « chat sur un canapé » (sémantique), "
            "« espece:chat » (axe explicite), « personne:Florine ».")
    n = max(1, min(int(args.get('limite') or LIMITE_DEFAUT), LIMITE_MAX))
    debut = int(args.get('debut') or 0)
    # On demande le PLAFOND de la route, pas `debut + limite` : `total` doit
    # compter ce que le fonds porte, pas ce que l'appelant a demandé. Le trajet
    # est local, la coupe se fait ici.
    brut = client.get('/api/search', {'q': q, 'n': PLAFOND_RECHERCHE})
    resultats = brut.get('results') or []
    out = tranche([photo_courte(p) for p in resultats], debut, n)
    out.update(_plancher(len(resultats), PLAFOND_RECHERCHE, '/api/search'))
    # Ce que le serveur a COMPRIS de la requête : les axes qu'il a reconnus, et
    # `reste_requete`, le texte parti en sémantique. Sans ça un agent ne sait
    # pas si « espece:chien » a filtré ou s'il a cherché les mots « espece » et
    # « chien ».
    out['axes'] = {
        'noms': brut.get('noms') or [],
        'lieux': brut.get('lieux') or [],
        'periode': brut.get('periode') or '',
        'especes': brut.get('especes') or [],
        'sans_date': bool(brut.get('sans_date')),
    }
    out['reste_requete'] = brut.get('reste') or ''
    return out


def _semblables(client, args):
    cle = (args.get('cle') or '').strip()
    if not cle:
        raise RefusDeLecture(
            "`cle` est vide. Une clé est le chemin d'index rendu par "
            "`ml_chercher` (champ `cle`), pas un nom de fichier seul.")
    n = max(1, min(int(args.get('limite') or LIMITE_DEFAUT), LIMITE_MAX))
    brut = client.get('/api/similar', {'key': cle, 'n': PLAFOND_SEMBLABLES})
    resultats = brut.get('results') or []
    out = tranche([photo_courte(p) for p in resultats], 0, n)
    out.update(_plancher(len(resultats), PLAFOND_SEMBLABLES, '/api/similar'))
    return out


def _meme_jour(client, args):
    jour = (args.get('jour') or '').strip()
    cle = (args.get('cle') or '').strip()
    if not jour and not cle:
        raise RefusDeLecture(
            "il faut `jour` (MM-JJ, ex. « 12-28 ») ou `cle` (une photo dont on "
            "prend le jour).")
    n = max(1, min(int(args.get('limite') or LIMITE_DEFAUT), LIMITE_MAX))
    debut = int(args.get('debut') or 0)
    brut = client.get('/api/jour', {'jour': jour, 'key': cle})
    out = tranche([photo_courte(p) for p in brut.get('results') or []], debut, n)
    out['annees'] = brut.get('annees') or []
    return out


def _faits(client, args):
    """La ligne de faits (date . lieu . noms), telle que la page l'affiche.

    Un lot, pas N appels : le serveur bâtit son contexte UNE fois pour toutes
    les clés, et c'est là qu'est l'économie."""
    cles = args.get('cles') or args.get('cle') or []
    if isinstance(cles, str):
        cles = [cles]
    cles = [str(c).strip() for c in cles if str(c).strip()]
    if not cles:
        raise RefusDeLecture(
            "`cles` est vide. Passer les cles rendues par `ml_chercher` "
            "(champ `cle`), jusqu'a %d." % PLAFOND_FAITS)
    trop = len(cles) - PLAFOND_FAITS
    brut = client.get('/api/faits', {'key': cles[:PLAFOND_FAITS]})
    out = {
        'faits': brut.get('faits') or {},
        'inconnues': brut.get('inconnues') or [],
        'demandees': brut.get('demandees'),
    }
    if trop > 0:
        # On coupe ici plutôt que de laisser le serveur le faire en silence.
        out['tronque'] = True
        out['non_demandees'] = trop
        out['note'] = ("%d cles au plus par appel : %d n'ont pas ete "
                       "demandees." % (PLAFOND_FAITS, trop))
    return out


def _sujets(client, args):
    genre = (args.get('genre') or 'tous').strip().lower()
    if genre not in ('tous', 'personnes', 'animaux', 'lieux'):
        raise RefusDeLecture(
            "`genre` vaut tous, personnes, animaux ou lieux — pas %r." % genre)
    prefixe = (args.get('prefixe') or '').strip().lower()
    n = max(1, min(int(args.get('limite') or 50), LIMITE_MAX))
    debut = int(args.get('debut') or 0)
    brut = client.get('/api/sujets/list')
    out = {}
    for cle_genre in ('personnes', 'animaux', 'lieux'):
        if genre not in ('tous', cle_genre):
            continue
        liste = brut.get(cle_genre) or []
        if prefixe:
            liste = [s for s in liste
                     if prefixe in json.dumps(s, ensure_ascii=False).lower()]
        out[cle_genre] = tranche(liste, debut, n)
    return out


def _photos_de(client, args):
    nom = (args.get('nom') or '').strip()
    if not nom:
        raise RefusDeLecture(
            "`nom` est vide. `ml_sujets` donne les noms connus.")
    genre = (args.get('genre') or 'personne').strip().lower()
    if genre not in ('personne', 'animal'):
        raise RefusDeLecture(
            "`genre` vaut personne ou animal — pas %r. Luna est un ANIMAL : "
            "demandée en personne, elle rend zéro photo sans rien dire." % genre)
    n = max(1, min(int(args.get('limite') or LIMITE_DEFAUT), LIMITE_MAX))
    debut = int(args.get('debut') or 0)
    chemin = '/api/people/photos' if genre == 'personne' else '/api/pets/photos'
    brut = client.get(chemin, {'name': nom, 'limit': PLAFOND_PERSONNE})
    photos = brut.get('photos') or []
    out = tranche([photo_courte(p) for p in photos], debut, n)
    out.update(_plancher(len(photos), PLAFOND_PERSONNE, chemin))
    out['nom'] = nom
    out['genre'] = genre
    return out


def _etat(client, args):
    """L'état que la photothèque donne d'elle-même.

    `code_a_jour` est ici parce qu'il change le sens de tout le reste : un
    serveur qui tourne l'ANCIEN code répond avec assurance des chiffres qui ne
    décrivent pas ce qui est sur le disque."""
    srv = client.get('/api/serveur')
    maint = client.get('/api/maint/status')
    return {
        'demarre_a': srv.get('demarre_a'),
        'uptime_s': srv.get('uptime_s'),
        'code_a_jour': srv.get('code_a_jour'),
        'files': maint.get('queues') or {},
        'occupe': maint.get('busy'),
        'compte': maint.get('counts') or {},
    }


OUTILS = [
    {
        'name': 'ml_chercher',
        'title': 'Chercher des photos',
        'description':
            "Cherche dans la photothèque. La requête accepte du texte libre "
            "(recherche sémantique) et des axes explicites qui FILTRENT : "
            "`espece:chat`, `personne:Nom`, `animal:Nom`, un lieu, une année. "
            "La réponse dit ce que le serveur a compris (`axes`) et ce qui est "
            "parti en sémantique (`reste_requete`) — sans quoi on ne sait pas "
            "si le filtre a mordu. Rend `total` et `reste` : la liste est "
            "coupée, jamais en silence. Pour ce que la photothèque AFFIRME "
            "d'une photo trouvée — date, lieu, noms et leurs sources — "
            "enchaîner sur `ml_faits`.",
        'inputSchema': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string',
                      'description': "Requête. Ex. « espece:chat », « Florine "
                                     "2019 », « chien dans la neige »."},
                'limite': {'type': 'integer', 'minimum': 1,
                           'maximum': LIMITE_MAX, 'default': LIMITE_DEFAUT},
                'debut': {'type': 'integer', 'minimum': 0, 'default': 0,
                          'description': "Rang de départ, pour paginer."},
            },
            'required': ['q'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _chercher,
    },
    {
        'name': 'ml_semblables',
        'title': 'Photos semblables',
        'description':
            "Les photos visuellement proches d'une photo donnée (empreinte "
            "SigLIP 2). `cle` est le champ `cle` rendu par `ml_chercher`.",
        'inputSchema': {
            'type': 'object',
            'properties': {
                'cle': {'type': 'string',
                        'description': "Clé d'index de la photo de départ."},
                'limite': {'type': 'integer', 'minimum': 1,
                           'maximum': LIMITE_MAX, 'default': LIMITE_DEFAUT},
            },
            'required': ['cle'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _semblables,
    },
    {
        'name': 'ml_meme_jour',
        'title': 'Le même jour, les autres années',
        'description':
            "Les photos prises le même jour du calendrier, toutes années "
            "confondues. Donner `jour` (MM-JJ) ou `cle` (on prend son jour).",
        'inputSchema': {
            'type': 'object',
            'properties': {
                'jour': {'type': 'string',
                         'description': "Jour au format MM-JJ, ex. « 12-28 »."},
                'cle': {'type': 'string',
                        'description': "Clé d'une photo, dont on prend le jour."},
                'limite': {'type': 'integer', 'minimum': 1,
                           'maximum': LIMITE_MAX, 'default': LIMITE_DEFAUT},
                'debut': {'type': 'integer', 'minimum': 0, 'default': 0},
            },
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _meme_jour,
    },
    {
        'name': 'ml_faits',
        'title': 'La ligne de faits de photos designees',
        'description':
            "Ce que la photothèque AFFIRME d'une photo : sa date, son lieu et "
            "les personnes ou animaux nommés, chacun avec sa SOURCE (`exif`, "
            "`gps`, le nom du dossier…). C'est la même vue que celle de "
            "l'écran, recalculée à la lecture — pas un champ figé en base. "
            "Passer plusieurs clés en UN appel : le contexte est bâti une "
            "seule fois côté serveur. Trois réponses distinctes par clé : les "
            "faits ; `null` si la photo est connue mais ne porte ni date, ni "
            "lieu, ni nom ; et la clé listée dans `inconnues` si l'index "
            "l'ignore.",
        'inputSchema': {
            'type': 'object',
            'properties': {
                'cles': {'type': 'array', 'items': {'type': 'string'},
                         'maxItems': PLAFOND_FAITS,
                         'description': "Clés rendues par `ml_chercher` "
                                        "(champ `cle`)."},
            },
            'required': ['cles'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _faits,
    },
    {
        'name': 'ml_sujets',
        'title': 'Les sujets connus',
        'description':
            "Les personnes, animaux et lieux que la photothèque connaît, avec "
            "leur compte. À appeler AVANT `ml_photos_de` : un nom mal orthographié "
            "ou rangé dans le mauvais genre rend zéro photo sans rien expliquer.",
        'inputSchema': {
            'type': 'object',
            'properties': {
                'genre': {'type': 'string',
                          'enum': ['tous', 'personnes', 'animaux', 'lieux'],
                          'default': 'tous'},
                'prefixe': {'type': 'string',
                            'description': "Ne garde que les sujets dont le nom "
                                           "contient ce texte (insensible à la casse)."},
                'limite': {'type': 'integer', 'minimum': 1,
                           'maximum': LIMITE_MAX, 'default': 50},
                'debut': {'type': 'integer', 'minimum': 0, 'default': 0},
            },
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _sujets,
    },
    {
        'name': 'ml_photos_de',
        'title': 'Les photos d’une personne ou d’un animal',
        'description':
            "Les photos où un sujet NOMMÉ apparaît. `genre` sépare les "
            "personnes des animaux : ce sont deux fiches différentes, et "
            "demander un chat parmi les personnes rend une liste vide.",
        'inputSchema': {
            'type': 'object',
            'properties': {
                'nom': {'type': 'string', 'description': "Nom exact du sujet."},
                'genre': {'type': 'string', 'enum': ['personne', 'animal'],
                          'default': 'personne'},
                'limite': {'type': 'integer', 'minimum': 1,
                           'maximum': LIMITE_MAX, 'default': LIMITE_DEFAUT},
                'debut': {'type': 'integer', 'minimum': 0, 'default': 0},
            },
            'required': ['nom'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _photos_de,
    },
    {
        'name': 'ml_etat',
        'title': 'État de la photothèque',
        'description':
            "Ce que le serveur dit de lui-même : depuis quand il tourne, s'il "
            "fait tourner le code qui est sur le disque (`code_a_jour`), et ce "
            "que ses files ont encore à faire. Un `code_a_jour` faux change le "
            "sens de toutes les autres réponses.",
        'inputSchema': {'type': 'object', 'properties': {}},
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
        'handler': _etat,
    },
]

PAR_NOM = {o['name']: o for o in OUTILS}


def outils_publics():
    """La liste telle que le protocole l'attend : `handler` n'en fait pas partie."""
    return [{k: v for k, v in o.items() if k != 'handler'} for o in OUTILS]


# ────────────────────────────── le protocole ─────────────────────────────────

def _erreur(ident, code, message):
    return {'jsonrpc': '2.0', 'id': ident,
            'error': {'code': code, 'message': message}}


def _resultat(ident, valeur):
    return {'jsonrpc': '2.0', 'id': ident, 'result': valeur}


def appeler_outil(client, nom, arguments):
    """Rend le `result` d'un `tools/call`.

    Un outil qui échoue n'est PAS une erreur JSON-RPC : le protocole veut
    `isError` dans le résultat, pour que le modèle voie le message et corrige
    au lieu que le client casse."""
    outil = PAR_NOM.get(nom)
    if outil is None:
        return {'isError': True, 'content': [{'type': 'text', 'text':
                "outil inconnu : %s. Connus : %s."
                % (nom, ', '.join(sorted(PAR_NOM)))}]}
    try:
        valeur = outil['handler'](client, arguments or {})
    except RefusDeLecture as e:
        return {'isError': True, 'content': [{'type': 'text', 'text': str(e)}]}
    except (TypeError, ValueError) as e:
        return {'isError': True, 'content': [{'type': 'text', 'text':
                "argument invalide pour %s : %s" % (nom, e)}]}
    texte = json.dumps(valeur, ensure_ascii=False, indent=1)
    return {'content': [{'type': 'text', 'text': texte}],
            'structuredContent': valeur}


def traiter(message, client):
    """Un message entrant → un message sortant, ou None pour une notification.

    Aucune E/S ici : c'est ce qui rend le protocole vérifiable sans serveur,
    sans réseau et sans processus."""
    if not isinstance(message, dict):
        return _erreur(None, -32600, "message JSON-RPC invalide : objet attendu")
    ident = message.get('id')
    methode = message.get('method')
    params = message.get('params') or {}
    if not methode:
        return _erreur(ident, -32600, "message sans `method`")

    if methode.startswith('notifications/'):
        return None                      # une notification n'a pas de réponse

    if methode == 'initialize':
        return _resultat(ident, {
            'protocolVersion': PROTOCOLE,
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': {'name': NOM_SERVEUR, 'version': VERSION,
                           'title': 'Photothèque (lecture seule)'},
            'instructions':
                "Photothèque familiale locale, en LECTURE SEULE : rien de ce "
                "qui est ici n'écrit sur le disque ni dans l'index. Commencer "
                "par `ml_etat` quand un chiffre surprend : un serveur qui "
                "tourne l'ancien code répond sans le dire.",
        })

    if methode == 'ping':
        return _resultat(ident, {})

    if methode == 'tools/list':
        return _resultat(ident, {'tools': outils_publics()})

    if methode == 'tools/call':
        nom = params.get('name')
        if not nom:
            return _erreur(ident, -32602, "`tools/call` sans `name`")
        return _resultat(ident, appeler_outil(client, nom,
                                              params.get('arguments')))

    if ident is None:
        return None
    return _erreur(ident, -32601,
                   "méthode inconnue : %s. Ce serveur répond à initialize, "
                   "ping, tools/list et tools/call." % methode)


def boucle(entree, sortie, client):
    """Lit des messages ligne à ligne, écrit les réponses. Rend le nombre servi.

    Une ligne vide est ignorée, une ligne illisible rend une erreur de parse et
    la boucle CONTINUE : un client qui bafouille ne doit pas tuer la session."""
    servis = 0
    for ligne in entree:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            message = json.loads(ligne)
        except ValueError as e:
            reponse = _erreur(None, -32700, "JSON illisible : %s" % e)
        else:
            reponse = traiter(message, client)
        if reponse is None:
            continue
        sortie.write(json.dumps(reponse, ensure_ascii=False) + '\n')
        sortie.flush()
        servis += 1
    return servis


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if '--outils' in argv:
        # Pour un humain : ce que le serveur expose, sans parler le protocole.
        for o in OUTILS:
            print('%-16s %s' % (o['name'], o['title']))
        return 0
    client = ClientLecture()
    sys.stderr.write('[mcp] %s v%s -> %s\n' % (NOM_SERVEUR, VERSION, client.base))
    sys.stderr.flush()
    boucle(sys.stdin, sys.stdout, client)
    return 0


if __name__ == '__main__':
    sys.exit(main())
