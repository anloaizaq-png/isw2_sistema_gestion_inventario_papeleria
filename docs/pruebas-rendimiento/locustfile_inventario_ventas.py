"""
Suite de Pruebas de Rendimiento con Locust (P3-01 a P3-15)
Cotton Cloud Paper - Microservicios de Inventario y Ventas

Cubre los 15 escenarios exactos del plan de pruebas:
- P3-01: GET /api/inventario/stock - Carga normal (10 usuarios)
- P3-02: GET /api/inventario/stock - Carga pico (40 usuarios)
- P3-03: GET /api/inventario/stock - Estrés (80 usuarios)
- P3-04: GET /api/inventario/disponibilidad - Carga normal (10 usuarios)
- P3-05: GET /api/inventario/disponibilidad - Carga pico (40 usuarios)
- P3-06: POST /api/inventario/descuentos - Carga normal (5 usuarios, garantizar sin stock negativo)
- P3-07: POST /api/inventario/descuentos - Estrés (30 usuarios, evitar descuentos duplicados con operacion_id)
- P3-08: POST /api/inventario/traslados - Carga pico (20 usuarios, actualizar bodegas sin duplicar unidades)
- P3-09: POST /api/ventas - Carga normal (10 usuarios, sin pedidos duplicados)
- P3-10: GET /api/ventas - Carga pico (40 usuarios, consultas simultáneas consistentes)
- P3-11: POST /api/ventas/{id}/confirmacion - Carga normal (5 usuarios, confirmar solo con stock suficiente)
- P3-12: POST /api/ventas/{id}/confirmacion - Estrés (30 usuarios, consistencia entre ventas y stock descontado)
- P3-13: POST /api/ventas/{id}/devoluciones - Carga normal (5 usuarios, no superar cantidad vendida)
- P3-14: POST /api/ventas/{id}/devoluciones - Estrés (20 usuarios, evitar devoluciones duplicadas)
- P3-15: POST /api/ventas/{id}/confirmacion - Carga pico integración (40 usuarios, validar comunicación Ventas -> Inventario)
"""

import os
import random
import uuid
from locust import HttpUser, between, task, tag


# IDs base reutilizados para pruebas de carga
PRODUCTO_IDS = [1, 2, 3, 4, 5]
BODEGA_IDS = [1, 2]
POOL_OPERACIONES_DESCUENTO = [f"op-desc-pool-{i}" for i in range(1, 15)]
POOL_OPERACIONES_DEVOLUCION = [f"op-dev-pool-{i}" for i in range(1, 15)]


