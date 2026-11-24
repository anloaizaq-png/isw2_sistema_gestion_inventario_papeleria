# Suite de Pruebas de Rendimiento con Locust (`PR01`–`PR15`)
## Microservicio: API Gateway y Servicio de Identidad (`gateway-service`)
**Proyecto:** Sistema de Gestión de Inventarios - Cotton Cloud Paper

---

## 1. Descripción General

Esta suite implementa en **Locust** (`locustfile_gateway.py`) los **15 escenarios de rendimiento y resiliencia** definidos en la especificación técnica (`docs/GATEWAY_SPEC.md`). Evalúa la latencia, concurrencia, resiliencia del reverse proxy y el comportamiento de seguridad (autenticación JWT, rotación obligatoria de refresh tokens, revocación de sesiones, control de acceso RBAC y rate limiting por cuenta/IP).

---

## 2. Catálogo de los 15 Escenarios de Prueba

| ID | Nombre del Escenario | Endpoint / Operación | Concurrencia | Resultado Esperado |
| :--- | :--- | :--- | :--- | :--- |
| **`PR01`** | Enrutamiento repetido | `GET /api/productos` | 1 usuario (20 iter.) | Reenvío pass-through exitoso (`200 OK` o `503` si el microservicio está detenido). |
| **`PR02`** | Enrutamiento concurrente | `/api/{productos,inventario,ventas,compras,alertas}` | 5 usuarios concurrentes | Reenvío balanceado a los 5 servicios con inyección de cabeceras `X-User-*`. |
| **`PR03`** | Incremento progresivo de carga | `GET /health` y rutas base | 1, 5 y 10 usuarios | Medición de degradación controlada de latencia y estabilidad de memoria. |
| **`PR04`** | Pico de solicitudes | Rampa rápida (spawn-rate 10) | 1 a 10 usuarios simultáneos | Absorción del pico sin bloqueos ni errores 500 no controlados. |
| **`PR05`** | Servicio de destino no disponible | Peticiones a servicio detenido y `/health` | Concurrente | Respuestas `503`/`502` controladas sin colapsar el Gateway ni frenar otros servicios. |
| **`PR06`** | Listado paginado de usuarios | `GET /api/usuarios?page=1&limit=5` | 1 admin (20 iter.) | Paginación rápida validando permiso `usuarios:administrar`. |
| **`PR07`** | Perfiles distintos concurrentes | `GET /api/usuarios/{id}` | 5 admins concurrentes | Sin mezcla de datos (*data leakage*); cada petición retorna su ID correspondiente. |
| **`PR08`** | Creación concurrente de cuentas | `POST /api/usuarios` (cuentas únicas) | 5 admins (10 cuentas) | Códigos `201 Created` e inserción íntegra con hashing bcrypt. |
| **`PR09`** | Creación concurrente correo repetido | `POST /api/usuarios` (mismo correo) | 5 peticiones simultáneas | Exactamente **1 creada (`201`)** y **4 rechazadas con `409 Conflict`**. |
| **`PR10`** | Actualización concurrente de perfiles | `PATCH /api/usuarios/{id}` | 5 admins concurrentes | Actualizaciones atómicas en MySQL sin bloqueos de tabla. |
| **`PR11`** | Inicio de sesión concurrente | `POST /api/auth/login` | 5 usuarios simultáneos | Generación concurrente de JWT y Refresh Tokens sin colisión. |
| **`PR12`** | Consultas concurrentes a `/me` | `GET /api/auth/me` | 5 sesiones independientes | Extracción correcta de claims de sesión (`sid`, roles y permisos). |
| **`PR13`** | Renovación y rechazo token rotado | `POST /api/auth/refresh` | 5 sesiones concurrentes | Emisión de nuevo par y **rechazo obligatorio (`401`)** del token anterior rotado. |
| **`PR14`** | Rate limiting por cuenta vs normal | `POST /api/auth/login` (fallos) | Concurrente | Bloqueo temporal `429` en cuenta atacada mientras la cuenta válida ingresa normal (`200`). |
| **`PR15`** | Ciclo completo repetido | Login -> Me -> Refresh -> Logout -> Reuso | 5 clientes (10 ciclos) | `200` en pasos válidos y **rechazo `401`** inmediato al reusar sesión revocada. |

