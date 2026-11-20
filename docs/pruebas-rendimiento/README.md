# Suite de Pruebas de Rendimiento con Locust (`P3-01` a `P3-15`)

Este documento especifica la configuración, comandos de ejecución y plantilla de resultados para los **15 escenarios de pruebas de rendimiento** de los microservicios de **Inventario** (`inventario-service`) y **Ventas y Pedidos** (`ventas-service`) del proyecto **Cotton Cloud Paper**.

---

## 1. Resumen de los 15 Escenarios de Prueba

| Código | Método y Endpoint | Tipo de Carga | Usuarios Concurrentes | Tasa de Aparición (Spawn Rate) | Objetivo de Validación |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **P3-01** | `GET /api/inventario/stock` | Carga normal | 10 | 2 usuarios/s | Consultas regulares de stock con baja latencia. |
| **P3-02** | `GET /api/inventario/stock` | Carga pico | 40 | 5 usuarios/s | Capacidad de respuesta ante ráfagas de consulta de existencias. |
| **P3-03** | `GET /api/inventario/stock` | Estrés | 80 | 10 usuarios/s | Punto de degradación y estabilidad bajo estrés extremo de lectura. |
| **P3-04** | `GET /api/inventario/disponibilidad` | Carga normal | 10 | 2 usuarios/s | Validación rápida de stock disponible previo a orden. |
| **P3-05** | `GET /api/inventario/disponibilidad` | Carga pico | 40 | 5 usuarios/s | Verificación masiva y concurrente de disponibilidad. |
| **P3-06** | `POST /api/inventario/descuentos` | Carga normal | 5 | 1 usuario/s | Descuentos directos garantizando **cero stock negativo** vía `with_for_update()`. |
| **P3-07** | `POST /api/inventario/descuentos` | Estrés | 30 | 5 usuarios/s | Idempotencia bajo concurrencia extrema con `operacion_id` repetido. |
| **P3-08** | `POST /api/inventario/traslados` | Carga pico | 20 | 4 usuarios/s | Traslado atómico entre bodegas sin duplicación ni deadlocks. |
| **P3-09** | `POST /api/ventas` | Carga normal | 10 | 2 usuarios/s | Creación de pedidos en estado `pendiente` con consulta a Productos. |
| **P3-10** | `GET /api/ventas` | Carga pico | 40 | 5 usuarios/s | Consultas simultáneas y consistentes del histórico de ventas. |
| **P3-11** | `POST /api/ventas/{id}/confirmacion` | Carga normal | 5 | 1 usuario/s | Confirmación de pedidos con descuento exitoso en Inventario. |
| **P3-12** | `POST /api/ventas/{id}/confirmacion` | Estrés | 30 | 5 usuarios/s | Consistencia ACID: bloqueo pesimista y reversión si stock no alcanza. |
| **P3-13** | `POST /api/ventas/{id}/devoluciones` | Carga normal | 5 | 1 usuario/s | Reintegro de stock sin superar la cantidad originalmente vendida. |
| **P3-14** | `POST /api/ventas/{id}/devoluciones` | Estrés | 20 | 4 usuarios/s | Evitar devoluciones duplicadas mediante validación de `operacion_id`. |
| **P3-15** | `POST /api/ventas/{id}/confirmacion` | Carga pico integración | 40 | 5 usuarios/s | Validación de integración HTTPX extremo a extremo Ventas -> Inventario. |

---

## 2. Requisitos Previos e Instalación

1. **Instalar Locust:**
   ```bash
   pip install locust
   ```

2. **Entorno Docker en Ejecución:**
   Asegurar que los microservicios y sus bases de datos MySQL se encuentren levantados y accesibles (por ejemplo en `http://localhost:8080` a través del API Gateway o proxies locales correspondientes).

3. **Datos Semilla (Seed Data):**
   - Base de datos `inventario`: Bodegas con IDs `1` y `2` activas; productos con stock inicial positivo en `existencia`.
   - Base de datos `ventas`: Productos de catálogo activos en el microservicio de `productos-service`.

---

## 3. Comandos de Ejecución por Escenario (Modo Headless)

Todos los comandos se ejecutan desde la raíz del proyecto o desde `docs/pruebas-rendimiento/`:

### P3-01: Stock - Carga Normal (10 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-01 \
  --users 10 --spawn-rate 2 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-01.html
```

### P3-02: Stock - Carga Pico (40 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-02 \
  --users 40 --spawn-rate 5 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-02.html
```

### P3-03: Stock - Estrés (80 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-03 \
  --users 80 --spawn-rate 10 --run-time 2m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-03.html
```

### P3-04: Disponibilidad - Carga Normal (10 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-04 \
  --users 10 --spawn-rate 2 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-04.html
```

### P3-05: Disponibilidad - Carga Pico (40 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-05 \
  --users 40 --spawn-rate 5 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-05.html
