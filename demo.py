import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
import ideam
import mensajes
import riesgo


def sin_html(texto):
    return re.sub(r"<[^>]+>", "", texto)


def linea(caracter="-", ancho=78):
    print(caracter * ancho)


def main():
    cfg = config.zonas()
    print()
    linea("=")
    print("  SISTEMA DE ALERTAS TEMPRANAS DE MOVILIDAD RURAL")
    print(f"  Departamento del piloto: {cfg.get('departamento', '')}")
    print(f"  Hora local de Colombia: {ideam.ahora_local():%d/%m/%Y %H:%M}")
    linea("=")

    resultados = []
    for zona in cfg["zonas"]:
        print()
        print(f"Zona {zona['id']}: {zona['nombre']} ({zona['municipio']})")
        print(f"Estación IDEAM {zona['estacion']} · {zona['estacion_nombre']}")

        inicio = time.time()
        try:
            res = riesgo.evaluar(zona["estacion"])
        except ideam.IDEAMError as exc:
            print(f"  ERROR: {exc}")
            continue
        demora = time.time() - inicio

        if res.datos.get("ultima"):
            print(f"  Última lectura: {res.datos['ultima']:%d/%m/%Y %H:%M}")
        print(f"  {res.detalle}")
        print(f"  Consulta en {demora:.1f} s")
        print()
        linea()
        print(sin_html(mensajes.alerta(zona["nombre"], res, zona["municipio"])))
        linea()
        resultados.append((zona, res))

    print()
    print("RESUMEN")
    linea("=")
    print(f"{'Zona':<32}{'Nivel':<12}{'1 h (mm)':>10}{'3 h (mm)':>10}{'Estado':>14}")
    linea()
    for zona, res in resultados:
        print(f"{zona['nombre'][:31]:<32}{res.nivel:<12}{res.mm_1h:>10.1f}{res.mm_3h:>10.1f}{res.estado:>14}")
    linea("=")
    print()
    print("Este texto es el mismo que enviaría el bot de Telegram.")
    print("Para activarlo: cree el bot con @BotFather, guarde el token en .env")
    print("y ejecute:  python bot.py")


if __name__ == "__main__":
    main()
