from googleapiclient.discovery import build
from google_apis import _credentials

drive = build("drive", "v3", credentials=_credentials(), cache_discovery=False)

FOLDER_ID = "YOUR_FOLDER_ID"  # Replace with your folder ID

# Query Drive for items inside the folder
res = drive.files().list(
    q=f"'{FOLDER_ID}' in parents and trashed = false",
    fields="files(id, name, mimeType, parents)"
).execute()

import json
print(json.dumps(res, indent=2))