import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'D:\Post cronos\laboratorio-cordoba-2060-9fc2ad8ce3c5.json'

from google.cloud import storage

client = storage.Client(project='laboratorio-cordoba-2060')
bucket = client.get_bucket('post-cronos-dibujos-2060')

for blob in bucket.list_blobs():
    print(f'Blob: {blob.name}')
    acl = blob.acl
    for entry in acl:
        print(f'  {entry.get("entity")}: {entry.get("role")}')
    if not acl:
        print('  (default bucket ACL - no per-blob ACL)')
    print()
