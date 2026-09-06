import sqlite3, pathlib
db = pathlib.Path(__file__).resolve().parent / 'photos.db'
cx = sqlite3.connect('file:' + str(db) + '?mode=ro', uri=True, timeout=30)
for (n,) in cx.execute("select name from sqlite_master where type='table'"):
    try:
        c = cx.execute(f'select count(*) from "{n}"').fetchone()[0]
    except Exception as e:
        c = e
    print(n, c)
