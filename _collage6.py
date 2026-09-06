# -*- coding: utf-8 -*-
import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

BASE = Path.home() / 'mnt' / 'Photos'
CIBLES = [
    ('Photos Mike/2026/260531_Samsung_MHU/Camera/20260411_160856.jpg', 'releve de compte bancaire'),
    ('Photos Mike/2023/20230326_190923.jpg',                            'decompte de charges + bulletin de versement'),
    ('Photos Mike/2022/20220805_200910.jpg',                            'courrier bancaire avec IBAN'),
    ('Photos Mike/2026/260531_Samsung_MHU/Camera/20260502_093501.jpg',   'carte d assurance-maladie (no AVS, date de naissance)'),
    ('Photos Flo/Floufline/20240226_223732.jpg',                        'document officiel au nom de Florine'),
    ('Photos Mike/2026/20260201_202623.jpg',                            'certificat medical d incapacite de travail'),
]
COTE, COLS, MARGE = 620, 3, 44
lignes = (len(CIBLES) + COLS - 1) // COLS
toile = Image.new('RGB', (COLS * COTE, lignes * (COTE + MARGE)), (12, 11, 10))
crayon = ImageDraw.Draw(toile)
etats = []
for i, (rel, quoi) in enumerate(CIBLES):
    p = BASE / rel
    x, y = (i % COLS) * COTE, (i // COLS) * (COTE + MARGE)
    n = i + 1
    marque = ''
    if not p.exists():
        # Mike a deja agi : soit PRIVE, soit la corbeille d effacements.
        nom = Path(rel).name
        parts = Path(rel).parts
        for k in range(1, len(parts)):
            cand = BASE.joinpath(*parts[:k], 'PRIVE', nom)
            if cand.exists():
                p, marque = cand, ' — deja PRIVEE'
                break
        if not p.exists():
            for lot in sorted((BASE / '.corbeille-effacements').iterdir(),
                              reverse=True):
                cand = lot / nom
                if lot.is_dir() and cand.exists():
                    p, marque = cand, ' — a la CORBEILLE'
                    break
    if p.exists():
        try:
            im = Image.open(p); im.draft('RGB', (COTE, COTE)); im = im.convert('RGB')
            im.thumbnail((COTE, COTE))
            toile.paste(im, (x + (COTE - im.width) // 2, y + (COTE - im.height) // 2))
            etats.append(f'{n}. OK{marque}   {rel}')
        except Exception as e:
            crayon.text((x + 14, y + COTE // 2), f'illisible ({type(e).__name__})', fill=(200, 50, 30))
            etats.append(f'{n}. ILLISIBLE {rel}')
    else:
        crayon.text((x + 14, y + COTE // 2), 'INTROUVABLE — deja deplacee ?', fill=(255, 122, 26))
        etats.append(f'{n}. ABSENTE  {rel}')
    crayon.text((x + 10, y + COTE + 6),  f'{n}. {quoi}{marque}', fill=(242, 237, 230))
    crayon.text((x + 10, y + COTE + 24), f'   {Path(rel).name}', fill=(163, 156, 147))
SORTIE = Path.home() / 'mnt' / 'MediaLibrary' / '_planches' / 'les_6_sensibles.jpg'
SORTIE.parent.mkdir(exist_ok=True)
toile.save(SORTIE, quality=80, optimize=True)
print('\n'.join(etats))
print(f'\n{SORTIE.name} : {SORTIE.stat().st_size/1024:.0f} Ko')
