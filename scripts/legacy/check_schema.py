import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'
import sys
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)

from google.cloud import bigquery

client = bigquery.Client(project='laboratorio-cordoba-2060')
table = client.get_table('laboratorio-cordoba-2060.post_cronos.encuestas')

for f in table.schema:
    print(f'{f.name} ({f.field_type}, {f.mode})')