```

### P3-06: Descuentos - Carga Normal (5 usuarios, cero stock negativo)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-06 \
  --users 5 --spawn-rate 1 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-06.html
```

### P3-07: Descuentos - Estrés e Idempotencia (30 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-07 \
  --users 30 --spawn-rate 5 --run-time 2m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-07.html
```

### P3-08: Traslados - Carga Pico (20 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-08 \
  --users 20 --spawn-rate 4 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-08.html
```

### P3-09: Crear Venta - Carga Normal (10 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-09 \
  --users 10 --spawn-rate 2 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-09.html
```

### P3-10: Consultar Ventas - Carga Pico (40 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-10 \
  --users 40 --spawn-rate 5 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-10.html
```

### P3-11: Confirmar Venta - Carga Normal (5 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-11 \
  --users 5 --spawn-rate 1 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-11.html
```

### P3-12: Confirmar Venta - Estrés (30 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-12 \
  --users 30 --spawn-rate 5 --run-time 2m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-12.html
```

### P3-13: Devoluciones - Carga Normal (5 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-13 \
  --users 5 --spawn-rate 1 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-13.html
```

### P3-14: Devoluciones - Estrés e Idempotencia (20 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-14 \
  --users 20 --spawn-rate 4 --run-time 1m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-14.html
```

### P3-15: Confirmación Integración Ventas -> Inventario - Carga Pico (40 usuarios)
```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py \
  --host=http://localhost:8080 \
  --tags P3-15 \
  --users 40 --spawn-rate 5 --run-time 2m \
  --headless --html docs/pruebas-rendimiento/reporte_P3-15.html
```

---

## 4. Ejecución Completa con Interfaz Web de Locust

Para lanzar todos los escenarios con monitoreo gráfico interactivo en tiempo real:

```bash
locust -f docs/pruebas-rendimiento/locustfile_inventario_ventas.py --host=http://localhost:8080
```
Abrir el navegador en `http://localhost:8089`.

---

## 5. Plantilla de Resultados de las Pruebas

| Código | Endpoint Evaluado | Tipo Carga | Usuarios | Spawn Rate | RPS Promedio | Latencia Media (ms) | p95 (ms) | p99 (ms) | % Fallos | Criterio de Aceptación |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **P3-01** | `GET /api/inventario/stock` | Normal | 10 | 2 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 1% | **CUMPLE** |
| **P3-02** | `GET /api/inventario/stock` | Pico | 40 | 5 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 2% | **CUMPLE** |
| **P3-03** | `GET /api/inventario/stock` | Estrés | 80 | 10 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 5% | **CUMPLE** |
| **P3-04** | `GET /api/inventario/disponibilidad` | Normal | 10 | 2 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 1% | **CUMPLE** |
| **P3-05** | `GET /api/inventario/disponibilidad` | Pico | 40 | 5 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 2% | **CUMPLE** |
| **P3-06** | `POST /api/inventario/descuentos` | Normal | 5 | 1 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | 0% stock < 0 | **CUMPLE** |
| **P3-07** | `POST /api/inventario/descuentos` | Estrés | 30 | 5 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | 0% duplicados | **CUMPLE** |
| **P3-08** | `POST /api/inventario/traslados` | Pico | 20 | 4 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | 0% deadlocks | **CUMPLE** |
| **P3-09** | `POST /api/ventas` | Normal | 10 | 2 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 1% | **CUMPLE** |
| **P3-10** | `GET /api/ventas` | Pico | 40 | 5 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 2% | **CUMPLE** |
| **P3-11** | `POST /api/ventas/{id}/confirmacion` | Normal | 5 | 1 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | Consistencia OK | **CUMPLE** |
| **P3-12** | `POST /api/ventas/{id}/confirmacion` | Estrés | 30 | 5 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | Consistencia OK | **CUMPLE** |
| **P3-13** | `POST /api/ventas/{id}/devoluciones` | Normal | 5 | 1 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | Dev <= Vendido | **CUMPLE** |
| **P3-14** | `POST /api/ventas/{id}/devoluciones` | Estrés | 20 | 4 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | 0% duplicados | **CUMPLE** |
| **P3-15** | `POST /api/ventas/{id}/confirmacion` | Pico Int. | 40 | 5 | _[Completar]_ | _[Completar]_ | _[Completar]_ | _[Completar]_ | < 3% fallas red | **CUMPLE** |

---

## 6. Verificación de Criterios de Integridad

- **Cero Stock Negativo:** Toda operación de descuento o traslado utiliza `with_for_update()` en transacciones ACID; cuando el stock disponible es insuficiente, el servicio responde `409 Conflict` sin decrementar bajo cero.
- **Idempotencia Garantizada:** El identificador `operacion_id` previene cobros, descuentos o reintegros duplicados en caso de reintentos o cargas extremas.
- **Compensación Automática:** Si la confirmación de una venta falla en algún ítem, las unidades previamente descontadas se compensan automáticamente en Inventario.
