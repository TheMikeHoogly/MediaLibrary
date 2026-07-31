"""
Tests de l'ordonnanceur et de l'arbitre GPU.

Le test central est celui de la NON-FAMINE : c'est le defaut qu'on corrige,
il doit etre demontre, pas suppose.

    python test_ordonnanceur.py
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ordonnanceur import ArbitreGPU, Ordonnanceur  # noqa: E402

ECHECS, RESULTATS = [], []


def verifie(nom, cond, detail=""):
    RESULTATS.append((nom, bool(cond), detail))
    if not cond:
        ECHECS.append(f"{nom} — {detail}")


def t_exclusion_mutuelle():
    o = Ordonnanceur({"a": 1, "b": 1})
    simultanes = [0]
    maxi = [0]
    verrou = threading.Lock()

    def travail(nom, n):
        for _ in range(n):
            with o.creneau(nom, timeout=10) as ok:
                if not ok:
                    return
                with verrou:
                    simultanes[0] += 1
                    maxi[0] = max(maxi[0], simultanes[0])
                time.sleep(0.004)
                with verrou:
                    simultanes[0] -= 1

    ths = [threading.Thread(target=travail, args=(n, 25)) for n in ("a", "b")]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=20)
    verifie("un seul travail lourd a la fois", maxi[0] == 1,
            f"max simultane = {maxi[0]}")


def t_pas_de_famine():
    """LE test : un travail lent et peu prioritaire doit passer quand meme.

    C'est exactement le cas de l'encodage semantique face au balayage des
    visages, ou l'ancien « if system_busy(): dors » le bloquait a 5 %.
    """
    o = Ordonnanceur({"visages": 4, "semantique": 1})
    passages = {"visages": 0, "semantique": 0}
    stop = [False]

    def gourmand():
        while not stop[0]:
            with o.creneau("visages", timeout=5) as ok:
                if ok:
                    passages["visages"] += 1
                    time.sleep(0.003)

    def affame():
        while not stop[0]:
            with o.creneau("semantique", timeout=5) as ok:
                if ok:
                    passages["semantique"] += 1
                    time.sleep(0.003)

    ths = [threading.Thread(target=gourmand), threading.Thread(target=gourmand),
           threading.Thread(target=affame)]
    for t in ths:
        t.start()
    time.sleep(1.2)
    stop[0] = True
    for t in ths:
        t.join(timeout=10)

    verifie("le travail peu prioritaire n'est jamais affame",
            passages["semantique"] > 0, str(passages))
    total = sum(passages.values())
    part = passages["semantique"] / max(total, 1)
    # poids 1 contre 4 (x2 threads) -> part theorique ~1/9 ; on verifie
    # simplement qu'elle est du bon ordre et jamais nulle.
    verifie("sa part reste dans l'ordre de grandeur attendu",
            0.03 <= part <= 0.40, f"part = {part:.2%}  {passages}")
    print(f"\n  Repartition observee : {passages}  "
          f"(semantique {part:.1%} des creneaux)")


def t_poids_respectes():
    o = Ordonnanceur({"fort": 3, "faible": 1})
    p = {"fort": 0, "faible": 0}
    stop = [False]

    def boucle(nom):
        while not stop[0]:
            with o.creneau(nom, timeout=5) as ok:
                if ok:
                    p[nom] += 1
                    time.sleep(0.001)

    ths = [threading.Thread(target=boucle, args=(n,)) for n in ("fort", "faible")]
    for t in ths:
        t.start()
    time.sleep(1.0)
    stop[0] = True
    for t in ths:
        t.join(timeout=10)
    ratio = p["fort"] / max(p["faible"], 1)
    verifie("le poids 3:1 est approche", 2.0 <= ratio <= 4.5,
            f"ratio observe = {ratio:.2f}  {p}")


def t_delai_expire():
    o = Ordonnanceur({"a": 1, "b": 1})
    assert o.tour("a", timeout=1)
    t0 = time.time()
    ok = o.tour("b", timeout=0.3)
    verifie("le delai d'attente est respecte",
            (not ok) and 0.2 < time.time() - t0 < 1.0,
            f"ok={ok} duree={time.time()-t0:.2f}s")
    o.fin("a")
    verifie("le tour se libere ensuite", o.tour("b", timeout=1))
    o.fin("b")


def t_travail_bloque():
    """Un travail qui ne rend jamais la main ne doit pas figer les autres."""
    o = Ordonnanceur({"bloque": 1, "sain": 1})
    o.tour("bloque", timeout=1)          # jamais de fin() : simule un blocage
    ok = o.tour("sain", timeout=3, duree_max=0.4)
    verifie("un travail bloque est evince apres sa duree max", ok)
    if ok:
        o.fin("sain")


def t_arbitre_vram():
    libre = [4096.0]
    a = ArbitreGPU(lambda: libre[0], total_mb=4096, reserve_mb=192)

    verifie("un premier bail passe", a.demander("ollama", 2000))
    verifie("le second tient compte du premier", a.demander("visages", 1000))
    verifie("le troisieme est refuse (plus de place)",
            not a.demander("semantique", 1200),
            f"libre = {a.libre_mb():.0f} Mo")
    a.rendre("ollama")
    verifie("apres liberation, il passe", a.demander("semantique", 1200))
    verifie("l'etat liste les baux",
            set(a.etat()["baux"]) == {"visages", "semantique"}, a.etat())

    # la marge de reserve n'est jamais allouee
    b = ArbitreGPU(lambda: 300.0, reserve_mb=192)
    verifie("la reserve est preservee", not b.demander("x", 200),
            f"libre = {b.libre_mb():.0f} Mo")
    verifie("mais une petite demande passe", b.demander("x", 100))


def t_arbitre_concurrent():
    """Deux demandes simultanees ne doivent pas se croire seules."""
    a = ArbitreGPU(lambda: 1500.0, reserve_mb=0)
    obtenus = []
    verrou = threading.Lock()

    def demande(nom):
        if a.demander(nom, 1000):
            with verrou:
                obtenus.append(nom)

    ths = [threading.Thread(target=demande, args=(f"t{i}",)) for i in range(8)]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=5)
    verifie("un seul bail de 1000 Mo sur 1500 disponibles",
            len(obtenus) == 1, f"{len(obtenus)} baux accordes : {obtenus}")


def t_sonde_en_panne():
    def sonde():
        raise RuntimeError("nvidia-smi absent")
    a = ArbitreGPU(sonde)
    verifie("une sonde en panne refuse au lieu de planter",
            not a.demander("x", 100) and a.libre_mb() == 0.0)


def main():
    for t in (t_exclusion_mutuelle, t_pas_de_famine, t_poids_respectes,
              t_delai_expire, t_travail_bloque, t_arbitre_vram,
              t_arbitre_concurrent, t_sonde_en_panne):
        try:
            t()
        except Exception as e:                                # noqa: BLE001
            import traceback
            traceback.print_exc()
            ECHECS.append(f"{t.__name__} a leve {e!r}")
            RESULTATS.append((t.__name__, False, repr(e)))

    print("\n" + "=" * 70)
    print("  RESULTATS")
    print("=" * 70)
    for nom, ok, detail in RESULTATS:
        print(f"  {'+' if ok else 'x'} {nom}" + (f"  -> {detail}" if not ok else ""))
    print("=" * 70)
    print(f"  {sum(1 for _, o, _ in RESULTATS if o)}/{len(RESULTATS)} verifications")
    print("  " + ("aucun echec" if not ECHECS else f"x {len(ECHECS)} echec(s)"))
    print("=" * 70)
    return 1 if ECHECS else 0


if __name__ == '__main__':
    sys.exit(main())
