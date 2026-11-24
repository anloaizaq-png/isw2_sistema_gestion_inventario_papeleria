"""
Pruebas de rendimiento con Locust - Alertas y Analítica (A01 a A15)
Cotton Cloud Paper

Los 15 escenarios corresponden a la Tabla 23 del documento de la Entrega 2.
Cada escenario se ejecuta por separado con --tags (ver README_alertas_analitica.md).

Variables de entorno (opcionales):
  ALERTAS_HOST    URL base de Alertas y Analítica (por defecto http://localhost:8080, el API Gateway)
  PRODUCTOS_PERF  Ids de producto con stock en Inventario, separados por coma (por defecto 10,11,12,13,14)

Antes de iniciar, el test crea (si no existen) umbrales para esos productos y una
temporada llamada "PERF Temporada", y ejecuta una evaluación para tener alertas.
Si el servicio no responde, reintenta hasta 5 veces. Si aun así no hay alertas,
A03 y A04 registran un fallo "sin datos de prueba" en lugar de consultar ids falsos.
"""
import os
import random
import time
import uuid
from datetime import date, datetime, timezone

import requests
from locust import HttpUser, between, events, tag, task

ALERTAS_HOST = os.getenv("ALERTAS_HOST", "http://localhost:8080")
PRODUCTOS_PERF = [int(p) for p in os.getenv("PRODUCTOS_PERF", "10,11,12,13,14").split(",")]

ESTADOS_ALERTA = ("pendiente", "en_gestion", "atendida", "descartada")
TIPOS_ALERTA = ("stock_bajo", "agotado", "sin_movimiento")
NIVELES = ("alta", "media", "baja")
CATEGORIAS = ("A", "B", "C")

# Datos de prueba (se llenan en preparar_datos)
DATOS = {"alertas": [], "temporada": None}

# Resultado de referencia para comprobar que A11 es igual para todos los usuarios
REFERENCIA = {"clasificacion": None}

# Ids de umbrales creados en A08, para detectar duplicados
UMBRALES_CREADOS = set()


def _hoy():
    return datetime.now(timezone.utc).date()


# ---------------------------------------------------------------------------
# Preparación de datos de prueba (idempotente)
# ---------------------------------------------------------------------------
def _get_json(url, params=None):
    """GET que exige respuesta 200; si no, lanza un error para reintentar."""
    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"GET {url} respondió {r.status_code}")
    return r.json()


def _preparar():
    # Umbrales para los productos de prueba (solo si el producto aún no tiene uno activo)
    umbrales = _get_json(f"{ALERTAS_HOST}/api/alertas/umbrales")
    con_umbral = {u["producto_id"] for u in umbrales if u["activo"]}
    for producto_id in PRODUCTOS_PERF:
        if producto_id not in con_umbral:
            requests.post(
                f"{ALERTAS_HOST}/api/alertas/umbrales",
                json={"producto_id": producto_id, "stock_minimo": 5},
                timeout=10,
            )

    # Temporada de prueba que cubre el mes en curso
    temporadas = _get_json(f"{ALERTAS_HOST}/api/alertas/temporadas")
    existente = next((t for t in temporadas if t["nombre"] == "PERF Temporada"), None)
    if existente is None:
        hoy = _hoy()
        r = requests.post(
            f"{ALERTAS_HOST}/api/alertas/temporadas",
            json={
                "nombre": "PERF Temporada",
                "fecha_inicio": hoy.replace(day=1).isoformat(),
                "fecha_fin": date(hoy.year, 12, 31).isoformat(),
                "multiplicador": 1,
            },
            timeout=10,
        )
        if r.status_code != 201:
            raise RuntimeError(f"No se pudo crear la temporada: HTTP {r.status_code}")
        existente = r.json()
    DATOS["temporada"] = existente["id"]

    # Una evaluación para que existan alertas y sugerencias (si Inventario responde)
    requests.post(f"{ALERTAS_HOST}/api/alertas/evaluar", timeout=10)
    alertas = _get_json(f"{ALERTAS_HOST}/api/alertas/", params={"limite": 100})
    DATOS["alertas"] = [a["id"] for a in alertas["items"]]


