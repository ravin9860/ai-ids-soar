import sqlite3, os, json, time
DB_PATH = os.path.join(os.path.dirname(__file__), "soar.db")

def _conn():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("""CREATE TABLE IF NOT EXISTS incidents(
        id TEXT PRIMARY KEY, time_utc TEXT, label TEXT, severity TEXT,
        src_ip TEXT, dst_ip TEXT, score REAL, meta_json TEXT, status TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS actions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT, time_utc TEXT,
        action TEXT, result_json TEXT
    )""")
    return con

CON = _conn()

def add_incident(inc):
    CON.execute("""INSERT OR REPLACE INTO incidents
      (id, time_utc, label, severity, src_ip, dst_ip, score, meta_json, status)
      VALUES (?,?,?,?,?,?,?,?,?)""",
      (inc["id"], inc["time_utc"], inc["label"], inc["severity"],
       inc.get("source",""), inc.get("destination",""), inc["probability"],
       json.dumps(inc.get("meta",{})), "Open"))
    CON.commit()

def list_incidents(limit=50):
    cur = CON.execute("SELECT id,time_utc,label,severity,src_ip,dst_ip,score,status FROM incidents ORDER BY time_utc DESC LIMIT ?", (limit,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

def update_status(incident_id, status):
    CON.execute("UPDATE incidents SET status=? WHERE id=?", (status, incident_id))
    CON.commit()

def add_action(incident_id, action, result):
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    CON.execute("INSERT INTO actions (incident_id, time_utc, action, result_json) VALUES (?,?,?,?)",
                (incident_id, now, action, json.dumps(result)))
    CON.commit()

def list_actions(incident_id):
    cur = CON.execute("SELECT time_utc, action, result_json FROM actions WHERE incident_id=? ORDER BY id ASC", (incident_id,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]
