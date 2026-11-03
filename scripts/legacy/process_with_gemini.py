import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'
import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)
import json
import re
from datetime import datetime, timezone

from google import genai
from google.genai import types
from google.cloud import bigquery, storage

PROJECT = 'laboratorio-cordoba-2060'
BUCKET = 'post-cronos-dibujos-2060'
TABLE_ID = f'{PROJECT}.post_cronos.encuestas'
MODEL = 'gemini-2.5-flash-lite'

client = genai.Client(project=PROJECT, location='us-central1', vertexai=True)
bq = bigquery.Client(project=PROJECT)
gcs = storage.Client(project=PROJECT)
bucket = gcs.get_bucket(BUCKET)

SCHOOL = input('Nombre de la carpeta/colegio (ej: santa_ana): ').strip()
FOLDER = f'{SCHOOL}/'

bq.query(f"""
    CREATE TABLE IF NOT EXISTS `{TABLE_ID}` (
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
    )
""").result()
print(f'OK - Tabla verificada, procesando carpeta: {FOLDER}')

blobs = list(bucket.list_blobs(prefix=FOLDER))
blobs.sort(key=lambda b: b.name)

for blob in blobs:
    if not blob.name.lower().endswith(('.jpg', '.jpeg', '.png')):
        continue

    public_url = f'https://storage.googleapis.com/{BUCKET}/{blob.name}'
    gcs_uri = f'gs://{BUCKET}/{blob.name}'
    filename = os.path.basename(blob.name)

    match = re.search(r'(\d+)', filename)
    img_id = match.group(1) if match else filename.rsplit('.', 1)[0]
    enc_id = f'{SCHOOL}_{img_id}'

    print(f'\n=== {filename} ===')

    prompt = f"""Eres un asistente analizando fichas del proyecto "Post-Cronos: Cordoba 2060".
La imagen TIENE DOS COSAS: (1) un dibujo, y (2) un formulario escrito a mano.

Extrae en JSON (sin markdown, solo JSON):

{{
  "edad": "edad en numeros",
  "genero": "SOLO mira la casilla de GENERO en el formulario. Busca la MARCA CON UNA X (tachada/cruz) al lado de Masculino, Femenino, No binario, Otro o No responder. NO infieras el genero por el nombre, la letra o el dibujo. Debe ser UNO de: (Masculino|Femenino|No binario|Otro|No responder)",
  "institucion": "nombre del colegio",
  "ciudad_barrio": "ciudad o barrio escrito",
  "eje": "Busca las X o tildes en la seccion de EJES TEMATICOS. PUEDE HABER MULTIPLES ejes seleccionados. Devolve los que esten marcados, separados por coma y espacio. Ej: 'Moda, Tecnologia' o 'Mobiliario' o 'Comunicacion, Salud'. Opciones: (Moda|Tecnologia|Mobiliario|Educacion|Herramientas|Salud|Comunicacion|Otro). NO inventes ejes que no esten marcados.",
  "interpretacion_ia": "INTERPRETA el dibujo: que representa, que quiere comunicar, que emocion transmite",
  "texto_p3_LITERAL": "TRANSCRIBE TEXTUALMENTE lo que el nino escribio en la pregunta 3 (descripcion final) -- copia exacta, sin cambiar ni interpretar nada. Si no hay texto, pon null"
}}

IMPORTANTE: "texto_p3_LITERAL" debe ser COPIA EXACTA de lo que escribio el nino, palabra por palabra, sin resumir ni mejorar ni interpretar."""

    try:
        image = types.Part.from_uri(file_uri=gcs_uri, mime_type='image/jpeg')
        response = client.models.generate_content(model=MODEL, contents=[prompt, image])
        text = re.sub(r'```(?:json)?\s*', '', response.text.strip())
        data = json.loads(text)

        row = {
            'id_encuesta': enc_id,
            'edad': int(data['edad']) if data.get('edad') else None,
            'genero': data.get('genero'),
            'colegio': data.get('institucion') or SCHOOL,
            'ciudad_barrio': data.get('ciudad_barrio'),
            'fecha_registro': datetime.now(timezone.utc).isoformat(),
            'url_imagen_dibujo': public_url,
            'eje': data.get('eje'),
            'descripcion_audio_o_ia': data.get('interpretacion_ia'),
            'descripcion_final_texto': data.get('texto_p3_LITERAL'),
        }

        print(f'  Edad: {row["edad"]} | Genero: {row["genero"]} | Eje: {row["eje"]}')
        print(f'  P3 literal: {row["descripcion_final_texto"][:100] if row["descripcion_final_texto"] else "null"}...')

        errors = bq.insert_rows_json(TABLE_ID, [row])
        if errors:
            print(f'  ERROR BQ: {errors}')
        else:
            print(f'  OK - {enc_id} insertado')

    except Exception as e:
        print(f'  ERROR: {e}')

print('\n=== COMPLETADO ===')
