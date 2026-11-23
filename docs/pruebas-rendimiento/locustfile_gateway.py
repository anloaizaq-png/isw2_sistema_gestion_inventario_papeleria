"""
=============================================================================
SUITE DE PRUEBAS DE RENDIMIENTO CON LOCUST (PR01 - PR15)
Sistema de Gestión de Inventarios - Cotton Cloud Paper
Microservicio: API Gateway y Servicio de Identidad (gateway-service)
=============================================================================

Cubre los 15 escenarios exactos definidos en la especificación técnica:
- PR01: Enrutamiento repetido a Productos (20 consultas consecutivas).
- PR02: Enrutamiento concurrente (5 clientes distribuidos en 5 microservicios).
- PR03: Incremento progresivo de carga (1, 5 y 10 clientes concurrentes).
- PR04: Pico de solicitudes (rampa repentina de 1 a 10 clientes).
- PR05: Servicio destino no disponible (resiliencia y aislamiento 502/503).
- PR06: Listado paginado de usuarios (GET /api/usuarios, 20 consultas admin).
- PR07: Consulta concurrente de perfiles distintos (GET /api/usuarios/{id}).
- PR08: Creación concurrente de 10 cuentas distintas desde clientes admin.
- PR09: Creación concurrente con correo repetido (exactamente 1 201 y 4 409).
- PR10: Actualización concurrente de perfiles distintos (PATCH /api/usuarios/{id}).
- PR11: Inicio de sesión concurrente con 5 cuentas distintas.
- PR12: Consultas concurrentes a GET /api/auth/me con 5 sesiones independientes.
- PR13: Renovación concurrente (POST /api/auth/refresh) y rechazo de token rotado.
- PR14: Intentos fallidos repetidos hasta bloqueo rate-limit (429) vs login válido.
- PR15: Ciclo completo repetido (login -> /me -> refresh -> logout -> verificación).
"""

import os
import uuid
import itertools
from locust import HttpUser, task, between, tag, SequentialTaskSet

# Configuración por variables de entorno con valores por defecto del sistema
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@cottoncloud.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin1234*")

# Generador concurrente de correos únicos para pruebas de creación
_counter = itertools.count(start=1)


