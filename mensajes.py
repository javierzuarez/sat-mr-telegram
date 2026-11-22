"""
Redacción de los mensajes que recibe la comunidad.

El primer bloque imita el formato del SMS del prototipo, de modo que el
mismo texto pueda enviarse después por cualquier canal (Telegram, radio
o SMS) sin reescribirlo.

Se usa formato HTML de Telegram, por eso todo dato dinámico se escapa.
"""

from datetime import datetime
from html import escape

ICONO = {"BAJO": "🟢", "MEDIO": "🟡", "ALTO": "🔴", "SIN DATOS": "⚪"}

RECOMENDACION = {
    "BAJO": "puede viajar con precaución",
    "MEDIO": "evite viajar de noche y extreme precauciones",
    "ALTO": "no viaje hasta nuevo aviso",
    "SIN DATOS": "consulte con la emisora comunitaria antes de viajar",
}


def condicion(resultado):
    """Describe la condición climática en lenguaje sencillo."""
    if resultado.nivel == "SIN DATOS":
        return "sin información reciente de la estación"
    mm = resultado.mm_3h
    if resultado.nivel == "ALTO":
        return "lluvias fuertes y posible crecida de quebradas"
    if resultado.nivel == "MEDIO":
        return "lluvias moderadas y viento"
    if mm > 0:
        return "lluvias ligeras"
    return "sin lluvia registrada en las últimas horas"


def alerta(nombre_zona, resultado, municipio=""):
    """Mensaje principal de alerta."""
    cuando = datetime.now().strftime("%d/%m/%Y %H:%M")
    lugar = f"{nombre_zona} ({municipio})" if municipio else nombre_zona
    icono = ICONO.get(resultado.nivel, "⚪")

    lineas = [
        f"{icono} <b>ALERTA MOVILIDAD RURAL</b>",
        f"Nivel: <b>{escape(resultado.nivel)}</b>",
        "",
        f"Zona: {escape(lugar)}",
        f"Condición: {escape(condicion(resultado))}",
        f"Recomendación: {escape(RECOMENDACION.get(resultado.nivel, ''))}",
        f"Reporte: {cuando}",
    ]

    if resultado.nivel != "SIN DATOS":
        lineas.append("")
        lineas.append(f"Lluvia: {resultado.mm_1h} mm en 1 h · {resultado.mm_3h} mm en 3 h")

    fuentes = (resultado.datos or {}).get("fuentes")
    if fuentes:
        lineas.append(f"Estaciones IDEAM: {len(fuentes)} en la zona")
        for fuente in fuentes[:4]:
            icono_fuente = ICONO.get(fuente.get("nivel"), "⚪")
            nombre = str(fuente.get("nombre", ""))[:42]
            lineas.append(
                f"   {icono_fuente} {escape(nombre)} · {fuente.get('nivel')} · "
                f"{fuente.get('mm_3h')} mm/3 h"
            )
    else:
        nombre_estacion = (resultado.datos or {}).get("nombre") or ""
        if nombre_estacion:
            lineas.append(f"Estación IDEAM: {escape(nombre_estacion)}")

    if resultado.estado == "simulado":
        lineas.append("<i>Datos de ejemplo (demostración).</i>")
    else:
        lineas.append("<i>Dato del IDEAM sin validar oficialmente.</i>")

    return "\n".join(lineas)


def resumen_zonas(filas):
    """Lista compacta del estado de varias zonas.

    filas: lista de tuplas (numero, nombre_zona, municipio, Resultado)
    """
    if not filas:
        return "No hay zonas configuradas en el piloto."

    partes = ["<b>Estado de tus zonas</b>", ""]
    for numero, nombre, municipio, res in filas:
        icono = ICONO.get(res.nivel, "⚪")
        lugar = f"{nombre} ({municipio})" if municipio else nombre
        partes.append(f"{icono} <b>{numero}. {escape(lugar)}</b>")
        partes.append(f"   Nivel {escape(res.nivel)} · {res.mm_1h} mm/1 h · {res.mm_3h} mm/3 h")
    partes.append("")
    partes.append("Actualizado: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
    return "\n".join(partes)


def resultados_busqueda(grupos, texto):
    """Muestra las coincidencias de /buscar."""
    if not grupos:
        return sin_resultado(texto)

    lineas = [f"<b>Municipios que coinciden con “{escape(texto)}”</b>", ""]
    for g in grupos[:8]:
        lineas.append(
            f"<b>{escape(g['municipio'])}</b> · {escape(g['departamento'])} "
            f"({len(g['estaciones'])} estaciones)"
        )
    lineas.append("")
    lineas.append("Ejemplo: /consultar Medellín Antioquia")
    return "\n".join(lineas)


def lista_departamentos(datos):
    lineas = ["<b>Departamentos con estaciones del IDEAM</b>", ""]
    for nombre, cantidad in datos:
        lineas.append(f"{escape(nombre)} — {cantidad} estaciones")
    lineas.append("")
    lineas.append("Consulta: /consultar <municipio> <departamento>")
    return "\n".join(lineas)


def sin_resultado(texto):
    return (
        f"No encontré una estación para <b>{escape(texto)}</b>.\n\n"
        "Prueba con /buscar <parte del nombre> o revisa los nombres con "
        "/departamentos.\n"
        "También puedes usar /ubicacion <latitud> <longitud>."
    )


def sin_coordenadas():
    return (
        "No hay estaciones con precipitación reciente cerca de esas coordenadas. "
        "Prueba con otra ubicación o usa /consultar <municipio>."
    )


BIENVENIDA = (
    "👋 <b>Sistema de Alertas Tempranas de Movilidad Rural</b>\n"
    "Datos abiertos del IDEAM · cobertura nacional · canal gratuito\n\n"
    "<b>Consulta nacional</b>\n"
    "/consultar &lt;municipio&gt; [departamento] — nivel de riesgo en vivo\n"
    #"También puede escribir solo el municipio, por ejemplo: bogota\n"
    #"/ubicacion &lt;lat&gt; &lt;lon&gt; — estación más cercana (ideal para veredas)\n"
    #"/buscar &lt;texto&gt; — encontrar municipios\n"
    #"/departamentos — ver la cobertura\n\n"
    #"<b>Piloto Cundinamarca</b>\n"
    #"/estado — riesgo actual de las zonas del piloto\n"
    #"/zonas — listar las zonas del piloto\n\n"
    "/demo — ejemplo de los tres niveles\n"
    "/fuente — enlaces de donde salen los datos\n"
    #"/ayuda — mostrar esta ayuda"
)

AYUDA = BIENVENIDA

FUENTES = (
    "<b>De dónde salen los datos</b>\n\n"
    "El IDEAM publica la información en el Portal Nacional de Datos Abiertos.\n"
    "El bot consulta directamente este conjunto (precipitación cada 10 minutos):\n\n"
    "<a href=\"https://www.datos.gov.co/dataset/57sv-p2fu\">"
    "📊 Datos de Estaciones de IDEAM y de Terceros</a>\n"
    "https://www.datos.gov.co/dataset/57sv-p2fu\n\n"
    "<a href=\"https://www.ideam.gov.co/\">🌎 Sitio oficial del IDEAM</a>\n"
    "https://www.ideam.gov.co/\n\n"
    "<i>Datos crudos sin validar oficialmente. No sustituyen los sistemas "
    "oficiales de alerta de emergencia.</i>"
)
