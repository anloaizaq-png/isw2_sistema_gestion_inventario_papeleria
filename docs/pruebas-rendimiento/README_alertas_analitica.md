# Pruebas de rendimiento: Alertas y Analítica (`A01` a `A15`)

Los 15 escenarios corresponden a la Tabla 23 del documento de la Entrega 2, ejecutados con Locust.
Script: `locustfile_alertas_analitica.py`. Cada escenario se ejecuta con `--tags`.

## 1. Escenarios

| Código | Endpoint | Tipo | Usuarios | Spawn rate | Duración | Qué se verifica |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| A01 | `GET /api/alertas/` | Carga normal | 50 | 5 | 1 min | 200; cada alerta cumple el filtro pedido |
| A02 | `GET /api/alertas/` | Pico | 200 | 20 | 1 min | Sin errores 5xx; filtros correctos |
| A03 | `GET /api/alertas/{id}` | Carga normal | 50 | 5 | 1 min | 200 con la alerta pedida, 404 si no existe |
| A04 | `PATCH /api/alertas/{id}/estado` | Carga normal | 30 | 5 | 1 min | Estado y usuario guardados y consistentes |
| A05 | `POST /api/alertas/evaluar` | Carga normal | 10 | 2 | 1 min | Respuesta correcta y sin alertas abiertas duplicadas |
| A06 | `POST /api/alertas/evaluar` | Estrés con Inventario detenido | 50 | 10 | 1 min | 503 controlado; el servicio no se cae y se recupera |
| A07 | `GET /api/alertas/umbrales` | Carga normal | 50 | 5 | 1 min | Lista completa y válida |
| A08 | `POST /api/alertas/umbrales` | Escritura concurrente | 30 | 5 | 1 min | 201 válidos, 400 inválidos, sin ids repetidos |
| A09 | `GET /api/alertas/analitica/rotacion` | Carga normal | 30 | 5 | 1 min | Niveles válidos y consistentes |
| A10 | `GET /api/alertas/analitica/rotacion` | Estrés | 30→60→100→150 | 10 | 1 min por nivel | Punto de degradación; sigue operativo |
| A11 | `GET /api/alertas/analitica/clasificacion-abc` | Carga normal | 30 | 5 | 1 min | Clasificación igual para todos los usuarios |
| A12 | `GET /api/alertas/analitica/proximos-agotarse` | Pico | 100 | 10 | 1 min | Productos dentro del margen del 25 % |
| A13 | `GET /api/alertas/analitica/demanda-temporada` | Carga normal | 30 | 5 | 1 min | Orden por demanda; 404 si la temporada no existe |
| A14 | `GET /api/alertas/sugerencias-reabastecimiento` | Concurrencia (consumo de Compras) | 50 | 5 | 1 min | Solo sugerencias pendientes y válidas |
| A15 | Mezcla de lecturas y escrituras | Carga sostenida | 50 | 5 | 3 min | Sin errores acumulados ni datos inconsistentes |

## 2. Requisitos

1. Servicios corriendo: Alertas y Analítica, Inventario y Ventas y Pedidos, cada uno con su base MySQL.
   A06 exige detener Inventario durante la prueba.
2. Locust: `pip install locust` (en un entorno virtual; no forma parte del `requirements.txt` del servicio).
3. Apuntar al destino (directo, o el API Gateway cuando esté disponible):
   ```bash
   export ALERTAS_HOST=http://localhost:8081
   ```
   Opcional: `PRODUCTOS_PERF` con los ids de producto que tienen stock en Inventario (por defecto `10,11,12,13,14`).

Al iniciar, el script crea (si no existen) umbrales para esos productos y una temporada "PERF Temporada",
y ejecuta una evaluación para tener alertas. Los umbrales de A08 se crean inactivos para no afectar a otras pruebas.

## 3. Ejecución (desde la raíz del repositorio)

