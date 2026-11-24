import os

from dotenv import load_dotenv

load_dotenv()


def _obligatoria(nombre):
    valor = os.getenv(nombre)
    if valor is None or valor.strip() == "":
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. "
            "Revise el archivo .env (use .env.example como guía)."
        )
    return valor.strip()


class Config:
    APP_PORT = int(os.getenv("APP_PORT", "8080"))

    DB_HOST = _obligatoria("DB_HOST")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = _obligatoria("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = _obligatoria("DB_NAME")

    INVENTARIO_URL = _obligatoria("INVENTARIO_URL").rstrip("/")
    VENTAS_URL = _obligatoria("VENTAS_URL").rstrip("/")