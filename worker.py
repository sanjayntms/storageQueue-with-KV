from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import json
from PIL import Image, ImageDraw, ImageFont
import io
import os
import time

# Key Vault
KEY_VAULT_URI = os.environ.get("KEY_VAULT_URI")
SECRET_NAME = "AZURE-STORAGE-CONNECTION-STRING"
WATERMARK_TEXT = "NTMS"

QUEUE_NAME = "image-processing-queue"
UPLOADED_CONTAINER_NAME = "uploaded-images"
PROCESSED_CONTAINER_NAME = "processed-images"

# Initialize Azure credentials
credential = DefaultAzureCredential()

# Fetch connection string from Key Vault
try:
    secret_client = SecretClient(vault_url=KEY_VAULT_URI, credential=credential)
    STORAGE_CONNECTION_STRING = secret_client.get_secret(SECRET_NAME).value
    print("Worker successfully retrieved connection string from Azure Key Vault.")
except Exception as e:
    print(f"Worker error retrieving connection string from Azure Key Vault: {e}")
    STORAGE_CONNECTION_STRING = None

if not STORAGE_CONNECTION_STRING:
    print("Worker error: Could not retrieve Azure Storage Connection String.")

# Azure clients
queue_service_client = QueueServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
queue_client = queue_service_client.get_queue_client(queue=QUEUE_NAME)

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


# ---------------------------
# Utility: Detect image format
# ---------------------------
def detect_image_format(image_data):
    img = Image.open(io.BytesIO(image_data))
    fmt = img.format.upper()

    if fmt == "PNG":
        return "PNG"
    else:
        return "JPEG"  # default fallback


# ---------------------------
# Resize (supports PNG)
# ---------------------------
def resize_image(image_data, max_size=(128, 128)):
    img = Image.open(io.BytesIO(image_data))

    # Preserve alpha for PNG
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    img.thumbnail(max_size)

    output = io.BytesIO()
    fmt = detect_image_format(image_data)
    img.save(output, format=fmt)
    output.seek(0)
    return output.getvalue(), fmt


# ---------------------------
# Add watermark (supports PNG)
# ---------------------------
def add_watermark(image_data, text=WATERMARK_TEXT):
    img = Image.open(io.BytesIO(image_data))

    # Keep transparency for PNG
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    width, height = img.size
    watermark_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_layer)

    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", size=int(height / 15))
    except IOError:
        font = ImageFont.load_default()

    # Text size
    bbox = draw.textbbox((0, 0), text, font=font)
    textwidth = bbox[2] - bbox[0]
    textheight = bbox[3] - bbox[1]

    # Bottom-right position
    x = width - textwidth - 10
    y = height - textheight - 10

    # Outline + main watermark
    draw.text((x - 1, y - 1), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 180))

    # Combine watermark and base image
    composed = Image.alpha_composite(img, watermark_layer)

    # Output with correct format
    fmt = detect_image_format(image_data)
    output = io.BytesIO()

    if fmt == "PNG":
        composed.save(output, format="PNG")
    else:
        composed.convert("RGB").save(output, format="JPEG")

    output.seek(0)
    return output.getvalue(), fmt


# ---------------------------
# Main message processor
# ---------------------------
def process_message(message):
    try:
        message_content = json.loads(message.content)
        blob_name = message_content.get("blob_name")
        if not blob_name:
            print("Error: 'blob_name' not found in message.")
            return

        print(f"Processing blob: {blob_name}")
        blob_client = uploaded_container_client.get_blob_client(blob=blob_name)
        image_data = blob_client.download_blob().readall()

        # Resize
        resized_image, fmt = resize_image(image_data)

        # Watermark
        watermarked_image, fmt = add_watermark(resized_image)

        # Output filename
        ext = "png" if fmt == "PNG" else "jpg"
        processed_blob_name = f"processed_{os.path.splitext(blob_name)[0]}.{ext}"

        # Upload
        processed_blob_client = processed_container_client.get_blob_client(processed_blob_name)
        processed_blob_client.upload_blob(watermarked_image, overwrite=True)
        print(f"Processed image saved as: {processed_blob_name}")

    except Exception as e:
        print(f"Error processing message: {e}")


# ---------------------------
# Worker Loop
# ---------------------------
if __name__ == "__main__":
    print("Worker process started. Listening for messages...")
    while True:
        messages = queue_client.receive_messages(max_messages=5)
        for message in messages:
            process_message(message)
            queue_client.delete_message(message.id, message.pop_receipt)
        time.sleep(5)
