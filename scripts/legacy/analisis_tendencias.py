import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'
import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)
import json
import re

from google import genai
from google.cloud import bigquery

PROJECT = 'laboratorio-cordoba-2060'
TABLE_ID = f'{PROJECT}.post_cronos.encuestas'
MODEL = 'gemini-2.5-flash-lite'
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resumen_ia.js')

bq = bigquery.Client(project=PROJECT)

rows = bq.query(f'''
    SELECT id_encuesta, edad, genero, colegio, ciudad_barrio, eje,
           descripcion_audio_o_ia, descripcion_final_texto
    FROM `{TABLE_ID}`
    ORDER BY id_encuesta
''').result()

data = []
for r in rows:
    data.append({
        'id_encuesta': r.id_encuesta,
        'edad': r.edad,
        'genero': r.genero,
        'colegio': r.colegio,
        'ciudad_barrio': r.ciudad_barrio,
        'eje': r.eje,
        'interpretacion_ia': r.descripcion_audio_o_ia,
        'texto_p3_literal': r.descripcion_final_texto,
    })

print(f'{len(data)} encuestas cargadas. Enviando a Gemini...')

prompt = f"""Eres un analista del proyecto "Post-Cronos: Cordoba 2060", donde ninos y adolescentes dibujaron su vision de la ciudad de Cordoba en el anio 2060.

A continuacion te paso el detalle de cada participante (id, edad, genero, colegio, barrio, eje tematico elegido, interpretacion IA del dibujo y el texto literal que escribio).

{f"{json.dumps(data, ensure_ascii=False, indent=2)}"}

Realiza un ANALISIS DE TENDENCIAS de los dibujos. Devolve SOLO JSON valido, sin markdown, con este esquema EXACTO:

{{
  "resumen_general": "parrafo de 3-5 oraciones resumiendo como imaginan Cordoba en 2060, que emociones y valores predominan",
  "tendencias": [
    {{"tema": "nombre corto de la tendencia",
      "detalle": "2-3 oraciones describiendo como aparece en los dibujos",
      "ejemplos": ["id_encuesta", "id_encuesta"]}}
  ],
  "insight_por_eje": {{
    "Tecnologia": "observacion sobre ese eje",
    "Mobiliario": "observacion sobre ese eje",
    "Moda": "observacion sobre ese eje",
    "Educacion": "observacion sobre ese eje",
    "Salud": "observacion sobre ese eje",
    "Comunicacion": "observacion sobre ese eje",
    "Herramientas": "observacion sobre ese eje",
    "Otro": "observacion sobre ese eje"
  }},
  "recomendaciones": [
    "recomendacion 1 para el equipo del proyecto",
    "recomendacion 2"
  ]
}}

Reglas:
- Las tendencias deben basarse SOLO en lo que ves en los datos, no inventar.
- insight_por_eje: usa SOLO los ejes que existan en los datos; para los demas usa null.
- Escribi todo en espanol (Argentina), tono profesional pero accesible.
- Inclui ejemplos citando los id_encuesta reales."""

client = genai.Client(project=PROJECT, location='us-central1', vertexai=True)
response = client.models.generate_content(model=MODEL, contents=[prompt])

text = re.sub(r'```(?:json)?\s*', '', response.text.strip())
text = re.sub(r'\s*```$', '', text.strip())
resumen = json.loads(text)

js = '// GENERADO AUTOMATICAMENTE por analisis_tendencias.py\n'
js += '// Ejecutar: .venv\\Scripts\\python analisis_tendencias.py\n'
js += 'window.RESUMEN = ' + json.dumps(resumen, ensure_ascii=False, indent=2) + ';\n'

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(js)

print(f'OK - Resumen IA escrito en {OUTPUT}')
print('Resumen general:', resumen.get('resumen_general', '')[:120] + '...')
