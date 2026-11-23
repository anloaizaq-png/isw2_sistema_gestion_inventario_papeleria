"""Rutas de sugerencias de reabastecimiento (tag Reabastecimiento del contrato OpenAPI).

Las consume el servicio de Proveedores y Compras.

GET   /api/alertas/sugerencias-reabastecimiento              Listar sugerencias
PATCH /api/alertas/sugerencias-reabastecimiento/{id}/estado  Marcar como atendida o pendiente

Las sugerencias no se crean aquí: se generan junto con las alertas en
POST /api/alertas/evaluar.
"""

from flask import Blueprint, abort, jsonify, request

from database import consultar, consultar_uno, ejecutar

bp = Blueprint(
    "sugerencias", __name__, url_prefix="/api/alertas/sugerencias-reabastecimiento"
)

COLUMNAS = (
    "id, alerta_id, producto_id, proveedor_id, cantidad_sugerida, estado, orden_compra_id"
)

# Valores permitidos según el contrato (esquema Sugerencia)
ESTADOS = ("pendiente", "atendida")


def _es_entero(valor):
    """True si el valor es un entero (en Python, True/False también son enteros)."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def _buscar(sugerencia_id):
    """Devuelve la sugerencia o responde 404 si no existe."""
    fila = consultar_uno(
        f"SELECT {COLUMNAS} FROM sugerencia_reabastecimiento WHERE id = %s",
        (sugerencia_id,),
    )
    if fila is None:
        abort(404, "Sugerencia no encontrada")
    return fila


@bp.get("/")
def listar_sugerencias():
    estado = request.args.get("estado")
    if estado:
        if estado not in ESTADOS:
            abort(400, "estado debe ser uno de: " + ", ".join(ESTADOS))
        filas = consultar(
            f"SELECT {COLUMNAS} FROM sugerencia_reabastecimiento "
            "WHERE estado = %s ORDER BY id",
            (estado,),
        )
    else:
        filas = consultar(f"SELECT {COLUMNAS} FROM sugerencia_reabastecimiento ORDER BY id")
    return jsonify(filas)


@bp.patch("/<int:sugerencia_id>/estado")
def cambiar_estado(sugerencia_id):
    _buscar(sugerencia_id)

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        abort(400, "El cuerpo de la solicitud debe ser un objeto JSON")

    estado = datos.get("estado")
    if estado not in ESTADOS:
        abort(400, "estado es obligatorio y debe ser uno de: " + ", ".join(ESTADOS))

    orden_compra_id = datos.get("orden_compra_id")
    if orden_compra_id is not None and (
        not _es_entero(orden_compra_id) or orden_compra_id <= 0
    ):
        abort(400, "orden_compra_id debe ser un entero positivo o null")

    # Reglas acordadas:
    #   atendida  -> se guarda el orden_compra_id recibido (puede quedar vacío)
    #   pendiente -> se borra el orden_compra_id
    if estado == "pendiente":
        orden_compra_id = None

    ejecutar(
        "UPDATE sugerencia_reabastecimiento SET estado = %s, orden_compra_id = %s "
        "WHERE id = %s",
        (estado, orden_compra_id, sugerencia_id),
    )
    return jsonify(_buscar(sugerencia_id))