"""
Bot de Telegram del Sistema de Alertas Tempranas de Movilidad Rural.
Comandos nacionales: /consultar, /ubicacion, /buscar, /departamentos
Comandos del piloto: /estado, /zonas, /alertas
"""
import json
import os
import sys
import threading
import time
from html import escape

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
import ideam
import mensajes
import nacional
import riesgo
import telegram_api as tg

RUTA_USUARIOS = os.path.join(config.BASE_DIR, "usuarios.json")
RUTA_ESTADO = os.path.join(config.BASE_DIR, "estado_zonas.json")
INTERVALO_AUTO = 600  # segundos entre revisiones automáticas

_candado = threading.Lock()


def _leer_json(ruta, defecto):
    if not os.path.exists(ruta):
        return defecto
    try:
        with open(ruta, encoding="utf-8") as archivo:
            return json.load(archivo)
    except (json.JSONDecodeError, OSError):
        return defecto


def _escribir_json(ruta, datos):
    with _candado:
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)


def usuarios():
    return _leer_json(RUTA_USUARIOS, [])


def registrar_usuario(chat_id):
    lista = usuarios()
    if chat_id not in lista:
        lista.append(chat_id)
        _escribir_json(RUTA_USUARIOS, lista)


# ----------------------------------------------------------------------
# "Apoyo para las consultas nacionales"
# ----------------------------------------------------------------------
def _argumentos(texto):
    """Devuelve lo que el usuario escribió después del comando."""
    partes = texto.strip().split()
    return " ".join(partes[1:]).strip()


def responder_grupo(token, chat_id, grupo):
    """Evalúa todas las estaciones de un municipio y envía la alerta."""
    codigos = [e["codigo"] for e in grupo["estaciones"] if e.get("codigo")]
    if not codigos:
        tg.enviar(token, chat_id, "El municipio no tiene estaciones con datos recientes.")
        return

    lugar = f"{grupo['municipio']}, {grupo['departamento']}"
    tg.enviar(
        token, chat_id,
        f"Consultando {len(codigos)} estación(es) en {escape(lugar)}, un momento...",
    )
    try:
        res = riesgo.evaluar_multi(codigos)
    except ideam.IDEAMError as exc:
        tg.enviar(token, chat_id, f"No se pudo consultar {escape(lugar)}: {exc}")
        return

    texto = mensajes.alerta(grupo["municipio"], res, grupo["departamento"])
    if res.estado == "parcial":
        texto += "\n\n<i>Advertencia: la serie de lluvia está incompleta.</i>"
    tg.enviar(token, chat_id, texto)


# ----------------------------------------------------------------------
# Comandos nacionales
# ----------------------------------------------------------------------
def cmd_consultar(token, chat_id, texto):
    registrar_usuario(chat_id)
    consulta = _argumentos(texto)
    if not consulta:
        tg.enviar(
            token, chat_id,
            "Uso: /consultar <municipio> [departamento]\n"
            "Ejemplos:\n"
            "/consultar Medellín\n"
            "/consultar Socha Boyacá\n"
            "/consultar San Pedro Valle del Cauca",
        )
        return

    tg.enviar(token, chat_id, f"Buscando estaciones para <b>{escape(consulta)}</b>...")
    try:
        grupo = nacional.resolver(consulta)
    except ideam.IDEAMError as exc:
        tg.enviar(token, chat_id, str(exc))
        return

    if grupo:
        responder_grupo(token, chat_id, grupo)
        return

    # Sin coincidencia directa: se ofrecen alternativas.
    try:
        grupos = nacional.buscar(consulta, limite=8)
    except ideam.IDEAMError as exc:
        tg.enviar(token, chat_id, str(exc))
        return
    tg.enviar(token, chat_id, mensajes.resultados_busqueda(grupos, consulta))


