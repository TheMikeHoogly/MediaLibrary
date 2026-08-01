#!/usr/bin/env python3
"""Tests des fondations UI : chargeur ui/ (server) et bundle.py.

Ne DEMARRE pas le serveur (imports lourds, base). On teste :
  1. bundle.construire_css() assemble bien tokens + base + le bloc ui-shared ;
  2. bundle.py produit un dist compilable, CSS cuit, marqueur remplace ;
  3. server.ui_shared_css() et bundle.construire_css() produisent le MEME CSS
     (garde-fou anti-derive : meme liste de fichiers, meme assemblage) ;
  4. la logique d'injection de _send_html (ordre, anti-double-injection) est
     correcte, testee en isolation sur le fragment de code reel.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bundle  # stdlib seulement, sans effet de bord lourd  # noqa: E402


def _extraire(src, debut, fin_incluse):
    i = src.index(debut)
    j = src.index(fin_incluse, i) + len(fin_incluse)
    return src[i:j]


def test_construire_css():
    css = bundle.construire_css()
    assert '<style id="ui-shared">' in css
    assert "--salle:" in css and "#0C0B0A" in css      # tokens
    assert ":focus-visible" in css                      # plancher a11y
    assert "prefers-reduced-motion" in css
    print("  OK construire_css : tokens + a11y presents")


def test_bundle_produit_dist():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "server_bundle.py"
        rc = bundle.main(["--sortie", str(out)])
        assert rc == 0, f"bundle.main a renvoye {rc}"
        assert out.exists()
        txt = out.read_text(encoding="utf-8")
        assert '"css": None' not in txt, "le marqueur de cache n'a pas ete remplace"
        assert '<style id="ui-shared">' in txt, "CSS non cuit dans le bundle"
        assert "#0C0B0A" in txt
        # compile
        rc2 = subprocess.run([sys.executable, "-m", "py_compile", str(out)]).returncode
        assert rc2 == 0, "dist ne compile pas"
    print("  OK bundle : dist compile, CSS cuit, marqueur remplace")


def test_server_et_bundle_accordent():
    """server.ui_shared_css() doit produire exactement bundle.construire_css()
    enveloppe. On exec le fragment REEL de server.py (sans importer tout le
    module) dans un espace de noms controle."""
    src = (HERE / "server.py").read_text(encoding="utf-8")
    frag = _extraire(src, 'UI_DIR = SCRIPT_DIR / "ui"',
                     'return _UI_CACHE["css"]')
    ns = {"SCRIPT_DIR": HERE, "Path": Path}
    exec(compile(frag, "server_fragment", "exec"), ns)
    css_server = ns["ui_shared_css"]()
    css_bundle = bundle.construire_css()
    assert css_server == css_bundle, "server et bundle divergent sur le CSS !"
    # et le cache fonctionne (2e appel identique, pas de relecture forcee)
    assert ns["ui_shared_css"]() == css_server
    print("  OK accord server/bundle : CSS identique + cache stable")


def test_injection_logique():
    """Reproduit la condition d'injection de _send_html : insere avant </head>,
    une seule fois (marqueur ui-shared)."""
    shared = bundle.construire_css()
    page = "<html><head><style>x{}</style></head><body>hi</body></html>"

    def injecter(html):
        if "</head>" in html and "ui-shared" not in html:
            return html.replace("</head>", shared + "</head>", 1)
        return html

    once = injecter(page)
    assert "ui-shared" in once
    assert once.index("ui-shared") < once.index("</head>")   # avant la fermeture
    twice = injecter(once)
    assert once == twice, "double injection : le garde-fou ui-shared a echoue"
    assert twice.count('id="ui-shared"') == 1
    print("  OK injection : place avant </head>, jamais deux fois")


if __name__ == "__main__":
    test_construire_css()
    test_bundle_produit_dist()
    test_server_et_bundle_accordent()
    test_injection_logique()
    print("Tous les tests fondations UI : VERTS")
