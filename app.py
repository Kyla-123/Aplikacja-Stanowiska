from flask import Flask, request, jsonify, session, make_response
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super_secret_key'
CORS(app, supports_credentials=True, origins=["http://127.0.0.1:8080"])

DB = 'stanowiska.db'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # główna tabela
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
    # tabela ustawień użytkowników
    c.execute("""CREATE TABLE IF NOT EXISTS user_settings (
        username TEXT PRIMARY KEY,
        default_duration INTEGER DEFAULT 1,
        notifications INTEGER DEFAULT 1
    )""")
    conn.commit()
    conn.close()

def clean_expired():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("""
      UPDATE stanowiska
      SET reserved=0, reserved_by=NULL, reserved_from=NULL, reserved_to=NULL
      WHERE reserved=1 AND reserved_to <= ?
    """, (now,))
    conn.commit()
    conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    username = request.get_json().get('username')
    session['username'] = username
    return jsonify({"message": f"Zalogowano jako {username}"})

@app.route('/api/get_status', methods=['GET'])
def get_status():
    clean_expired()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, occupied, reserved, reserved_by, reserved_from, reserved_to FROM stanowiska")
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/api/reserve', methods=['POST'])
def reserve():
    user = session.get('username')
    if not user:
        return jsonify({"error":"Nie zalogowano"}), 403
    data = request.get_json()
    id_, start, end = data['id'], data['start'], data['end']
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT occupied, reserved FROM stanowiska WHERE id=?", (id_,))
    occ, res = c.fetchone()
    if occ or res:
        conn.close()
        return jsonify({"error":"Stanowisko zajęte lub zarezerwowane"}), 400
    c.execute("""
      UPDATE stanowiska
      SET reserved=1, reserved_by=?, reserved_from=?, reserved_to=?
      WHERE id=?
    """, (user, start, end, id_))
    conn.commit()
    conn.close()
    return jsonify({"status":"Zarezerwowano"})

@app.route('/api/cancel', methods=['POST'])
def cancel():
    user = session.get('username')
    if not user:
        return jsonify({"error":"Nie zalogowano"}), 403
    id_ = request.get_json().get('id')
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
      UPDATE stanowiska
      SET reserved=0, reserved_by=NULL, reserved_from=NULL, reserved_to=NULL
      WHERE id=? AND reserved_by=?
    """, (id_, user))
    conn.commit()
    conn.close()
    return jsonify({"status":"Anulowano"})

@app.route('/api/my_reservations', methods=['GET'])
def my_reservations():
    user = session.get('username')
    if not user:
        return jsonify([]), 403
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
      SELECT id, reserved_from, reserved_to
      FROM stanowiska
      WHERE reserved=1 AND reserved_by=?
    """, (user,))
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/api/admin/reservations', methods=['GET'])
def admin_reservations():
    if session.get('username') != 'admin':
        return jsonify([]), 403
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
      SELECT id, reserved_by, reserved_from, reserved_to
      FROM stanowiska
      WHERE reserved=1
    """)
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/api/admin/cancel', methods=['POST'])
def admin_cancel():
    if session.get('username') != 'admin':
        return jsonify({"error":"Brak uprawnień"}), 403
    id_ = request.get_json().get('id')
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
      UPDATE stanowiska
      SET reserved=0, reserved_by=NULL, reserved_from=NULL, reserved_to=NULL
      WHERE id=?
    """, (id_,))
    conn.commit()
    conn.close()
    return jsonify({"status":"Anulowano przez admina"})

@app.route('/api/export_csv')
def export_csv():
    import csv, io
    clean_expired()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, reserved_by, reserved_from, reserved_to FROM stanowiska WHERE reserved=1")
    rows = c.fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','User','From','To'])
    writer.writerows(rows)
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv'
    resp.headers['Content-Disposition'] = 'attachment; filename=rezerwacje.csv'
    return resp

@app.route('/api/settings', methods=['GET','POST'])
def settings():
    user = session.get('username')
    if not user:
        return jsonify({"error":"Nie zalogowano"}), 403
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if request.method == 'GET':
        c.execute("SELECT default_duration, notifications FROM user_settings WHERE username=?", (user,))
        row = c.fetchone()
        conn.close()
        if row:
            return jsonify({"default_duration": row[0], "notifications": bool(row[1])})
        else:
            return jsonify({"default_duration": 1, "notifications": True})
    data = request.get_json()
    dur = int(data.get('default_duration', 1))
    notif = 1 if data.get('notifications', True) else 0
    c.execute("""
      INSERT INTO user_settings(username, default_duration, notifications)
      VALUES(?,?,?)
      ON CONFLICT(username) DO UPDATE SET
        default_duration=excluded.default_duration,
        notifications=excluded.notifications
    """, (user, dur, notif))
    conn.commit()
    conn.close()
    return jsonify({"status":"Settings saved"})

@app.route('/api/stats', methods=['GET'])
def stats():
    clean_expired()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stanowiska WHERE reserved=1")
    total = c.fetchone()[0]
    c.execute("""
      SELECT id, COUNT(*) as cnt FROM stanowiska
      WHERE reserved=1
      GROUP BY id
      ORDER BY cnt DESC
      LIMIT 1
    """)
    top = c.fetchone()
    top_station = {"id": top[0], "count": top[1]} if top else {"id": None, "count": 0}
    c.execute("SELECT reserved_from FROM stanowiska WHERE reserved=1")
    byDay = {}
    byHour = {}
    for (fr,) in c.fetchall():
        dt = datetime.fromisoformat(fr)
        dy = dt.strftime("%a")
        hr = dt.hour
        byDay[dy] = byDay.get(dy, 0) + 1
        byHour[hr] = byHour.get(hr, 0) + 1
    conn.close()
    return jsonify({"total": total, "topStation": top_station, "byDay": byDay, "byHour": byHour})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
