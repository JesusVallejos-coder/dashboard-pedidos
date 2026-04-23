"""
app.py
Punto de entrada de la aplicación Flask.
Solo contiene la configuración de la app y las rutas HTTP.
Toda la lógica de negocio vive en services.py y queries.py.
"""

import csv
import io
import re
from datetime import datetime

from flask import Flask, jsonify, render_template, request, Response, abort
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from database import db
import services


def create_app() -> Flask:
    """Factory de la aplicación Flask."""
    app = Flask(__name__)

    # ── Seguridad: ProxyFix si está detrás de nginx/heroku ──────────────────
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # ── Configuración ──────────────────────────────────────────────────────
    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = config.SQLALCHEMY_ENGINE_OPTIONS
    
    # Seguridad adicional
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limitar a 16MB

    db.init_app(app)

    # ── Cabeceras de seguridad ─────────────────────────────────────────────
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response

    # ── Validadores ────────────────────────────────────────────────────────
    def validar_fecha(fecha_str: str) -> bool:
        """Valida formato de fecha YYYY-MM-DD"""
        if not fecha_str:
            return False
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        return bool(re.match(pattern, fecha_str))

    def sanitizar_nombre_archivo(nombre: str) -> str:
        """Elimina caracteres peligrosos para nombres de archivo"""
        return re.sub(r'[^\w\-_\.]', '_', nombre)

    # ── Rutas ──────────────────────────────────────────────────────────────

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/api/pedidos")
    def get_pedidos():
        try:
            datos = services.construir_datos_pedidos()
            return jsonify(datos)
        except Exception:
            # No exponer detalles del error
            return jsonify({"error": "Error interno del servidor"}), 500

    @app.route("/api/exportar-excel")
    def exportar_excel():
        fecha_inicio = request.args.get("fecha_inicio", "").strip()
        fecha_fin = request.args.get("fecha_fin", "").strip()

        # Validar parámetros obligatorios
        if not fecha_inicio or not fecha_fin:
            return jsonify({"error": "Se requieren fecha_inicio y fecha_fin"}), 400

        # Validar formato de fechas
        if not (validar_fecha(fecha_inicio) and validar_fecha(fecha_fin)):
            return jsonify({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}), 400

        # Validar rango lógico
        try:
            fecha_ini = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            fecha_fi = datetime.strptime(fecha_fin, '%Y-%m-%d')
            if fecha_ini > fecha_fi:
                return jsonify({"error": "fecha_inicio no puede ser mayor que fecha_fin"}), 400
        except ValueError:
            return jsonify({"error": "Fechas no válidas"}), 400

        try:
            filas = services.generar_filas_csv(fecha_inicio, fecha_fin)
        except ValueError:
            return jsonify({"error": "No se encontraron pedidos en ese rango"}), 404
        except Exception:
            # No exponer detalles del error en producción
            return jsonify({"error": "Error interno al generar el archivo"}), 500

        output = io.StringIO()
        csv.writer(output).writerows(filas)
        output.seek(0)

        # Sanitizar fechas para nombre de archivo seguro
        nombre_seguro_inicio = sanitizar_nombre_archivo(fecha_inicio)
        nombre_seguro_fin = sanitizar_nombre_archivo(fecha_fin)
        nombre_archivo = f"pedidos_finalizados_{nombre_seguro_inicio}_{nombre_seguro_fin}.csv"
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{nombre_archivo}"',
                "Content-Type": "text/csv; charset=utf-8",
            },
        )

    # ── Manejadores de error ──────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Recurso no encontrado"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Error interno del servidor"}), 500

    return app


# ── Arranque directo ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()

    services.cargar_fechas_finalizacion()
    services.iniciar_hilo_background(app)

    # ⚠️ NUNCA usar debug=True en producción
    debug_mode = config.FLASK_DEBUG if hasattr(config, 'FLASK_DEBUG') else False
    
    app.run(
        host="0.0.0.0",
        port=config.FLASK_PORT,
        debug=debug_mode
    )