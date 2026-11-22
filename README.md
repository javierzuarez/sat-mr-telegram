# Demo del Sistema de Alertas Tempranas de Movilidad Rural (SAT-MR)

Bot de Telegram con **consulta nacional** sobre datos abiertos del IDEAM. Clasifica el riesgo de
movilidad rural en tres niveles y envía la alerta a la comunidad. **Costo: cero pesos.** No usa
SMS, no usa servicios pagos y no necesita instalar librerías externas.

---

## 1. Qué hace

```
IDEAM (datos.gov.co) → índice de ~595 estaciones activas → búsqueda del municipio
                     → limpieza de datos → reglas de riesgo → Telegram
```

1. Consulta el conjunto **`57sv-p2fu`** (Datos de Estaciones de IDEAM y de Terceros).
2. Descarga y guarda en caché (10 min) el índice nacional de estaciones con lluvia reciente.
3. Busca el municipio por nombre, con o sin tildes, con departamento o con coordenadas.
4. Filtra sensores de precipitación y descarta lecturas imposibles.
5. Suma la lluvia en ventanas de **1 hora** y **3 horas**.
6. Clasifica en **BAJO / MEDIO / ALTO** (si hay varias estaciones, toma el nivel más severo).
7. Redacta el mensaje del prototipo (mismo formato del SMS) y lo envía por Telegram.

---

## Fuentes oficiales (enlaces clicables)

- Dataset consultado por el bot: **Datos de Estaciones de IDEAM y de Terceros**
  https://www.datos.gov.co/dataset/57sv-p2fu
- Endpoint JSON que usa el código (`ideam.py`, línea 22):
  https://www.datos.gov.co/resource/57sv-p2fu.json
- Sitio oficial del IDEAM: https://www.ideam.gov.co/
- Catálogo de estaciones (referencia): https://www.datos.gov.co/resource/hp9r-jxuu.json

Dentro del bot, estos enlaces aparecen con el comando **`/fuente`**.

---

## 2. Requisitos

- Python 3.9 o superior (probado con Python 3.14).
- Conexión a internet.
- **No hay que instalar nada**: usa solo `urllib`, `json`, `datetime`, etc. de la librería estándar.

---

## 3. Parte 1 — Ver el demo sin Telegram (funciona ya)

```bash
python demo.py            # zonas del piloto en Cundinamarca
python demo_nacional.py   # cobertura nacional, búsquedas y coordenadas
```

O haga doble clic en `1_demo_sin_token.bat` y `3_demo_nacional.bat`.

Muestra la estación usada, última lectura, lluvia acumulada, nivel de riesgo y el mensaje
completo que el bot enviaría. No necesitan token.

---

## 4. Parte 2 — Activar el bot de Telegram

### Paso 1: crear el bot

1. Abra Telegram y busque **@BotFather**.
2. Envíe `/newbot`.
3. Escriba el nombre (ej.: `Alertas Movilidad Rural UNAD`).
4. Escriba un usuario único terminado en `bot` (ej.: `alertas_movilidad_unad_bot`).
5. BotFather devolverá un token parecido a `7123456789:AAF...`. **Guárdelo, no se muestra de nuevo.**

### Paso 2: guardar el token

Copie `.env.example` como `.env` y reemplace el valor:

```
TELEGRAM_TOKEN=7123456789:AAF...
```

### Paso 3: iniciar

```bash
python bot.py
```

O haga doble clic en `2_iniciar_bot.bat`. Debe aparecer:

```
Conectado como @alertas_movilidad_unad_bot (Alertas Movilidad Rural)
Bot escuchando. Presiona Ctrl+C para detener.
```

### Paso 4: abrir el bot en Telegram

Busque el usuario de su bot y envíe `/start`.

---

## 5. Comandos del bot

### Consulta nacional (para cualquier persona)

