"""Punto de entrada del microservicio Alertas y Analítica.

Crea la aplicación Flask, define el formato común de errores
({"codigo": ..., "mensaje": ...}) y una ruta de salud para comprobar
que el servicio y la base de datos responden.
"""

from datetime import date, datetime
from decimal import Decimal

import pymysql
from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException

from config import Config
from database import consultar_uno
from rutas.umbrales import bp as umbrales_bp
from rutas.temporadas import bp as temporadas_bp
from rutas.alertas import bp as alertas_bp
from rutas.sugerencias import bp as sugerencias_bp
from rutas.analitica import bp as analitica_bp

class ProveedorJSON(DefaultJSONProvider):
    """Convierte fechas a formato ISO 8601 y decimales a números."""

    @staticmethod
    def default(objeto):
        if isinstance(objeto, (datetime, date)):
            return objeto.isoformat()
        if isinstance(objeto, Decimal):
            return float(objeto)
        return DefaultJSONProvider.default(objeto)


# Mensajes en español para los errores HTTP más comunes.
MENSAJES_HTTP = {
    400: "Datos de entrada inválidos",
    401: "Token ausente o inválido",
    403: "El rol no tiene permiso para esta operación",
    404: "Recurso no encontrado",
    405: "Método no permitido para esta ruta",
}


def error_json(codigo, mensaje):
    """Respuesta de error con el formato del contrato OpenAPI."""
    return jsonify({"codigo": codigo, "mensaje": mensaje}), codigo


def crear_app():
    app = Flask(__name__)
    app.json = ProveedorJSON(app)

    # Acepta las rutas con y sin barra final (/api/alertas y /api/alertas/)
    # para que el Gateway no reciba redirecciones.
    app.url_map.strict_slashes = False

    app.register_blueprint(umbrales_bp)
    app.register_blueprint(temporadas_bp)
    app.register_blueprint(alertas_bp)
    app.register_blueprint(sugerencias_bp)
    app.register_blueprint(analitica_bp)

    @app.get("/health")
    def salud():
        """Comprueba que el servicio está activo y que la base de datos responde."""
        consultar_uno("SELECT 1 AS ok")
        return jsonify({"servicio": "alertas-analitica", "estado": "ok", "base_datos": "ok"})

    @app.errorhandler(HTTPException)
    def manejar_error_http(error):
        # Si el código lanzó el error con un mensaje propio, se usa ese mensaje;
        # si no, se usa el mensaje en español de MENSAJES_HTTP.
        if error.description != type(error).description:
            mensaje = error.description
        else:
            mensaje = MENSAJES_HTTP.get(error.code, error.name)
        return error_json(error.code, mensaje)

    @app.errorhandler(pymysql.err.OperationalError)
    def manejar_error_bd(error):
        app.logger.error("Error de conexión con la base de datos: %s", error)
        return error_json(503, "Base de datos no disponible")

    @app.errorhandler(Exception)
    def manejar_error_general(error):
        app.logger.exception("Error no controlado")
        return error_json(500, "Error interno del servidor")

    return app


app = crear_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.APP_PORT)