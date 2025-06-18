 import sqlite3

conn = sqlite3.connect('stanowiska.db')
c = conn.cursor()


try:
    c.execute("ALTER TABLE stanowiska ADD COLUMN reserved_by TEXT")
except sqlite3.OperationalError:
    print("Kolumna 'reserved_by' już istnieje")

try:
    c.execute("ALTER TABLE stanowiska ADD COLUMN reserved_from TEXT")
except sqlite3.OperationalError:
    print("Kolumna 'reserved_from' już istnieje")

try:
    c.execute("ALTER TABLE stanowiska ADD COLUMN reserved_to TEXT")
except sqlite3.OperationalError:
    print("Kolumna 'reserved_to' już istnieje")

conn.commit()
conn.close()

print("Gotowe – struktura bazy została zaktualizowana.")