@events.test_start.add_listener
def preparar_datos(environment, **kwargs):
    for intento in range(1, 6):
        try:
            _preparar()
            print(f"[datos de prueba] alertas={len(DATOS['alertas'])} temporada={DATOS['temporada']}")
            if not DATOS["alertas"]:
                print("[ADVERTENCIA] No hay alertas: A03 y A04 registrarán fallos 'sin datos de prueba'.")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[ADVERTENCIA] Intento {intento}/5 de preparar los datos falló: {exc}")
            time.sleep(2)
    print("[ERROR] No se pudieron preparar los datos de prueba.")


def _sin_datos(nombre):
    """Registra un fallo explícito cuando no hay alertas de prueba."""
    events.request.fire(
        request_type="DATOS",
        name=nombre,
        response_time=0,
        response_length=0,
        exception=RuntimeError("Sin alertas de prueba"),
        context={},
    )


def _verificar(response, codigos_ok, validar=None):
    """Marca la respuesta como correcta solo si el código HTTP y el contenido son los esperados."""
    if response.status_code not in codigos_ok:
        response.failure(f"HTTP {response.status_code}: {response.text[:200]}")
        return
    if validar is not None and response.status_code == 200:
        try:
            error = validar(response)
        except Exception as exc:  # noqa: BLE001
            error = f"Respuesta inválida: {exc}"
        if error:
            response.failure(error)
            return
    response.success()


def _id_alerta():
    return random.choice(DATOS["alertas"]) if DATOS["alertas"] else None


def _rango_mes():
    hoy = _hoy()
    return {"desde": hoy.replace(day=1).isoformat(), "hasta": hoy.isoformat()}


def _validar_rotacion(r):
    for fila in r.json():
        if fila["nivel"] not in NIVELES:
            return f"Nivel inválido: {fila['nivel']}"
        if fila["unidades_vendidas"] < 0 or fila["indice_rotacion"] < 0:
            return f"Valores negativos: {fila}"


