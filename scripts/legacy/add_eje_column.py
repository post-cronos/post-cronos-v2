import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'
import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)

from google.cloud import bigquery

client = bigquery.Client(project='laboratorio-cordoba-2060')
table_id = 'laboratorio-cordoba-2060.post_cronos.encuestas'

# Add columns
for col in [
    'ALTER TABLE `laboratorio-cordoba-2060.post_cronos.encuestas` ADD COLUMN IF NOT EXISTS eje STRING',
    'ALTER TABLE `laboratorio-cordoba-2060.post_cronos.encuestas` ADD COLUMN IF NOT EXISTS eje_otro_texto STRING'
]:
    job = client.query(col)
    job.result()
    print(f'OK - {col}')

# Update Nina French (enc_007) - selected Mobiliario
job = client.query(
    'UPDATE laboratorio-cordoba-2060.post_cronos.encuestas '
    'SET eje = @eje WHERE id_encuesta = @id',
    job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter('eje', 'STRING', 'Mobiliario'),
        bigquery.ScalarQueryParameter('id', 'STRING', 'enc_007')
    ])
)
job.result()
print('OK - enc_007 eje=Mobiliario')

# Verify
results = client.query('SELECT id_encuesta, nombre_participante, eje, eje_otro_texto FROM laboratorio-cordoba-2060.post_cronos.encuestas ORDER BY id_encuesta')
for row in results:
    print(f'{row.id_encuesta} | {row.nombre_participante or ""} | eje={row.eje or "-"}')
