"""
Entrada WSGI para recibir los mensajes de Telegram por webhook.

Se usa en PythonAnywhere (plan gratuito) para responder al instante, sin
esperar a que GitHub Actions haga polling. No necesita Flask ni ninguna
librería externa: expone una aplicación WSGI estándar.

Variables de entorno que se configuran en el archivo WSGI de PythonAnywhere:

    TELEGRAM_TOKEN_FILE = /home/usuario/.satmr_token   (recomendado)
    WEBHOOK_PATH        = /telegram-<segmento-secreto>
    WEBHOOK_SECRET      = <secreto-largo-para-el-header>

El token NUNCA se guarda en este repositorio.
"""

import hmac
import json
import os
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import bot
import config

RUTA_ULTIMO = os.path.join(config.BASE_DIR, "webhook_offset.txt")
LIMITE_CUERPO = 1_000_000  # bytes; un update de Telegram es mucho más pequeño

_bloqueo = threading.Lock()


def _responder(start_response, estado, texto):
    """Devuelve una respuesta WSGI de texto plano."""
    cuerpo = texto.encode("utf-8")
    cabeceras = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(cuerpo))),
    ]
    start_response(estado, cabeceras)
    return [cuerpo]


def _leer_ultimo():
    """Último update_id ya atendido."""
    try:
        with open(RUTA_ULTIMO, encoding="utf-8") as archivo:
            return int((archivo.read() or "0").strip() or 0)
    except (OSError, ValueError):
        return 0


def _guardar_ultimo(update_id):
    with _bloqueo:
        with open(RUTA_ULTIMO, "w", encoding="utf-8") as archivo:
            archivo.write(str(update_id))


def _ruta_esperada():
    return os.environ.get("WEBHOOK_PATH", "/telegram").strip() or "/telegram"


def _secreto_esperado():
    return os.environ.get("WEBHOOK_SECRET", "").strip()


def application(environ, start_response):
    """Punto de entrada WSGI que Telegram llama en cada mensaje."""
    ruta = environ.get("PATH_INFO", "") or "/"
    metodo = environ.get("REQUEST_METHOD", "GET").upper()

    # Health check sencillo para comprobar que el web app está levantado.
    if metodo == "GET" and ruta == "/":
        return _responder(start_response, "200 OK", "SAT-MR webhook activo")

    if ruta != _ruta_esperada():
        return _responder(start_response, "404 Not Found", "Ruta no encontrada")

    secreto = _secreto_esperado()
    if secreto:
        recibido = environ.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
        if not hmac.compare_digest(recibido, secreto):
            return _responder(start_response, "403 Forbidden", "Secreto invalido")

    if metodo != "POST":
        return _responder(start_response, "405 Method Not Allowed", "Solo POST")

    try:
        longitud = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        longitud = 0
    if longitud <= 0 or longitud > LIMITE_CUERPO:
        return _responder(start_response, "400 Bad Request", "Cuerpo invalido")

    try:
        update = json.loads(environ["wsgi.input"].read(longitud))
    except (ValueError, KeyError):
        return _responder(start_response, "400 Bad Request", "JSON invalido")

    try:
        update_id = int(update.get("update_id", 0))
    except (AttributeError, TypeError, ValueError):
        return _responder(start_response, "400 Bad Request", "Update invalido")
    if update_id <= 0:
        return _responder(start_response, "400 Bad Request", "Update invalido")

    # Telegram reenvía un update si tarda en responder. No queremos dos respuestas.
    if update_id <= _leer_ultimo():
        print(f"[webhook] update {update_id} duplicado, se ignora")
        return _responder(start_response, "200 OK", "duplicado")

    token = config.token()
    if not token:
        print("[webhook] falta TELEGRAM_TOKEN")
        return _responder(start_response, "500 Internal Server Error", "sin token")

    try:
        bot.procesar(token, update)
    except Exception as exc:  # devolvemos 500 para que Telegram lo reintente
        print(f"[webhook] error al procesar {update_id}: {exc}")
        return _responder(start_response, "500 Internal Server Error", "error")

    _guardar_ultimo(update_id)
    print(f"[webhook] update {update_id} procesado")
    return _responder(start_response, "200 OK", "ok")
