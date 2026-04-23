"""
database.py
Instancia única de SQLAlchemy, importada por modelos y la app para evitar
importaciones circulares.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
