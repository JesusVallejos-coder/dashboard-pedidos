"""
Servicio de lógica de negocio para pedidos
"""
from datetime import datetime
import json
import os
import hashlib
from pathlib import Path
from models import Pedido, db
from sqlalchemy import or_

# Archivo para persistencia - Usar ruta absoluta segura
BASE_DIR = Path(__file__).parent
FECHAS_FINALIZACION_FILE = BASE_DIR / 'fechas_finalizacion.json'
FECHAS_FINALIZACION_BACKUP = BASE_DIR / 'fechas_finalizacion_backup.json'

fechas_finalizacion = {}
ultimo_estado_pedidos = {}


def _validar_identificador(identificador: str) -> bool:
    """
    Valida que el identificador tenga formato correcto:
    'CLIENTEID_DOCEXT' donde ambos son alfanuméricos
    """
    if '_' not in identificador:
        return False
    partes = identificador.split('_', 1)
    if len(partes) != 2:
        return False
    return all(p.isalnum() or p.replace('-', '').isalnum() for p in partes)


def _validar_fecha_iso(fecha_str: str) -> bool:
    """Valida formato de fecha ISO"""
    try:
        datetime.fromisoformat(fecha_str)
        return True
    except (ValueError, TypeError):
        return False


def cargar_fechas_finalizacion():
    """Carga las fechas de finalización desde JSON con validación"""
    global fechas_finalizacion
    try:
        # Verificar que existe y está dentro del directorio del proyecto
        filepath = Path(FECHAS_FINALIZACION_FILE).resolve()
        if not str(filepath).startswith(str(BASE_DIR.resolve())):
            print(" Intento de path traversal detectado")
            return
        
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            # Validar cada entrada
            for key, value in datos.items():
                if _validar_identificador(key) and _validar_fecha_iso(value):
                    fechas_finalizacion[key] = datetime.fromisoformat(value)
                else:
                    print(f" Entrada inválida ignorada: {key}")
            
            print(f" Cargadas {len(fechas_finalizacion)} fechas de finalización")
    except json.JSONDecodeError:
        print(" Archivo JSON corrupto, intentando backup...")
        _restaurar_backup()
    except Exception as e:
        print(f" Error cargando fechas: {e}")
        fechas_finalizacion = {}


def guardar_fechas_finalizacion():
    """Guarda las fechas de finalización en JSON con backup"""
    global fechas_finalizacion
    try:
        datos = {k: v.isoformat() for k, v in fechas_finalizacion.items()}
        
        # Guardar archivo principal
        with open(FECHAS_FINALIZACION_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        
        # Crear backup
        with open(FECHAS_FINALIZACION_BACKUP, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        
        print(f" Guardadas {len(fechas_finalizacion)} fechas")
    except Exception as e:
        print(f" Error guardando: {e}")


def _restaurar_backup():
    """Restaura desde backup si el archivo principal está corrupto"""
    global fechas_finalizacion
    try:
        if FECHAS_FINALIZACION_BACKUP.exists():
            with open(FECHAS_FINALIZACION_BACKUP, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            fechas_finalizacion = {k: datetime.fromisoformat(v) for k, v in datos.items()}
            print(" Restaurado desde backup")
            guardar_fechas_finalizacion()  # Regenerar archivo principal
    except:
        print(" No se pudo restaurar backup")
        fechas_finalizacion = {}


def registrar_finalizacion(identificador: str, fecha=None) -> bool:
    """Registra un pedido como finalizado con validación"""
    if not _validar_identificador(identificador):
        print(f" Identificador inválido: {identificador}")
        return False
    
    global fechas_finalizacion
    if identificador not in fechas_finalizacion:
        fechas_finalizacion[identificador] = fecha or datetime.now()
        guardar_fechas_finalizacion()
        return True
    return False


def obtener_pedidos_activos():
    """Obtiene pedidos activos (no finalizados)"""
    estados_activos = [
        'PEDIDO SIN PROCESAR',
        'PEDIDO EN PROCESO DE PICKING',
        'PEDIDO EN PROCESO DE FINALIZACION'
    ]
    return Pedido.query.filter(
        or_(*[Pedido.ESTADO == estado for estado in estados_activos])
    ).order_by(Pedido.FECHA_CREACION_WMS.desc()).all()


def obtener_pedidos_finalizados_hoy():
    """Obtiene pedidos finalizados hoy con validación"""
    global fechas_finalizacion
    fecha_actual = datetime.now().date()
    pedidos = []
    
    for identificador, fecha_fin in fechas_finalizacion.items():
        if fecha_fin.date() == fecha_actual:
            if _validar_identificador(identificador):
                try:
                    cliente_id, doc_ext = identificador.split('_', 1)
                    # Validar que no estén vacíos
                    if cliente_id and doc_ext:
                        pedido = Pedido.query.filter_by(
                            CLIENTE_ID=cliente_id,
                            DOC_EXT=doc_ext,
                            ESTADO='PEDIDO FINALIZADO'
                        ).first()
                        if pedido:
                            pedidos.append(pedido)
                except Exception as e:
                    print(f" Error procesando {identificador}: {e}")
                    continue
    return pedidos


def calcular_tiempo_espera(fecha_creacion, estado: str) -> str:
    """Calcula tiempo de espera actual con validación de tipos"""
    if estado == 'PEDIDO FINALIZADO':
        return "Finalizado"
    if not isinstance(fecha_creacion, datetime):
        return "N/A"
    
    diferencia = datetime.now() - fecha_creacion
    minutos = int(diferencia.total_seconds() / 60)
    
    if minutos < 0:
        return "0 min"
    elif minutos < 60:
        return f"{minutos} min"
    else:
        horas = minutos // 60
        min_restantes = minutos % 60
        return f"{horas}h {min_restantes}min"


def calcular_tiempo_preparacion(pedido_id: str, fecha_creacion, estado: str, para_excel: bool = False):
    """Calcula tiempo total de preparación con validación"""
    if not isinstance(fecha_creacion, datetime):
        return "N/A" if not para_excel else 0
    
    global fechas_finalizacion
    
    if estado == 'PEDIDO FINALIZADO':
        if pedido_id in fechas_finalizacion:
            diferencia = fechas_finalizacion[pedido_id] - fecha_creacion
        else:
            diferencia = datetime.now() - fecha_creacion
    else:
        diferencia = datetime.now() - fecha_creacion
    
    minutos = int(diferencia.total_seconds() / 60)
    
    if para_excel:
        return max(0, minutos)  # No permitir negativos
    
    if minutos < 0:
        return "0 min"
    elif minutos < 60:
        return f"{minutos} min"
    else:
        horas = minutos // 60
        min_restantes = minutos % 60
        if horas < 24:
            return f"{horas}h {min_restantes}min"
        else:
            dias = horas // 24
            horas_restantes = horas % 24
            return f"{dias}d {horas_restantes}h {min_restantes}min"