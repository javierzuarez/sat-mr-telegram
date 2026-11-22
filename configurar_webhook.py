"""
Configura o elimina el webhook de Telegram usando solo la librería estándar.

Uso (en la consola Bash de PythonAnywhere):

    export TELEGRAM_TOKEN_FILE="$HOME/.satmr_token"
    export WEBHOOK_URL="https://TU_USUARIO.pythonanywhere.com/telegram-TU_SECRETO"
    export WEBHOOK_SECRET="EL_MISMO_SECRETO_del_WSGI"
    python configurar_webhook.py set

    python configurar_webhook.py info
    python configurar_webhook.py delete

También se puede pasar la URL como argumento:
    python configurar_webhook.py set "https://.../telegram-xxx"
"""

import json
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import config
import telegram_api as tg


def _ocultar_url(url):
    """Recorta el segmento secreto de la ruta para no exponerlo en los logs."""
    if not url:
        return "(sin URL)"
    partes = urlsplit(url)
    return urlunsplit((partes.scheme, partes.netloc, "/***", "", ""))


def main():
    accion = (sys.argv[1] if len(sys.argv) > 1 else "set").lower()
    token = config.token()
    if not token:
        print("Falta el token de Telegram.")
        print("Use TELEGRAM_TOKEN, un .env local o TELEGRAM_TOKEN_FILE.")
        return 1

    try:
        if accion in ("info", "estado", "status"):
            info = tg.llamar(token, "getWebhookInfo")
            if info.get("url"):
                info["url"] = _ocultar_url(info["url"])
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0

        if accion in ("delete", "borrar", "off", "stop"):
            tg.llamar(token, "deleteWebhook")
            print("Webhook eliminado. Telegram volverá a usar getUpdates.")
            return 0

        if accion in ("set", "configurar", "on", "start"):
            url = os.environ.get("WEBHOOK_URL", "").strip()
            if len(sys.argv) > 2 and sys.argv[2].strip():
                url = sys.argv[2].strip()
            if not url:
                print("Falta WEBHOOK_URL. Ejemplo:")
                print("  export WEBHOOK_URL=https://TU_USUARIO.pythonanywhere.com/telegram-XXX")
                return 1

            secreto = os.environ.get("WEBHOOK_SECRET", "").strip()
            parametros = {
                "url": url,
                "allowed_updates": json.dumps(["message"]),
                "drop_pending_updates": "true",
            }
            if secreto:
                parametros["secret_token"] = secreto

            tg.llamar(token, "setWebhook", **parametros)
            print("Webhook configurado correctamente.")
            print(f"Dominio registrado: {_ocultar_url(url)}")
            if not secreto:
                print("Aviso: no definió WEBHOOK_SECRET; la ruta secreta es la única protección.")

            info = tg.llamar(token, "getWebhookInfo")
            print(f"Último error informado por Telegram: {info.get('last_error') or 'ninguno'}")
            return 0

        print("Acción no reconocida. Use: set | info | delete")
        return 1

    except tg.TelegramError as exc:
        print(f"Error de Telegram: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
