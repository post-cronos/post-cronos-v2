import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'
import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)

from google.cloud import bigquery

client = bigquery.Client(project='laboratorio-cordoba-2060')

# Add column
job = client.query('ALTER TABLE laboratorio-cordoba-2060.post_cronos.encuestas ADD COLUMN IF NOT EXISTS genero STRING')
job.result()
print('OK - columna genero agregada')

# Update enc_007
job = client.query(
    'UPDATE laboratorio-cordoba-2060.post_cronos.encuestas SET genero = @v WHERE id_encuesta = @id',
    job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter('v', 'STRING', 'Femenino'),
        bigquery.ScalarQueryParameter('id', 'STRING', 'enc_007')
    ])
)
job.result()
print('OK - enc_007 genero=Femenino')

# Verify
results = client.query('SELECT id_encuesta, nombre_participante, edad, genero, lugar FROM laboratorio-cordoba-2060.post_cronos.encuestas ORDER BY id_encuesta')
for row in results:
    print(f'{row.id_encuesta} | {row.nombre_participante or ""} | {row.edad or ""} | {row.genero or "-"} | {row.lugar or ""}')
