import os
from google.cloud import storage

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'

client = storage.Client(project='laboratorio-cordoba-2060')
buckets = list(client.list_buckets())

if not buckets:
    print("No hay buckets")
else:
    for bucket in buckets:
        print(f"Borrando: {bucket.name}")
        bucket.delete(force=True)
    print("Listo")