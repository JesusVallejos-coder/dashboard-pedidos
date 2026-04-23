"""
queries.py
Centraliza todas las consultas a la base de datos.
Ningún otro módulo debe ejecutar queries directamente.

IMPORTANTE: Los nombres de tablas y columnas han sido generalizados 
por seguridad. En producción, reemplazar según corresponda.
"""

import re
from datetime import datetime
from sqlalchemy import or_, text

from database import db
from models import Pedido


# ── Constantes de estado ───────────────────────────────────────────────────────

ESTADO_SIN_PROCESAR = "PEDIDO SIN PROCESAR"
ESTADO_PICKING = "PEDIDO EN PROCESO DE PICKING"
ESTADO_FINALIZACION = "PEDIDO EN PROCESO DE FINALIZACION"
ESTADO_FINALIZADO = "PEDIDO FINALIZADO"

ESTADOS_ACTIVOS = [ESTADO_SIN_PROCESAR, ESTADO_PICKING, ESTADO_FINALIZACION]


# ── Validadores ────────────────────────────────────────────────────────────────

def _validar_identificador(valor: str, max_len: int = 50) -> bool:
    """Valida que un identificador sea alfanumérico y tenga longitud segura."""
    if not valor or len(valor) > max_len:
        return False
    return bool(re.match(r'^[a-zA-Z0-9\-_]+$', valor))


def _validar_fecha(fecha_str: str) -> bool:
    """Valida formato de fecha YYYY-MM-DD"""
    if not fecha_str:
        return False
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', fecha_str))


def _sanitizar_lista_pedidos(pedidos_list: list) -> list:
    """Sanitiza y valida una lista de identificadores de pedido."""
    sanitizados = []
    for pedido in pedidos_list:
        if _validar_identificador(str(pedido), max_len=100):
            sanitizados.append(str(pedido))
    return sanitizados


# ── Pedidos ────────────────────────────────────────────────────────────────────

def get_pedidos_activos() -> list[Pedido]:
    """Retorna todos los pedidos que aún no han sido finalizados."""
    return (
        Pedido.query.filter(or_(*[Pedido.ESTADO == e for e in ESTADOS_ACTIVOS]))
        .order_by(Pedido.FECHA_CREACION_WMS.desc())
        .all()
    )


def get_pedidos_finalizados_hoy() -> list[Pedido]:
    """
    Retorna los pedidos con estado FINALIZADO cuya FECHA_PROCESADO_WMS
    corresponde al día de hoy.
    """
    hoy = datetime.now().date()
    inicio = datetime.combine(hoy, datetime.min.time())
    fin = datetime.combine(hoy, datetime.max.time())

    return Pedido.query.filter(
        Pedido.ESTADO == ESTADO_FINALIZADO,
        Pedido.FECHA_PROCESADO_WMS.between(inicio, fin),
    ).all()


def get_pedido_finalizado_por_ids(cliente_id: str, doc_ext: str) -> Pedido | None:
    """Busca un pedido específico ya finalizado por su clave compuesta."""
    # Validar inputs
    if not _validar_identificador(cliente_id) or not _validar_identificador(doc_ext, max_len=100):
        return None
    
    return Pedido.query.filter_by(
        CLIENTE_ID=cliente_id,
        DOC_EXT=doc_ext,
        ESTADO=ESTADO_FINALIZADO,
    ).first()


# ── Exportación ────────────────────────────────────────────────────────────────

def get_pedidos_finalizados_por_rango(fecha_inicio: str, fecha_fin: str):
    """
    Retorna los pedidos finalizados dentro del rango de fechas indicado.
    Se usa para la exportación a CSV.
    
    Las fechas DEBEN ser validadas antes de llamar esta función.
    """
    # Validar fechas
    if not _validar_fecha(fecha_inicio) or not _validar_fecha(fecha_fin):
        raise ValueError("Formato de fecha inválido. Use YYYY-MM-DD")
    
    query = text("""
        SELECT
            DOC_EXT,
            CLIENTE_ID,
            FECHA_CREACION_WMS,
            FECHA_PROCESADO_WMS AS FECHA_INICIO_PICKING
        FROM VISTADB
        WHERE FECHA_CREACION_WMS BETWEEN :fecha_inicio AND DATEADD(day, 1, :fecha_fin)
          AND ESTADO = 'PEDIDO FINALIZADO'
        ORDER BY FECHA_CREACION_WMS DESC
    """)
    result = db.session.execute(query, {
        "fecha_inicio": fecha_inicio, 
        "fecha_fin": fecha_fin
    })
    return result.fetchall()


def get_egresos_por_pedidos(pedidos: list):
    """
    Retorna el detalle de egresos (líneas de picking) para una lista
    de números de pedido.
    
    """
    # Sanitizar lista de pedidos
    pedidos_sanitizados = _sanitizar_lista_pedidos(pedidos)
    
    if not pedidos_sanitizados:
        return []
    
    # Usar parámetros en lugar de interpolación de strings
    placeholders = ','.join([f':pedido_{i}' for i in range(len(pedidos_sanitizados))])
    params = {f'pedido_{i}': p for i, p in enumerate(pedidos_sanitizados)}
    
    query = text(f"""
        SELECT
            CLIENTE_ID,
            PEDIDO,
            DESTINATARIO,
            ARTICULO,
            DESCRIPCION,
            CANTIDAD_UNIDADES,
            USUARIO_PICKING
        FROM VISTADB
        WHERE PEDIDO IN ({placeholders})
    """)
    result = db.session.execute(query, params)
    return result.fetchall()