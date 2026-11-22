"""Configuración del demo: token de Telegram y zonas del territorio piloto."""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def cargar_env(ruta=None):
    """Lee un archivo .env sencillo (clave=valor) sin dependencias externas."""
    ruta = ruta or os.path.join(BASE_DIR, ".env")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def token():
    cargar_env()
    return os.environ.get("TELEGRAM_TOKEN", "").strip()


def zonas():
    with open(os.path.join(BASE_DIR, "zonas.json"), encoding="utf-8") as archivo:
        config = json.load(archivo)
    return config


def zona_por_numero(numero):
    for zona in zonas()["zonas"]:
        if int(zona["id"]) == int(numero):
            return zona
    return None