def cmd_ubicacion(token, chat_id, texto):
    registrar_usuario(chat_id)
    partes = texto.strip().split()[1:]
    if len(partes) < 2:
        tg.enviar(
            token, chat_id,
            "Uso: /ubicacion <latitud> <longitud>\n"
            "Ejemplo: /ubicacion 4.7110 -74.0721\n\n"
            "Sirve para consultar por vereda o finca. Se usa la estación "
            "más cercana dentro de 250 km.",
        )
        return

    try:
        lat = float(partes[0].replace(",", "."))
        lon = float(partes[1].replace(",", "."))
    except ValueError:
        tg.enviar(token, chat_id, "Coordenadas no válidas. Ejemplo: /ubicacion 4.7110 -74.0721")
        return
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        tg.enviar(token, chat_id, "Latitud o longitud fuera de rango.")
        return

    try:
        cercanas = nacional.cercanos(lat, lon, cantidad=5)
    except ideam.IDEAMError as exc:
        tg.enviar(token, chat_id, str(exc))
        return

    if not cercanas:
        tg.enviar(token, chat_id, mensajes.sin_coordenadas())
        return

    mejor = cercanas[0]
    tg.enviar(
        token, chat_id,
        f"Ubicación <b>{lat:.4f}, {lon:.4f}</b>. Estación más cercana: "
        f"{escape(mejor['nombre'])} a {mejor['distancia_km']} km.",
    )

    try:
        res = riesgo.evaluar(mejor["codigo"])
    except ideam.IDEAMError as exc:
        tg.enviar(token, chat_id, f"No se pudo consultar la estación: {exc}")
        return

    zona = f"Ubicación {lat:.4f}, {lon:.4f}"
    referencia = f"{mejor['municipio']} · {mejor['distancia_km']} km"
    tg.enviar(token, chat_id, mensajes.alerta(zona, res, referencia))

    if len(cercanas) > 1:
        lineas = ["<b>Otras estaciones cercanas</b>", ""]
        for i, est in enumerate(cercanas[1:], start=1):
            lineas.append(
                f"{i}. {escape(str(est['nombre'])[:38])} — "
                f"{escape(est['municipio'])}, {escape(est['departamento'])} · "
                f"{est['distancia_km']} km"
            )
        tg.enviar(token, chat_id, "\n".join(lineas))


def cmd_buscar(token, chat_id, texto):
    registrar_usuario(chat_id)
    consulta = _argumentos(texto)
    if not consulta:
        tg.enviar(token, chat_id, "Uso: /buscar <parte del nombre del municipio>")
        return
    try:
        grupos = nacional.buscar(consulta, limite=8)
    except ideam.IDEAMError as exc:
        tg.enviar(token, chat_id, str(exc))
        return
    tg.enviar(token, chat_id, mensajes.resultados_busqueda(grupos, consulta))


def cmd_departamentos(token, chat_id, _texto):
    registrar_usuario(chat_id)
    tg.enviar(token, chat_id, "Consultando la cobertura nacional...")
    try:
        datos = nacional.departamentos()
        total = sum(cantidad for _, cantidad in datos)
    except ideam.IDEAMError as exc:
        tg.enviar(token, chat_id, str(exc))
        return
    texto = mensajes.lista_departamentos(datos)
    texto += f"\n\nTotal: <b>{len(datos)} departamentos · {total} estaciones</b> con lluvia reciente."
    tg.enviar(token, chat_id, texto)


def cmd_fuente(token, chat_id, _texto):
    registrar_usuario(chat_id)
    tg.enviar(token, chat_id, mensajes.FUENTES)


# ----------------------------------------------------------------------
# Comandos del piloto
# ----------------------------------------------------------------------
def cmd_start(token, chat_id, _texto):
    registrar_usuario(chat_id)
    tg.enviar(token, chat_id, mensajes.BIENVENIDA)


def cmd_zonas(token, chat_id, _texto):
    registrar_usuario(chat_id)
    lineas = ["<b>Zonas del piloto (Cundinamarca)</b>", ""]
    for zona in config.zonas()["zonas"]:
        lineas.append(
            f"<b>{zona['id']}. {zona['nombre']}</b>\n"
            f"   {zona['municipio']} · estación {zona['estacion_nombre']}"
        )
    lineas.append("")
    lineas.append("Para cualquier otro municipio use /consultar.")
    tg.enviar(token, chat_id, "\n".join(lineas))


def cmd_estado(token, chat_id, _texto):
    registrar_usuario(chat_id)
    tg.enviar(token, chat_id, "Consultando el IDEAM, un momento...")

    filas = []
    for zona in config.zonas()["zonas"]:
        try:
            res = riesgo.evaluar(zona["estacion"])
        except ideam.IDEAMError as exc:
            tg.enviar(token, chat_id, f"No se pudo consultar la zona {zona['id']}: {exc}")
            continue
        filas.append((zona["id"], zona["nombre"], zona["municipio"], res))

    tg.enviar(token, chat_id, mensajes.resumen_zonas(filas))

    for numero, nombre, municipio, res in filas:
        if res.hay_alerta:
            tg.enviar(token, chat_id, mensajes.alerta(nombre, res, municipio))


def cmd_demo(token, chat_id, _texto):
    registrar_usuario(chat_id)
    tg.enviar(
        token, chat_id,
        "Así se ven los tres niveles de alerta. Los datos son de ejemplo.",
    )
    ejemplo = config.zonas()["zonas"][0]
    for nivel in ("BAJO", "MEDIO", "ALTO"):
        res = riesgo.simulado(nivel)
        tg.enviar(token, chat_id, mensajes.alerta(ejemplo["nombre"], res, ejemplo["municipio"]))
        time.sleep(0.4)


