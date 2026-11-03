import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google import genai
from google.cloud import bigquery, storage
from google.genai import types

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
BUCKET = os.environ.get("BUCKET", "")
DATASET = os.environ.get("DATASET", "post_cronos")
TABLE = os.environ.get("TABLE", "encuestas")
LOCATION = os.environ.get("LOCATION", "us-central1")
MODEL = os.environ.get("MODEL", "gemini-2.5-flash-lite")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))
UPLOAD_PREFIX = os.environ.get("UPLOAD_PREFIX", "uploads").strip("/")
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "600"))
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "2"))
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

if not PROJECT:
    raise RuntimeError("Falta la variable GOOGLE_CLOUD_PROJECT")
if not BUCKET:
    raise RuntimeError("Falta la variable BUCKET")

TABLE_ID = f"{PROJECT}.{DATASET}.{TABLE}"
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

app = FastAPI(title="Post-Cronos API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_rate_lock = threading.Lock()
_rate_by_ip = defaultdict(deque)
_processing = threading.BoundedSemaphore(MAX_CONCURRENT)

PROMPT = """Eres un asistente analizando fichas del proyecto "Post-Cronos: Cordoba 2060".
La imagen TIENE DOS COSAS: (1) un dibujo, y (2) un formulario escrito a mano.

Extrae en JSON (sin markdown, solo JSON):

{
  "edad": "edad en numeros",
  "genero": "SOLO mira la casilla de GENERO en el formulario. Busca la MARCA CON UNA X (tachada/cruz) al lado de Masculino, Femenino, No binario, Otro o No responder. NO infieras el genero por el nombre, la letra o el dibujo. Debe ser UNO de: (Masculino|Femenino|No binario|Otro|No responder)",
  "institucion": "nombre del colegio",
  "ciudad_barrio": "ciudad o barrio escrito",
  "eje": "Busca las X o tildes en la seccion de EJES TEMATICOS. PUEDE HABER MULTIPLES ejes seleccionados. Devolve los que esten marcados, separados por coma y espacio. Ej: 'Moda, Tecnologia' o 'Mobiliario' o 'Comunicacion, Salud'. Opciones: (Moda|Tecnologia|Mobiliario|Educacion|Herramientas|Salud|Comunicacion|Otro). NO inventes ejes que no esten marcados.",
  "interpretacion_ia": "INTERPRETA el dibujo: que representa, que quiere comunicar, que emocion transmite",
  "texto_p3_LITERAL": "TRANSCRIBE TEXTUALMENTE lo que el nino escribio en la pregunta 3 (descripcion final) -- copia exacta, sin cambiar ni interpretar nada. Si no hay texto, pon null"
}

IMPORTANTE: "texto_p3_LITERAL" debe ser COPIA EXACTA de lo que escribio el nino, palabra por palabra, sin resumir ni mejorar ni interpretar."""


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate(ip: str) -> None:
    now = time.time()
    with _rate_lock:
        hits = _rate_by_ip[ip]
        while hits and now - hits[0] > RATE_LIMIT_WINDOW:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_MAX:
            retry = max(1, int(RATE_LIMIT_WINDOW - (now - hits[0])))
            raise HTTPException(429, f"Demasiadas subidas desde esta conexión. Probá en {retry}s.")
        hits.append(now)


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "_", (value or "").strip().lower())
    return value.strip("_") or "subidas"


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", (text or "").strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text)


def _ensure_table() -> None:
    bq = bigquery.Client(project=PROJECT)
    dataset = bigquery.Dataset(f"{PROJECT}.{DATASET}")
    dataset.location = LOCATION
    bq.create_dataset(dataset, exists_ok=True)
    bq.query(
        f"""CREATE TABLE IF NOT EXISTS `{TABLE_ID}` (
            id_encuesta STRING,
            edad INT64,
            genero STRING,
            colegio STRING,
            fecha_registro TIMESTAMP,
            url_imagen_dibujo STRING,
            eje STRING,
            descripcion_audio_o_ia STRING,
            descripcion_final_texto STRING,
            ciudad_barrio STRING
        )"""
    ).result()