```bash
correr() {   # uso: correr ETIQUETA USUARIOS SPAWN DURACION
  locust -f docs/pruebas-rendimiento/locustfile_alertas_analitica.py --headless --only-summary \
    --tags "$1" --users "$2" --spawn-rate "$3" --run-time "$4" \
    --html "docs/pruebas-rendimiento/resultados/reporte_$1_$2u.html" AlertasUser
}

correr A01 50 5 1m
correr A02 200 20 1m
correr A03 50 5 1m
correr A04 30 5 1m
correr A05 10 2 1m
correr A07 50 5 1m
correr A08 30 5 1m
correr A09 30 5 1m
for u in 30 60 100 150; do correr A10 $u 10 1m; done
correr A11 30 5 1m
correr A12 100 10 1m
correr A13 30 5 1m
correr A14 50 5 1m
correr A15 50 5 3m

docker stop inventario-service        # A06: Inventario no disponible
correr A06 50 10 1m
docker start inventario-service       # recuperación
curl -X POST "$ALERTAS_HOST/api/alertas/evaluar"
```

Los reportes HTML de cada ejecución quedan en `resultados/`.

## 4. Resultados preliminares

Ejecución local, 23/11/2026. Todos los servicios en Docker en el mismo equipo y en la misma red:
Alertas y Analítica con gunicorn (2 procesos), Inventario y Ventas y Pedidos tomados de `develop`,
una base MySQL 8 por servicio y Locust en el mismo equipo. Datos de prueba: 5 productos con stock,
4 ventas (3 confirmadas) y 4 alertas.

| Código | Usuarios | RPS | Media (ms) | p95 (ms) | p99 (ms) | % fallos | Criterio | Resultado |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| A01 | 50 | 151.96 | 5 | 7 | 9 | 0 | 200 y filtros correctos | Cumple |
| A02 | 200 | 606.81 | 4 | 8 | 20 | 0 | Sin 5xx | Cumple (tras corrección) |
| A03 | 50 | 152.09 | 4 | 6 | 7 | 0 | 200 / 404 | Cumple (tras corrección del script) |
| A04 | 30 | 185.08 | 5 | 10 | 12 | 0 | Estado y usuario consistentes | Cumple (tras corrección) |
| A05 | 10 | 89.75 | 6 | 14 | 15 | 0 | Sin alertas duplicadas | Cumple |
| A06 | 50 | 19.83 | 2089 | 2400 | 2400 | 0 | 503 controlado y recuperación | Cumple, con hallazgo |
| A07 | 50 | 151.24 | 4 | 6 | 7 | 0 | Lista válida | Cumple |
| A08 | 30 | 93.68 | 5 | 9 | 11 | 0 | 201 / 400, sin duplicados | Cumple |
| A09 | 30 | 89.28 | 21 | 39 | 51 | 0 | Niveles válidos | Cumple |
| A10 | 30 | 91.66 | 20 | 36 | 47 | 0 | Sin errores | Cumple |
| A10 | 60 | 177.40 | 24 | 70 | 110 | 0 | Sin errores | Cumple |
| A10 | 100 | 231.80 | 98 | 170 | 460 | 0 | Sin errores | Cumple (degradación) |
| A10 | 150 | 226.96 | 281 | 450 | 690 | 0 | Sin errores | Cumple (degradación) |
| A11 | 30 | 88.34 | 24 | 44 | 63 | 0 | Igual para todos | Cumple |
| A12 | 100 | 281.49 | 28 | 130 | 150 | 0 | Margen del 25 % | Cumple |
| A13 | 30 | 90.49 | 19 | 36 | 46 | 0 | Orden y 404 | Cumple |
| A14 | 50 | 152.01 | 4 | 6 | 7 | 0 | Solo pendientes | Cumple |
| A15 | 50 (3 min) | 166.78 | 15 | 47 | 66 | 0 | Sin errores acumulados | Cumple |

