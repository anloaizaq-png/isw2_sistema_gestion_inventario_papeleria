"""Acceso a la base de datos MySQL del servicio Alertas y Analítica.

Usa PyMySQL con SQL directo. Cada proceso (o hilo) reutiliza una sola
conexión en lugar de abrir una por consulta: abrir y cerrar miles de
conexiones por minuto agota los puertos disponibles (error 99) bajo carga
alta, como mostró la prueba de rendimiento A02.

Los resultados se devuelven como diccionarios (nombre de columna -> valor).
"""

import threading
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from config import Config

# Una conexión por hilo: gunicorn usa un hilo por proceso y el servidor de
# desarrollo de Flask atiende cada petición en un hilo distinto.
_local = threading.local()


def obtener_conexion():
    """Devuelve la conexión del hilo actual, abriéndola o reconectándola si hace falta."""
    conexion = getattr(_local, "conexion", None)
    if conexion is None or not conexion.open:
        conexion = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=5,
        )
        _local.conexion = conexion
    else:
        # Comprueba que la conexión siga viva; si MySQL la cerró, reconecta
        conexion.ping(reconnect=True)
    return conexion


def consultar(sql, parametros=None):
    """Ejecuta un SELECT y devuelve una lista de filas (diccionarios)."""
    with obtener_conexion().cursor() as cursor:
        cursor.execute(sql, parametros)
        return list(cursor.fetchall())


def consultar_uno(sql, parametros=None):
    """Ejecuta un SELECT y devuelve una sola fila, o None si no hay resultados."""
    with obtener_conexion().cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.fetchone()


def ejecutar(sql, parametros=None):
    """Ejecuta un INSERT, UPDATE o DELETE (se confirma automáticamente).

    Devuelve un diccionario con:
      - id: el id generado por un INSERT (0 si no aplica).
      - filas: la cantidad de filas afectadas.
    """
    with obtener_conexion().cursor() as cursor:
        cursor.execute(sql, parametros)
        return {"id": cursor.lastrowid, "filas": cursor.rowcount}


@contextmanager
def transaccion():
    """Agrupa varias operaciones: se confirman todas o ninguna.

    Uso:
        with transaccion() as cursor:
            cursor.execute("INSERT ...", (...))
            cursor.execute("INSERT ...", (...))
    """
    conexion = obtener_conexion()
    conexion.begin()
    try:
        with conexion.cursor() as cursor:
            yield cursor
        conexion.commit()
    except Exception:
        try:
            conexion.rollback()
        except pymysql.err.Error:
            # Si la conexión se perdió, se descarta para reconectar en la siguiente petición
            _local.conexion = None
        raise