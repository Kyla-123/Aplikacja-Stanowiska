from flask import Flask, request, jsonify, session, make_response
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'
CORS(app, supports_credentials=True, origins=["http://127.0.0.1:8080"])

def init_db():
    conn = sqlite3.connect('stanowiska.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS stanowiska (
        id INTEGER PRIMARY KEY,
        occupied INTEGER DEFAULT 0,
        reserved INTEGER DEFAULT 0,
        reserved_by TEXT,
        reserved_from TEXT,
        reserved_to TEXT
    )""")
    for i in range(1, 6):
        c.execute('INSERT OR IGNORE INTO stanowiska (id) VALUES (?)', (i,))
    conn.commit()
    conn.close()

def clean_expired():
    conn = sqlite3.connect('stanowiska.db')
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("UPDATE stanowiska SET reserved = 0, reserved_by = NULL, reserved_from = NULL, reserved_to = NULL WHERE reserved = 1 AND reserved_to <= ?", (now,))
    conn.commit()
    conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    username = request.get_json().get('username')
    session['username'] = username
    return jsonify({"message": f"Zalogowano jako {username}"})

@app.route('/api/reserve', methods=['POST'])
def reserve():
    user = session.get('username')
    if not user:
        return jsonify({"error": "Nie zalogowano"}), 403

    data = request.get_json()
    id = data['id']
    start = data['start']
    end = data['end']

    conn = sqlite3.connect('stanowiska.db')
    c = conn.cursor()
    c.execute("SELECT occupied, reserved FROM stanowiska WHERE id = ?", (id,))
    row = c.fetchone()
    if row and (row[0] or row[1]):
        conn.close()
        return jsonify({"error": "Stanowisko zajęte lub zarezerwowane"}), 400

    c.execute("UPDATE stanowiska SET reserved = 1, reserved_by = ?, reserved_from = ?, reserved_to = ? WHERE id = ?",
              (user, start, end, id))
    conn.commit()
    conn.close()
    return jsonify({"status": "Zarezerwowano"})

@app.route('/api/get_status', methods=['GET'])
def get_status():
    clean_expired()
    conn = sqlite3.connect('stanowiska.db')
    c = conn.cursor()
    c.execute("SELECT id, occupied, reserved, reserved_by, reserved_from, reserved_to FROM stanowiska")
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/api/me')
def whoami():
    return jsonify({'user': session.get('username')})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)