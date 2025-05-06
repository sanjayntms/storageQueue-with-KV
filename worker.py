from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import json
from PIL import Image, ImageDraw, ImageFont
import io
import os
import time

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

QUEUE_NAME = "image-processing-queue"
UPLOADED_CONTAINER_NAME = "uploaded-images"
PROCESSED_CONTAINER_NAME = "processed-images"
WATERMARK_TEXT = "NTMS"

# Initialize Queue Service Client
queue_service_client = QueueServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
queue_client = queue_service_client.get_queue_client(queue=QUEUE_NAME)

# Initialize Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
uploaded_container_client = blob_service_client.get_container_client(UPLOADED_CONTAINER_NAME)
processed_container_client = blob_service_client.get_container_client(PROCESSED_CONTAINER_NAME)
try:
    processed_container_client.create_container()
except Exception as e:
    if "ContainerAlreadyExists" not in str(e):
        raise
    else:
        print(f"Processed container '{PROCESSED_CONTAINER_NAME}' already exists.")

def resize_image(image_data, max_size=(128, 128)):
    img = Image.open(io.BytesIO(image_data))
    img.thumbnail(max_size)
    output = io.BytesIO()
    img.save(output, format="JPEG")
    output.seek(0)
    return output.getvalue()

def add_watermark(image_data, text=WATERMARK_TEXT):
    img = Image.open(io.BytesIO(image_data)).convert("RGBA")
    width, height = img.size
    watermark_img = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_img)

    # Load a clear font; fallback to default if unavailable
    try:
        font = ImageFont.truetype("arial.ttf", size=int(height / 15))
    except IOError:
        font = ImageFont.load_default()

    # Get text size using textbbox (Pillow 10+)
    bbox = draw.textbbox((0, 0), text, font=font)
    textwidth = bbox[2] - bbox[0]
    textheight = bbox[3] - bbox[1]

    # Position watermark at bottom right with padding
    x = width - textwidth - 10
    y = height - textheight - 10

    # Draw watermark with black outline + white fill for visibility
    draw.text((x - 1, y - 1), text, font=font, fill=(0, 0, 0, 180))  # Shadow/outline
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 180))  # Shadow/outline
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 180))    # Main text

    composite = Image.alpha_composite(img, watermark_img)
    output = io.BytesIO()
    composite.convert("RGB").save(output, format="JPEG")
    output.seek(0)
    return output.getvalue()

def process_message(message):
    try:
        message_content = json.loads(message.content)
        blob_name = message_content.get("blob_name")
        if blob_name:
            print(f"Processing blob: {blob_name}")
            blob_client = uploaded_container_client.get_blob_client(blob=blob_name)
            download_stream = blob_client.download_blob()
            image_data = download_stream.readall()

            # Perform image processing: resize first
            resized_image = resize_image(image_data)
            # Then add watermark to resized image
            watermarked_image = add_watermark(resized_image)

            # Upload the processed image
            processed_blob_client = processed_container_client.get_blob_client(blob=f"processed_{blob_name}")
            processed_blob_client.upload_blob(watermarked_image, overwrite=True)
            print(f"Processed image saved as: processed_{blob_name}")
        else:
            print("Error: 'blob_name' not found in the message.")
    except Exception as e:
        print(f"Error processing message: {e}")

if __name__ == "__main__":
    print("Worker process started. Listening for messages...")
    while True:
        messages = queue_client.receive_messages(max_messages=5)
        for message in messages:
            process_message(message)
            queue_client.delete_message(message.id, message.pop_receipt)
        time.sleep(5)
