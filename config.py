"""
config.py
Carga y expone toda la configuración de la aplicación desde variables de entorno.
Toda la información sensible se obtiene EXCLUSIVAMENTE de variables de entorno.
"""

import os
import sys
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# ── Validación de entorno ──────────────────────────────────────────────────────
def _validar_configuracion():
    """Valida que las variables de entorno requeridas estén presentes."""
    requeridas = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_NAME"]
    faltantes = [var for var in requeridas if not os.getenv(var)]
    
    if faltantes:
        print(f" ERROR: Faltan variables de entorno: {', '.join(faltantes)}")
        print("   Crea un archivo .env basado en .env.example")
        sys.exit(1)

_validar_configuracion()

# ── Base de datos ──────────────────────────────────────────────────────────────
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

# Citar contraseña para manejar caracteres especiales (@, :, /, etc.)
DB_PASSWORD_QUOTED = urllib.parse.quote_plus(DB_PASSWORD)

SQLALCHEMY_DATABASE_URI = (
    f"mssql+pymssql://{DB_USER}:{DB_PASSWORD_QUOTED}@{DB_HOST}/{DB_NAME}"
)

SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    # Ocultar la URI en logs de error
    "hide_parameters": True,
    # Limitar conexiones para evitar saturación
    "pool_size": 5,
    "max_overflow": 10,
}

# ── Aplicación ─────────────────────────────────────────────────────────────────
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))

#  SEGURIDAD: Debug NUNCA debe habilitarse en producción
_FLASK_DEBUG_ENV = os.getenv("FLASK_DEBUG", "False").lower()
if _FLASK_DEBUG_ENV == "true":
    print(" ADVERTENCIA: Modo DEBUG activado. NO usar en producción.")
    FLASK_DEBUG = True
else:
    FLASK_DEBUG = False

# ── Lógica de negocio ──────────────────────────────────────────────────────────
BACKGROUND_CHECK_INTERVAL = int(os.getenv("BACKGROUND_CHECK_INTERVAL", 20))
MAX_PEDIDOS = int(os.getenv("MAX_PEDIDOS", 200))
MAX_PEDIDOS_POR_COLUMNA = int(os.getenv("MAX_PEDIDOS_POR_COLUMNA", 10))

# Archivo donde se persisten las fechas de finalización entre reinicios
FECHAS_FINALIZACION_FILE = os.getenv(
    "FECHAS_FINALIZACION_FILE",
    "fechas_finalizacion.json"
)

# ── Logging de configuración (sin exponer contraseñas) ─────────────────────────
def log_configuracion():
    """Muestra configuración cargada sin exponer datos sensibles."""
    print("=" * 50)
    print(" Configuración cargada:")
    print(f"   DB_USER: {'*' * len(DB_USER) if DB_USER else 'No configurado'}")
    print(f"   DB_HOST: {DB_HOST}")
    print(f"   DB_NAME: {DB_NAME}")
    print(f"   FLASK_PORT: {FLASK_PORT}")
    print(f"   FLASK_DEBUG: {FLASK_DEBUG}")
    print(f"   Pool size: {SQLALCHEMY_ENGINE_OPTIONS['pool_size']}")
    print("=" * 50)