| Comando | Qué hace |
|---|---|
| `/consultar <municipio> [departamento]` | Nivel de riesgo en vivo. Ej.: `/consultar Medellín`, `/consultar Socha Boyacá` |
| `/ubicacion <lat> <lon>` | Estación más cercana a una vereda, finca o punto cualquiera (hasta 250 km) |
| `/buscar <texto>` | Lista municipios con ese texto en el nombre |
| `/departamentos` | Muestra la cobertura real de estaciones por departamento |

Alias: `/clima` = `/consultar`, `/coordenadas` = `/ubicacion`, `/cobertura` = `/departamentos`.

Se aceptan nombres sin tildes (`medellin`), en mayúsculas (`POPAYAN`) y con errores de grafía
(`villa de leyva` → `Villa De Leiva`). Si no hay coincidencia, el bot sugiere opciones.

### Piloto de Cundinamarca

| Comando | Qué hace |
|---|---|
| `/estado` | Consulta el IDEAM y muestra el nivel de las 4 zonas del piloto |
| `/zonas` | Lista las zonas del piloto y sus estaciones |
| `/alertas` | Fuerza la revisión de todas las zonas del piloto |
| `/demo` | Envía los tres niveles con datos de ejemplo (para el video) |
| `/fuente` | Muestra los enlaces del IDEAM y del dataset usado |
| `/start`, `/ayuda` | Bienvenida y ayuda |

No hay suscripciones: cualquier persona que haya iniciado el bot recibe las alertas.

Secuencia recomendada para el video de la Fase 4:

```
/start → /departamentos → /consultar Medellín → /ubicacion 4.7110 -74.0721 → /estado → /demo
```

---

## 6. Cobertura real verificada

Medición del 21/11/2026 sobre las últimas 12 horas de datos de precipitación:

| Métrica | Valor |
|---|---:|
| Estaciones reportando | **595** |
| Departamentos cubiertos | **33** (los 32 + Bogotá) |
| Municipios con al menos una estación | **374** |

Departamentos con más estaciones: Bogotá 65, Antioquia 60, Boyacá 58, Santander 45,
Cundinamarca 42, Tolima 37, Huila 28, Nariño 28, Valle del Cauca 26.

**Importante:** Colombia tiene cerca de 1.100 municipios, así que la cobertura es nacional en el
sentido de que hay estaciones en todo el país, pero **no todos los municipios tienen estación propia**.
En esos casos el comando `/ubicacion` usa la estación más cercana y muestra la distancia.
Amazonas, Guaviare y Vaupés, por ejemplo, tienen una sola estación reportando.

El índice se actualiza en caché cada 10 minutos (`CACHE_TTL` en `nacional.py`), para no saturar
la API de datos.gov.co.

---

## 7. Archivos del proyecto

| Archivo | Función |
|---|---|
| `ideam.py` | Cliente de datos.gov.co. Maneja la hora local y filtra datos erróneos. |
| `nacional.py` | Índice nacional de estaciones, búsqueda por nombre y por coordenadas. |
| `riesgo.py` | Ventanas de 1 h y 3 h, clasificación y agregación de varias estaciones. |
| `mensajes.py` | Redacción de las alertas (formato del SMS del boceto). |
| `telegram_api.py` | Cliente HTTP mínimo de la Bot API, con reintentos por límite de velocidad. |
| `bot.py` | Bucle de comandos, registro de usuarios y avisos automáticos. |
| `demo.py`, `demo_nacional.py` | Pruebas de consola sin token. |
| `config.py` | Lectura de `.env` y del archivo de zonas. |
| `zonas.json` | Zonas del piloto de Cundinamarca y sus estaciones. |
| `usuarios.json` | Se crea solo: guarda los chats que han iniciado el bot. |
| `estado_zonas.json` | Se crea solo: nivel anterior de cada zona (avisos automáticos). |

---

## 8. Cambiar el territorio piloto

Edite `zonas.json`. Cada zona necesita:

```json
{
  "id": 5,
  "nombre": "Ruta vereda - cabecera",
  "municipio": "Su municipio",
  "estacion": "0021205970",
  "estacion_nombre": "NOMBRE DE LA ESTACION"
}
```

