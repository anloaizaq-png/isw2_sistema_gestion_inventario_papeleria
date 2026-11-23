"""Rutas de alertas de inventario (tag Alertas del contrato OpenAPI).

GET   /api/alertas/              Listar alertas (filtros y paginación)
GET   /api/alertas/{id}          Consultar una alerta
PATCH /api/alertas/{id}/estado   Cambiar el estado de una alerta

POST /api/alertas/evaluar se agregará cuando esté definida la integración
con el servicio de Inventario.
"""

from flask import Blueprint, abort, jsonify, request

from database import consultar, consultar_uno, ejecutar

bp = Blueprint("alertas", __name__, url_prefix="/api/alertas")

COLUMNAS = (
    "id, producto_id, tipo, estado, stock_actual, umbral_aplicado, "
    "multiplicador_aplicado, fecha_generacion, fecha_atencion, usuario_atencion_id"
)

# Valores permitidos según el contrato (EstadoAlerta y TipoAlerta)
ESTADOS = ("pendiente", "en_gestion", "atendida", "descartada")
TIPOS = ("stock_bajo", "agotado", "sin_movimiento")

LIMITE_MAXIMO = 100


def _buscar(alerta_id):
    """Devuelve la alerta o responde 404 si no existe."""
    fila = consultar_uno(f"SELECT {COLUMNAS} FROM alerta WHERE id = %s", (alerta_id,))
    if fila is None:
        abort(404, "Alerta no encontrada")
    return fila


def _entero_query(nombre, por_defecto=None, minimo=1):
    """Lee un parámetro entero de la URL (?nombre=valor) o responde 400."""
    valor = request.args.get(nombre)
    if valor is None or valor == "":
        return por_defecto
    try:
        numero = int(valor)
    except ValueError:
        abort(400, f"{nombre} debe ser un número entero")
    if numero < minimo:
        abort(400, f"{nombre} debe ser mayor o igual a {minimo}")
    return numero


def _usuario_actual():
    """Id del usuario enviado por el API Gateway en X-Usuario-Id, o None."""
    valor = request.headers.get("X-Usuario-Id", "").strip()
    return int(valor) if valor.isdigit() else None


@bp.get("/")
def listar_alertas():
    condiciones = []
    parametros = []

    estado = request.args.get("estado")
    if estado:
        if estado not in ESTADOS:
            abort(400, "estado debe ser uno de: " + ", ".join(ESTADOS))
        condiciones.append("estado = %s")
        parametros.append(estado)

    tipo = request.args.get("tipo")
    if tipo:
        if tipo not in TIPOS:
            abort(400, "tipo debe ser uno de: " + ", ".join(TIPOS))
        condiciones.append("tipo = %s")
        parametros.append(tipo)

    producto_id = _entero_query("producto_id")
    if producto_id is not None:
        condiciones.append("producto_id = %s")
        parametros.append(producto_id)

    pagina = _entero_query("pagina", por_defecto=1)
    limite = _entero_query("limite", por_defecto=20)
    if limite > LIMITE_MAXIMO:
        abort(400, f"limite no puede ser mayor que {LIMITE_MAXIMO}")

    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""

    total = consultar_uno(f"SELECT COUNT(*) AS total FROM alerta{where}", tuple(parametros))
    items = consultar(
        f"SELECT {COLUMNAS} FROM alerta{where} "
        "ORDER BY fecha_generacion DESC, id DESC LIMIT %s OFFSET %s",
        tuple(parametros) + (limite, (pagina - 1) * limite),
    )
    return jsonify({"total": total["total"], "items": items})


@bp.get("/<int:alerta_id>")
def consultar_alerta(alerta_id):
    return jsonify(_buscar(alerta_id))


@bp.patch("/<int:alerta_id>/estado")
def cambiar_estado(alerta_id):
    _buscar(alerta_id)

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        abort(400, "El cuerpo de la solicitud debe ser un objeto JSON")
    estado = datos.get("estado")
    if estado not in ESTADOS:
        abort(400, "estado es obligatorio y debe ser uno de: " + ", ".join(ESTADOS))

    usuario_id = _usuario_actual()

    # Reglas acordadas para los datos de atención:
    #   pendiente               -> sin usuario ni fecha de atención
    #   en_gestion              -> se guarda quién la tomó, sin fecha
    #   atendida o descartada   -> se guarda quién la cerró y la fecha actual
    if estado == "pendiente":
        ejecutar(
            "UPDATE alerta SET estado = %s, usuario_atencion_id = NULL, "
            "fecha_atencion = NULL WHERE id = %s",
            (estado, alerta_id),
        )
    elif estado == "en_gestion":
        ejecutar(
            "UPDATE alerta SET estado = %s, usuario_atencion_id = %s, "
            "fecha_atencion = NULL WHERE id = %s",
            (estado, usuario_id, alerta_id),
        )
    else:
        ejecutar(
            "UPDATE alerta SET estado = %s, usuario_atencion_id = %s, "
            "fecha_atencion = NOW() WHERE id = %s",
            (estado, usuario_id, alerta_id),
        )

    return jsonify(_buscar(alerta_id))