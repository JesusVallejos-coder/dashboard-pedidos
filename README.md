#  Dashboard de Pedidos WMS

Monitor en tiempo real del estado de pedidos de un sistema WMS (Warehouse Management System), construido con Flask y SQLAlchemy sobre SQL Server.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.1-lightgrey?logo=flask)
![SQL Server](https://img.shields.io/badge/SQL_Server-mssql-red?logo=microsoftsqlserver)
![License](https://img.shields.io/badge/License-MIT-green)

---

##  Funcionalidades

- **Tablero Kanban** con 4 columnas de estado: Sin Procesar → Picking → Finalización → Finalizado
- **Actualización automática** cada 30 segundos sin recargar la página
- **Notificaciones en tiempo real** al detectar cambios de estado en un pedido
- **Cálculo de tiempos** de espera y preparación por pedido
- **Exportación a CSV** con detalle de líneas de picking filtrado por rango de fechas
- **Hilo de fondo** que persiste fechas de finalización entre reinicios de la app

---

##  Arquitectura del proyecto

```
dashboard-pedidos/
├── app.py                  # Rutas HTTP (Flask)
├── services.py             # Lógica de negocio
├── queries.py              # Acceso a base de datos
├── models.py               # Modelos ORM (SQLAlchemy)
├── database.py             # Instancia única de SQLAlchemy
├── config.py               # Configuración desde variables de entorno
├── requirements.txt
├── .env.example            # Plantilla de variables de entorno
├── .gitignore
└── templates/
    └── dashboard.html      # UI (Tailwind CSS + Vanilla JS)
```

| Módulo | Responsabilidad |
|---|---|
| `app.py` | Solo rutas Flask, sin lógica de negocio |
| `services.py` | Orquestación, cálculo de tiempos, hilo de fondo |
| `queries.py` | Todas las consultas SQL centralizadas |
| `models.py` | Definición del modelo ORM |
| `config.py` | Lee `.env` y expone constantes tipadas |

---

##  Instalación y configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/JesusVallejos-coder/dashboard-pedidos.git
cd dashboard-pedidos
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con los datos del entorno:

```env
DB_USER=tu_usuario
DB_PASSWORD=tu_password
DB_HOST=tu_servidor_sql
DB_NAME=tu_base_de_datos

FLASK_PORT=5000
FLASK_DEBUG=False

BACKGROUND_CHECK_INTERVAL=20
MAX_PEDIDOS=200
MAX_PEDIDOS_POR_COLUMNA=10
```


### 4. Ejecutar la aplicación

```bash
python app.py
```

La app estará disponible en `http://localhost:5000`.

---

## Requisitos de base de datos

La aplicación se conecta a **SQL Server** y requiere dos vistas (nombres generalizados por seguridad, revisar `models.py` y `queries.py` para configuración real):

### Vista principal de pedidos

| Columna | Tipo | Descripción |
|---|---|---|
| Identificador cliente | VARCHAR | Código único del cliente |
| Documento externo | VARCHAR (PK) | Número de pedido |
| Estado | VARCHAR | Estado actual del pedido |
| Fecha creación | DATETIME | Fecha de ingreso al WMS |
| Fecha procesado | DATETIME | Fecha de inicio de picking |

**Estados esperados:**
- `PEDIDO SIN PROCESAR`
- `PEDIDO EN PROCESO DE PICKING`
- `PEDIDO EN PROCESO DE FINALIZACION`
- `PEDIDO FINALIZADO`

### Vista de egresos (exportación CSV)

Columnas requeridas: código de cliente, número de pedido, destinatario, artículo, descripción, cantidad, usuario de picking.

>  **Importante:** Los nombres reales de vistas y columnas deben configurarse en los archivos `models.py` y `queries.py` según el entorno de producción.

---

##  Seguridad

- **Variables de entorno:** Credenciales exclusivamente en `.env`, nunca hardcodeadas
- **Prevención SQL Injection:** Consultas parametrizadas con SQLAlchemy
- **Prevención XSS:** Sanitización HTML de todos los datos dinámicos en el frontend
- **Cabeceras de seguridad:** CSP, X-Frame-Options, X-Content-Type-Options
- **Validación de inputs:** Fechas y parámetros validados antes de procesar
- **Path Traversal:** Rutas de archivos verificadas antes de acceso
- **Rate Limiting:** Límites en rutas de API

---

##  Autor

**Jesús Vallejos**
- GitHub: [@JesusVallejos-coder](https://github.com/JesusVallejos-coder)

##  Licencia

MIT License.

---