def _to_record(row: dict) -> dict:
    return {
        "id": row["id_encuesta"],
        "edad": row["edad"],
        "genero": row["genero"],
        "ciudad_barrio": row["ciudad_barrio"],
        "colegio": row["colegio"],
        "eje": row["eje"],
        "img": row["url_imagen_dibujo"],
        "interp": row["descripcion_audio_o_ia"],
        "diseno": row["descripcion_final_texto"],
    }


@app.get("/health")
def health():
    return {"ok": True, "project": PROJECT, "bucket": BUCKET}


@app.get("/api/data")
def get_data():
    bq = bigquery.Client(project=PROJECT)
    rows = bq.query(
        f"""SELECT id_encuesta, edad, genero, colegio, ciudad_barrio, eje,
                   url_imagen_dibujo, descripcion_audio_o_ia, descripcion_final_texto
            FROM `{TABLE_ID}`
            ORDER BY id_encuesta"""
    ).result()
    return [
        {
            "id": r.id_encuesta,
            "edad": r.edad,
            "genero": r.genero,
            "ciudad_barrio": r.ciudad_barrio,
            "colegio": r.colegio,
            "eje": r.eje,
            "img": r.url_imagen_dibujo,
            "interp": r.descripcion_audio_o_ia,
            "diseno": r.descripcion_final_texto,
        }
        for r in rows
    ]


@app.get("/api/img/{object_name:path}")
def get_image(object_name: str):
    gcs = storage.Client(project=PROJECT)
    blob = gcs.bucket(BUCKET).blob(object_name)
    if not blob.exists():
        raise HTTPException(404, "Imagen no encontrada")
    return StreamingResponse(
        blob.open("rb"),
        media_type=blob.content_type or "image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.post("/api/upload")
def upload(request: Request, file: UploadFile = File(...), school: str = Form("")):
    ip = _client_ip(request)
    _check_rate(ip)

    content_type = (file.content_type or "").lower()
    if content_type not in ("image/jpeg", "image/jpg"):
        raise HTTPException(400, "Solo se aceptan archivos JPG/JPEG.")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"El archivo supera el máximo de {MAX_UPLOAD_MB} MB.")
    if len(data) < 4 or not data.startswith(b"\xff\xd8\xff"):
        raise HTTPException(400, "El archivo no es un JPEG válido.")

    folder = f"{UPLOAD_PREFIX}/{_slug(school)}"
    name = f"{folder}/{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:10]}.jpg"
    blob = storage.Client(project=PROJECT).bucket(BUCKET).blob(name)
    blob.upload_from_string(data, content_type="image/jpeg")

    public_url = f"https://storage.googleapis.com/{BUCKET}/{name}"
    try:
        blob.make_public()
    except Exception:
        public_url = f"{str(request.base_url).rstrip('/')}/api/img/{quote(name)}"

    if not _processing.acquire(timeout=30):
        raise HTTPException(503, "El servidor está ocupado procesando dibujos. Reintentá en unos segundos.")

    try:
        _ensure_table()
        image = types.Part.from_bytes(data=data, mime_type="image/jpeg")
        client = genai.Client(project=PROJECT, location=LOCATION, vertexai=True)
        response = client.models.generate_content(model=MODEL, contents=[PROMPT, image])
        parsed = _parse_json(response.text)

        enc_id = f"{_slug(school)}_{uuid.uuid4().hex[:6]}"
        row = {
            "id_encuesta": enc_id,
            "edad": int(parsed["edad"]) if parsed.get("edad") else None,
            "genero": parsed.get("genero"),
            "colegio": parsed.get("institucion") or (school or None),
            "ciudad_barrio": parsed.get("ciudad_barrio"),
            "fecha_registro": datetime.now(timezone.utc).isoformat(),
            "url_imagen_dibujo": public_url,
            "eje": parsed.get("eje"),
            "descripcion_audio_o_ia": parsed.get("interpretacion_ia"),
            "descripcion_final_texto": parsed.get("texto_p3_LITERAL"),
        }

        errors = bigquery.Client(project=PROJECT).insert_rows_json(TABLE_ID, [row])
        if errors:
            raise HTTPException(502, f"No se pudo guardar en BigQuery: {errors}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"No se pudo procesar la imagen con IA: {exc}") from exc
    finally:
        _processing.release()

    return {"ok": True, "record": _to_record(row)}
