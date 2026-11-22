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
    """Devuelve el token desde entorno, .env o un archivo fuera del repo."""
    cargar_env()
    valor = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if valor:
        return valor

    # En PythonAnywhere es más cómodo guardar el token en un archivo fuera del
    # repositorio, por ejemplo /home/usuario/.satmr_token, y apuntar aquí.
    ruta = os.environ.get("TELEGRAM_TOKEN_FILE", "").strip()
    if ruta:
        try:
            with open(os.path.expanduser(ruta), encoding="utf-8") as archivo:
                return archivo.read().strip()
        except OSError as exc:
            print(f"[config] no se pudo leer TELEGRAM_TOKEN_FILE: {exc}")
    return ""


def zonas():
    with open(os.path.join(BASE_DIR, "zonas.json"), encoding="utf-8") as archivo:
        config = json.load(archivo)
    return config


def zona_por_numero(numero):
    for zona in zonas()["zonas"]:
        if int(zona["id"]) == int(numero):
            return zona
    return None
