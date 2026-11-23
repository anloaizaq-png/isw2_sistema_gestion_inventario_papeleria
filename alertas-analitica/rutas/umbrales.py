"""Rutas de umbrales de stock mínimo (tag Umbrales del contrato OpenAPI).

GET    /api/alertas/umbrales        Listar umbrales
POST   /api/alertas/umbrales        Crear umbral
PUT    /api/alertas/umbrales/{id}   Actualizar umbral
DELETE /api/alertas/umbrales/{id}   Desactivar umbral (no se borra de la base)
"""

from flask import Blueprint, abort, jsonify, request

from database import consultar, consultar_uno, ejecutar

bp = Blueprint("umbrales", __name__, url_prefix="/api/alertas/umbrales")

COLUMNAS = "id, producto_id, bodega_id, stock_minimo, activo"


def _es_entero(valor):
    """True si el valor es un entero (en Python, True/False también son enteros)."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def _formatear(fila):
    """MySQL guarda BOOLEAN como 0/1; se devuelve como true/false."""
    fila["activo"] = bool(fila["activo"])
    return fila


def _buscar(umbral_id):
    """Devuelve el umbral o responde 404 si no existe."""
    fila = consultar_uno(f"SELECT {COLUMNAS} FROM umbral_stock WHERE id = %s", (umbral_id,))
    if fila is None:
        abort(404, "Umbral no encontrado")
    return _formatear(fila)


def _validar_entrada():
    """Valida el cuerpo según el esquema UmbralEntrada del contrato."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        abort(400, "El cuerpo de la solicitud debe ser un objeto JSON")

    producto_id = datos.get("producto_id")
    if not _es_entero(producto_id) or producto_id <= 0:
        abort(400, "producto_id es obligatorio y debe ser un entero positivo")

    stock_minimo = datos.get("stock_minimo")
    if not _es_entero(stock_minimo) or stock_minimo < 0:
        abort(400, "stock_minimo es obligatorio y debe ser un entero mayor o igual a 0")

    bodega_id = datos.get("bodega_id")
    if bodega_id is not None and (not _es_entero(bodega_id) or bodega_id <= 0):
        abort(400, "bodega_id debe ser un entero positivo o null")

    activo = datos.get("activo", True)
    if not isinstance(activo, bool):
        abort(400, "activo debe ser true o false")

    return producto_id, bodega_id, stock_minimo, activo


@bp.get("/")
def listar_umbrales():
    filas = consultar(f"SELECT {COLUMNAS} FROM umbral_stock ORDER BY id")
    return jsonify([_formatear(fila) for fila in filas])


@bp.post("/")
def crear_umbral():
    producto_id, bodega_id, stock_minimo, activo = _validar_entrada()
    resultado = ejecutar(
        "INSERT INTO umbral_stock (producto_id, bodega_id, stock_minimo, activo) "
        "VALUES (%s, %s, %s, %s)",
        (producto_id, bodega_id, stock_minimo, activo),
    )
    return jsonify(_buscar(resultado["id"])), 201


@bp.put("/<int:umbral_id>")
def actualizar_umbral(umbral_id):
    _buscar(umbral_id)
    producto_id, bodega_id, stock_minimo, activo = _validar_entrada()
    ejecutar(
        "UPDATE umbral_stock SET producto_id = %s, bodega_id = %s, "
        "stock_minimo = %s, activo = %s WHERE id = %s",
        (producto_id, bodega_id, stock_minimo, activo, umbral_id),
    )
    return jsonify(_buscar(umbral_id))


@bp.delete("/<int:umbral_id>")
def desactivar_umbral(umbral_id):
    _buscar(umbral_id)
    ejecutar("UPDATE umbral_stock SET activo = FALSE WHERE id = %s", (umbral_id,))
    return "", 204