"""
Pruebas de rendimiento con Locust - Productos y Proveedores/Compras (PC-01 a PC-15)
Cotton Cloud Paper

Los 15 escenarios corresponden a la Tabla 21 del documento de la Entrega 2.
Cada escenario se ejecuta por separado con --tags (ver README_productos_compras.md).

Variables de entorno (opcionales):
  PRODUCTOS_HOST  URL base de Productos  (por defecto http://localhost:8080, el API Gateway)
  COMPRAS_HOST    URL base de Compras    (por defecto http://localhost:8080, el API Gateway)
  BODEGA_ID       Bodega de Inventario usada en las recepciones (por defecto 1)

Antes de iniciar, el test crea (si no existen) unos datos de prueba con prefijo PERF.
"""
import os
import random
import uuid
from decimal import Decimal

import requests
from locust import HttpUser, between, events, tag, task

PRODUCTOS_HOST = os.getenv("PRODUCTOS_HOST", "http://localhost:8080")
COMPRAS_HOST = os.getenv("COMPRAS_HOST", "http://localhost:8080")
BODEGA_ID = int(os.getenv("BODEGA_ID", "1"))

NIT_REPETIDO = "800000001-1"
CODIGO_PUT = "PERF-PUT"

# Ids de los datos de prueba (se llenan en preparar_datos)
DATOS = {"categoria": None, "productos": [], "producto_put": None, "proveedores": []}


# ---------------------------------------------------------------------------
# Preparación de datos de prueba (idempotente)
# ---------------------------------------------------------------------------
def _post(url, cuerpo):
    return requests.post(url, json=cuerpo, timeout=10)


@events.test_start.add_listener
def preparar_datos(environment, **kwargs):
    try:
        # Categoría
        r = _post(f"{PRODUCTOS_HOST}/api/productos/categorias", {"nombre": "PERF-Categoria"})
        if r.status_code != 201:
            lista = requests.get(f"{PRODUCTOS_HOST}/api/productos/categorias", timeout=10).json()
            DATOS["categoria"] = next(c["id"] for c in lista if c["nombre"] == "PERF-Categoria")
        else:
            DATOS["categoria"] = r.json()["id"]

        # Productos PERF-001..PERF-010 y PERF-PUT (409 = ya existían)
        codigos = [f"PERF-{i:03d}" for i in range(1, 11)] + [CODIGO_PUT]
        for codigo in codigos:
            _post(
                f"{PRODUCTOS_HOST}/api/productos",
                {
                    "codigo": codigo,
                    "nombre": f"Producto prueba {codigo}",
                    "categoria_id": DATOS["categoria"],
                    "marca": "PERF",
                    "unidad_medida": "unidad",
                    "precio_venta": 1500.00,
                },
            )
        encontrados = requests.get(
            f"{PRODUCTOS_HOST}/api/productos/buscar", params={"marca": "PERF", "limit": 100}, timeout=10
        ).json()
        DATOS["productos"] = [p["id"] for p in encontrados if p["estado"] == "activo" and p["codigo"] != CODIGO_PUT]
        DATOS["producto_put"] = next(p["id"] for p in encontrados if p["codigo"] == CODIGO_PUT)

        # Proveedores PERF (422 = ya existían)
        for i in range(1, 4):
            _post(
                f"{COMPRAS_HOST}/api/compras/proveedores",
                {"nombre": f"PERF Proveedor {i}", "nit": f"80000000{i}-1"},
            )
        provs = requests.get(
            f"{COMPRAS_HOST}/api/compras/proveedores", params={"nombre": "PERF", "estado": "activo"}, timeout=10
        ).json()
        DATOS["proveedores"] = [p["id"] for p in provs]
        print(f"[datos de prueba] productos={len(DATOS['productos'])} proveedores={len(DATOS['proveedores'])}")
    except Exception as exc:  # noqa: BLE001
        print(f"[ADVERTENCIA] No se pudieron preparar los datos de prueba: {exc}")


def _verificar(response, codigos_ok, validar=None):
    """Marca la respuesta como correcta solo si el código HTTP y el contenido son los esperados."""
    if response.status_code not in codigos_ok:
        response.failure(f"HTTP {response.status_code}: {response.text[:200]}")
        return
    if validar is not None:
        try:
            error = validar(response)
        except Exception as exc:  # noqa: BLE001
            error = f"Respuesta inválida: {exc}"
        if error:
            response.failure(error)
            return
    response.success()


