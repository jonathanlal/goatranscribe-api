from authlib.integrations.flask_oauth2 import current_token
from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas, generate_blob_sas, BlobSasPermissions
from flaskr.auth import getUserID
from datetime import datetime, timedelta
from os import environ as env

# language detection from text
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.document import DocumentTranslationClient

def getBlobUrl(container_name, blob_name):
    sas_token = get_blob_sas(blob_name)
    return 'https://goatranscribe.azureedge.net/'+container_name+'/'+blob_name+'?'+sas_token

def get_container_client(user_id=None):
    if user_id is None:
        container_name = getUserID(current_token)
    else:
        container_name = user_id
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
    except:
        pass  # Container already exists
    return {"container_client": container_client, "blob_service_client": blob_service_client, "container_name": container_name}

def create_container_and_sas(container_name):
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
    except:
        pass  # Container already exists
    
    sas_token = generate_container_sas(
        blob_service_client.account_name,
        container_name,
        account_key=blob_service_client.credential.account_key,
        permission=ContainerSasPermissions(read=True, write=True, list=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
        )
    return f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}?{sas_token}"

def get_blob_sas_test(container_name, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    # container_client = blob_service_client.get_container_client(container_name)
    
    sas_blob = generate_blob_sas(account_name=blob_service_client.account_name, 
                                container_name=container_name,
                                blob_name=blob_name,
                                account_key=blob_service_client.credential.account_key,
                                permission=BlobSasPermissions(read=True, write=True, list=True, add=True),
                                expiry=datetime.utcnow() + timedelta(hours=1))
    return sas_blob
    # account_url = blob_service_client.primary_endpoint
    # sas_container = f"{account_url}?{sas_token}"
    # return sas_container

def delete_container(container_name):
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    try:
        blob_service_client.delete_container(container_name)
        # print(f"Container '{container_name}' deleted.")
    except Exception as e:
        print(f"Could not delete container: {e}")


def get_blob_client(blob_name, user_id=None):
    container_client = get_container_client(user_id)["container_client"]
    return container_client.get_blob_client(blob_name)

def upload_file_to_azure(blob_name, data, user_id=None, metadata=None):
    blob_client = get_blob_client(blob_name, user_id)
    blob_client.upload_blob(data, overwrite=True, metadata=metadata)

def upload_file_to_container(data, container_name, blob_name, metadata=None):
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    # container_client = blob_service_client.get_container_client(container_name)
    blob_client = blob_service_client.get_blob_client(container_name, blob_name)
    # blob_client = container_client.get_blob_client(blob_name)
        # If the data is a string, encode it to bytes
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    try:
        blob_client.upload_blob(data, overwrite=True, metadata=metadata)
    except Exception as e:
        print(f"Error uploading blob: {e}")

def download_file_from_container(container_name, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob_name)
    return blob_client.download_blob()

def file_exists_azure(blob_name, user_id=None):
    blob_client = get_blob_client(blob_name, user_id)
    return blob_client.exists()

def download_file_from_azure(blob_name, user_id=None):
    blob_client = get_blob_client(blob_name, user_id)
    return blob_client.download_blob()

def upload_file_to_azure_blob(file):
    clients = get_container_client()
    container_client = clients["container_client"]
    blob_client = container_client.get_blob_client(file.filename)
    blob_client.upload_blob(file)
    return blob_client.url

def get_container_sas(user_id=None):
    clients = get_container_client(user_id)
    blob_service_client = clients["blob_service_client"]
    container_name = clients["container_name"]

    sas_token = generate_container_sas(
        blob_service_client.account_name,
        container_name,
        account_key=blob_service_client.credential.account_key,
        permission=ContainerSasPermissions(read=True, write=True, list=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    account_url = blob_service_client.primary_endpoint
    sas_container = f"{account_url}?{sas_token}"
    return sas_container

def get_blob_sas(blob_name):
    clients = get_container_client()
    blob_service_client = clients["blob_service_client"]
    container_name = clients["container_name"]
    
    sas_blob = generate_blob_sas(account_name=blob_service_client.account_name, 
                                container_name=container_name,
                                blob_name=blob_name,
                                account_key=blob_service_client.credential.account_key,
                                permission=BlobSasPermissions(read=True),
                                expiry=datetime.utcnow() + timedelta(hours=1))
    return sas_blob


def authenticate_cognitive_client():
    ta_credential = AzureKeyCredential(env.get("AZURE_COGNITIVE_KEY"))
    text_analytics_client = TextAnalyticsClient(
            endpoint=env.get("AZURE_COGNITIVE_ENDPOINT"), 
            credential=ta_credential)
    return text_analytics_client

def detect_language(text_to_analyze):
    client = authenticate_cognitive_client()
    try:
        documents = [text_to_analyze]
        response = client.detect_language(documents=documents, country_hint='')[0]
        language = response.primary_language.name
        iso = response.primary_language.iso6391_name
        return {"language": language, "iso": iso}
    except Exception as err:
        print("Encountered exception. {}".format(err))

def translate_docs(target_language, sourceUrl, targetUrl):
    document_translation_client = DocumentTranslationClient(env.get("AZURE_COGNITIVE_DOCUMENT_ENDPOINT"), AzureKeyCredential(env.get("AZURE_COGNITIVE_DOCUMENT_KEY")))

    try:
        poller = document_translation_client.begin_translation(sourceUrl, targetUrl, target_language)
        return poller
    except Exception as err:
        print("Encountered exception. {}".format(err))
        raise