"""Rutas de alertas de inventario (tag Alertas del contrato OpenAPI).

GET   /api/alertas/              Listar alertas (filtros y paginación)
GET   /api/alertas/{id}          Consultar una alerta
PATCH /api/alertas/{id}/estado   Cambiar el estado de una alerta
POST  /api/alertas/evaluar       Evaluar el stock contra los umbrales y generar alertas
"""

import math
from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, abort, jsonify, request

from clientes.inventario import stock_agrupado
from database import consultar, consultar_uno, ejecutar, transaccion

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
    """Id del usuario enviado por el API Gateway en X-User-Id, o None."""
    valor = request.headers.get("X-User-Id", "").strip()
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
        sql = (
            "UPDATE alerta SET estado = %s, usuario_atencion_id = NULL, "
            "fecha_atencion = NULL WHERE id = %s"
        )
        parametros = (estado, alerta_id)
    elif estado == "en_gestion":
        sql = (
            "UPDATE alerta SET estado = %s, usuario_atencion_id = %s, "
            "fecha_atencion = NULL WHERE id = %s"
        )
        parametros = (estado, usuario_id, alerta_id)
    else:
        sql = (
            "UPDATE alerta SET estado = %s, usuario_atencion_id = %s, "
            "fecha_atencion = NOW() WHERE id = %s"
        )
        parametros = (estado, usuario_id, alerta_id)

    # Bloqueo de la fila (FOR UPDATE): si dos usuarios cambian la misma alerta
    # a la vez, uno espera al otro y cada respuesta muestra exactamente lo que
    # guardó esa petición (RF10, trazabilidad).
    with transaccion() as cursor:
        cursor.execute("SELECT id FROM alerta WHERE id = %s FOR UPDATE", (alerta_id,))
        if cursor.fetchone() is None:
            abort(404, "Alerta no encontrada")
        cursor.execute(sql, parametros)
        cursor.execute(f"SELECT {COLUMNAS} FROM alerta WHERE id = %s", (alerta_id,))
        alerta = cursor.fetchone()

    return jsonify(alerta)


@bp.post("/evaluar")
def evaluar_stock():
    """Compara el stock de Inventario con los umbrales activos (RF09).

    Reglas acordadas:
      - Stock del umbral: el de su bodega, o la suma de todas si no tiene bodega.
      - Umbral aplicado = stock_minimo x multiplicador de la temporada vigente
        (1 si no hay), redondeado hacia arriba.
      - Si stock <= umbral aplicado: alerta "agotado" (stock 0) o "stock_bajo".
      - No se duplica una alerta pendiente o en gestión del mismo producto y tipo.
      - Cada alerta nueva genera una sugerencia por (2 x umbral aplicado - stock).
    """
    umbrales = consultar(
        "SELECT producto_id, bodega_id, stock_minimo FROM umbral_stock "
        "WHERE activo = TRUE ORDER BY id"
    )
    if not umbrales:
        return jsonify({"productos_evaluados": 0, "alertas_generadas": 0})

    # Responde 503 si Inventario no está disponible
    por_producto, por_producto_bodega = stock_agrupado()

    # Temporada vigente hoy (fechas en UTC); si hay varias, se usa el mayor multiplicador
    hoy = datetime.now(timezone.utc).date()
    temporada = consultar_uno(
        "SELECT MAX(multiplicador) AS multiplicador FROM temporada "
        "WHERE fecha_inicio <= %s AND fecha_fin >= %s",
        (hoy, hoy),
    )
    multiplicador = Decimal(temporada["multiplicador"] or 1)

    abiertas = {
        (fila["producto_id"], fila["tipo"])
        for fila in consultar(
            "SELECT producto_id, tipo FROM alerta "
            "WHERE estado IN ('pendiente', 'en_gestion')"
        )
    }

    productos_evaluados = set()
    alertas_generadas = 0

    with transaccion() as cursor:
        for umbral in umbrales:
            producto_id = umbral["producto_id"]
            bodega_id = umbral["bodega_id"]
            productos_evaluados.add(producto_id)

            if bodega_id is None:
                stock = por_producto.get(producto_id, 0)
            else:
                stock = por_producto_bodega.get((producto_id, bodega_id), 0)

            umbral_aplicado = math.ceil(umbral["stock_minimo"] * multiplicador)
            if stock > umbral_aplicado:
                continue

            tipo = "agotado" if stock <= 0 else "stock_bajo"
            if (producto_id, tipo) in abiertas:
                continue

            cursor.execute(
                "INSERT INTO alerta (producto_id, tipo, stock_actual, umbral_aplicado, "
                "multiplicador_aplicado) VALUES (%s, %s, %s, %s, %s)",
                (producto_id, tipo, stock, umbral_aplicado, multiplicador),
            )
            cursor.execute(
                "INSERT INTO sugerencia_reabastecimiento "
                "(alerta_id, producto_id, cantidad_sugerida) VALUES (%s, %s, %s)",
                (cursor.lastrowid, producto_id, max(1, 2 * umbral_aplicado - stock)),
            )
            abiertas.add((producto_id, tipo))
            alertas_generadas += 1

    return jsonify(
        {
            "productos_evaluados": len(productos_evaluados),
            "alertas_generadas": alertas_generadas,
        }
    )