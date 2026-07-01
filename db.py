import os

DATABASE_URL = os.environ.get("DATABASE_URL")


def _is_pg():
    return bool(DATABASE_URL)


def _ph():
    return "%s" if _is_pg() else "?"


def _now():
    return "CURRENT_TIMESTAMP" if _is_pg() else "datetime('now','localtime')"


def get_connection():
    if _is_pg():
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        import sqlite3

        DB_PATH = os.path.join(os.path.dirname(__file__), "data", "loteria.db")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def _cur(conn):
    if _is_pg():
        import psycopg2.extras

        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor() if hasattr(conn, 'cursor') else conn


def _commit(conn):
    if _is_pg():
        conn.commit()
    else:
        conn.commit()


def _close(conn, cur=None):
    if cur:
        cur.close()
    conn.close()


def init_db():
    conn = get_connection()
    cur = _cur(conn)

    if _is_pg():
        cur.execute("""
            CREATE TABLE IF NOT EXISTS numeros (
                id SERIAL PRIMARY KEY,
                numero INTEGER NOT NULL UNIQUE,
                estado VARCHAR(20) NOT NULL DEFAULT 'disponible',
                comprador_nombre TEXT DEFAULT '',
                comprador_email TEXT DEFAULT '',
                comprador_telefono TEXT DEFAULT '',
                comprador_whatsapp TEXT DEFAULT '',
                fecha_reserva TIMESTAMP,
                fecha_pago TIMESTAMP,
                monto NUMERIC DEFAULT 0,
                mp_preference_id TEXT DEFAULT '',
                mp_payment_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS config (
                clave VARCHAR(100) PRIMARY KEY,
                valor TEXT NOT NULL DEFAULT ''
            )
        """)
    else:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS numeros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero INTEGER NOT NULL UNIQUE,
                estado TEXT NOT NULL DEFAULT 'disponible',
                comprador_nombre TEXT DEFAULT '',
                comprador_email TEXT DEFAULT '',
                comprador_telefono TEXT DEFAULT '',
                comprador_whatsapp TEXT DEFAULT '',
                fecha_reserva TEXT,
                fecha_pago TEXT,
                monto REAL DEFAULT 0,
                mp_preference_id TEXT DEFAULT '',
                mp_payment_id TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL DEFAULT ''
            );
        """)

    _commit(conn)
    p = _ph()
    cur.execute(f"SELECT COUNT(*) as cnt FROM numeros")
    row = cur.fetchone()
    cnt = row["cnt"] if isinstance(row, dict) else row[0]
    if cnt == 0:
        for i in range(1, 101):
            cur.execute(f"INSERT INTO numeros (numero, estado) VALUES ({p}, 'disponible')", (i,))
        _commit(conn)

    _close(conn, cur)


def get_numeros(estado=None):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    query = "SELECT * FROM numeros"
    params = []
    if estado:
        query += f" WHERE estado = {p}"
        params.append(estado)
    query += " ORDER BY numero"
    cur.execute(query, params)
    rows = cur.fetchall()
    _close(conn, cur)
    return [dict(r) for r in rows]


def get_numero(numero_id):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    cur.execute(f"SELECT * FROM numeros WHERE id = {p}", (numero_id,))
    row = cur.fetchone()
    _close(conn, cur)
    return dict(row) if row else None


def get_numero_by_numero(numero):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    cur.execute(f"SELECT * FROM numeros WHERE numero = {p}", (numero,))
    row = cur.fetchone()
    _close(conn, cur)
    return dict(row) if row else None


def reservar_numero(numero_id, nombre, email, telefono, whatsapp):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    now = _now()

    cur.execute(f"SELECT estado FROM numeros WHERE id = {p}", (numero_id,))
    row = cur.fetchone()
    if not row or (row["estado"] if isinstance(row, dict) else row[0]) != "disponible":
        _close(conn, cur)
        return False

    cur.execute(
        f"""UPDATE numeros SET estado='reservado',
           comprador_nombre={p}, comprador_email={p}, comprador_telefono={p},
           comprador_whatsapp={p}, fecha_reserva={now},
           updated_at={now}
           WHERE id={p}""",
        (nombre, email, telefono, whatsapp, numero_id),
    )
    _commit(conn)
    _close(conn, cur)
    return True


def marcar_pagado(numero_id, monto=0):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    now = _now()
    cur.execute(
        f"""UPDATE numeros SET estado='pagado', fecha_pago={now},
           monto={p}, updated_at={now}
           WHERE id={p}""",
        (monto, numero_id),
    )
    _commit(conn)
    _close(conn, cur)


def actualizar_mp_preference(numero_id, preference_id):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    now = _now()
    cur.execute(
        f"UPDATE numeros SET mp_preference_id={p}, updated_at={now} WHERE id={p}",
        (preference_id, numero_id),
    )
    _commit(conn)
    _close(conn, cur)


def actualizar_mp_payment(numero_id, payment_id):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    now = _now()
    cur.execute(
        f"UPDATE numeros SET mp_payment_id={p}, updated_at={now} WHERE id={p}",
        (payment_id, numero_id),
    )
    _commit(conn)
    _close(conn, cur)


def stats():
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    cur.execute(f"SELECT COUNT(*) as c FROM numeros")
    total = cur.fetchone()["c"]
    cur.execute(f"SELECT COUNT(*) as c FROM numeros WHERE estado='disponible'")
    disponibles = cur.fetchone()["c"]
    cur.execute(f"SELECT COUNT(*) as c FROM numeros WHERE estado='reservado'")
    reservados = cur.fetchone()["c"]
    cur.execute(f"SELECT COUNT(*) as c FROM numeros WHERE estado='pagado'")
    pagados = cur.fetchone()["c"]
    cur.execute(f"SELECT COALESCE(SUM(monto),0) as s FROM numeros WHERE estado='pagado'")
    recaudado = cur.fetchone()["s"]
    _close(conn, cur)
    return {
        "total": total,
        "disponibles": disponibles,
        "reservados": reservados,
        "pagados": pagados,
        "recaudado": recaudado,
    }


def get_config(clave, default=""):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    cur.execute(f"SELECT valor FROM config WHERE clave={p}", (clave,))
    row = cur.fetchone()
    _close(conn, cur)
    return row["valor"] if row else default


def set_config(clave, valor):
    conn = get_connection()
    cur = _cur(conn)
    p = _ph()
    if _is_pg():
        cur.execute(
            f"INSERT INTO config (clave, valor) VALUES ({p}, {p}) ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor",
            (clave, valor),
        )
    else:
        cur.execute(
            f"INSERT INTO config (clave, valor) VALUES ({p}, {p}) ON CONFLICT(clave) DO UPDATE SET valor={p}",
            (clave, valor, valor),
        )
    _commit(conn)
    _close(conn, cur)


def get_all_config():
    conn = get_connection()
    cur = _cur(conn)
    cur.execute("SELECT * FROM config")
    rows = cur.fetchall()
    _close(conn, cur)
    return {r["clave"]: r["valor"] for r in rows}
