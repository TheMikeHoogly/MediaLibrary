"""Sonde de diagnostic pour l'« Errno 22 / Invalid argument » de _load_bgr.

Isole chaque etape du chargement d'image (comme _load_bgr dans server.py) sur
le fichier reel, puis compare l'ouverture via SMB a une copie locale. C'est la
copie locale qui departage :
  - copie locale KO  -> le fichier lui-meme est abime (tronque / en-tete / EXIF)
  - copie locale OK  -> le probleme est cote SMB (chemin UNC, handle, concurrence)

Usage :
  python diag_errno22.py "\\\\NAS-Bremblens\\home\\Photos\\_Uploads\\ARZOPA\\RKKuGn-20260604_134326682.jpg"

Sans argument, teste le fichier signale par defaut.
"""
import os
import sys
import shutil
import tempfile
import traceback

DEFAULT = r"\\NAS-Bremblens\home\Photos\_Uploads\ARZOPA\RKKuGn-20260604_134326682.jpg"


def step(label, fn):
    """Lance fn(), affiche OK ou l'exception complete (type + errno)."""
    try:
        res = fn()
        print(f"  [OK]  {label}" + (f" -> {res}" if res is not None else ""))
        return True
    except Exception as e:
        errno = getattr(e, "errno", None)
        print(f"  [KO]  {label} : {type(e).__name__}: {e}"
              + (f"  (errno={errno})" if errno is not None else ""))
        traceback.print_exc()
        return False


def probe(path, tag):
    print(f"\n=== {tag} : {path} ===")
    try:
        sz = os.path.getsize(path)
        print(f"  taille : {sz} octets")
    except Exception as e:
        print(f"  taille : illisible ({e})")
        return

    # Premiers / derniers octets : SOI = ff d8, EOI = ff d9 pour un JPEG sain.
    try:
        with open(path, "rb") as f:
            head = f.read(4)
            f.seek(-4, os.SEEK_END)
            tail = f.read(4)
        print(f"  head : {head.hex()}   tail : {tail.hex()}"
              f"   (JPEG sain : head ffd8..., tail ...ffd9)")
    except Exception as e:
        print(f"  lecture brute des bornes : KO ({e})")

    from PIL import Image, ImageOps

    # Etape par etape, comme _load_bgr.
    im_box = {}

    def _open():
        im_box["im"] = Image.open(path)
        return f"format={im_box['im'].format}, size={im_box['im'].size}, mode={im_box['im'].mode}"

    if not step("Image.open (lazy, en-tete seul)", _open):
        return
    step("im.load() (decode complet)", lambda: im_box["im"].load() and None)
    step("ImageOps.exif_transpose", lambda: ImageOps.exif_transpose(im_box["im"]) and None)
    step('convert("RGB")', lambda: im_box["im"].convert("RGB") and None)

    # Rejeu avec tolerance aux images tronquees.
    def _truncated():
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            with Image.open(path) as im2:
                im2 = ImageOps.exif_transpose(im2).convert("RGB")
                return f"decode tolerant OK, size={im2.size}"
        finally:
            ImageFile.LOAD_TRUNCATED_IMAGES = False

    step("Rejeu avec LOAD_TRUNCATED_IMAGES=True", _truncated)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    print("Sonde Errno 22 --", path)

    # 1) Via le chemin d'origine (SMB si UNC).
    probe(path, "SOURCE (chemin d'origine)")

    # 2) Copie locale, puis meme batterie de tests.
    try:
        tmpdir = tempfile.mkdtemp(prefix="diag_errno22_")
        local = os.path.join(tmpdir, os.path.basename(path))
        shutil.copyfile(path, local)
        print(f"\ncopie locale creee : {local}")
        probe(local, "COPIE LOCALE")
    except Exception as e:
        print(f"\ncopie locale impossible : {type(e).__name__}: {e}")
        print("  -> si la copie elle-meme echoue en Errno 22, le probleme est"
              " la lecture SMB du fichier, pas son contenu.")


if __name__ == "__main__":
    main()
