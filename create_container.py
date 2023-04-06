from os import environ as env
from dotenv import load_dotenv, find_dotenv
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas


ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

def create_container_and_generate_sas(container_name):
    connection_string = env.get("AZURE_STORAGE_CONNECTION_STRING")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    # Create the container if it doesn't exist
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
    except:
        pass  # Container already exists

    # Generate a SAS token for the container
    sas_token = generate_container_sas(
        blob_service_client.account_name,
        container_name,
        account_key=blob_service_client.credential.account_key,
        permission=ContainerSasPermissions(read=True, write=True, list=True),
        expiry=datetime.utcnow() + timedelta(hours=1)  # Set an appropriate expiry time
    )

    return sas_token