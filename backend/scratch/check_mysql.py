import pymysql

# Try common passwords or blank
passwords = ['', 'root', 'password', 'admin', '123456', 'mysql']
users = ['root', 'bg_ai', 'bgai']

for u in users:
    for p in passwords:
        try:
            conn = pymysql.connect(host='localhost', port=3306, user=u, password=p)
            print(f"SUCCESS connecting as {u} with password {p!r}")
            with conn.cursor() as cur:
                cur.execute("SHOW DATABASES")
                dbs = cur.fetchall()
                print("Databases:", dbs)
                for (db,) in dbs:
                    if db in ('information_schema', 'mysql', 'performance_schema', 'sys'):
                        continue
                    cur.execute(f"USE `{db}`")
                    cur.execute("SHOW TABLES")
                    tbls = cur.fetchall()
                    tot_rows = 0
                    tot_cols = 0
                    for (tbl,) in tbls:
                        cur.execute(f"SELECT COUNT(*) FROM `{tbl}`")
                        r_cnt = cur.fetchone()[0]
                        cur.execute(f"DESCRIBE `{tbl}`")
                        c_cnt = len(cur.fetchall())
                        tot_rows += r_cnt
                        tot_cols += c_cnt
                        print(f"  [{db}] table {tbl}: rows={r_cnt}, cols={c_cnt}")
                    print(f"DATABASE {db}: tables={len(tbls)}, rows={tot_rows}, cols={tot_cols}")
            conn.close()
            break
        except Exception as e:
            pass