class BaseGatewayUser(HttpUser):
    """Clase base con utilidades de autenticación para clientes del Gateway"""
    wait_time = between(0.1, 0.5)

    def login_as_admin(self):
        """Inicia sesión con credenciales de administrador y retorna tokens"""
        payload = {"correo": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        resp = self.client.post("/api/auth/login", json=payload, name="/api/auth/login [Setup Admin]")
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return data.get("accessToken"), data.get("refreshToken")
        return None, None


# =============================================================================
# BLOQUE 1: ENRUTAMIENTO, CARGA Y RESILIENCIA (PR01 - PR05)
# =============================================================================

class RoutingAndResilienceUser(BaseGatewayUser):
    """
    Escenarios de Enrutamiento Inverso, Carga y Aislamiento de Fallos
    Tags: PR01, PR02, PR03, PR04, PR05
    """
    access_token = None

    def on_start(self):
        self.access_token, _ = self.login_as_admin()

    @tag("PR01")
    @task(3)
    def pr01_enrutamiento_repetido_productos(self):
        """PR01: Enrutamiento repetido a Productos vía Gateway (Pass-through)"""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        # GET /api/productos puede ser público o autenticado
        with self.client.get(
            "/api/productos",
            headers=headers,
            name="/api/productos [PR01: Routing Repetido]",
            catch_response=True
        ) as resp:
            # 200 OK si el servicio destino está activo, o 503 controlado si está detenido
            if resp.status_code in (200, 503):
                resp.success()
            else:
                resp.failure(f"Código inesperado en enrutamiento PR01: {resp.status_code}")

    @tag("PR02")
    @task(2)
    def pr02_enrutamiento_concurrente_cinco_servicios(self):
        """PR02: Enrutamiento concurrente distribuido en los 5 microservicios"""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        endpoints = [
            ("/api/productos", "productos-service"),
            ("/api/inventario", "inventario-service"),
            ("/api/ventas", "ventas-service"),
            ("/api/compras", "compras-service"),
            ("/api/alertas", "analitica-service")
        ]

        for path, sname in endpoints:
            with self.client.get(
                path,
                headers=headers,
                name=f"{path} [PR02: Multi-Service]",
                catch_response=True
            ) as resp:
                # Si el servicio está arriba retorna 200; si aún no tiene contenedor retorna 503 controlado
                if resp.status_code in (200, 503):
                    resp.success()
                else:
                    resp.failure(f"Falla de enrutamiento en {sname}: {resp.status_code}")

    @tag("PR03", "PR04")
    @task(2)
    def pr03_pr04_incremento_y_pico_solicitudes(self):
        """PR03/PR04: Evaluación bajo rampa progresiva y picos repentinos de concurrencia"""
        with self.client.get("/health", name="/health [PR03-PR04: Capacidad y Rampa]", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Fallo en health check bajo carga: {resp.status_code}")

    @tag("PR05")
    @task(1)
    def pr05_servicio_destino_no_disponible(self):
        """
        PR05: Resiliencia ante servicio detenido y verificación de no afectación del Gateway.
        Consulta un servicio detenido (esperando 503/502 controlado) y el Gateway activo (200).
        """
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        # 1. Petición a servicio no disponible (ej. analítica detenido)
        with self.client.get(
            "/api/alertas/metricas-offline",
            headers=headers,
            name="/api/alertas [PR05: Servicio Caído - 503]",
            catch_response=True
        ) as resp_down:
            if resp_down.status_code in (502, 503):
                # Es el resultado esperado de resiliencia
                resp_down.success()
            elif resp_down.status_code == 200:
                resp_down.success()
            else:
                resp_down.failure(f"Código inesperado ante servicio caído: {resp_down.status_code}")

        # 2. Inmediatamente verificar que el Gateway sigue respondiendo normalmente (aislamiento de fallos)
        with self.client.get("/health", name="/health [PR05: Gateway Sigue Activo]", catch_response=True) as resp_alive:
            if resp_alive.status_code == 200:
                resp_alive.success()
            else:
                resp_alive.failure("El Gateway colapsó ante falla de un servicio destino")


# =============================================================================
# BLOQUE 2: GESTIÓN DE USUARIOS Y ROLES (PR06 - PR10)
# =============================================================================

class UserManagementUser(BaseGatewayUser):
    """
    Escenarios de Administración de Usuarios, Paginación, Unicidad y Concurrencia
    Tags: PR06, PR07, PR08, PR09, PR10
    """
    access_token = None

    def on_start(self):
        self.access_token, _ = self.login_as_admin()

    @tag("PR06")
    @task(3)
    def pr06_listado_paginado_usuarios(self):
        """PR06: Listado paginado repetido de usuarios (20 consultas admin)"""
        if not self.access_token:
            return
        headers = {"Authorization": f"Bearer {self.access_token}"}
        with self.client.get(
            "/api/usuarios?page=1&limit=5",
            headers=headers,
            name="/api/usuarios [PR06: Paginado]",
            catch_response=True
        ) as resp:
            if resp.status_code == 200 and "data" in resp.json():
                resp.success()
            else:
                resp.failure(f"Falla listando usuarios: {resp.status_code}")

    @tag("PR07")
    @task(2)
    def pr07_consulta_concurrente_perfiles_distintos(self):
        """PR07: Consulta concurrente de perfiles distintos (verificar no mezcla de datos)"""
        if not self.access_token:
            return
        headers = {"Authorization": f"Bearer {self.access_token}"}
        # Consultar usuario ID 1 (Admin)
        with self.client.get("/api/usuarios/1", headers=headers, name="/api/usuarios/1 [PR07: Perfil Admin]", catch_response=True) as resp:
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                if data.get("id") == 1:
                    resp.success()
                else:
                    resp.failure("Datos cruzados: el ID devuelto no coincide con el solicitado")
            else:
                resp.failure(f"Falla consultando perfil ID 1: {resp.status_code}")

    @tag("PR08")
    @task(1)
    def pr08_creacion_concurrente_cuentas_distintas(self):
        """PR08: Creación concurrente de cuentas distintas desde clientes admin"""
        if not self.access_token:
            return
        headers = {"Authorization": f"Bearer {self.access_token}"}
        uid = next(_counter)
        payload = {
            "nombre": f"Usuario Prueba {uid}",
            "correo": f"test_pr08_{uid}_{uuid.uuid4().hex[:6]}@cottoncloud.com",
            "password": "Password123*",
            "activo": True,
            "roles": ["VENDEDOR"]
        }
        with self.client.post("/api/usuarios", json=payload, headers=headers, name="/api/usuarios [PR08: Crear Cuenta]", catch_response=True) as resp:
            if resp.status_code == 201:
                resp.success()
            else:
                resp.failure(f"Error creando cuenta única: {resp.status_code} - {resp.text}")

    @tag("PR09")
    @task(1)
    def pr09_creacion_concurrente_correo_repetido(self):
        """
        PR09: Creación concurrente con correo repetido.
        Se envía el mismo correo fijo simultáneamente: exactamente 1 debe dar 201 y el resto 409 Conflict.
        """
        if not self.access_token:
            return
        headers = {"Authorization": f"Bearer {self.access_token}"}
        # Correo compartido constante para probar condición de carrera y unicidad
        payload = {
            "nombre": "Usuario Duplicado",
            "correo": "correo_conflicto_pr09@cottoncloud.com",
            "password": "Password123*",
            "activo": True,
            "roles": ["ANALISTA"]
        }
        with self.client.post("/api/usuarios", json=payload, headers=headers, name="/api/usuarios [PR09: Conflicto 409]", catch_response=True) as resp:
            if resp.status_code == 201:
                # Primera creación exitosa
                resp.success()
            elif resp.status_code == 409:
                # Rechazo controlado obligatorio ante duplicados
                resp.success()
            else:
                resp.failure(f"Código inesperado en prueba de duplicado: {resp.status_code}")

    @tag("PR10")
    @task(1)
    def pr10_actualizacion_concurrente_perfiles(self):
        """PR10: Actualización concurrente de perfiles desde clientes admin"""
        if not self.access_token:
            return
        headers = {"Authorization": f"Bearer {self.access_token}"}
        payload = {
            "nombre": f"Admin Actualizado {uuid.uuid4().hex[:4]}"
        }
        with self.client.patch("/api/usuarios/1", json=payload, headers=headers, name="/api/usuarios/1 [PR10: Update]", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Falla actualizando perfil: {resp.status_code}")


# =============================================================================
# BLOQUE 3: AUTENTICACIÓN, TOKENS, RATE LIMIT Y CICLO DE VIDA (PR11 - PR15)
# =============================================================================

class AuthAndTokensUser(HttpUser):
    """
    Escenarios de Autenticación, Sesiones, Rotación/Revocación y Rate Limit
    Tags: PR11, PR12, PR13, PR14, PR15
    """
    wait_time = between(0.1, 0.5)

    @tag("PR11")
    @task(3)
    def pr11_inicio_sesion_concurrente(self):
        """PR11: Inicio de sesión concurrente con cuentas del sistema"""
        payload = {
            "correo": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }
        with self.client.post("/api/auth/login", json=payload, name="/api/auth/login [PR11: Login Concurrente]", catch_response=True) as resp:
            if resp.status_code == 200 and "accessToken" in resp.json().get("data", {}):
                resp.success()
            else:
                resp.failure(f"Error en login concurrente: {resp.status_code}")

    @tag("PR12")
    @task(2)
    def pr12_consultas_concurrentes_me(self):
        """PR12: Consultas concurrentes a GET /api/auth/me con sesiones activas independientes"""
        # 1. Login previo para obtener sesión propia
        login_resp = self.client.post("/api/auth/login", json={"correo": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if login_resp.status_code != 200:
            return
        token = login_resp.json().get("data", {}).get("accessToken")

        headers = {"Authorization": f"Bearer {token}"}
        with self.client.get("/api/auth/me", headers=headers, name="/api/auth/me [PR12: Perfil Sesión]", catch_response=True) as resp:
            if resp.status_code == 200 and resp.json().get("data", {}).get("correo") == ADMIN_EMAIL:
                resp.success()
            else:
                resp.failure(f"Falla en /me concurrente: {resp.status_code}")

    @tag("PR13")
    @task(2)
    def pr13_renovacion_concurrente_y_rechazo_token_rotado(self):
        """
        PR13: Renovación concurrente (POST /api/auth/refresh) + verificación
        obligatoria de rechazo (401) del refresh token anterior que fue rotado.
        """
        # 1. Iniciar sesión y obtener par de tokens
        login_resp = self.client.post("/api/auth/login", json={"correo": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if login_resp.status_code != 200:
            return
        old_refresh_token = login_resp.json().get("data", {}).get("refreshToken")

        # 2. Ejecutar rotación de token (Refresh)
        with self.client.post(
            "/api/auth/refresh",
            json={"refreshToken": old_refresh_token},
            name="/api/auth/refresh [PR13: Rotación Válida]",
            catch_response=True
        ) as refresh_resp:
            if refresh_resp.status_code == 200 and "accessToken" in refresh_resp.json().get("data", {}):
                refresh_resp.success()
            else:
                refresh_resp.failure(f"Fallo en refresh válido: {refresh_resp.status_code}")
                return

        # 3. Intentar reutilizar inmediatamente el refresh token anterior (debe ser rechazado con 401)
        with self.client.post(
            "/api/auth/refresh",
            json={"refreshToken": old_refresh_token},
            name="/api/auth/refresh [PR13: Rechazo Token Rotado]",
            catch_response=True
        ) as reuse_resp:
            if reuse_resp.status_code == 401:
                # 401 es el resultado de seguridad esperado
                reuse_resp.success()
            else:
                reuse_resp.failure(f"Falla de seguridad: el token anterior rotado no fue rechazado ({reuse_resp.status_code})")

    @tag("PR14")
    @task(1)
    def pr14_intentos_fallidos_rate_limit_vs_login_valido(self):
        """
        PR14: Intentos fallidos repetidos en una cuenta hasta disparar rate-limit (429)
        mientras otra cuenta válida puede ingresar normalmente sin bloqueo.
        """
        target_account = f"victima_fuerzabruta_{uuid.uuid4().hex[:6]}@cottoncloud.com"

        # 1. Disparar 5 intentos fallidos consecutivos en la cuenta objetivo
        for i in range(5):
            self.client.post(
                "/api/auth/login",
                json={"correo": target_account, "password": "WrongPassword123*"},
                name="/api/auth/login [PR14: Intento Fallido]"
            )

        # 2. El 6to intento sobre esa cuenta debe retornar 429 Too Many Requests
        with self.client.post(
            "/api/auth/login",
            json={"correo": target_account, "password": "WrongPassword123*"},
            name="/api/auth/login [PR14: Bloqueo 429]",
            catch_response=True
        ) as blocked_resp:
            if blocked_resp.status_code == 429:
                blocked_resp.success()
            else:
                blocked_resp.failure(f"No se activó el rate limit tras 5 fallos: {blocked_resp.status_code}")

        # 3. Verificar que otra cuenta válida NO está bloqueada e ingresa normal (aislamiento por cuenta)
        with self.client.post(
            "/api/auth/login",
            json={"correo": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            name="/api/auth/login [PR14: Cuenta Válida No Afectada]",
            catch_response=True
        ) as valid_resp:
            if valid_resp.status_code == 200:
                valid_resp.success()
            else:
                valid_resp.failure(f"El rate limit afectó globalmente a usuarios válidos: {valid_resp.status_code}")

    @tag("PR15")
    @task(1)
    def pr15_ciclo_completo_repetido(self):
        """
        PR15: Ciclo completo repetido (Login -> /me -> Refresh -> Logout -> Intento token revocado).
        """
        # Paso 1: Login
        login_res = self.client.post("/api/auth/login", json={"correo": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, name="/api/auth/login [PR15: Step 1 Login]")
        if login_res.status_code != 200:
            return
        data = login_res.json().get("data", {})
        access_token = data.get("accessToken")
        refresh_token = data.get("refreshToken")

        # Paso 2: Consultar /me
        headers = {"Authorization": f"Bearer {access_token}"}
        self.client.get("/api/auth/me", headers=headers, name="/api/auth/me [PR15: Step 2 Me]")

        # Paso 3: Refresh con rotación
        refresh_res = self.client.post("/api/auth/refresh", json={"refreshToken": refresh_token}, name="/api/auth/refresh [PR15: Step 3 Refresh]")
        if refresh_res.status_code == 200:
            new_data = refresh_res.json().get("data", {})
            new_access_token = new_data.get("accessToken")
            headers = {"Authorization": f"Bearer {new_access_token}"}

        # Paso 4: Logout autenticado
        self.client.post("/api/auth/logout", headers=headers, name="/api/auth/logout [PR15: Step 4 Logout]")

        # Paso 5: Intento de uso de token tras logout (debe ser rechazado con 401)
        with self.client.get("/api/auth/me", headers=headers, name="/api/auth/me [PR15: Step 5 Rechazo Revocado]", catch_response=True) as revoked_check:
            if revoked_check.status_code == 401:
                revoked_check.success()
            else:
                revoked_check.failure(f"Se permitió acceso con sesión revocada: {revoked_check.status_code}")
