"""Teste les fonctions REELLES de server.py (extraites par ast, sans importer le
module ni ses effets de bord) : _read_bytes_retry, _is_transient_io_fail,
_load_bgr. Aucun acces NAS ; on simule EINVAL avec un open injecte."""
import ast, io, os, sys, tempfile, time
from PIL import Image, ImageOps
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "server.py"), encoding="utf-8").read()
tree = ast.parse(SRC)

# Espace d'execution avec les dependances reelles.
G = {"time": time, "Image": Image, "ImageOps": ImageOps, "np": np,
     "os": os, "io": io, "PIL_OK": True, "FACE_MAX_SIDE": 1024, "OSError": OSError}

WANT = {"ImageReadError", "_read_bytes_retry", "_is_transient_io_fail", "_load_bgr"}
for node in tree.body:
    name = getattr(node, "name", None)
    if name in WANT:
        exec(compile(ast.Module([node], []), "server.py", "exec"), G)

ImageReadError = G["ImageReadError"]
_read_bytes_retry = G["_read_bytes_retry"]
_is_transient_io_fail = G["_is_transient_io_fail"]
_load_bgr = G["_load_bgr"]

ok = True
def check(label, cond):
    global ok
    print(("  [OK]  " if cond else "  [KO]  ") + label)
    ok = ok and cond

# 1) Decodage en memoire d'un vrai JPEG (le chemin nominal de _load_bgr).
tmp = tempfile.mkdtemp()
jpg = os.path.join(tmp, "good.jpg")
Image.new("RGB", (1440, 1080), (120, 60, 30)).save(jpg, "JPEG")
arr, scale = _load_bgr(jpg)
check("_load_bgr decode un JPEG sain -> array BGR",
      isinstance(arr, np.ndarray) and arr.ndim == 3 and arr.shape[2] == 3)
check("thumbnail applique (cote max 1024) et scale coherent",
      max(arr.shape[:2]) <= 1024 and abs(scale - 1440/arr.shape[1]) < 1e-6)

# 2) EINVAL persistant -> ImageReadError apres 3 essais (open injecte).
calls = {"n": 0}
def fake_open_einval(*a, **k):
    calls["n"] += 1
    raise OSError(22, "Invalid argument")
G["open"] = fake_open_einval
t0 = time.time()
try:
    _read_bytes_retry("X", tries=3, pause=0.01)
    check("EINVAL persistant -> ImageReadError", False)
except ImageReadError as e:
    check("EINVAL persistant -> ImageReadError leve", True)
    check("3 tentatives effectuees", calls["n"] == 3)
    check("errno d'origine chaine (Invalid argument)", "Invalid argument" in str(e))
except Exception as e:
    check(f"type d'exception attendu ImageReadError (recu {type(e).__name__})", False)

# 3) EINVAL transitoire : echoue 2 fois puis reussit -> renvoie les octets.
seq = {"n": 0}
real_open = open
def fake_open_flaky(path, *a, **k):
    seq["n"] += 1
    if seq["n"] < 3:
        raise OSError(22, "Invalid argument")
    return real_open(jpg, "rb")
G["open"] = fake_open_flaky
data = _read_bytes_retry("X", tries=3, pause=0.01)
check("EINVAL transitoire (2 KO puis OK) -> octets recuperes", len(data) > 100)
G["open"] = real_open  # restaure

# 4) Classement des entrees `failed`.
check("failed 'Invalid argument' -> transitoire",
      _is_transient_io_fail({"failed": True, "error": "[Errno 22] Invalid argument"}))
check("failed 'Errno 22' -> transitoire",
      _is_transient_io_fail({"failed": True, "error": "OSError Errno 22"}))
check("failed decodage corrompu -> NON transitoire (reste failed)",
      not _is_transient_io_fail({"failed": True, "error": "cannot identify image file"}))
check("entree saine (non failed) -> NON transitoire",
      not _is_transient_io_fail({"faces": [], "n": 0}))
check("None -> NON transitoire", not _is_transient_io_fail(None))

print("\nRESULTAT:", "TOUS VERTS" if ok else "ECHEC")
sys.exit(0 if ok else 1)
