"""
Cliente mínimo de la API de Telegram usando solo la librería estándar.

No requiere python-telegram-bot ni requests. Implementa:
  - llamadas a cualquier método de la API
  - envío de mensajes con formato HTML
  - espera automática cuando Telegram responde 429 (límite de velocidad)
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{metodo}"


class TelegramError(Exception):
    """Error devuelto por la API de Telegram."""


def llamar(token, metodo, timeout=30, **parametros):
    """Invoca un método de la Bot API y devuelve el campo 'result'."""
    url = API.format(token=token, metodo=metodo)
    limpios = {k: v for k, v in parametros.items() if v is not None}
    datos = urllib.parse.urlencode(limpios).encode("utf-8")
    peticion = urllib.request.Request(url, data=datos)

    for intento in (1, 2):
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as resp:
                cuerpo = json.load(resp)
            if not cuerpo.get("ok"):
                raise TelegramError(cuerpo.get("description", "Error desconocido"))
            return cuerpo.get("result")
        except urllib.error.HTTPError as exc:
            detalle = exc.read().decode("utf-8", "replace")
            try:
                info = json.loads(detalle)
            except json.JSONDecodeError:
                info = {}
            if info.get("error_code") == 429 and intento == 1:
                espera = info.get("parameters", {}).get("retry_after", 3)
                print(f"[telegram] límite alcanzado, esperando {espera} s...")
                time.sleep(espera)
                continue
            raise TelegramError(f"{exc.code}: {info.get('description', detalle)}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            # Un timeout de socket no es URLError: sin esto el bucle muere.
            detalle = getattr(exc, "reason", exc)
            raise TelegramError(f"No hay conexión con Telegram: {detalle}") from exc


def enviar(token, chat_id, texto, silencioso=False):
    """Envía un mensaje de texto con formato HTML."""
    return llamar(
        token,
        "sendMessage",
        chat_id=chat_id,
        text=texto,
        parse_mode="HTML",
        disable_web_page_preview="true",
        disable_notification="true" if silencioso else "false",
    )


def actualizaciones(token, offset=None, timeout=30):
    """Long polling: espera hasta 'timeout' segundos por novedades."""
    return llamar(
        token,
        "getUpdates",
        offset=offset,
        timeout=timeout,
        allowed_updates=json.dumps(["message"]),
    )
