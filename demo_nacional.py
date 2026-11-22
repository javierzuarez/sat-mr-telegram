
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ideam
import mensajes
import nacional
import riesgo


def sin_html(texto):
    return re.sub(r"<[^>]+>", "", texto)


def linea(caracter="-", ancho=78):
    print(caracter * ancho)


def main():
    print()
    linea("=")
    print("  CONSULTA NACIONAL DE RIESGO DE MOVILIDAD RURAL")
    print(f"  Hora local de Colombia: {ideam.ahora_local():%d/%m/%Y %H:%M}")
    linea("=")

    print("\nDescargando el índice nacional de estaciones...")
    estaciones = nacional.estaciones_activas()
    departamentos = nacional.departamentos()
    municipios = {(e["municipio"], e["departamento"]) for e in estaciones}
    print(f"  Estaciones con lluvia reciente: {len(estaciones)}")
    print(f"  Departamentos cubiertos:       {len(departamentos)}")
    print(f"  Municipios con estación:       {len(municipios)}")
    print("\n  Top 10 departamentos:")
    for nombre, cantidad in departamentos[:10]:
        print(f"    {nombre:<28} {cantidad:>3} estaciones")

    print("\n\nPRUEBA 1 — Resolución de nombres")
    linea()
    consultas = [
        "Medellín",
        "Socha Boyacá",
        "San Pedro Valle del Cauca",
        "Bogotá",
        "POPAYAN",
        "villa de leyva",
        "MunicipioQueNoExiste",
    ]
    for consulta in consultas:
        grupo = nacional.resolver(consulta)
        if grupo:
            print(
                f"  {consulta:<28} -> {grupo['municipio']}, "
                f"{grupo['departamento']} ({len(grupo['estaciones'])} est., "
                f"puntaje {grupo['puntaje']})"
            )
        else:
            sugerencias = nacional.buscar(consulta, limite=3)
            nombres = ", ".join(
                f"{g['municipio']}/{g['departamento']}" for g in sugerencias
            )
            print(f"  {consulta:<28} -> sin coincidencia. Sugerencias: {nombres or 'ninguna'}")

    print("\n\nPRUEBA 2 — Búsqueda por texto parcial")
    linea()
    for texto in ("san pedro", "san andres", "puerto"):
        grupos = nacional.buscar(texto, limite=4)
        print(f"  '{texto}':")
        for g in grupos:
            print(f"     {g['municipio']}, {g['departamento']} ({len(g['estaciones'])})")

    print("\n\nPRUEBA 3 — Alerta nacional por municipio (varias estaciones)")
    linea()
    for consulta in ("Medellín", "Socha Boyacá"):
        grupo = nacional.resolver(consulta)
        if not grupo:
            print(f"  No se resolvió {consulta}")
            continue
        codigos = [e["codigo"] for e in grupo["estaciones"]]
        print(f"\n  {grupo['municipio']}, {grupo['departamento']} — {len(codigos)} estaciones")
        try:
            res = riesgo.evaluar_multi(codigos)
        except ideam.IDEAMError as exc:
            print(f"  ERROR: {exc}")
            continue
        print(f"  Nivel: {res.nivel} · {res.detalle}")
        print()
        linea()
        print(sin_html(mensajes.alerta(grupo["municipio"], res, grupo["departamento"])))
        linea()

    print("\n\nPRUEBA 4 — Consulta por coordenadas (vereda / finca)")
    linea()
    for lat, lon in ((4.7110, -74.0721), (6.2518, -75.5636)):
        cercanas = nacional.cercanos(lat, lon, cantidad=3)
        print(f"\n  Coordenadas {lat}, {lon}:")
        if not cercanas:
            print("     Sin estaciones a menos de 250 km.")
            continue
        for est in cercanas:
            print(
                f"     {est['distancia_km']:>6} km · {est['nombre'][:36]:<36} "
                f"· {est['municipio']}, {est['departamento']}"
            )
        mejor = cercanas[0]
        res = riesgo.evaluar(mejor["codigo"])
        texto = mensajes.alerta(
            f"Ubicación {lat:.4f}, {lon:.4f}",
            res,
            f"{mejor['municipio']} · {mejor['distancia_km']} km",
        )
        print()
        linea()
        print(sin_html(texto))
        linea()

    print("\nListo. Estos son los mismos textos que envía el bot de Telegram.")
    print("Para activarlo: cree el bot con @BotFather, guarde el token en .env")
    print("y ejecute:  python bot.py\n")


if __name__ == "__main__":
    main()
