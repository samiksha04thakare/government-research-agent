import sqlite3
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect("research.db")
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in tables:
    count = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"\nTable {t} ({count} rows):")
    cols = [d[0] for d in c.execute(f"SELECT * FROM {t} LIMIT 1").description]
    print("  Columns:", cols)
    rows = c.execute(f"SELECT * FROM {t} LIMIT 5").fetchall()
    for row in rows:
        print(" ", row[:4])
