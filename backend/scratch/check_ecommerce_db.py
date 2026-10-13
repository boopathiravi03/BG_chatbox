import sqlite3
conn = sqlite3.connect('A:/bgai1/BG_AI/database/ecommerce.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('Tables:', tables)
total_rows = 0
total_cols = 0
for (t,) in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    cnt = cur.fetchone()[0]
    cur.execute(f'PRAGMA table_info("{t}")')
    cols = cur.fetchall()
    total_rows += cnt
    total_cols += len(cols)
    print(f'  {t}: rows={cnt}, cols={len(cols)}')
print(f'TOTAL: tables={len(tables)}, rows={total_rows}, cols={total_cols}')

