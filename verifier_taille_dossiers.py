import sqlite3, pathlib, collections
db = pathlib.Path(__file__).resolve().parent / 'photos.db'
cx = sqlite3.connect('file:' + str(db) + '?mode=ro', uri=True, timeout=30)
cx.execute('PRAGMA busy_timeout=30000')
comptes = collections.Counter()
for (k,) in cx.execute('SELECT k FROM tags'):
    comptes[str(pathlib.PureWindowsPath(k).parent)] += 1
cx.close()
print('dossiers indexes :', len(comptes))
print('--- les 12 plus gros ---')
for d, n in comptes.most_common(12):
    print('%6d  %s' % (n, d))
print('--- les dossiers des 6 photos sensibles ---')
for d in ('2026\\260531_Samsung_MHU\\Camera', '2026', '2023', '2022', 'Floufline'):
    for k, n in comptes.items():
        if k.endswith(d):
            print('%6d  %s' % (n, k))