def cmd_alertas(token, chat_id, _texto):
    registrar_usuario(chat_id)
    tg.enviar(token, chat_id, "Revisando todas las zonas del piloto...")
    for zona in config.zonas()["zonas"]:
        try:
            res = riesgo.evaluar(zona["estacion"])
        except ideam.IDEAMError as exc:
            tg.enviar(token, chat_id, f"Zona {zona['id']}: {exc}")
            continue
        tg.enviar(token, chat_id, mensajes.alerta(zona["nombre"], res, zona["municipio"]))
        time.sleep(0.4)


COMANDOS = {
    "/start": cmd_start,
    "/help": cmd_start,
    "/ayuda": cmd_start,
    "/consultar": cmd_consultar,
    "/clima": cmd_consultar,
    "/ubicacion": cmd_ubicacion,
    "/coordenadas": cmd_ubicacion,
    "/buscar": cmd_buscar,
    "/departamentos": cmd_departamentos,
    "/cobertura": cmd_departamentos,
    "/fuente": cmd_fuente,
    "/fuentes": cmd_fuente,
    "/estado": cmd_estado,
    "/zonas": cmd_zonas,
    "/demo": cmd_demo,
    "/alertas": cmd_alertas,
}


# ----------------------------------------------------------------------
# Revisiones automáticas del piloto
# ----------------------------------------------------------------------
def revisar_automatico(token):
    estado_previo = _leer_json(RUTA_ESTADO, {})
    estado_nuevo = dict(estado_previo)
    chats = usuarios()

    for zona in config.zonas()["zonas"]:
        try:
            res = riesgo.evaluar(zona["estacion"])
        except ideam.IDEAMError as exc:
            print(f"[auto] zona {zona['id']}: {exc}")
            continue

        anterior = estado_previo.get(str(zona["id"]))
        estado_nuevo[str(zona["id"])] = res.nivel

        if res.hay_alerta and res.nivel != anterior:
            texto = mensajes.alerta(zona["nombre"], res, zona["municipio"])
            for chat_id in chats:
                try:
                    tg.enviar(token, chat_id, texto)
                    print(f"[auto] alerta enviada a {chat_id} (zona {zona['id']})")
                except tg.TelegramError as exc:
                    print(f"[auto] error con {chat_id}: {exc}")

    _escribir_json(RUTA_ESTADO, estado_nuevo)


def hilo_automatico(token):
    while True:
        time.sleep(INTERVALO_AUTO)
        try:
            revisar_automatico(token)
        except Exception as exc:  # el hilo nunca debe morir
            print(f"[auto] error inesperado: {exc}")


# ----------------------------------------------------------------------
# Bucle principal
# ----------------------------------------------------------------------
def procesar(token, update):
    mensaje = update.get("message")
    if not mensaje:
        return

    chat_id = mensaje["chat"]["id"]
    registrar_usuario(chat_id)
    texto = (mensaje.get("text") or "").strip()
    comando = texto.split()[0].split("@")[0].lower() if texto.startswith("/") else None

    if comando in COMANDOS:
        COMANDOS[comando](token, chat_id, texto)
    elif comando:
        tg.enviar(token, chat_id, "Comando no reconocido. Usa /ayuda.")
    else:
        # Texto libre: se interpreta como el nombre de un municipio.
        # Así escribir "bogota" funciona igual que "/consultar bogota".
        cmd_consultar(token, chat_id, "/consultar " + texto)


def main():
    token = config.token()
    if not token:
        print("Falta el token de Telegram.")
        print("Crea un archivo .env con esta línea:")
        print("  TELEGRAM_TOKEN=123456789:AAA...")
        print("Obtén el token hablando con @BotFather en Telegram.")
        return 1

    try:
        yo = tg.llamar(token, "getMe")
        print(f"Conectado como @{yo['username']} ({yo['first_name']})")
    except tg.TelegramError as exc:
        print(f"No se pudo conectar con Telegram: {exc}")
        return 1

    if os.environ.get("AUTO_ALERTAS") == "1":
        threading.Thread(target=hilo_automatico, args=(token,), daemon=True).start()
        print("Revisión automática del piloto activa (cada 10 minutos).")

    print("Bot escuchando. Presiona Ctrl+C para detener.")
    offset = None
    while True:
        try:
            updates = tg.actualizaciones(token, offset=offset, timeout=30)
        except tg.TelegramError as exc:
            print(f"[polling] {exc}")
            time.sleep(3)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            try:
                procesar(token, update)
            except Exception as exc:  # un error no debe tumbar el bot
                print(f"[error] {exc}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nBot detenido.")