Para encontrar el código de una estación:

```
https://www.datos.gov.co/resource/hp9r-jxuu.json?$where=municipio='SU_MUNICIPIO'
```

La consulta nacional no depende de este archivo: funciona automáticamente para todo el país.

---

## 9. Umbrales de riesgo

| Nivel | 1 hora | 3 horas |
|---|---:|---:|
| BAJO | < 3 mm | < 8 mm |
| MEDIO | 3 – 10 mm | 8 – 25 mm |
| ALTO | > 10 mm | > 25 mm |

Se toma el nivel más severo de las dos ventanas. Los umbrales están en `UMBRALES`
dentro de `riesgo.py` y deben ajustarse con la comunidad y el comité de riesgo en un piloto real.

---

## 10. Hallazgos importantes de la fuente de datos

Estos tres puntos deben quedar en el informe:

1. **Zona horaria.** El campo `fechaobservacion` viene en hora local de Colombia (UTC-5) y sin
   indicador de zona. Compararlo contra UTC devuelve cero registros. El módulo `ideam.py`
   ya usa `timezone(timedelta(hours=-5))`.

2. **Datos sin validar.** El IDEAM advierte que los datos son crudos y pueden tener errores. En la
   prueba real apareció una estación con **31.402 mm en 3 horas**, un valor imposible. El módulo
   `ideam.py` descarta lecturas negativas o mayores a 30 mm por registro de 10 minutos.

3. **Cobertura desigual.** Hay 595 estaciones activas pero solo 374 municipios con estación propia.
   La búsqueda por coordenadas y el aviso de distancia son necesarios para llegar a la ruralidad
   dispersa.

---

## 11. Límites y costos

La API de Telegram es gratuita. Límites documentados:

- 1 mensaje por segundo por chat.
- 20 mensajes por minuto por grupo.
- ~30 mensajes por segundo en difusión masiva.

El bot respeta esos límites con pausas entre envíos y reintentos ante el error 429.
Para un piloto comunitario el costo es **$0**.

---

## 12. Despliegue gratuito en GitHub Actions

El bot también corre **en la nube sin costo** usando el repositorio público:

- Archivo: `.github/workflows/bot.yml`
- Frecuencia: cada **5 minutos** (cron `*/5 * * * *`)
- Comando: `python bot.py --once` (procesa lo pendiente y termina)
- Token: guardado como **Secret** `TELEGRAM_TOKEN` en *Settings → Secrets and variables → Actions*
- Estado: `offset.txt`, `usuarios.json` y `estado_zonas.json` se guardan de vuelta en el repo con
  un commit automático `[skip ci]`, para no responder dos veces el mismo mensaje.

Para probarlo: abra el bot en Telegram y envíe `/start`. La respuesta puede tardar **hasta 5 minutos**.

⚠️ Si el bot corre en GitHub Actions, **detenga el bot local** (`Ctrl+C` en la terminal o no use
`Ctrl+Shift+B`). Si los dos están activos, Telegram reparte los mensajes entre ellos y se duplican
o se pierden respuestas.

⚠️ GitHub desactiva los workflows programados después de **60 días sin actividad** en el repo.
Haga un commit o ejecute el workflow manualmente (*Actions → Run workflow*) al menos una vez al mes.

También puede forzar una ejecución desde la pestaña **Actions** del repositorio.

---

## 13. Alcance y advertencia

Este bot es un **canal comunitario de demostración**, no sustituye los sistemas oficiales de
alerta de emergencia (SMS masivo o *cell broadcast*). Requiere que la persona tenga teléfono
inteligente e internet, por lo que la emisora comunitaria se mantiene como canal de respaldo
para zonas sin cobertura de datos.

El dato del IDEAM es **crudo y sin validar oficialmente**: el mensaje lo advierte siempre.
No debe usarse para decidir evacuaciones sin contraste con el comité local de riesgo.

---

*Proyecto de Ingeniería II — UNAD · Grupo 202337121_2 · noviembre de 2026*
