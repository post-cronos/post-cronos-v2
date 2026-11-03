import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'

import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)

from google.cloud import bigquery

client = bigquery.Client(project='laboratorio-cordoba-2060')
BUCKET = 'post-cronos-dibujos-2060'

query = 'SELECT id_encuesta, url_imagen_dibujo FROM laboratorio-cordoba-2060.post_cronos.encuestas'
results = client.query(query)

for row in results:
    old_url = row.url_imagen_dibujo
    if old_url and old_url.startswith('gs://'):
        filename = old_url.replace('gs://' + BUCKET + '/', '')
        new_url = 'https://storage.googleapis.com/' + BUCKET + '/' + filename
        update = 'UPDATE laboratorio-cordoba-2060.post_cronos.encuestas SET url_imagen_dibujo = @new WHERE id_encuesta = @id'
        job = client.query(update, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter('new', 'STRING', new_url),
                bigquery.ScalarQueryParameter('id', 'STRING', row.id_encuesta)
            ]
        ))
        job.result()
        print(f'{row.id_encuesta}: {old_url} -> {new_url}')

print('OK - URLs actualizadas a HTTPS publicas')
