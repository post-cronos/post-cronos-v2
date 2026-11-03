import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'
import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)

from google.cloud import bigquery

client = bigquery.Client(project='laboratorio-cordoba-2060')

data = [
    ('55acc4f9-e743-4c04-b8ce-c15a08307646', 'Femenino'),
    ('6cf23dd0-c2e8-4441-8040-a12a8273f053', 'Masculino'),
    ('bc03abdf-b802-4382-ada5-d021dd36add1', 'Femenino'),
    ('enc_001', 'Femenino'),
    ('enc_002', 'Masculino'),
    ('enc_003', 'Femenino'),
    ('enc_004', 'Femenino'),
    ('enc_005', 'Masculino'),
    ('enc_006', 'Femenino'),
    ('enc_test_001', 'Masculino'),
    # Corrección Santa Ana: las 7 son Femenino
    ('santa_ana_5336', 'Femenino'),
    ('santa_ana_5337', 'Femenino'),
    ('santa_ana_5338', 'Femenino'),
    ('santa_ana_5340', 'Femenino'),
]

for id_encuesta, genero in data:
    job = client.query(
        'UPDATE laboratorio-cordoba-2060.post_cronos.encuestas SET genero = @g WHERE id_encuesta = @id',
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter('g', 'STRING', genero),
            bigquery.ScalarQueryParameter('id', 'STRING', id_encuesta)
        ])
    )
    job.result()
    print(f'{id_encuesta} -> {genero}')

print('\nOK - todos actualizados')
