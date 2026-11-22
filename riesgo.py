"""
Motor de clasificación de riesgo de movilidad rural.

Traduce la precipitación observada en un nivel de alerta de tres escalas:
BAJO, MEDIO y ALTO. Los umbrales son parámetros de configuración: en un
piloto real se ajustan con la comunidad y con el criterio de la emisora
o del comité de gestión del riesgo.

El criterio combina dos ventanas de tiempo (1 hora y 3 horas) y toma el
nivel más severo de las dos, para no subestimar una lluvia corta e
intensa.
"""

from dataclasses import dataclass, field
from datetime import timedelta

import ideam

# Umbrales en milímetros acumulados.
UMBRALES = {
    "1h": {"medio": 3.0, "alto": 10.0},
    "3h": {"medio": 8.0, "alto": 25.0},
}

NIVELES = ["BAJO", "MEDIO", "ALTO"]

# Si la última lectura tiene más de este tiempo, el dato no sirve para alertar.
MAX_ANTIGUEDAD_HORAS = 2.0


@dataclass
class Resultado:
    nivel: str                    # BAJO | MEDIO | ALTO | SIN DATOS
    mm_1h: float = 0.0
    mm_3h: float = 0.0
    motivo: str = ""
    estado: str = "ok"            # ok | sin_datos | desactualizado | parcial
    detalle: str = ""
    datos: dict = field(default_factory=dict)

    @property
    def hay_alerta(self):
        return self.nivel in ("MEDIO", "ALTO")


def _clasificar_ventana(mm, umbral):
    if mm >= umbral["alto"]:
        return "ALTO"
    if mm >= umbral["medio"]:
        return "MEDIO"
    return "BAJO"


def evaluar(codigo_estacion, horas=12):
    """Consulta la estación y devuelve el Resultado de riesgo."""
    datos = ideam.precipitacion(codigo_estacion, horas=horas)
    ahora = ideam.ahora_local()
    serie = datos["serie"]

    if not serie:
        return Resultado(
            nivel="SIN DATOS",
            estado="sin_datos",
            motivo="La estación no reporta precipitación en las últimas horas.",
            datos=datos,
        )

    antiguedad = (ahora - datos["ultima"]).total_seconds() / 3600.0
    if antiguedad > MAX_ANTIGUEDAD_HORAS:
        return Resultado(
            nivel="SIN DATOS",
            estado="desactualizado",
            motivo=f"La última lectura tiene {antiguedad:.1f} horas.",
            datos=datos,
        )

    mm_1h = ideam.acumulado(serie, ahora - timedelta(hours=1))
    mm_3h = ideam.acumulado(serie, ahora - timedelta(hours=3))

    nivel_1h = _clasificar_ventana(mm_1h, UMBRALES["1h"])
    nivel_3h = _clasificar_ventana(mm_3h, UMBRALES["3h"])
    nivel = max(nivel_1h, nivel_3h, key=NIVELES.index)

    # Si la serie cubre menos de 3 horas, la ventana de 3 h está incompleta.
    cobertura = (serie[-1][0] - serie[0][0]).total_seconds() / 3600.0
    estado = "parcial" if cobertura < 3 else "ok"

    if nivel == "ALTO":
        motivo = f"Precipitación intensa: {mm_1h} mm en 1 h y {mm_3h} mm en 3 h."
    elif nivel == "MEDIO":
        motivo = f"Precipitación moderada: {mm_1h} mm en 1 h y {mm_3h} mm en 3 h."
    else:
        motivo = f"Lluvia baja o nula: {mm_1h} mm en 1 h y {mm_3h} mm en 3 h."

    return Resultado(
        nivel=nivel,
        mm_1h=mm_1h,
        mm_3h=mm_3h,
        motivo=motivo,
        estado=estado,
        detalle=f"{len(serie)} lecturas válidas, {datos['descartadas']} descartadas por rango imposible.",
        datos=datos,
    )


def evaluar_multi(codigos):
    """Evalúa varias estaciones y devuelve una única alerta agregada.

    Se usa cuando un municipio tiene más de una estación: el nivel del
    municipio es el más severo de todas sus estaciones.
    """
    individuales = []
    for codigo in codigos:
        try:
            individuales.append(evaluar(codigo))
        except ideam.IDEAMError:
            continue

    if not individuales:
        raise ideam.IDEAMError("No se pudo consultar ninguna estación.")

    validos = [r for r in individuales if r.nivel != "SIN DATOS"]
    if not validos:
        resultado = individuales[0]
        resultado.datos["fuentes"] = []
        return resultado

    nivel = max(validos, key=lambda r: NIVELES.index(r.nivel)).nivel
    mm_1h = max(r.mm_1h for r in validos)
    mm_3h = max(r.mm_3h for r in validos)

    return Resultado(
        nivel=nivel,
        mm_1h=mm_1h,
        mm_3h=mm_3h,
        motivo=f"Nivel más alto entre {len(validos)} estaciones: {nivel}.",
        estado="ok",
        detalle=f"{len(validos)} de {len(individuales)} estaciones con datos válidos.",
        datos={
            "nombre": f"{len(validos)} estaciones",
            "fuentes": [
                {
                    "nombre": (r.datos or {}).get("nombre", ""),
                    "nivel": r.nivel,
                    "mm_1h": r.mm_1h,
                    "mm_3h": r.mm_3h,
                }
                for r in validos
            ],
            "descartadas": sum((r.datos or {}).get("descartadas", 0) for r in validos),
        },
    )


def simulado(nivel, mm_1h=None, mm_3h=None):
    """Construye un Resultado ficticio para demostraciones."""
    base = {"BAJO": (0.4, 1.2), "MEDIO": (5.0, 14.0), "ALTO": (14.0, 32.0)}
    m1, m3 = base[nivel]
    return Resultado(
        nivel=nivel,
        mm_1h=mm_1h if mm_1h is not None else m1,
        mm_3h=mm_3h if mm_3h is not None else m3,
        motivo="Escenario de demostración.",
        estado="simulado",
        detalle="Datos de ejemplo, no provienen de una estación en tiempo real.",
        datos={"nombre": "Estación de ejemplo", "municipio": "", "descartadas": 0},
    )
