"""
models.py
Define los modelos de base de datos (SQLAlchemy ORM).

IMPORTANTE: El nombre de la tabla ha sido generalizado por seguridad.
En producción, reemplazar "VISTA_PEDIDOS" por el nombre real de la vista.
"""

from database import db


class Pedido(db.Model):
    """
    Mapea la vista de estado de pedidos del WMS.
    Representa el estado actual de cada pedido.
    """

    __tablename__ = "VISTA_PEDIDOS"

    CLIENTE_ID = db.Column(db.String(50))
    DOC_EXT = db.Column(db.String(100), primary_key=True)
    ESTADO = db.Column(db.String(100))
    FECHA_CREACION_WMS = db.Column(db.DateTime)
    FECHA_PROCESADO_WMS = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Pedido {self.DOC_EXT} | {self.ESTADO}>"