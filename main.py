from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import os

from fastapi import FastAPI
from dotenv import load_dotenv

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import get_connection, release_connection, close_pool

load_dotenv()


def _load_timezone():
    tz_name = os.getenv("APP_TIMEZONE", "America/Bogota")  # por defecto Bogotá
    try:
        return tz_name, ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        fallback = "America/Bogota"
        print(f"⚠️  Invalid APP_TIMEZONE='{tz_name}', defaulting to {fallback}")
        return fallback, ZoneInfo(fallback)


TZ_NAME, LOCAL_TZ = _load_timezone()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        close_pool()


app = FastAPI(lifespan=lifespan)

# Config SMTP Gmail (usa variables de entorno en producción)
EMAIL = os.getenv("SMTP_EMAIL")
PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def enviar_email(destinatario, asunto, mensaje):
    if not EMAIL or not PASSWORD:
        raise RuntimeError("SMTP credentials missing. Set SMTP_EMAIL and SMTP_PASSWORD env vars.")
    msg = MIMEText(mensaje)
    msg["Subject"] = asunto
    msg["From"] = EMAIL
    msg["To"] = destinatario

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, destinatario, msg.as_string())
        print(f"📧 Correo enviado a {destinatario}")


@app.get("/enviar-recordatorios")
def enviar_recordatorios():
    enviadas = 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            # Hora local (ej. Bogotá)
            ahora = datetime.now(LOCAL_TZ).replace(tzinfo=None)

            # Ventana de búsqueda (puedes ajustarla a más minutos si necesitas tolerancia)
            ventana_inicio = ahora - timedelta(minutes=5)
            ventana_fin = ahora + timedelta(minutes=5)

            print(
                "🕒 Ventana de recordatorios:",
                {
                    "timezone": TZ_NAME,
                    "ventana_inicio": ventana_inicio.isoformat(),
                    "ventana_fin": ventana_fin.isoformat(),
                },
            )

            cur.execute("""
                SELECT t.id, t.descripcion, t.fecha_hora_asignada, t.recordatorio_fecha,
                       u.email, u.name
                FROM tasks t
                JOIN users u ON t.id_user = u.id
                WHERE t.recordatorio_fecha BETWEEN %s AND %s
            """, (ventana_inicio, ventana_fin))

            tareas = cur.fetchall()

            for tarea in tareas:
                id_t, descripcion, fecha_hora, recordatorio_fecha, email, nombre = tarea
                enviar_email(
                    email,
                    "📌 Recordatorio de tarea",
                    f"Hola {nombre},\n\n"
                    f"Este es tu recordatorio programado ({recordatorio_fecha}).\n"
                    f"Tu tarea es '{descripcion}' el {fecha_hora}.\n\n"
                    "¡Éxitos!"
                )
                enviadas += 1

        finally:
            cur.close()
    finally:
        release_connection(conn)

    return {"status": "ok", "tareas_enviadas": enviadas}


@app.on_event("shutdown")
def shutdown_event():
    close_pool()