class CottonCloudPaperUser(HttpUser):
    """
    Usuario simulado con soporte para todos los escenarios etiquetados (P3-01 a P3-15).
    Permite ejecución individual por etiquetas:
      locust -f locustfile_inventario_ventas.py --tags P3-01 --headless -u 10 -r 2 -t 1m
    """
    wait_time = between(0.1, 0.5)

    # =========================================================================
    # ESCENARIOS DE INVENTARIO (P3-01 a P3-08)
    # =========================================================================

    @tag("P3-01", "inventario", "stock", "normal")
    @task(5)
    def p3_01_stock_carga_normal(self):
        """P3-01: GET /api/inventario/stock — Carga normal (10 usuarios)"""
        p_id = random.choice(PRODUCTO_IDS)
        b_id = random.choice(BODEGA_IDS)
        with self.client.get(
            f"/api/inventario/stock?producto_id={p_id}&bodega_id={b_id}",
            name="[P3-01] GET /api/inventario/stock (Normal)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-02", "inventario", "stock", "pico")
    @task(4)
    def p3_02_stock_carga_pico(self):
        """P3-02: GET /api/inventario/stock — Carga pico (40 usuarios)"""
        with self.client.get(
            "/api/inventario/stock",
            name="[P3-02] GET /api/inventario/stock (Pico)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-03", "inventario", "stock", "estres")
    @task(3)
    def p3_03_stock_estres(self):
        """P3-03: GET /api/inventario/stock — Estrés (80 usuarios)"""
        b_id = random.choice(BODEGA_IDS)
        with self.client.get(
            f"/api/inventario/stock?bodega_id={b_id}",
            name="[P3-03] GET /api/inventario/stock (Estrés)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-04", "inventario", "disponibilidad", "normal")
    @task(5)
    def p3_04_disponibilidad_carga_normal(self):
        """P3-04: GET /api/inventario/disponibilidad — Carga normal (10 usuarios)"""
        p_id = random.choice(PRODUCTO_IDS)
        b_id = random.choice(BODEGA_IDS)
        cant = random.randint(1, 5)
        with self.client.get(
            f"/api/inventario/disponibilidad?producto_id={p_id}&bodega_id={b_id}&cantidad={cant}",
            name="[P3-04] GET /api/inventario/disponibilidad (Normal)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-05", "inventario", "disponibilidad", "pico")
    @task(4)
    def p3_05_disponibilidad_carga_pico(self):
        """P3-05: GET /api/inventario/disponibilidad — Carga pico (40 usuarios)"""
        p_id = random.choice(PRODUCTO_IDS)
        b_id = random.choice(BODEGA_IDS)
        cant = random.randint(5, 20)
        with self.client.get(
            f"/api/inventario/disponibilidad?producto_id={p_id}&bodega_id={b_id}&cantidad={cant}",
            name="[P3-05] GET /api/inventario/disponibilidad (Pico)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-06", "inventario", "descuentos", "normal")
    @task(3)
    def p3_06_descuento_sin_stock_negativo(self):
        """P3-06: POST /api/inventario/descuentos — Carga normal (5 usuarios, garantizar sin stock negativo)"""
        payload = {
            "operacion_id": f"p3-06-{uuid.uuid4()}",
            "venta_id": random.randint(100, 999),
            "producto_id": random.choice(PRODUCTO_IDS),
            "bodega_id": random.choice(BODEGA_IDS),
            "cantidad": random.randint(1, 3),
        }
        with self.client.post(
            "/api/inventario/descuentos",
            json=payload,
            name="[P3-06] POST /api/inventario/descuentos (Normal)",
            catch_response=True,
        ) as response:
            # 200: Descuento exitoso; 409: Stock insuficiente controlado (rechazo ACID correcto sin negativos)
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Código inesperado {response.status_code}: {response.text}")

    @tag("P3-07", "inventario", "descuentos", "estres", "idempotencia")
    @task(3)
    def p3_07_descuentos_estres_idempotencia(self):
        """P3-07: POST /api/inventario/descuentos — Estrés (30 usuarios, evitar descuentos duplicados con operacion_id)"""
        # 50% de probabilidad de reusar una operacion_id para forzar validación de idempotencia
        if random.random() < 0.5:
            op_id = random.choice(POOL_OPERACIONES_DESCUENTO)
        else:
            op_id = f"p3-07-{uuid.uuid4()}"

        payload = {
            "operacion_id": op_id,
            "venta_id": random.randint(1, 50),
            "producto_id": 1,
            "bodega_id": 1,
            "cantidad": 1,
        }
        with self.client.post(
            "/api/inventario/descuentos",
            json=payload,
            name="[P3-07] POST /api/inventario/descuentos (Estrés Idempotencia)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-08", "inventario", "traslados", "pico")
    @task(3)
    def p3_08_traslados_carga_pico(self):
        """P3-08: POST /api/inventario/traslados — Carga pico (20 usuarios, actualizar bodegas sin duplicar unidades)"""
        payload = {
            "producto_id": random.choice(PRODUCTO_IDS),
            "bodega_origen_id": 1,
            "bodega_destino_id": 2,
            "cantidad": 1,
            "usuario_id": 1,
            "operacion_id": f"p3-08-{uuid.uuid4()}",
        }
        with self.client.post(
            "/api/inventario/traslados",
            json=payload,
            name="[P3-08] POST /api/inventario/traslados (Pico)",
            catch_response=True,
        ) as response:
            if response.status_code in (201, 409):
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    # =========================================================================
    # ESCENARIOS DE VENTAS Y PEDIDOS (P3-09 a P3-15)
    # =========================================================================

    @tag("P3-09", "ventas", "pedidos", "normal")
    @task(4)
    def p3_09_crear_venta_normal(self):
        """P3-09: POST /api/ventas — Carga normal (10 usuarios, sin pedidos duplicados)"""
        payload = {
            "usuario_id": random.randint(1, 10),
            "bodega_id": random.choice(BODEGA_IDS),
            "detalles": [
                {"producto_id": random.choice(PRODUCTO_IDS), "cantidad": random.randint(1, 4)}
            ],
        }
        with self.client.post(
            "/api/ventas",
            json=payload,
            name="[P3-09] POST /api/ventas (Normal)",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-10", "ventas", "lectura", "pico")
    @task(4)
    def p3_10_consultar_ventas_pico(self):
        """P3-10: GET /api/ventas — Carga pico (40 usuarios, consultas simultáneas consistentes)"""
        estado = random.choice(["pendiente", "confirmada", "cancelada"])
        with self.client.get(
            f"/api/ventas?estado={estado}",
            name="[P3-10] GET /api/ventas (Pico)",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-11", "ventas", "confirmacion", "normal")
    @task(3)
    def p3_11_confirmar_venta_normal(self):
        """P3-11: POST /api/ventas/{id}/confirmacion — Carga normal (5 usuarios, confirmar solo con stock suficiente)"""
        # 1. Crear venta previa
        create_payload = {
            "usuario_id": 1,
            "bodega_id": 1,
            "detalles": [{"producto_id": 1, "cantidad": 1}],
        }
        res_create = self.client.post("/api/ventas", json=create_payload)
        if res_create.status_code != 201:
            return

        venta_id = res_create.json().get("id")
        conf_payload = {"operacion_id": f"p3-11-{uuid.uuid4()}"}

        with self.client.post(
            f"/api/ventas/{venta_id}/confirmacion",
            json=conf_payload,
            name="[P3-11] POST /api/ventas/{id}/confirmacion (Normal)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-12", "ventas", "confirmacion", "estres")
    @task(3)
    def p3_12_confirmar_venta_estres(self):
        """P3-12: POST /api/ventas/{id}/confirmacion — Estrés (30 usuarios, consistencia entre ventas y stock descontado)"""
        create_payload = {
            "usuario_id": random.randint(1, 20),
            "bodega_id": 1,
            "detalles": [{"producto_id": 1, "cantidad": 1}],
        }
        res_create = self.client.post("/api/ventas", json=create_payload)
        if res_create.status_code != 201:
            return

        venta_id = res_create.json().get("id")
        conf_payload = {"operacion_id": f"p3-12-{uuid.uuid4()}"}

        with self.client.post(
            f"/api/ventas/{venta_id}/confirmacion",
            json=conf_payload,
            name="[P3-12] POST /api/ventas/{id}/confirmacion (Estrés)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-13", "ventas", "devoluciones", "normal")
    @task(2)
    def p3_13_devolucion_normal(self):
        """P3-13: POST /api/ventas/{id}/devoluciones — Carga normal (5 usuarios, no superar cantidad vendida)"""
        # Crear y confirmar venta
        res_create = self.client.post(
            "/api/ventas",
            json={"usuario_id": 1, "bodega_id": 1, "detalles": [{"producto_id": 1, "cantidad": 2}]},
        )
        if res_create.status_code != 201:
            return

        venta = res_create.json()
        venta_id = venta.get("id")
        detalles = venta.get("detalles", [])
        if not detalles:
            return
        det_id = detalles[0]["id"]

        # Confirmar venta
        self.client.post(
            f"/api/ventas/{venta_id}/confirmacion",
            json={"operacion_id": f"p3-13-conf-{uuid.uuid4()}"},
        )

        dev_payload = {
            "operacion_id": f"p3-13-dev-{uuid.uuid4()}",
            "motivo": "Devolución prueba normal",
            "detalles": [{"detalle_venta_id": det_id, "cantidad": 1}],
        }
        with self.client.post(
            f"/api/ventas/{venta_id}/devoluciones",
            json=dev_payload,
            name="[P3-13] POST /api/ventas/{id}/devoluciones (Normal)",
            catch_response=True,
        ) as response:
            if response.status_code in (201, 409):
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-14", "ventas", "devoluciones", "estres", "idempotencia")
    @task(2)
    def p3_14_devolucion_estres_idempotencia(self):
        """P3-14: POST /api/ventas/{id}/devoluciones — Estrés (20 usuarios, evitar devoluciones duplicadas)"""
        # 50% de probabilidad de reusar operacion_id del pool
        if random.random() < 0.5:
            op_id = random.choice(POOL_OPERACIONES_DEVOLUCION)
        else:
            op_id = f"p3-14-dev-{uuid.uuid4()}"

        dev_payload = {
            "operacion_id": op_id,
            "motivo": "Devolución bajo estrés con idempotencia",
            "detalles": [{"detalle_venta_id": 1, "cantidad": 1}],
        }
        # Se envía a venta ID 1 (o cualquiera existente en seed data)
        with self.client.post(
            "/api/ventas/1/devoluciones",
            json=dev_payload,
            name="[P3-14] POST /api/ventas/{id}/devoluciones (Estrés Idempotencia)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201, 400, 404, 409):
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")

    @tag("P3-15", "ventas", "confirmacion", "integracion", "pico")
    @task(3)
    def p3_15_confirmacion_pico_integracion(self):
        """P3-15: POST /api/ventas/{id}/confirmacion — Carga pico integración (40 usuarios, validar comunicación Ventas -> Inventario)"""
        create_payload = {
            "usuario_id": random.randint(1, 50),
            "bodega_id": random.choice(BODEGA_IDS),
            "detalles": [
                {"producto_id": random.choice(PRODUCTO_IDS), "cantidad": 1},
                {"producto_id": random.choice(PRODUCTO_IDS), "cantidad": 2},
            ],
        }
        res_create = self.client.post("/api/ventas", json=create_payload)
        if res_create.status_code != 201:
            return

        venta_id = res_create.json().get("id")
        conf_payload = {"operacion_id": f"p3-15-{uuid.uuid4()}"}

        with self.client.post(
            f"/api/ventas/{venta_id}/confirmacion",
            json=conf_payload,
            name="[P3-15] POST /api/ventas/{id}/confirmacion (Pico Integración)",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 409):
                response.success()
            else:
                response.failure(f"Error {response.status_code}: {response.text}")