def _id_producto():
    return random.choice(DATOS["productos"] or [1])


def _id_proveedor():
    return random.choice(DATOS["proveedores"] or [1])


# ---------------------------------------------------------------------------
# Usuario de Productos (PC-01 a PC-09, y la parte de Productos de PC-15)
# ---------------------------------------------------------------------------
class ProductosUser(HttpUser):
    host = PRODUCTOS_HOST
    wait_time = between(0.1, 0.5)

    @tag("PC-01")
    @task
    def pc01_humo_listado(self):
        """PC-01: GET /api/productos - prueba de humo."""

        def validar(r):
            cuerpo = r.json()
            if not isinstance(cuerpo.get("data"), list) or not cuerpo["data"]:
                return "El listado no trae productos"

        with self.client.get("/api/productos?limit=5", name="[PC-01] GET /api/productos", catch_response=True) as r:
            _verificar(r, (200,), validar)

    @tag("PC-02")
    @task
    def pc02_consulta_por_id(self):
        """PC-02: GET /api/productos/{id} - existentes (200) e inexistentes (404)."""
        if random.random() < 0.8:
            esperado, pid = 200, _id_producto()
        else:
            esperado, pid = 404, 99999999
        with self.client.get(
            f"/api/productos/{pid}", name="[PC-02] GET /api/productos/{id}", catch_response=True
        ) as r:
            _verificar(r, (esperado,))

    @tag("PC-03")
    @task
    def pc03_creacion_concurrente(self):
        """PC-03: POST /api/productos - códigos únicos (201) y duplicados (409)."""
        if random.random() < 0.2:
            codigo, esperado = "PERF-001", 409
        else:
            codigo, esperado = f"PERF-{uuid.uuid4().hex[:12]}", 201
        cuerpo = {
            "codigo": codigo,
            "nombre": "Producto creado en prueba de carga",
            "categoria_id": DATOS["categoria"],
            "marca": "PERF-CARGA",
            "precio_venta": round(random.uniform(500, 5000), 2),
        }
        with self.client.post(
            "/api/productos", json=cuerpo, name="[PC-03] POST /api/productos", catch_response=True
        ) as r:
            _verificar(r, (esperado,))

    @tag("PC-04")
    @task
    def pc04_busqueda_con_filtros(self):
        """PC-04: GET /api/productos/buscar - cada filtro solo devuelve lo que cumple."""
        filtro = random.choice(
            [
                {"codigo": "PERF-001"},
                {"nombre": "prueba"},
                {"categoria": "PERF"},
                {"marca": "PERF"},
                {"proveedor": 1},
            ]
        )

        def validar(r):
            for p in r.json():
                if "codigo" in filtro and p["codigo"] != filtro["codigo"]:
                    return f"Código inesperado: {p['codigo']}"
                if "nombre" in filtro and filtro["nombre"] not in p["nombre"].lower():
                    return f"Nombre inesperado: {p['nombre']}"
                if "marca" in filtro and filtro["marca"].lower() not in (p["marca"] or "").lower():
                    return f"Marca inesperada: {p['marca']}"
                if "proveedor" in filtro and p["proveedor_id"] != filtro["proveedor"]:
                    return f"Proveedor inesperado: {p['proveedor_id']}"

        with self.client.get(
            "/api/productos/buscar", params=filtro, name="[PC-04] GET /api/productos/buscar", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

    @tag("PC-05")
    @task
    def pc05_actualizacion_concurrente(self):
        """PC-05: PUT /api/productos/{id} - varios usuarios sobre el mismo producto."""
        cuerpo = {
            "codigo": CODIGO_PUT,
            "nombre": f"Producto PUT {random.randint(1, 10**6)}",
            "marca": "PERF",
            "precio_venta": round(random.uniform(500, 5000), 2),
            "estado": "activo",
        }

        def validar(r):
            p = r.json()
            if p["codigo"] != CODIGO_PUT or p["estado"] != "activo":
                return f"Registro inconsistente: {p}"

        with self.client.put(
            f"/api/productos/{DATOS['producto_put']}",
            json=cuerpo,
            name="[PC-05] PUT /api/productos/{id}",
            catch_response=True,
        ) as r:
            _verificar(r, (200,), validar)

    @tag("PC-06")
    @task
    def pc06_baja_logica(self):
        """PC-06: DELETE /api/productos/{id} - queda inactivo y sigue consultable."""
        creado = self.client.post(
            "/api/productos",
            json={
                "codigo": f"PERF-DEL-{uuid.uuid4().hex[:10]}",
                "nombre": "Producto para baja",
                "precio_venta": 100,
            },
            name="[PC-06] (preparación) POST /api/productos",
        )
        if creado.status_code != 201:
            return
        pid = creado.json()["id"]

        def inactivo(r):
            if r.json()["estado"] != "inactivo":
                return "El producto no quedó inactivo"

        with self.client.delete(
            f"/api/productos/{pid}", name="[PC-06] DELETE /api/productos/{id}", catch_response=True
        ) as r:
            _verificar(r, (200,), inactivo)
        with self.client.get(
            f"/api/productos/{pid}", name="[PC-06] GET tras la baja", catch_response=True
        ) as r:
            _verificar(r, (200,), inactivo)

    @tag("PC-07")
    @task
    def pc07_listado_categorias(self):
        """PC-07: GET /api/productos/categorias."""

        def validar(r):
            if not isinstance(r.json(), list):
                return "La respuesta no es una lista"

        with self.client.get(
            "/api/productos/categorias", name="[PC-07] GET /api/productos/categorias", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

    @tag("PC-08")
    @task
    def pc08_creacion_categorias(self):
        """PC-08: POST /api/productos/categorias - la subcategoría queda ligada a su padre."""
        padre = self.client.post(
            "/api/productos/categorias",
            json={"nombre": f"PERF-CAT-{uuid.uuid4().hex[:10]}"},
            name="[PC-08] POST categoría raíz",
        )
        if padre.status_code != 201:
            return
        padre_id = padre.json()["id"]

        def ligada(r):
            if r.json()["categoria_padre_id"] != padre_id:
                return "La subcategoría no quedó asociada a su padre"

        with self.client.post(
            "/api/productos/categorias",
            json={"nombre": f"PERF-SUB-{uuid.uuid4().hex[:10]}", "categoria_padre_id": padre_id},
            name="[PC-08] POST subcategoría",
            catch_response=True,
        ) as r:
            _verificar(r, (201,), ligada)

    @tag("PC-09", "PC-15")
    @task
    def pc09_pc15_listado_bajo_carga(self):
        """PC-09 (estrés) y PC-15 (pico, parte de Productos): GET /api/productos."""
        with self.client.get(
            f"/api/productos?page={random.randint(1, 3)}&limit=20",
            name="[PC-09/15] GET /api/productos",
            catch_response=True,
        ) as r:
            # Bajo sobrecarga se aceptan 429/503 controlados; un 500 sí es fallo
            _verificar(r, (200, 429, 503))


# ---------------------------------------------------------------------------
# Usuario de Compras (PC-10 a PC-14, y la parte de Compras de PC-15)
# ---------------------------------------------------------------------------
class ComprasUser(HttpUser):
    host = COMPRAS_HOST
    wait_time = between(0.1, 0.5)

    def _crear_orden(self, cantidad=2, nombre="[PC-14] (preparación) POST /ordenes-compra"):
        r = self.client.post(
            "/api/compras/ordenes-compra",
            json={
                "proveedor_id": _id_proveedor(),
                "detalles": [{"producto_id": _id_producto(), "cantidad": cantidad, "precio_unitario": 100}],
            },
            name=nombre,
        )
        return r.json() if r.status_code == 201 else None

    @tag("PC-10")
    @task
    def pc10_listado_proveedores(self):
        """PC-10: GET /api/compras/proveedores con filtros por estado y nombre."""
        filtro = random.choice([{}, {"estado": "activo"}, {"nombre": "PERF"}])

        def validar(r):
            for p in r.json():
                if filtro.get("estado") and p["estado"] != filtro["estado"]:
                    return f"Estado inesperado: {p['estado']}"
                if filtro.get("nombre") and filtro["nombre"].lower() not in p["nombre"].lower():
                    return f"Nombre inesperado: {p['nombre']}"

        with self.client.get(
            "/api/compras/proveedores", params=filtro, name="[PC-10] GET /api/compras/proveedores", catch_response=True
        ) as r:
            _verificar(r, (200,), validar)

    @tag("PC-11")
    @task
    def pc11_consulta_proveedor_por_id(self):
        """PC-11: GET /api/compras/proveedores/{id} - existentes (200) e inexistentes (404)."""
        if random.random() < 0.8:
            esperado, pid = 200, _id_proveedor()
        else:
            esperado, pid = 404, 99999999
        with self.client.get(
            f"/api/compras/proveedores/{pid}",
            name="[PC-11] GET /api/compras/proveedores/{id}",
            catch_response=True,
        ) as r:
            _verificar(r, (esperado,))

    @tag("PC-12")
    @task
    def pc12_creacion_proveedores(self):
        """PC-12: POST /api/compras/proveedores - NIT distinto (201) y NIT repetido (422)."""
        if random.random() < 0.2:
            nit, esperado = NIT_REPETIDO, 422
        else:
            nit, esperado = f"{random.randint(100000000, 999999999)}-{random.randint(0, 9)}", 201
        with self.client.post(
            "/api/compras/proveedores",
            json={"nombre": f"PERF Proveedor {uuid.uuid4().hex[:8]}", "nit": nit},
            name="[PC-12] POST /api/compras/proveedores",
            catch_response=True,
        ) as r:
            _verificar(r, (esperado,))

    @tag("PC-13")
    @task
    def pc13_consistencia_orden(self):
        """PC-13: POST /api/compras/ordenes-compra - total = suma(cantidad * precio_unitario)."""
        ids = random.sample(DATOS["productos"] or [1], k=min(random.randint(1, 3), len(DATOS["productos"]) or 1))
        detalles = [
            {"producto_id": pid, "cantidad": random.randint(1, 20), "precio_unitario": round(random.uniform(100, 5000), 2)}
            for pid in ids
        ]
        esperado = sum(Decimal(str(d["precio_unitario"])) * d["cantidad"] for d in detalles)

        def validar(r):
            orden = r.json()
            if abs(Decimal(str(orden["total"])) - esperado) > Decimal("0.01"):
                return f"Total {orden['total']} distinto de {esperado}"
            if len(orden["detalles"]) != len(detalles):
                return "El detalle de la orden está incompleto"

        with self.client.post(
            "/api/compras/ordenes-compra",
            json={"proveedor_id": _id_proveedor(), "detalles": detalles},
            name="[PC-13] POST /api/compras/ordenes-compra",
            catch_response=True,
        ) as r:
            _verificar(r, (201,), validar)

    @tag("PC-14")
    @task
    def pc14_recepcion_con_inventario(self):
        """PC-14: PUT /ordenes-compra/{id}/recibir - parcial, total y 409 si ya está cerrada o cancelada."""
        orden = self._crear_orden(cantidad=2)
        if orden is None:
            return
        pid = orden["detalles"][0]["producto_id"]
        url = f"/api/compras/ordenes-compra/{orden['id']}"

        def recibir(cantidad, estado_esperado):
            def validar(r):
                if r.json()["estado"] != estado_esperado:
                    return f"Estado {r.json()['estado']}, se esperaba {estado_esperado}"

            return validar

        cuerpo = {"bodega_id": BODEGA_ID, "productos_recibidos": [{"producto_id": pid, "cantidad": 1}]}
        nombre = "[PC-14] PUT /api/compras/ordenes-compra/{id}/recibir"
        with self.client.put(f"{url}/recibir", json=cuerpo, name=nombre, catch_response=True) as r:
            _verificar(r, (200,), recibir(1, "recibida_parcial"))
        with self.client.put(f"{url}/recibir", json=cuerpo, name=nombre, catch_response=True) as r:
            _verificar(r, (200,), recibir(1, "recibida_total"))
        with self.client.put(f"{url}/recibir", json=cuerpo, name=nombre + " (cerrada)", catch_response=True) as r:
            _verificar(r, (409,))

        cancelada = self._crear_orden(cantidad=1)
        if cancelada is not None:
            curl = f"/api/compras/ordenes-compra/{cancelada['id']}"
            self.client.put(f"{curl}/cancelar", name="[PC-14] (preparación) PUT cancelar")
            with self.client.put(
                f"{curl}/recibir", json=cuerpo, name=nombre + " (cancelada)", catch_response=True
            ) as r:
                _verificar(r, (409,))

    @tag("PC-15")
    @task
    def pc15_listado_proveedores_en_pico(self):
        """PC-15 (pico, parte de Compras): GET /api/compras/proveedores."""
        with self.client.get(
            "/api/compras/proveedores", name="[PC-15] GET /api/compras/proveedores", catch_response=True
        ) as r:
            _verificar(r, (200, 429, 503))
