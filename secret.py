from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import os

# Key Vault details (replace with your actual values in environment variables)
KEY_VAULT_URI = os.environ.get("KEY_VAULT_URI")
SECRET_NAME = "AZURE-STORAGE-CONNECTION-STRING"  # Replace with the actual secret name

if not KEY_VAULT_URI:
    print("Error: KEY_VAULT_URI environment variable not set.")
    exit(1)

print(f"Trying to retrieve secret: {SECRET_NAME} from Key Vault: {KEY_VAULT_URI}")

try:
    # Initialize Azure credentials
    credential = DefaultAzureCredential()

    # Initialize Key Vault Secret Client
    secret_client = SecretClient(vault_url=KEY_VAULT_URI, credential=credential)

    # Get the secret
    secret = secret_client.get_secret(SECRET_NAME)
    print(f"Successfully retrieved secret '{secret.name}'. Value (length): {len(secret.value) if secret.value else 0}")
    # TEMPORARILY PRINT THE SECRET VALUE (USE WITH EXTREME CAUTION):
    print(f"Secret Value: {secret.value}")

except Exception as e:
    print(f"Error retrieving secret '{SECRET_NAME}' from Azure Key Vault: {e}")
