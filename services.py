"""
services.py
Lógica de negocio: cálculo de tiempos, persistencia de fechas de finalización
y hilo de verificación en segundo plano.

IMPORTANTE: Nombres de columnas generalizados por seguridad.
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import config
import queries


# ── Seguridad: Validación de rutas ─────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

def _ruta_segura(ruta: str) -> bool:
    """Verifica que un archivo esté dentro del directorio del proyecto."""
    try:
        abs_ruta = Path(ruta).resolve()
        return str(abs_ruta).startswith(str(BASE_DIR.resolve()))
    except Exception:
        return False


# ── Estado en memoria ──────────────────────────────────────────────────────────

_ultimo_estado_pedidos: dict[str, str] = {}
_fechas_finalizacion: dict[str, datetime] = {}


# ── Persistencia en JSON ───────────────────────────────────────────────────────

def cargar_fechas_finalizacion() -> None:
    """Carga el archivo JSON de fechas de finalización al iniciar la app."""
    global _fechas_finalizacion
    
    archivo = config.FECHAS_FINALIZACION_FILE
    
    # Validar path traversal
    if not _ruta_segura(archivo):
        print(" Intento de path traversal detectado en carga de fechas")
        return
    
    try:
        if os.path.exists(archivo):
            # Verificar tamaño máximo (1MB)
            if os.path.getsize(archivo) > 1_000_000:
                print(" Archivo de fechas demasiado grande, ignorando")
                _fechas_finalizacion = {}
                return
            
            with open(archivo, "r", encoding="utf-8") as f:
                datos = json.load(f)
            
            # Validar estructura
            if not isinstance(datos, dict):
                print(" Formato inválido en archivo de fechas")
                _fechas_finalizacion = {}
                return
            
            # Validar cada entrada
            cargadas = {}
            for k, v in datos.items():
                if isinstance(k, str) and isinstance(v, str) and len(k) < 200:
                    try:
                        cargadas[k] = datetime.fromisoformat(v)
                    except (ValueError, TypeError):
                        print(f" Fecha inválida ignorada: {k}")
                        continue
            
            _fechas_finalizacion = cargadas
            print(f" Fechas de finalización cargadas: {len(_fechas_finalizacion)} registros")
        else:
            print(" No existe archivo de fechas de finalización; se creará al primer registro")
    except json.JSONDecodeError:
        print(" Archivo JSON corrupto, iniciando con diccionario vacío")
        _fechas_finalizacion = {}
    except Exception:
        print(" Error inesperado al cargar fechas de finalización")
        _fechas_finalizacion = {}


def guardar_fechas_finalizacion() -> None:
    """Persiste el diccionario de fechas de finalización en disco."""
    archivo = config.FECHAS_FINALIZACION_FILE
    
    # Validar path traversal
    if not _ruta_segura(archivo):
        print(" Intento de path traversal detectado en guardado de fechas")
        return
    
    try:
        datos = {k: v.isoformat() for k, v in _fechas_finalizacion.items()}
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        print(f" Fechas de finalización guardadas: {len(_fechas_finalizacion)} registros")
    except Exception:
        print(" Error al guardar fechas de finalización")


# ── Utilidades internas ────────────────────────────────────────────────────────

def _clave_pedido(cliente_id: str, doc_ext: str) -> str:
    """Crea clave compuesta validando los inputs."""
    # Sanitizar para evitar inyección en la clave
    cliente_id = str(cliente_id).strip()[:50]
    doc_ext = str(doc_ext).strip()[:100]
    return f"{cliente_id}_{doc_ext}"


def _registrar_finalizacion(clave: str) -> bool:
    """
    Registra la fecha actual para un pedido si aún no estaba registrado.
    Retorna True si se agregó un nuevo registro.
    """
    if clave not in _fechas_finalizacion:
        _fechas_finalizacion[clave] = datetime.now()
        return True
    return False


# ── Hilo de verificación en segundo plano ─────────────────────────────────────

def _verificar_pedidos_finalizados_background(app) -> None:
    """Hilo daemon de verificación periódica."""
    print(" Hilo de verificación en segundo plano iniciado")
    time.sleep(5)

    while True:
        try:
            with app.app_context():
                print(" [Background] Verificando pedidos finalizados...")
                pedidos = queries.get_pedidos_finalizados_hoy()
                nuevos = sum(
                    _registrar_finalizacion(_clave_pedido(p.CLIENTE_ID, p.DOC_EXT))
                    for p in pedidos
                )
                if nuevos:
                    guardar_fechas_finalizacion()
                    print(f"   [Background] {nuevos} nuevos finalizados guardados")
                else:
                    print(f"   [Background] Sin cambios. Total: {len(_fechas_finalizacion)}")
        except Exception:
            print(" [Background] Error en verificación")

        time.sleep(config.BACKGROUND_CHECK_INTERVAL)


def iniciar_hilo_background(app) -> None:
    """Crea e inicia el hilo daemon de verificación."""
    hilo = threading.Thread(
        target=_verificar_pedidos_finalizados_background,
        args=(app,),
        daemon=True,
        name="VerificadorPedidos",
    )
    hilo.start()
    print(" Hilo de verificación iniciado correctamente")


# ── Cálculo de tiempos ─────────────────────────────────────────────────────────

def _formatear_minutos(minutos: int) -> str:
    if minutos < 0:
        return "0 min"
    if minutos < 60:
        return f"{minutos} min"
    horas, mins = divmod(minutos, 60)
    if horas < 24:
        return f"{horas}h {mins}min"
    dias, horas_rest = divmod(horas, 24)
    return f"{dias}d {horas_rest}h {mins}min"


def calcular_tiempo_espera(fecha_creacion: datetime | None, estado: str) -> str:
    """Tiempo transcurrido desde la creación hasta ahora."""
    if estado == queries.ESTADO_FINALIZADO:
        return "Finalizado"
    if not isinstance(fecha_creacion, datetime):
        return "N/A"
    minutos = int((datetime.now() - fecha_creacion).total_seconds() / 60)
    return _formatear_minutos(minutos)


def calcular_tiempo_preparacion(
    clave: str,
    fecha_creacion: datetime | None,
    estado: str,
    fecha_procesado: datetime | None = None,
    para_excel: bool = False,
) -> str | int:
    """Tiempo total de preparación de un pedido."""
    if not isinstance(fecha_creacion, datetime):
        return 0 if para_excel else "N/A"

    if estado == queries.ESTADO_FINALIZADO:
        fecha_fin = _fechas_finalizacion.get(clave) or fecha_procesado
        if not isinstance(fecha_fin, datetime):
            return 0 if para_excel else "N/A"
        diferencia = fecha_fin - fecha_creacion
    else:
        diferencia = datetime.now() - fecha_creacion

    minutos = int(diferencia.total_seconds() / 60)
    return max(0, minutos) if para_excel else _formatear_minutos(max(0, minutos))


# ── Construcción de la respuesta de la API ─────────────────────────────────────

def construir_datos_pedidos() -> dict:
    """Orquesta la consulta y devuelve el payload para la API."""
    global _ultimo_estado_pedidos

    pedidos_activos = queries.get_pedidos_activos()
    pedidos_finalizados_hoy = queries.get_pedidos_finalizados_hoy()

    # Registrar nuevos finalizados
    hubo_nuevos = False
    for pedido in pedidos_finalizados_hoy:
        clave = _clave_pedido(pedido.CLIENTE_ID, pedido.DOC_EXT)
        if _registrar_finalizacion(clave):
            hubo_nuevos = True

    if hubo_nuevos:
        guardar_fechas_finalizacion()

    # Combinar evitando duplicados
    claves_finalizados = {_clave_pedido(p.CLIENTE_ID, p.DOC_EXT) for p in pedidos_finalizados_hoy}
    todos = pedidos_activos + [p for p in pedidos_finalizados_hoy if _clave_pedido(p.CLIENTE_ID, p.DOC_EXT) not in claves_finalizados]

    if len(todos) > config.MAX_PEDIDOS:
        todos = todos[: config.MAX_PEDIDOS]

    pedidos_data = []
    cambios_detectados = []
    estado_actual: dict[str, str] = {}

    for pedido in todos:
        clave = _clave_pedido(pedido.CLIENTE_ID, pedido.DOC_EXT)

        if pedido.ESTADO == queries.ESTADO_FINALIZADO:
            _registrar_finalizacion(clave)

        pedidos_data.append({
            "id_unico": clave,
            "cliente_id": pedido.CLIENTE_ID or "",
            "doc_ext": pedido.DOC_EXT or "",
            "estado": pedido.ESTADO or "",
            "fecha_creacion": (
                pedido.FECHA_CREACION_WMS.strftime("%Y-%m-%d %H:%M:%S")
                if pedido.FECHA_CREACION_WMS else None
            ),
            "fecha_inicio_picking": (
                pedido.FECHA_PROCESADO_WMS.strftime("%Y-%m-%d %H:%M:%S")
                if pedido.FECHA_PROCESADO_WMS else None
            ),
            "tiempo_espera": calcular_tiempo_espera(pedido.FECHA_CREACION_WMS, pedido.ESTADO or ""),
            "tiempo_preparacion": calcular_tiempo_preparacion(
                clave,
                pedido.FECHA_CREACION_WMS,
                pedido.ESTADO or "",
                fecha_procesado=pedido.FECHA_PROCESADO_WMS,
            ),
        })

        estado_actual[clave] = pedido.ESTADO or ""

        if clave in _ultimo_estado_pedidos and _ultimo_estado_pedidos[clave] != pedido.ESTADO:
            cambios_detectados.append({
                "id_unico": clave,
                "cliente_id": pedido.CLIENTE_ID or "",
                "doc_ext": pedido.DOC_EXT or "",
                "estado_anterior": _ultimo_estado_pedidos[clave],
                "estado_actual": pedido.ESTADO or "",
            })

    _ultimo_estado_pedidos = estado_actual

    return {
        "pedidos": pedidos_data,
        "cambios": cambios_detectados,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_pedidos": len(pedidos_data),
        "limite": config.MAX_PEDIDOS,
        "debug_info": {
            "finalizados_hoy": len(pedidos_finalizados_hoy),
            "activos": len(pedidos_activos),
        },
    }


# ── Generación del CSV de exportación ─────────────────────────────────────────

def generar_filas_csv(fecha_inicio: str, fecha_fin: str) -> list[list]:
    """
    Retorna todas las filas (incluida la cabecera) para el CSV de exportación.
    
    """
    pedidos = queries.get_pedidos_finalizados_por_rango(fecha_inicio, fecha_fin)
    if not pedidos:
        raise ValueError("No se encontraron pedidos finalizados para el rango indicado")

    pedidos_dict = {p.DOC_EXT: p for p in pedidos}
    
    
    lista_pedidos = [p.DOC_EXT for p in pedidos if p.DOC_EXT]
    egresos = queries.get_egresos_por_pedidos(lista_pedidos)

    egresos_por_pedido: dict[str, list] = {}
    for egreso in egresos:
        egresos_por_pedido.setdefault(egreso.PEDIDO, []).append(egreso)

    cabecera = [
        "CLIENTE_ID", "PEDIDO", "DESTINATARIO", "ARTICULO",
        "DESCRIPCION", "CANTIDAD_UNIDADES", "USUARIO_PICKING",
        "FECHA_CREACION_PEDIDO", "FECHA_INICIO_PICKING",
        "TIEMPO_PREPARACION_TOTAL(minutos)",
    ]
    filas = [cabecera]

    for doc_ext, pedido_info in pedidos_dict.items():
        clave = _clave_pedido(pedido_info.CLIENTE_ID, pedido_info.DOC_EXT)
        tiempo = calcular_tiempo_preparacion(
            clave,
            pedido_info.FECHA_CREACION_WMS,
            queries.ESTADO_FINALIZADO,
            fecha_procesado=pedido_info.FECHA_INICIO_PICKING,
            para_excel=True,
        )
        fecha_creacion = (
            pedido_info.FECHA_CREACION_WMS.strftime("%Y-%m-%d %H:%M:%S")
            if pedido_info.FECHA_CREACION_WMS else ""
        )
        fecha_picking = (
            pedido_info.FECHA_INICIO_PICKING.strftime("%Y-%m-%d %H:%M:%S")
            if pedido_info.FECHA_INICIO_PICKING else ""
        )

        detalles = egresos_por_pedido.get(doc_ext)
        if detalles:
            for det in detalles:
                try:
                    cantidad = int(float(det.CANTIDAD_UNIDADES)) if det.CANTIDAD_UNIDADES else 0
                except (ValueError, TypeError):
                    cantidad = 0
                filas.append([
                    det.CLIENTE_ID or pedido_info.CLIENTE_ID or "",
                    det.PEDIDO or doc_ext,
                    det.DESTINATARIO or "",
                    det.ARTICULO or "",
                    det.DESCRIPCION or "",
                    cantidad,
                    det.USUARIO_PICKING or "",
                    fecha_creacion,
                    fecha_picking,
                    tiempo,
                ])
        else:
            filas.append([
                pedido_info.CLIENTE_ID or "", doc_ext,
                "", "", "", 0, "",
                fecha_creacion, fecha_picking, tiempo,
            ])

    if len(filas) <= 1:
        raise ValueError("No se encontraron datos de detalle para exportar")

    return filas