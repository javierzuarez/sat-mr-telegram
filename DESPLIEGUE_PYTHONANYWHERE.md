# Despliegue gratuito con webhook en PythonAnywhere

Esta guía deja el bot respondiendo **al instante** (1–3 s) en Telegram, sin esperar al
polling de GitHub Actions. Usa el plan **Beginner / gratuito** de PythonAnywhere:
sin tarjeta y sin librerías externas.

**Verificación previa (22 nov 2026):** la lista de sitios permitidos de PythonAnywhere
incluye `api.telegram.org` y `www.datos.gov.co`, que son exactamente los dos dominios
que usa el bot. Si en el futuro cambia, se solicita la inclusión desde
https://help.pythonanywhere.com/pages/RequestingAllowlistAdditions/.

---

## 1. Crear la cuenta y clonar el código

1. Regístrese en https://www.pythonanywhere.com/registration/register/beginner/ (plan gratuito).
2. En la pestaña **Consoles**, abra un **Bash console** y ejecute:

```bash
git clone https://github.com/javierzuarez/sat-mr-telegram.git ~/sat-mr-telegram
cd ~/sat-mr-telegram
python --version
```

El repo es público, así que no hace falta configurar SSH.

---

## 2. Guardar el token fuera del repositorio

En el mismo Bash console:

```bash
nano ~/.satmr_token
```

Pegue el token de @BotFather, guarde con `Ctrl+O`, `Enter` y salga con `Ctrl+X`.
Después proteja el archivo:

```bash
chmod 600 ~/.satmr_token
```

Compruebe que funciona sin mostrar el token:

```bash
export TELEGRAM_TOKEN_FILE="$HOME/.satmr_token"
python -c "import config; print('token configurado' if config.token() else 'FALTA token')"
```

---

## 3. Crear el Web App

1. Pestaña **Web → Add a new web app**.
2. Elija **Manual configuration** y la versión de Python que mostró `python --version`.
3. En **Source code** y **Working directory** ponga:

```text
/home/TU_USUARIO/sat-mr-telegram
```

4. Abra el enlace del archivo WSGI (parecido a
   `/var/www/TU_USUARIO.pythonanywhere.com_wsgi.py`) y reemplace todo por el
   contenido de `pythonanywhere_wsgi.py.example`, cambiando:

   - `TU_USUARIO` por su usuario real (dos veces).
   - `WEBHOOK_PATH` por un valor aleatorio. Genérelo en el Bash console:

     ```bash
     python -c "import secrets; print('telegram-' + secrets.token_hex(16))"
     ```

   - `WEBHOOK_SECRET` por **otro** valor aleatorio distinto:

     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```

   El token **no** va en el WSGI: solo la ruta al archivo `~/.satmr_token`.

5. Guarde y pulse **Reload** en la pestaña Web.

6. Compruebe en el navegador:

```text
https://TU_USUARIO.pythonanywhere.com/
```

Debe mostrar: `SAT-MR webhook activo`.

---

## 4. Decirle a Telegram dónde enviar los mensajes

En el Bash console (use los **mismos** secretos del WSGI):

```bash
cd ~/sat-mr-telegram
export TELEGRAM_TOKEN_FILE="$HOME/.satmr_token"
export WEBHOOK_URL="https://TU_USUARIO.pythonanywhere.com/telegram-EL_SECRETO_GENERADO"
export WEBHOOK_SECRET="EL_OTRO_SECRETO_GENERADO"
python configurar_webhook.py set
python configurar_webhook.py info
```

`configurar_webhook.py` no imprime la URL completa para no filtrar el segmento secreto
en los logs. En `info`, el campo `pending_update_count` debe quedar en `0`.

---

## 5. Probar en Telegram

Envíe al bot `@alertas_movilidad_unad_bot`:

```text
/start
/consultar Medellín
/ubicacion 4.7110 -74.0721
/estado
```

La respuesta debe llegar en **1–3 segundos**. Si tarda, revise el *error log* de la
pestaña Web de PythonAnywhere y vuelva a ejecutar `configurar_webhook.py info`.

---

## 6. GitHub Actions ya no compite por los mensajes

No es obligatorio desactivar el workflow: `bot.py --once` detecta que hay webhook
activo y omite `getUpdates` (Telegram no permite usar ambos a la vez). El workflow
sigue sirviendo para las **alertas automáticas del piloto**.

Si aun así quiere detenerlo por completo:

```bash
gh workflow disable "Bot SAT-MR (cada minuto)" --repo javierzuarez/sat-mr-telegram
```

Y para volver atrás:

```bash
python configurar_webhook.py delete
gh workflow enable "Bot SAT-MR (cada minuto)" --repo javierzuarez/sat-mr-telegram
```

Tampoco arranque el bot local con `Ctrl+Shift+B` mientras el webhook esté activo:
`bot.py` se negará a iniciar y mostrará una advertencia.

---

## 7. Actualizaciones del código

Cuando suba cambios a GitHub:

```bash
cd ~/sat-mr-telegram
git pull
```

Luego pulse **Reload** en la pestaña Web. El archivo `webhook_offset.txt` se crea
solo en PythonAnywhere y está excluido de Git, así que no se sobrescribe con `git pull`.

---

## 8. Límites del plan gratuito

- 1 web app, 1 worker, 512 MiB de disco, sin tarjeta.
- Las web apps gratuitas **caducan al mes si no se usan**. El tráfico de Telegram
  suele contar como uso, pero conviene entrar una vez al mes y pulsar **Extend/Reload**.
- No hay tareas programadas ni base de datos MySQL en las cuentas nuevas. Por eso
  las alertas automáticas siguen siendo ejecutadas por GitHub Actions.
- Costo total: **$0/mes**.

---

## 9. Solución rápida de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| `403 Forbidden` en la Web app o en la consola | Dominio no permitido por el proxy | Revisar https://www.pythonanywhere.com/whitelist/ y solicitar el dominio |
| Telegram no responde | `WEBHOOK_PATH` o `WEBHOOK_SECRET` distintos del WSGI | Repetir el paso 4 con los valores exactos |
| `409 Conflict: bot is currently running in webhook mode` | Alguien sigue haciendo `getUpdates` | Ya está corregido en `bot.py`; asegúrese de haber hecho `git pull` |
| Llegan respuestas duplicadas | Quedó un bot local o Actions con código antiguo | Detener el bot local y verificar `git pull` + Reload |
| `getWebhookInfo` muestra `last_error` | URL caída o certificado | Comprobar que la URL pública responde y pulsar Reload |
| La app se detuvo después de un mes | Caducidad del plan gratuito | Entrar a PythonAnywhere y pulsar Extend/Reload |
