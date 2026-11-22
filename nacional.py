"""
Búsqueda nacional de estaciones del IDEAM.

Mantiene en caché el índice de las estaciones que reportaron precipitación
en las últimas horas (≈595 estaciones de 33 departamentos) y permite:

  - buscar por municipio (con o sin tildes)
  - buscar por municipio + departamento
  - encontrar la estación más cercana a unas coordenadas (veredas)

La fuente es el conjunto 57sv-p2fu de datos.gov.co.
"""

import difflib
import json
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import ideam

BASE = ideam.BASE
ZONA_HORARIA = timezone(timedelta(hours=-5))
CACHE_TTL = 600  # segundos

_cache = {"datos": None, "hora": 0.0}
_bloqueo = threading.Lock()

STOPWORDS = {"de", "del", "la", "el", "los", "las", "y"}


def normalizar(texto):
    """Quita tildes, puntuación y mayúsculas. 'Bogotá, D.C' -> 'bogota d c'."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-zA-Z0-9ñÑ\s]", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


def tokens(texto):
    return [t for t in normalizar(texto).split() if t not in STOPWORDS]


def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia en línea recta entre dos puntos (fórmula de Haversine)."""
    import math

    radio = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * radio * math.asin(math.sqrt(a))


def estaciones_activas(horas=12, forzar=False):
    """Devuelve el índice de estaciones con precipitación reciente."""
    with _bloqueo:
        if (not forzar and _cache["datos"] is not None
                and time.time() - _cache["hora"] < CACHE_TTL):
            return _cache["datos"]

        desde = (datetime.now(ZONA_HORARIA) - timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M:%S")
        params = {
            "$select": (
                "codigoestacion, max(fechaobservacion) as ultima, nombreestacion, "
                "municipio, departamento, latitud, longitud"
            ),
            "$where": f"descripcionsensor like '%Precipitaci%' AND fechaobservacion > '{desde}'",
            "$group": "codigoestacion, nombreestacion, municipio, departamento, latitud, longitud",
            "$limit": 2000,
        }
        url = BASE + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "SAT-MR-demo/1.0 (UNAD)"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                filas = json.load(resp)
        except Exception as exc:
            raise ideam.IDEAMError(f"No se pudo descargar el índice de estaciones: {exc}") from exc

        estaciones = []
        for fila in filas:
            try:
                lat = float(fila.get("latitud") or 0)
                lon = float(fila.get("longitud") or 0)
            except (TypeError, ValueError):
                continue
            estaciones.append({
                "codigo": str(fila.get("codigoestacion", "")),
                "nombre": fila.get("nombreestacion", ""),
                "municipio": fila.get("municipio", ""),
                "departamento": fila.get("departamento", ""),
                "latitud": lat,
                "longitud": lon,
                "ultima": fila.get("ultima", ""),
                "municipio_norm": normalizar(fila.get("municipio")),
                "departamento_norm": normalizar(fila.get("departamento")),
            })

        _cache["datos"] = estaciones
        _cache["hora"] = time.time()
        return estaciones


def departamentos():
    """Lista de departamentos con cantidad de estaciones."""
    conteo = {}
    for e in estaciones_activas():
        clave = e["departamento"]
        conteo[clave] = conteo.get(clave, 0) + 1
    return sorted(conteo.items(), key=lambda par: (-par[1], par[0]))


def _puntaje(texto, campo_norm):
    """Puntaje de coincidencia entre el texto del usuario y un campo."""
    consulta = normalizar(texto)
    if not consulta or not campo_norm:
        return 0
    if consulta == campo_norm:
        return 100
    if consulta in campo_norm:
        return 80
    ct = set(tokens(texto))
    campot = set(campo_norm.split())
    if not ct:
        return 0
    comun = ct & campot
    if comun == ct:
        return 70
    return int(50 * len(comun) / len(ct))


def buscar(texto, departamento=None, limite=8):
    """Busca grupos municipio/departamento que coincidan con el texto.

    Devuelve una lista de diccionarios con municipio, departamento,
    estaciones y puntaje, ordenada de mejor a peor coincidencia.
    """
    estaciones = estaciones_activas()
    grupos = {}

    for e in estaciones:
        if departamento:
            pd = _puntaje(departamento, e["departamento_norm"])
            if pd < 70:
                continue
        else:
            pd = 0

        pm = _puntaje(texto, e["municipio_norm"])
        if pm == 0 and pd == 0:
            continue
        # si el texto coincide con el departamento, se acepta como resultado
        puntaje = max(pm, pd // 2)

        clave = (e["municipio"], e["departamento"])
        if clave not in grupos:
            grupos[clave] = {
                "municipio": e["municipio"],
                "departamento": e["departamento"],
                "estaciones": [],
                "puntaje": puntaje,
            }
        grupos[clave]["estaciones"].append(e)

    ordenados = sorted(
        grupos.values(),
        key=lambda g: (-g["puntaje"], -len(g["estaciones"]), g["municipio"]),
    )
    return ordenados[:limite]


def _grupo(estaciones, municipio, departamento, puntaje):
    return {
        "municipio": municipio,
        "departamento": departamento,
        "estaciones": [
            e for e in estaciones
            if (e["municipio"], e["departamento"]) == (municipio, departamento)
        ],
        "puntaje": puntaje,
    }


def _parecido(texto, departamento, estaciones):
    """Último recurso: nombres parecidos (grafías alternas o errores)."""
    consulta = normalizar(texto)
    if not consulta:
        return None

    por_norm = {}
    for e in estaciones:
        if departamento and _puntaje(departamento, e["departamento_norm"]) < 50:
            continue
        por_norm.setdefault(e["municipio_norm"], (e["municipio"], e["departamento"]))
    if not por_norm:
        return None

    sugeridos = difflib.get_close_matches(consulta, list(por_norm), n=1, cutoff=0.78)
    if not sugeridos:
        return None
    municipio, dep = por_norm[sugeridos[0]]
    return _grupo(estaciones, municipio, dep, 60)


def resolver(texto, departamento=None):
    """Devuelve el mejor grupo de estaciones para la consulta del usuario.

    La coincidencia se calcula sobre municipio + departamento juntos, de
    modo que "Medellín Antioquia" o "San Pedro Valle" funcionen sin que
    el usuario tenga que separar los campos con un formato especial.
    """
    estaciones = estaciones_activas()
    consulta_tokens = set(tokens(texto))
    if departamento:
        consulta_tokens |= set(tokens(departamento))
    if not consulta_tokens:
        return None

    grupos = {}
    for e in estaciones:
        if departamento and _puntaje(departamento, e["departamento_norm"]) < 50:
            continue

        campo = set(e["municipio_norm"].split()) | set(e["departamento_norm"].split())
        comun = consulta_tokens & campo
        if not comun:
            continue

        cobertura = len(comun) / len(consulta_tokens)
        pm = _puntaje(texto, e["municipio_norm"])
        pd = _puntaje(departamento, e["departamento_norm"]) if departamento else 0
        puntaje = max(int(100 * cobertura), pm, pd)
        if pm == 100:
            puntaje += 20

        clave = (e["municipio"], e["departamento"])
        if clave not in grupos or puntaje > grupos[clave]["puntaje"]:
            grupos[clave] = {
                "municipio": e["municipio"],
                "departamento": e["departamento"],
                "estaciones": [],
                "puntaje": puntaje,
            }

    if not grupos:
        return _parecido(texto, departamento, estaciones)

    mejor = max(
        grupos.values(),
        key=lambda g: (g["puntaje"], len(g["estaciones"])),
    )
    if mejor["puntaje"] < 60:
        return _parecido(texto, departamento, estaciones)

    # Completar con todas las estaciones del grupo ganador
    mejor["estaciones"] = [
        e for e in estaciones
        if (e["municipio"], e["departamento"]) == (mejor["municipio"], mejor["departamento"])
    ]
    return mejor


def cercanos(latitud, longitud, cantidad=5, max_km=250):
    """Estaciones más cercanas a unas coordenadas."""
    lista = []
    for e in estaciones_activas():
        d = distancia_km(latitud, longitud, e["latitud"], e["longitud"])
        if d <= max_km:
            item = dict(e)
            item["distancia_km"] = round(d, 1)
            lista.append(item)
    lista.sort(key=lambda e: e["distancia_km"])
    return lista[:cantidad]
