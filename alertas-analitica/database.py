"""Acceso a la base de datos MySQL del servicio Alertas y Analítica.

Usa PyMySQL con SQL directo. Cada función abre su propia conexión y la
cierra al terminar. Los resultados se devuelven como diccionarios
(nombre de columna -> valor).
"""

from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from config import Config


def obtener_conexion():
    """Abre una conexión nueva con los datos de config.py."""
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
        connect_timeout=5,
    )


def consultar(sql, parametros=None):
    """Ejecuta un SELECT y devuelve una lista de filas (diccionarios)."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            return list(cursor.fetchall())
    finally:
        conexion.close()


def consultar_uno(sql, parametros=None):
    """Ejecuta un SELECT y devuelve una sola fila, o None si no hay resultados."""
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchone()
    finally:
        conexion.close()


def ejecutar(sql, parametros=None):
    """Ejecuta un INSERT, UPDATE o DELETE y confirma el cambio.

    Devuelve un diccionario con:
      - id: el id generado por un INSERT (0 si no aplica).
      - filas: la cantidad de filas afectadas.
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            conexion.commit()
            return {"id": cursor.lastrowid, "filas": cursor.rowcount}
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


@contextmanager
def transaccion():
    """Agrupa varias operaciones: se confirman todas o ninguna.

    Uso:
        with transaccion() as cursor:
            cursor.execute("INSERT ...", (...))
            cursor.execute("INSERT ...", (...))
    """
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            yield cursor
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()