---

## 3. Formas de Ejecución

El microservicio Gateway debe estar en ejecución previamente (en `http://localhost:8080`).

### Opción A: Ejecución 100% Contenerizada con Docker (Recomendada)
No requiere instalar Python ni dependencias en tu máquina local. Se utiliza la imagen oficial `locustio/locust`.

```bash
# 1. Ejecutar toda la suite en modo headless (consola):
docker run --rm --network=cotton-net \
  -v $(pwd)/docs/pruebas-rendimiento:/mnt/locust \
  locustio/locust \
  -f /mnt/locust/locustfile_gateway.py \
  --host=http://gateway-service:8080 \
  --headless -u 10 -r 2 --run-time 1m

# 2. Levantar la interfaz Web interactiva de Locust (puerto 8089):
docker run --rm -p 8089:8089 --network=cotton-net \
  -v $(pwd)/docs/pruebas-rendimiento:/mnt/locust \
  locustio/locust \
  -f /mnt/locust/locustfile_gateway.py \
  --host=http://gateway-service:8080
```
> Si usas la interfaz web, abre en tu navegador: [http://localhost:8089](http://localhost:8089).

---

### Opción B: Ejecución Local con Python (si tienes Locust instalado)
```bash
cd docs/pruebas-rendimiento

# Modo interactivo con Web UI:
locust -f locustfile_gateway.py --host=http://localhost:8080

# Modo Headless por consola:
locust -f locustfile_gateway.py --host=http://localhost:8080 --headless -u 10 -r 2 --run-time 1m
```

---

## 4. Comandos de Ejecución por Escenario Específico (Tags)

Puedes ejecutar cualquiera de los 15 escenarios de forma aislada mediante la bandera `--tags`:

```bash
# PR01: Enrutamiento repetido a Productos
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 1 -r 1 --run-time 30s --tags PR01

# PR02: Enrutamiento concurrente a los 5 microservicios
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 1 --run-time 45s --tags PR02

# PR03: Incremento progresivo de carga (1, 5, 10 clientes)
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 10 -r 1 --run-time 1m --tags PR03

# PR04: Pico repentino de solicitudes (rampa 10)
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 10 -r 10 --run-time 30s --tags PR04

# PR05: Servicio destino no disponible (resiliencia y 503)
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 1 --run-time 30s --tags PR05

# PR06: Listado paginado repetido de usuarios (20 consultas)
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 1 -r 1 --run-time 30s --tags PR06

# PR07: Consulta concurrente de perfiles distintos
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 2 --run-time 30s --tags PR07

# PR08: Creación concurrente de 10 cuentas distintas
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 2 --run-time 30s --tags PR08

# PR09: Creación concurrente con correo repetido (1 x 201, 4 x 409)
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 5 --run-time 20s --tags PR09

# PR10: Actualización concurrente de perfiles
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 2 --run-time 30s --tags PR10

# PR11: Inicio de sesión concurrente
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 2 --run-time 45s --tags PR11

# PR12: Consultas concurrentes a GET /api/auth/me
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 2 --run-time 45s --tags PR12

# PR13: Renovación concurrente y rechazo de refresh token anterior rotado
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 2 --run-time 45s --tags PR13

# PR14: Intentos fallidos hasta rate limit (429) vs cuenta válida
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 2 -r 1 --run-time 30s --tags PR14

# PR15: Ciclo completo repetido (Login -> /me -> Refresh -> Logout -> Reuso)
locust -f docs/pruebas-rendimiento/locustfile_gateway.py --host=http://localhost:8080 --headless -u 5 -r 2 --run-time 1m --tags PR15
```

---

## 5. Plantilla de Resultados de Pruebas de Rendimiento

Utiliza la siguiente tabla para documentar los resultados observados durante la ejecución de las pruebas:

| ID | Escenario de Prueba | Usuarios (U) | Rampa (R) | Duración | Total Reqs | Fallos (%) | RPS | Media (ms) | P95 (ms) | Resultado Esperado vs Observado | Estado |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| **PR01** | Enrutamiento repetido a Productos | 1 | 1 | 30s | - | 0% | - | - | - | Reenvío directo exitoso sin overhead | [ ] APROBADO |
| **PR02** | Enrutamiento concurrente a 5 servicios | 5 | 1 | 45s | - | 0% | - | - | - | Reenvío balanceado y propagación de identidad | [ ] APROBADO |
| **PR03** | Incremento progresivo de carga (1-10) | 10 | 1 | 60s | - | 0% | - | - | - | Rampa lineal estable sin degradación súbita | [ ] APROBADO |
| **PR04** | Pico repentino de solicitudes | 10 | 10 | 30s | - | 0% | - | - | - | Absorción del pico y estabilización rápida | [ ] APROBADO |
| **PR05** | Destino no disponible (Resiliencia) | 5 | 1 | 30s | - | 0% | - | - | - | Respuestas 503 controladas sin caída del Gateway | [ ] APROBADO |
| **PR06** | Listado paginado de usuarios | 1 | 1 | 30s | - | 0% | - | - | - | Paginado ágil con verificación de roles | [ ] APROBADO |
| **PR07** | Perfiles distintos concurrentes | 5 | 2 | 30s | - | 0% | - | - | - | Respuestas íntegras sin datos cruzados | [ ] APROBADO |
| **PR08** | Creación concurrente de 10 cuentas | 5 | 2 | 30s | - | 0% | - | - | - | Creación exitosa (201) con password hasheada | [ ] APROBADO |
| **PR09** | Creación con correo repetido | 5 | 5 | 20s | - | 0%* | - | - | - | 1 creado (201) y 4 conflictos (409) validados | [ ] APROBADO |
| **PR10** | Actualización concurrente perfiles | 5 | 2 | 30s | - | 0% | - | - | - | Actualización consistente en base de datos | [ ] APROBADO |
| **PR11** | Inicio de sesión concurrente (Login) | 5 | 2 | 45s | - | 0% | - | - | - | Emisión concurrente de JWT y Refresh Tokens | [ ] APROBADO |
| **PR12** | Consultas concurrentes a `/me` | 5 | 2 | 45s | - | 0% | - | - | - | Verificación de firma JWT y lectura de sesión | [ ] APROBADO |
| **PR13** | Renovación y rechazo token rotado | 5 | 2 | 45s | - | 0%* | - | - | - | Nuevo par emitido y token anterior revocado (401) | [ ] APROBADO |
| **PR14** | Rate limit en login vs cuenta válida | 2 | 1 | 30s | - | 0%* | - | - | - | Bloqueo 429 en cuenta atacada, ingreso normal en la otra | [ ] APROBADO |
| **PR15** | Ciclo completo repetido (10 ciclos) | 5 | 2 | 60s | - | 0%* | - | - | - | Flujo completo válido e invalidación tras logout | [ ] APROBADO |

*\*Nota: En Locust, las respuestas `409 Conflict` (PR09), `401 Unauthorized` ante tokens revocados/rotados (PR13, PR15), `429 Too Many Requests` (PR14) y `503/502` ante servicios caídos (PR05) son evaluadas con `catch_response=True` y marcadas como **éxitos esperados** de seguridad y resiliencia.*

---

## 6. Criterios de Aceptación (SLA)

1. **Latencia del Gateway:**
   - Tiempo de respuesta medio (`Avg`) menor a **50 ms** para peticiones internas de autenticación y salud bajo carga nominal.
   - Percentil 95 (`P95`) menor a **150 ms** para consultas concurrentes.
2. **Disponibilidad y Concurrencia:**
   - 0% de errores `500 Internal Server Error` no controlados.
   - 0% de fugas de memoria o caídas del proceso nativo de Node.js durante los picos de carga.
3. **Seguridad y Resiliencia:**
   - Activación precisa del límite de tasa (`429`) tras 5 intentos fallidos en una misma cuenta, sin afectar a otros usuarios.
   - Aislamiento total ante la caída de un microservicio destino (retorno controlado de `503 Service Unavailable`).
