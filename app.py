import os
import logging
from urllib.parse import quote
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session,
)

import db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") or os.urandom(24).hex()

TITULO_SORTEO = "Rifa Solidaria × Venezuela"
PREMIO = "Camiseta oficial de la Selección Argentina"
DESCRIPCION = "Participá por una camiseta oficial de la Selección Argentina. 100% de lo recaudado será donado a fundaciones que asisten la crisis humanitaria en Venezuela."
CAUSA = "Venezuela"
BENEFICIARIO = "Fundaciones de ayuda humanitaria en Venezuela"

def _precio():
    raw = db.get_config("precio", "3000")
    try:
        return int(raw)
    except ValueError:
        return 3000

def _wa():
    return db.get_config("wa_contacto", "https://wa.me/5491122539105")

def _banco():
    return {
        "banco": db.get_config("banco_nombre", "Banco de la Nación Argentina"),
        "titular": db.get_config("banco_titular", "Jesus Gabriel Balderrama"),
        "cbu": db.get_config("banco_cbu", "0110599520000001234567"),
        "alias": db.get_config("banco_alias", "Jesus.2605"),
        "tipo": db.get_config("banco_tipo", "Caja de Ahorro"),
    }

@app.context_processor
def inject_globals():
    stats = db.stats()
    return dict(
        titulo=TITULO_SORTEO,
        premio=PREMIO,
        descripcion=DESCRIPCION,
        causa=CAUSA,
        beneficiario=BENEFICIARIO,
        wa_contacto=_wa(),
        banco=_banco(),
        precio=_precio(),
        stats=stats,
        ruta=request.path,
    )

def _pesos(val):
    return f"$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ─── Routes publicas ───────────────────────────────────────────────

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def index():
    log.info("GET /")
    numeros = db.get_numeros()
    return render_template("index.html", numeros=numeros)

@app.route("/numero/<int:numero_id>")
def numero_detalle(numero_id):
    n = db.get_numero(numero_id)
    if not n:
        flash("Número no encontrado.", "error")
        return redirect(url_for("index"))
    return render_template("numero.html", n=n, pesos=_pesos)

@app.route("/reservar/<int:numero_id>", methods=["POST"])
def reservar(numero_id):
    n = db.get_numero(numero_id)
    if not n or n["estado"] != "disponible":
        flash("Este número ya no está disponible.", "error")
        return redirect(url_for("index"))

    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip()
    telefono = request.form.get("telefono", "").strip()
    whatsapp = request.form.get("whatsapp", "").strip()

    if not nombre or not email:
        flash("Completá tu nombre y email.", "error")
        return redirect(url_for("numero_detalle", numero_id=numero_id))

    ok = db.reservar_numero(numero_id, nombre, email, telefono, whatsapp)
    if not ok:
        flash("Error al reservar. El número podría haberse tomado.", "error")
        return redirect(url_for("index"))

    flash(f"¡Número {n['numero']} reservado! Transferí el valor y envianos el comprobante por WhatsApp.", "success")
    return redirect(url_for("gracias", numero_id=numero_id))

@app.route("/gracias/<int:numero_id>")
def gracias(numero_id):
    n = db.get_numero(numero_id)
    if not n:
        flash("Número no encontrado.", "error")
        return redirect(url_for("index"))
    return render_template("gracias.html", n=n, pesos=_pesos, banco=_banco())

# ─── Admin ─────────────────────────────────────────────────────────

PASSWD = os.environ.get("ADMIN_PASSWORD", "admin123")

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == PASSWD:
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Contraseña incorrecta.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/admin")
@require_auth
def admin():
    stats = db.stats()
    numeros = db.get_numeros()
    pagados = [n for n in numeros if n["estado"] == "pagado"]
    reservados = [n for n in numeros if n["estado"] == "reservado"]
    return render_template("admin.html", stats=stats, pagados=pagados, reservados=reservados, numeros=numeros, pesos=_pesos)

@app.route("/admin/numero/<int:numero_id>/confirmar-pago", methods=["POST"])
@require_auth
def admin_confirmar_pago(numero_id):
    n = db.get_numero(numero_id)
    if not n:
        flash("Número no encontrado.", "error")
        return redirect(url_for("admin"))
    db.marcar_pagado(numero_id, _precio())
    flash("Pago confirmado.", "success")
    if n.get("comprador_whatsapp"):
        wa = n["comprador_whatsapp"].replace(" ", "").replace("-", "")
        if not wa.startswith("+"):
            wa = "+" + wa
        msg = f"¡Hola {n['comprador_nombre']}! ✅ Tu pago por el N°{n['numero']} fue confirmado. Ya estás participando por {PREMIO}. ¡Gracias por sumarte! 🎉"
        from urllib.parse import quote
        wa_link = f"https://wa.me/{wa}?text={quote(msg)}"
        flash(f"📱 <a href='{wa_link}' target='_blank'>Click acá para notificar al comprador por WhatsApp</a>", "success")
    return redirect(url_for("admin"))

@app.route("/admin/numero/<int:numero_id>/liberar", methods=["POST"])
@require_auth
def admin_liberar(numero_id):
    n = db.get_numero(numero_id)
    if n:
        conn = db.get_connection()
        conn.execute(
            """UPDATE numeros SET estado='disponible',
               comprador_nombre='', comprador_email='', comprador_telefono='',
               comprador_whatsapp='', fecha_reserva=NULL, fecha_pago=NULL,
               monto=0, mp_preference_id='', mp_payment_id='',
               updated_at=datetime('now','localtime')
               WHERE id=?""",
            (numero_id,),
        )
        conn.commit()
        conn.close()
        flash("Número liberado.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/config", methods=["GET", "POST"])
@require_auth
def admin_config():
    if request.method == "POST":
        db.set_config("precio", request.form.get("precio", "3000"))
        db.set_config("wa_contacto", request.form.get("wa_contacto", ""))
        db.set_config("banco_nombre", request.form.get("banco_nombre", ""))
        db.set_config("banco_titular", request.form.get("banco_titular", ""))
        db.set_config("banco_cbu", request.form.get("banco_cbu", ""))
        db.set_config("banco_alias", request.form.get("banco_alias", ""))
        db.set_config("banco_tipo", request.form.get("banco_tipo", "Caja de Ahorro"))
        flash("Configuración guardada.", "success")
        return redirect(url_for("admin"))
    cfg = db.get_all_config()
    return render_template("admin_config.html", cfg=cfg)

db.init_db()

if __name__ == "__main__":
    print(f"⚡ {TITULO_SORTEO}")
    print(f"   http://localhost:5000")
    print(f"   Admin: http://localhost:5000/admin/login")
    app.run(debug=True, host="0.0.0.0", port=5000)
