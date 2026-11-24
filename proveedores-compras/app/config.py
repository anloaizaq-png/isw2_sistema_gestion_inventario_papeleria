from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o del archivo .env).

    Los valores por defecto de las URLs son los nombres de servicio de Docker Compose.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "compras"
    db_user: str = "root"
    db_password: str = "root"

    productos_url: str = "http://productos-service:8080"
    inventario_url: str = "http://inventario-service:8080"
    alertas_url: str = "http://analitica-service:8080"

    port: int = 8080

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )


settings = Settings()