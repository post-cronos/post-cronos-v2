import os
from google.cloud import storage

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'

client = storage.Client(project='laboratorio-cordoba-2060')

bucket_name = 'post-cronos-dibujos-2060'
bucket = client.create_bucket(bucket_name, location='us-central1')

print(f"Creado: gs://{bucket.name}")
print(f"Ubicación: {bucket.location}")