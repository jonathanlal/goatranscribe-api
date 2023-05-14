from authlib.integrations.flask_oauth2 import current_token
from azure.storage.blob import BlobServiceClient
from flaskr.create_container import get_blob_sas
from os import environ as env

# access tokens with an Auth0 API audience, excluding the /userinfo endpoint, cannot have private, non-namespaced custom claims
# https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-token-claims 
def getUserID(token):
    if not token:
        return 'try'
    sub_value = token.get('sub', '')
    return sub_value.replace('|', '')

def getBlobUrl(container_name, blob_name):
    sas_token = get_blob_sas(container_name, blob_name)
    #change url to custom domain url after fixing https
    return 'https://goatranscribe.azureedge.net/'+container_name+'/'+blob_name+'?'+sas_token

def get_container_client():
    container_name = getUserID(current_token)
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    return blob_service_client.get_container_client(container_name)

def get_blob_client(blob_name):
    container_client = get_container_client()
    return container_client.get_blob_client(blob_name)

def upload_file_to_azure(blob_name, data, metadata=None):
    blob_client = get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True, metadata=metadata)

def file_exists_azure(blob_name):
    blob_client = get_blob_client(blob_name)
    return blob_client.exists()

def download_file_from_azure(blob_name):
    blob_client = get_blob_client(blob_name)
    return blob_client.download_blob()