# ---------------------------------------------------------------------------
# Usuario de Alertas y Analítica
# ---------------------------------------------------------------------------
class AlertasUser(HttpUser):
    host = ALERTAS_HOST
    wait_time = between(0.1, 0.5)

    # ----- Alertas -------------------------------------------------------
    @tag("A01", "A02", "A15")
    @task(3)
    def a01_a02_listado_alertas(self):
        """A01 (carga normal) y A02 (pico): GET /api/alertas/ con filtros y paginación."""
        filtro = random.choice(
            [
                {},
                {"estado": random.choice(ESTADOS_ALERTA)},
                {"tipo": random.choice(TIPOS_ALERTA)},
                {"pagina": 1, "limite": 10},
            ]
        )

        def validar(r):
            cuerpo = r.json()
            if not isinstance(cuerpo.get("items"), list) or "total" not in cuerpo:
                return "La respuesta no tiene items y total"
            for alerta in cuerpo["items"]:
                if "estado" in filtro and alerta["estado"] != filtro["estado"]:
                    return f"Estado inesperado: {alerta['estado']}"
                if "tipo" in filtro and alerta["tipo"] != filtro["tipo"]:
                    return f"Tipo inesperado: {alerta['tipo']}"

        with self.client.get(
            "/api/alertas/", params=filtro, name="[A01/02/15] GET /api/alertas/", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

    @tag("A03")
    @task
    def a03_consulta_alerta(self):
        """A03: GET /api/alertas/{id} - existentes (200) e inexistentes (404)."""
        if random.random() < 0.8:
            esperado, alerta_id = 200, _id_alerta()
            if alerta_id is None:
                _sin_datos("[A03] sin alertas de prueba")
                return
        else:
            esperado, alerta_id = 404, 99999999

        def validar(r):
            if r.json()["id"] != alerta_id:
                return f"Se pidió la alerta {alerta_id} y llegó otra"

        with self.client.get(
            f"/api/alertas/{alerta_id}", name="[A03] GET /api/alertas/{id}", catch_response=True
        ) as r:
            _verificar(r, (esperado,), validar)

    @tag("A04", "A15")
    @task
    def a04_cambio_estado(self):
        """A04: PATCH /api/alertas/{id}/estado - el estado queda actualizado."""
        alerta_id = _id_alerta()
        if alerta_id is None:
            _sin_datos("[A04/15] sin alertas de prueba")
            return
        estado = random.choice(("pendiente", "en_gestion"))
        usuario = random.randint(1, 50)

        def validar(r):
            alerta = r.json()
            if alerta["estado"] != estado:
                return f"Estado {alerta['estado']}, se esperaba {estado}"
            if estado == "en_gestion" and alerta["usuario_atencion_id"] is None:
                return "No se guardó el usuario que tomó la alerta"
            if estado == "pendiente" and alerta["usuario_atencion_id"] is not None:
                return "La alerta pendiente conserva un usuario de atención"

        with self.client.patch(
            f"/api/alertas/{alerta_id}/estado",
            json={"estado": estado},
            headers={"X-User-Id": str(usuario)},
            name="[A04/15] PATCH /api/alertas/{id}/estado",
            catch_response=True,
        ) as r:
            _verificar(r, (200,), validar)

        with self.client.get(
            f"/api/alertas/{alerta_id}", name="[A04/15] GET tras el cambio", catch_response=True
        ) as r:
            _verificar(r, (200,), lambda resp: None if resp.json()["estado"] in ESTADOS_ALERTA else "Estado inválido")

    @tag("A05")
    @task
    def a05_evaluacion(self):
        """A05: POST /api/alertas/evaluar - sin alertas abiertas duplicadas."""

        def validar(r):
            cuerpo = r.json()
            if "productos_evaluados" not in cuerpo or "alertas_generadas" not in cuerpo:
                return "Faltan productos_evaluados o alertas_generadas"

        with self.client.post(
            "/api/alertas/evaluar", name="[A05] POST /api/alertas/evaluar", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

        def sin_duplicados(r):
            vistos = set()
            for alerta in r.json()["items"]:
                clave = (alerta["producto_id"], alerta["tipo"])
                if clave in vistos:
                    return f"Alerta abierta duplicada: producto {clave[0]}, tipo {clave[1]}"
                vistos.add(clave)

        for estado in ("pendiente", "en_gestion"):
            with self.client.get(
                "/api/alertas/",
                params={"estado": estado, "limite": 100},
                name="[A05] GET alertas abiertas (duplicados)",
                catch_response=True,
            ) as r:
                _verificar(r, (200,), sin_duplicados)

    @tag("A06")
    @task
    def a06_evaluacion_sin_inventario(self):
        """A06: POST /api/alertas/evaluar con Inventario detenido - 503 controlado."""

        def validar_503(r):
            if r.json().get("codigo") != 503:
                return "El error no tiene el formato {codigo, mensaje}"

        with self.client.post(
            "/api/alertas/evaluar", name="[A06] POST /api/alertas/evaluar (sin Inventario)", catch_response=True
        ) as r:
            if r.status_code == 503:
                error = validar_503(r)
                r.failure(error) if error else r.success()
            else:
                r.failure(f"Se esperaba 503 controlado y llegó HTTP {r.status_code}")

    # ----- Umbrales ------------------------------------------------------
    @tag("A07", "A15")
    @task(2)
    def a07_listado_umbrales(self):
        """A07: GET /api/alertas/umbrales."""

        def validar(r):
            umbrales = r.json()
            if not isinstance(umbrales, list):
                return "La respuesta no es una lista"
            for u in umbrales:
                if u["stock_minimo"] < 0:
                    return f"Umbral con stock_minimo negativo: {u}"

        with self.client.get(
            "/api/alertas/umbrales", name="[A07/15] GET /api/alertas/umbrales", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

    @tag("A08", "A15")
    @task
    def a08_creacion_umbrales(self):
        """A08: POST /api/alertas/umbrales - válidos (201) e inválidos (400), sin duplicados.

        Los umbrales se crean inactivos para que no afecten a POST /evaluar ni a otras pruebas.
        """
        if random.random() < 0.2:
            cuerpo, esperado = {"producto_id": 900000, "stock_minimo": -1, "activo": False}, 400
        else:
            producto_id = 900000 + uuid.uuid4().int % 1000000
            cuerpo = {"producto_id": producto_id, "stock_minimo": random.randint(0, 50), "activo": False}
            esperado = 201

        with self.client.post(
            "/api/alertas/umbrales", json=cuerpo, name="[A08/15] POST /api/alertas/umbrales", catch_response=True
        ) as r:
            if r.status_code != esperado:
                r.failure(f"HTTP {r.status_code}, se esperaba {esperado}: {r.text[:200]}")
                return
            if esperado == 201:
                umbral = r.json()
                if (
                    umbral["producto_id"] != cuerpo["producto_id"]
                    or umbral["stock_minimo"] != cuerpo["stock_minimo"]
                    or umbral["activo"] is not False
                ):
                    r.failure("El umbral creado no coincide con los datos enviados")
                    return
                if umbral["id"] in UMBRALES_CREADOS:
                    r.failure(f"Id de umbral repetido: {umbral['id']}")
                    return
                UMBRALES_CREADOS.add(umbral["id"])
            r.success()

    # ----- Analítica -----------------------------------------------------
    @tag("A09", "A10", "A15")
    @task(2)
    def a09_a10_rotacion(self):
        """A09 (carga normal) y A10 (estrés): GET /api/alertas/analitica/rotacion."""
        with self.client.get(
            "/api/alertas/analitica/rotacion",
            params=_rango_mes(),
            name="[A09/10/15] GET /analitica/rotacion",
            catch_response=True,
        ) as r:
            _verificar(r, (200,), _validar_rotacion)

    @tag("A11")
    @task
    def a11_clasificacion_abc(self):
        """A11: GET /api/alertas/analitica/clasificacion-abc - mismo resultado para todos."""

        def validar(r):
            resultado = sorted((f["producto_id"], f["categoria"]) for f in r.json())
            for _, categoria in resultado:
                if categoria not in CATEGORIAS:
                    return f"Categoría inválida: {categoria}"
            if REFERENCIA["clasificacion"] is None:
                REFERENCIA["clasificacion"] = resultado
            elif resultado != REFERENCIA["clasificacion"]:
                return "La clasificación cambió entre usuarios"

        with self.client.get(
            "/api/alertas/analitica/clasificacion-abc", name="[A11] GET /analitica/clasificacion-abc", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

    @tag("A12")
    @task
    def a12_proximos_agotarse(self):
        """A12: GET /api/alertas/analitica/proximos-agotarse (pico)."""

        def validar(r):
            for p in r.json():
                if not p["stock_minimo"] < p["stock_actual"] <= p["stock_minimo"] * 1.25:
                    return f"Producto fuera del margen del 25 %: {p}"

        with self.client.get(
            "/api/alertas/analitica/proximos-agotarse", name="[A12] GET /analitica/proximos-agotarse", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

    @tag("A13")
    @task
    def a13_demanda_temporada(self):
        """A13: GET /api/alertas/analitica/demanda-temporada - 200 existente, 404 inexistente."""
        if random.random() < 0.8:
            esperado, temporada_id = 200, DATOS["temporada"] or 1
        else:
            esperado, temporada_id = 404, 99999999

        def validar(r):
            unidades = [f["unidades_vendidas"] for f in r.json()]
            if unidades != sorted(unidades, reverse=True):
                return "Los productos no están ordenados de mayor a menor demanda"

        with self.client.get(
            "/api/alertas/analitica/demanda-temporada",
            params={"temporada_id": temporada_id},
            name="[A13] GET /analitica/demanda-temporada",
            catch_response=True,
        ) as r:
            _verificar(r, (esperado,), validar)

    # ----- Reabastecimiento ----------------------------------------------
    @tag("A14", "A15")
    @task(2)
    def a14_sugerencias_pendientes(self):
        """A14: GET /api/alertas/sugerencias-reabastecimiento?estado=pendiente (consumo de Compras)."""

        def validar(r):
            for s in r.json():
                if s["estado"] != "pendiente":
                    return f"Sugerencia no pendiente en el filtro: {s['id']}"
                if s["cantidad_sugerida"] <= 0:
                    return f"Cantidad sugerida inválida: {s}"

        with self.client.get(
            "/api/alertas/sugerencias-reabastecimiento",
            params={"estado": "pendiente"},
            name="[A14/15] GET /sugerencias-reabastecimiento",
            catch_response=True,
        ) as r:
            _verificar(r, (200,), validar)