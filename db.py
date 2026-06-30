import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "loteria.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_connection()
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
    conn.commit()

    existing = conn.execute("SELECT COUNT(*) as cnt FROM numeros").fetchone()
    if existing["cnt"] == 0:
        for i in range(1, 101):
            conn.execute(
                "INSERT INTO numeros (numero, estado) VALUES (?, 'disponible')",
                (i,),
            )
        conn.commit()
    conn.close()

def get_numeros(estado=None):
    conn = get_connection()
    query = "SELECT * FROM numeros"
    params = []
    if estado:
        query += " WHERE estado = ?"
        params.append(estado)
    query += " ORDER BY numero"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_numero(numero_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM numeros WHERE id = ?", (numero_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_numero_by_numero(numero):
    conn = get_connection()
    row = conn.execute("SELECT * FROM numeros WHERE numero = ?", (numero,)).fetchone()
    conn.close()
    return dict(row) if row else None

def reservar_numero(numero_id, nombre, email, telefono, whatsapp):
    conn = get_connection()
    row = conn.execute("SELECT estado FROM numeros WHERE id = ?", (numero_id,)).fetchone()
    if not row or row["estado"] != "disponible":
        conn.close()
        return False
    conn.execute(
        """UPDATE numeros SET estado='reservado',
           comprador_nombre=?, comprador_email=?, comprador_telefono=?,
           comprador_whatsapp=?, fecha_reserva=datetime('now','localtime'),
           updated_at=datetime('now','localtime')
           WHERE id=?""",
        (nombre, email, telefono, whatsapp, numero_id),
    )
    conn.commit()
    conn.close()
    return True

def marcar_pagado(numero_id, monto=0):
    conn = get_connection()
    conn.execute(
        """UPDATE numeros SET estado='pagado', fecha_pago=datetime('now','localtime'),
           monto=?, updated_at=datetime('now','localtime')
           WHERE id=?""",
        (monto, numero_id),
    )
    conn.commit()
    conn.close()

def actualizar_mp_preference(numero_id, preference_id):
    conn = get_connection()
    conn.execute(
        "UPDATE numeros SET mp_preference_id=?, updated_at=datetime('now','localtime') WHERE id=?",
        (preference_id, numero_id),
    )
    conn.commit()
    conn.close()

def actualizar_mp_payment(numero_id, payment_id):
    conn = get_connection()
    conn.execute(
        "UPDATE numeros SET mp_payment_id=?, updated_at=datetime('now','localtime') WHERE id=?",
        (payment_id, numero_id),
    )
    conn.commit()
    conn.close()

def stats():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as c FROM numeros").fetchone()["c"]
    disponibles = conn.execute("SELECT COUNT(*) as c FROM numeros WHERE estado='disponible'").fetchone()["c"]
    reservados = conn.execute("SELECT COUNT(*) as c FROM numeros WHERE estado='reservado'").fetchone()["c"]
    pagados = conn.execute("SELECT COUNT(*) as c FROM numeros WHERE estado='pagado'").fetchone()["c"]
    recaudado = conn.execute("SELECT COALESCE(SUM(monto),0) as s FROM numeros WHERE estado='pagado'").fetchone()["s"]
    conn.close()
    return {
        "total": total,
        "disponibles": disponibles,
        "reservados": reservados,
        "pagados": pagados,
        "recaudado": recaudado,
    }

def get_config(clave, default=""):
    conn = get_connection()
    row = conn.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
    conn.close()
    return row["valor"] if row else default

def set_config(clave, valor):
    conn = get_connection()
    conn.execute(
        "INSERT INTO config (clave, valor) VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor=?",
        (clave, valor, valor),
    )
    conn.commit()
    conn.close()

def get_all_config():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM config").fetchall()
    conn.close()
    return {r["clave"]: r["valor"] for r in rows}