Recuperación tras A06: al encender de nuevo Inventario, `POST /api/alertas/evaluar` respondió
`{"alertas_generadas":0,"productos_evaluados":5}` sin reiniciar el servicio.

## 5. Hallazgos y correcciones

Una primera ronda de pruebas (misma fecha) encontró cuatro problemas. Se corrigieron y se repitieron
las 15 pruebas; la tabla anterior corresponde a la segunda ronda.

| Prueba | Primera ronda | Causa | Corrección | Segunda ronda |
| :--- | :--- | :--- | :--- | :--- |
| A02 (200 usuarios) | 19,3 % de `503 Base de datos no disponible`; 301 RPS; media 312 ms; p95 570 ms | Se abría y cerraba una conexión MySQL por consulta; el contenedor agotó los puertos locales (`Errno 99 Cannot assign requested address`) | `database.py` reutiliza una conexión por proceso/hilo, con reconexión automática | 0 %; 607 RPS; media 4 ms; p95 8 ms |
| A04 | 29 respuestas (0,55 %) con el estado de otro usuario | Entre el `UPDATE` y la lectura de la respuesta, otra petición cambiaba la misma alerta | `SELECT ... FOR UPDATE`, `UPDATE` y lectura en una sola transacción | 0 % |
| A03 | 80,3 % de 404 | Error del script: la preparación de datos falló y usó un id inexistente | Preparación con reintentos y fallo explícito si no hay datos | 0 % |
| A08 | Sin fallos, pero dejó miles de umbrales activos que inflaron `evaluar` (6 081 umbrales evaluados) | Error del script | Los umbrales de A08 se crean inactivos | Sin efecto en otras pruebas |

Relación con los requerimientos de la Entrega 1: la corrección de A02 atiende RNF06 (rendimiento),
RNF18 (disponibilidad) y RNF05 (escalabilidad); la de A04, RF10 (trazabilidad: cada respuesta refleja
quién hizo el cambio); las del script, RNF11 (pruebas que detectan errores reales). El registro del
servicio (RNF10, observabilidad) permitió identificar la causa exacta del error de A02.

## 6. Análisis

- **Consultas:** todas las operaciones de consulta respondieron muy por debajo de los 2 s del RNF06, con
  0 fallos. El peor p99 fue 690 ms (A10 con 150 usuarios).
- **Estrés (A10):** la rotación consulta Inventario y Ventas en cada petición. El throughput se estabiliza
  en unas 230 peticiones por segundo desde 100 usuarios y la latencia media sube de 20 ms a 281 ms, sin
  errores. El límite corresponde a 2 procesos de gunicorn y a las llamadas a los otros dos servicios.
- **Pico (A02, A12):** después de la corrección, 200 usuarios en el listado de alertas se atienden con
  607 peticiones por segundo y p95 de 8 ms.
- **Concurrencia (A04, A05, A08, A15):** sin pérdida ni corrupción de datos, sin alertas abiertas
  duplicadas y sin ids repetidos; la carga mixta sostenida de 3 minutos no acumuló errores.
- **Fallo de Inventario (A06):** el servicio respondió siempre un 503 controlado con el formato
  `{codigo, mensaje}`, no se cayó y se recuperó solo. La respuesta tarda unos 2,2 s porque cada petición
  espera a que falle la conexión con Inventario y, con 2 procesos, las demás hacen fila.
- **Optimizaciones propuestas para la Entrega 4:**
  - Reducir el tiempo de espera hacia Inventario y Ventas y aplicar un corte rápido cuando un servicio
    no responde (circuit breaker), para que A06 responda en milisegundos.
  - Ejecutar varias réplicas del servicio en Kubernetes y ajustar los procesos de gunicorn (RNF05).
  - Proteger `POST /evaluar` con un bloqueo para que dos evaluaciones simultáneas no puedan crear la
    misma alerta nueva; en A05 no ocurrió, pero la prueba partía con alertas ya abiertas.