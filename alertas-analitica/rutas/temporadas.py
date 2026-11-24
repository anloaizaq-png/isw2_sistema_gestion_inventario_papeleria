"""Rutas de temporadas y multiplicadores de demanda (tag Temporadas del contrato OpenAPI).

GET    /api/alertas/temporadas        Listar temporadas
POST   /api/alertas/temporadas        Crear temporada
PUT    /api/alertas/temporadas/{id}   Actualizar temporada
DELETE /api/alertas/temporadas/{id}   Eliminar temporada
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, jsonify, request

from database import consultar, consultar_uno, ejecutar

bp = Blueprint("temporadas", __name__, url_prefix="/api/alertas/temporadas")

COLUMNAS = "id, nombre, fecha_inicio, fecha_fin, multiplicador"

# Límite del tipo DECIMAL(4,2) definido en el diagrama ER
MULTIPLICADOR_MAXIMO = Decimal("99.99")


def _buscar(temporada_id):
    """Devuelve la temporada o responde 404 si no existe."""
    fila = consultar_uno(f"SELECT {COLUMNAS} FROM temporada WHERE id = %s", (temporada_id,))
    if fila is None:
        abort(404, "Temporada no encontrada")
    return fila


def _leer_fecha(datos, campo):
    """Convierte un texto AAAA-MM-DD en fecha o responde 400."""
    valor = datos.get(campo)
    if not isinstance(valor, str):
        abort(400, f"{campo} es obligatoria y debe tener el formato AAAA-MM-DD")
    try:
        return date.fromisoformat(valor)
    except ValueError:
        abort(400, f"{campo} no es una fecha válida (formato AAAA-MM-DD)")


def _validar_entrada():
    """Valida el cuerpo según el esquema TemporadaEntrada del contrato."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        abort(400, "El cuerpo de la solicitud debe ser un objeto JSON")

    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or nombre.strip() == "":
        abort(400, "nombre es obligatorio")
    nombre = nombre.strip()
    if len(nombre) > 100:
        abort(400, "nombre no puede tener más de 100 caracteres")

    fecha_inicio = _leer_fecha(datos, "fecha_inicio")
    fecha_fin = _leer_fecha(datos, "fecha_fin")
    if fecha_fin < fecha_inicio:
        abort(400, "fecha_fin no puede ser anterior a fecha_inicio")

    multiplicador = datos.get("multiplicador")
    if isinstance(multiplicador, bool) or not isinstance(multiplicador, (int, float)):
        abort(400, "multiplicador es obligatorio y debe ser un número")
    try:
        multiplicador = Decimal(str(multiplicador)).quantize(Decimal("0.01"))
    except InvalidOperation:
        abort(400, "multiplicador no es un número válido")
    if multiplicador < 1 or multiplicador > MULTIPLICADOR_MAXIMO:
        abort(400, "multiplicador debe estar entre 1 y 99.99")

    return nombre, fecha_inicio, fecha_fin, multiplicador


@bp.get("/")
def listar_temporadas():
    filas = consultar(f"SELECT {COLUMNAS} FROM temporada ORDER BY fecha_inicio, id")
    return jsonify(filas)


@bp.post("/")
def crear_temporada():
    nombre, fecha_inicio, fecha_fin, multiplicador = _validar_entrada()
    resultado = ejecutar(
        "INSERT INTO temporada (nombre, fecha_inicio, fecha_fin, multiplicador) "
        "VALUES (%s, %s, %s, %s)",
        (nombre, fecha_inicio, fecha_fin, multiplicador),
    )
    return jsonify(_buscar(resultado["id"])), 201


@bp.put("/<int:temporada_id>")
def actualizar_temporada(temporada_id):
    _buscar(temporada_id)
    nombre, fecha_inicio, fecha_fin, multiplicador = _validar_entrada()
    ejecutar(
        "UPDATE temporada SET nombre = %s, fecha_inicio = %s, fecha_fin = %s, "
        "multiplicador = %s WHERE id = %s",
        (nombre, fecha_inicio, fecha_fin, multiplicador, temporada_id),
    )
    return jsonify(_buscar(temporada_id))


@bp.delete("/<int:temporada_id>")
def eliminar_temporada(temporada_id):
    _buscar(temporada_id)
    ejecutar("DELETE FROM temporada WHERE id = %s", (temporada_id,))
    return "", 204