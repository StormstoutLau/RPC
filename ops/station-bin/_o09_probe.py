import sqlite3, os
db = os.path.expanduser('~/.local/share/opencode/opencode.db')
con = sqlite3.connect('file:' + db + '?mode=ro', uri=True)
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print('TABLES_COUNT=', len(tabs))
print('TABLES=', tabs)
for t in tabs:
    if any(k in t.lower() for k in ['auth','cred','oauth','key','token','session','account']):
        try:
            n = con.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
            print('AUTH_TABLE %s rows=%d' % (t, n))
        except Exception as e:
            print('AUTH_TABLE %s err=%s' % (t, e))
con.close()