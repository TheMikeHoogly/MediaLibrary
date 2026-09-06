# -*- coding: utf-8 -*-
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
BASE = Path.home() / 'mnt' / 'Photos'
CORB = BASE / '.corbeille-rangement'
d = json.load(open('docs/corbeille_par_pixels.json', encoding='utf-8'))['lignes']
lot = [('SANS JUMEAU', e) for e in d['vraie_derniere_copie']] + \
      [('ILLISIBLE', e) for e in d['illisible']]
COTE, COLS, MARGE = 520, 4, 46
lignes = (len(lot) + COLS - 1) // COLS
toile = Image.new('RGB', (COLS * COTE, lignes * (COTE + MARGE)), (12, 11, 10))
cr = ImageDraw.Draw(toile)
for i, (cat, e) in enumerate(lot):
    x, y = (i % COLS) * COTE, (i // COLS) * (COTE + MARGE)
    p = CORB / e['groupe'] / e['fichier']
    try:
        im = Image.open(p); im.draft('RGB', (COTE, COTE)); im = im.convert('RGB')
        im.thumbnail((COTE, COTE))
        toile.paste(im, (x + (COTE - im.width)//2, y + (COTE - im.height)//2))
    except Exception as ex:
        cr.text((x+12, y+COTE//2), f'illisible ({type(ex).__name__})', fill=(200,60,40))
    cr.text((x+8, y+COTE+5),  f'{i+1}. {cat}', fill=(242,237,230))
    cr.text((x+8, y+COTE+21), f'   {e["fichier"][:44]}', fill=(163,156,147))
    cr.text((x+8, y+COTE+33), f'   {Path(e["canonique_notee"]).parent.name[:40]}', fill=(120,115,108))
out = Path('_planches_corbeille/les_7_a_juger.jpg')
toile.save(out, quality=80, optimize=True)
print(out, f'{out.stat().st_size/1024:.0f} Ko —', len(lot), 'cases')
for i,(c,e) in enumerate(lot,1):
    print(f'  {i}. [{c}] {e["fichier"]}  <- {e["canonique_notee"]}')
