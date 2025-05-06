from flask import Flask, request, render_template, redirect, url_for
from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os
import json
from uuid import uuid4

app = Flask(__name__)

# Key Vault details (replace with your actual values)
KEY_VAULT_URI = os.environ.get("KEY_VAULT_URI")
SECRET_NAME = "AZURE-STORAGE-CONNECTION-STRING"
WATERMARK_TEXT = "NTMS"

QUEUE_NAME = "image-processing-queue"
UPLOADED_CONTAINER_NAME = "uploaded-images"
PROCESSED_CONTAINER_NAME = "processed-images"

# Initialize Azure credentials
credential = DefaultAzureCredential()

# Initialize Key Vault Secret Client
secret_client = None
STORAGE_CONNECTION_STRING = None
try:
    secret_client = SecretClient(vault_url=KEY_VAULT_URI, credential=credential)
    STORAGE_CONNECTION_STRING = secret_client.get_secret(SECRET_NAME).value
    print("Worker successfully retrieved connection string from Azure Key Vault.")
except Exception as e:
    print(f"Worker error retrieving connection string from Azure Key Vault: {e}")
    # Consider how to handle this error - exit the worker or retry
    # exit(1)

if not STORAGE_CONNECTION_STRING:
    print("Worker error: Could not retrieve Azure Storage Connection String.")
    # Potentially exit the worker
    # exit(1)



# Initialize Queue Service Client
queue_service_client = QueueServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
queue_client = None
try:
    queue_client = queue_service_client.get_queue_client(queue=QUEUE_NAME)
    queue_client.create_queue()
except ResourceExistsError:
    pass  # Queue already exists
except Exception as e:
    print(f"Error creating/getting queue: {e}")

# Initialize Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)

# Uploaded container
uploaded_container_client = None
try:
    uploaded_container_client = blob_service_client.get_container_client(UPLOADED_CONTAINER_NAME)
    uploaded_container_client.create_container()
except ResourceExistsError:
    pass  # Already exists
except Exception as e:
    print(f"Error creating/getting uploaded container: {e}")

# Processed container
processed_container_client = None
try:
    processed_container_client = blob_service_client.get_container_client(PROCESSED_CONTAINER_NAME)
    processed_container_client.create_container()
except ResourceExistsError:
    pass  # Already exists
except Exception as e:
    print(f"Error creating/getting processed container: {e}")

@app.route('/', methods=['GET'])
def index():
    uploaded_blobs = []
    processed_blobs = []

    # List blobs in uploaded container
    if uploaded_container_client:
        uploaded_blobs = [
            uploaded_container_client.url + '/' + blob.name
            for blob in uploaded_container_client.list_blobs()
        ]

    # List blobs in processed container
    if processed_container_client:
        processed_blobs = [
            processed_container_client.url + '/' + blob.name
            for blob in processed_container_client.list_blobs()
        ]

    return render_template('index.html', uploaded_blobs=uploaded_blobs, processed_blobs=processed_blobs)

@app.route('/upload', methods=['POST'])
def upload_file():
    if uploaded_container_client is None:
        return "Error: Blob Storage container not initialized.", 500

    if queue_client is None:
        return "Error: Queue client not initialized.", 500

    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        try:
            file_extension = os.path.splitext(file.filename)[1]
            blob_name = f"{uuid4()}{file_extension}"
            uploaded_blob_client = uploaded_container_client.get_blob_client(blob=blob_name)
            uploaded_blob_client.upload_blob(file.read())

            # Create a message for the queue with 30s delay
            message = {"blob_name": blob_name}
            queue_client.send_message(json.dumps(message), visibility_timeout=30)

            return redirect(url_for('index'))

        except Exception as e:
            return f"Error during upload or enqueue: {e}", 500

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
