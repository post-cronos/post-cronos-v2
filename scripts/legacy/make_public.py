import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'

from google.cloud import storage

client = storage.Client(project='laboratorio-cordoba-2060')
bucket = client.get_bucket('post-cronos-dibujos-2060')

for blob in bucket.list_blobs():
    if not blob.name.endswith('.json'):  # Skip JSON files, only images
        acl = blob.acl
        acl.all().grant_read()
        acl.save()
        public_url = f'https://storage.googleapis.com/{bucket.name}/{blob.name}'
        print(f'OK - {blob.name}')
        print(f'     {public_url}')
