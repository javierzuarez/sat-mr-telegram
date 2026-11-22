"""
Cliente de datos abiertos del IDEAM (datos.gov.co).

Fuente: conjunto 57sv-p2fu — "Datos de Estaciones de IDEAM y de Terceros".
No requiere API key ni librerías externas.

Dos advertencias descubiertas al probar la API en vivo:

1. Las fechas (fechaobservacion) vienen en HORA LOCAL DE COLOMBIA (UTC-5)
   y sin sufijo de zona horaria. Si se comparan contra UTC, la consulta
   devuelve cero registros.
2. Los valores son crudos y sin validar. Se han observado lecturas
   imposibles (decenas de miles de mm en una hora), así que hay que
   descartar valores fuera de rango antes de usarlos.
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# Página del dataset: https://www.datos.gov.co/dataset/57sv-p2fu
# Sitio oficial:      https://www.ideam.gov.co/
BASE = "https://www.datos.gov.co/resource/57sv-p2fu.json"
ZONA_HORARIA = timezone(timedelta(hours=-5))  # hora local de Colombia
MAX_PLAUSIBLE_10MIN = 30.0                    # mm; por encima se asume error de sensor
USER_AGENT = "SAT-MR-demo/1.0 (UNAD - Proyecto de Ingenieria II)"


class IDEAMError(Exception):
    """Error al consultar la fuente de datos."""


def ahora_local():
    """Hora actual de Colombia, sin zona horaria (naive)."""
    return datetime.now(timezone.utc).astimezone(ZONA_HORARIA).replace(tzinfo=None)


def _consultar(params, timeout=60):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except Exception as exc:  # red, HTTP, JSON
        raise IDEAMError(f"No se pudo consultar datos.gov.co: {exc}") from exc


def precipitacion(codigo_estacion, horas=12):
    """Descarga la precipitación de una estación y la devuelve limpia.

    Devuelve un diccionario con:
        estacion, nombre, municipio, departamento,
        serie      -> lista de (datetime_local, mm) de más antigua a más reciente
        descartadas-> cantidad de lecturas descartadas por rango imposible
        ultima     -> datetime de la lectura más reciente (o None)
    """
    codigo = "".join(c for c in str(codigo_estacion) if c.isdigit())
    if not codigo:
        raise IDEAMError("Código de estación inválido.")

    desde = (ahora_local() - timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M:%S")
    where = (
        f"codigoestacion='{codigo}' "
        f"AND descripcionsensor like '%Precipitaci%' "
        f"AND fechaobservacion > '{desde}'"
    )
    filas = _consultar({"$where": where, "$limit": 2000, "$order": "fechaobservacion DESC"})

    serie = []
    descartadas = 0
    datos = {
        "estacion": codigo,
        "nombre": "",
        "municipio": "",
        "departamento": "",
        "serie": serie,
        "descartadas": 0,
        "ultima": None,
    }

    for fila in filas:
        datos["nombre"] = fila.get("nombreestacion", datos["nombre"])
        datos["municipio"] = fila.get("municipio", datos["municipio"])
        datos["departamento"] = fila.get("departamento", datos["departamento"])

        try:
            valor = float(fila.get("valorobservado", ""))
        except (TypeError, ValueError):
            descartadas += 1
            continue

        if valor < 0 or valor > MAX_PLAUSIBLE_10MIN:
            descartadas += 1
            continue

        try:
            fecha = datetime.fromisoformat(fila["fechaobservacion"])
        except (KeyError, ValueError):
            descartadas += 1
            continue

        serie.append((fecha, valor))

    serie.sort(key=lambda par: par[0])
    datos["descartadas"] = descartadas
    datos["ultima"] = serie[-1][0] if serie else None
    return datos


def acumulado(serie, desde):
    """Suma la precipitación registrada desde una fecha dada."""
    return round(sum(mm for fecha, mm in serie if fecha >= desde), 1)
