import asyncio
import logging
import time
from urllib.parse import urlparse
from authlib.integrations.flask_oauth2 import current_token
from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas, generate_blob_sas, BlobSasPermissions
from flaskr.auth import getUserID
from datetime import datetime, timedelta, timezone
from os import environ as env
import os

# language detection from text
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.document import DocumentTranslationClient

from azure.identity import ClientSecretCredential
from azure.mgmt.media import AzureMediaServices
from azure.mgmt.media.models import (
    Job,
    JobInputHttp,
    JobOutputAsset,
    TransformOutput,
    BuiltInStandardEncoderPreset,
    EncoderNamedPreset,
    ListContainerSasInput,
    Asset,
    Transform)

#THIS RETURNS CDN URL which apparently does not work with sas for the storage? 
# def getBlobUrl(container_name, blob_name, user_id=None):
#     sas_token = get_blob_sas(blob_name, user_id)
#     return 'https://goatranscribe.azureedge.net/'+container_name+'/'+blob_name+'?'+sas_token

def getBlobUrl(container_name, blob_name, user_id=None):
    sas_token = get_blob_sas(blob_name, user_id)
    clients = get_container_client(user_id)
    blob_service_client = clients["blob_service_client"]

    return f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

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

def get_blob_service_client(container_name, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    blob_client = blob_service_client.get_container_client(container_name)
    return blob_client.get_blob_client(blob_name)

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


def get_blob_sas(blob_name, user_id=None):
    clients = get_container_client(user_id)
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


def authenticate_media_client():
    # Tenant ID for your Azure Subscription
    TENANT_ID = env.get("AZURE_MEDIA_SERVICE_TENANT_ID")
    # Your Application Client ID of your Service Principal
    CLIENT_ID = env.get("AZURE_MEDIA_SERVICE_CLIENT_ID")
    # Your Service Principal secret key
    CLIENT_SECRET = env.get("AZURE_MEDIA_SERVICE_CLIENT_SECRET")
    # Your Azure Subscription ID
    SUBSCRIPTION_ID = env.get("AZURE_MEDIA_SERVICE_SUBSCRIPTION_ID")
    credentials = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    client = AzureMediaServices(credentials, SUBSCRIPTION_ID)
    return client

async def process_audio(input_url, output_asset_name, job_name, task_id, user_id, task_status_callback, audio_progress_callback, entry_key, update_audio_status_callback):
    job_id = encode_audio_to_mp3(input_url, output_asset_name, job_name)
    await wait_for_job_to_finish("AudioEncodingTransform", job_id, task_id, user_id, task_status_callback, audio_progress_callback, entry_key, update_audio_status_callback)

def encode_audio_to_mp3(input_url, output_asset_name, job_name):
    # The name of the transform
    transform_name = "AudioEncodingTransform"

    # Use the "AAC Good Quality Audio" preset
    # preset = BuiltInStandardEncoderPreset(preset_name=EncoderNamedPreset.DD_GOOD_QUALITY_AUDIO)
    preset = BuiltInStandardEncoderPreset(preset_name=EncoderNamedPreset.AAC_GOOD_QUALITY_AUDIO)

    transform_output = TransformOutput(preset=preset)

    client = authenticate_media_client()
    RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
    ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")

    # Check if the transform exists, and create a new one if it doesn't
    # transform = client.transforms.get(RESOURCE_GROUP_NAME, ACCOUNT_NAME, transform_name)
    # transform = Transform(outputs=[transform_output])

    # if transform is None:
    transform = client.transforms.create_or_update(
        RESOURCE_GROUP_NAME,
        ACCOUNT_NAME,
        transform_name,
        Transform(outputs=[transform_output])
    )

    # Create the job input
    job_input = JobInputHttp(files=[input_url])

    # Create the job output
    # job_output = JobOutputAsset(asset_name=output_asset_name)
    job_outputs = [JobOutputAsset(asset_name=output_asset_name)]

    # Create the job
    # job_name = "EncodingJob"
    job = Job(input=job_input, outputs=job_outputs)

    # Submit the job
    job = client.jobs.create(
        RESOURCE_GROUP_NAME,
        ACCOUNT_NAME,
        transform_name,
        job_name,
        job
    )
    
    return job_name

# def get_asset_by_name(asset_name):
#     # Get the asset
#     client = authenticate_media_client()
#     RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
#     ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")
#     asset = client.assets.get(RESOURCE_GROUP_NAME, ACCOUNT_NAME, asset_name)
#     return asset


def copy_encoded_asset_to_user_container(src_container_name, src_blob_name, dest_blob_name, user_id):

    asset_blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
    source_blob = asset_blob_service_client.get_blob_client(src_container_name, src_blob_name)

    source_blob_url = source_blob.url

    clients = get_container_client(user_id)
    blob_service_client = clients["blob_service_client"]

    dest_blob = blob_service_client.get_blob_client(f"{user_id}/encoded", dest_blob_name)
    copy_status = dest_blob.start_copy_from_url(source_blob_url)
    # Poll for copy status until the copy completes or fails
    while True:
        try:
            # Get the copy status
            copy_props = dest_blob.get_blob_properties().copy
            copy_status = copy_props.status

            # If the copy operation completed or failed, break out of the loop
            if copy_status in ['success', 'failed']:
                break
            else:
                # If the copy operation is still pending, wait a bit and then check the status again
                time.sleep(1)

        except Exception as e:
            # If the blob isn't found, the copy operation failed
            break

    # Return the final copy status
    return copy_status


def get_encoded_file_name_from_asset(asset_name):
    client = authenticate_media_client()
    RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
    ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")
    tracks = client.tracks.list(RESOURCE_GROUP_NAME, ACCOUNT_NAME, asset_name)
    for track in tracks:
        if '.mp4' in track.name:  # Assumes that the encoded track contains 'AACAudio' in the name
            return track.name
    return None 

def delete_asset(asset_name):
    client = authenticate_media_client()
    RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
    ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")

    client.assets.delete(RESOURCE_GROUP_NAME, ACCOUNT_NAME, asset_name)


async def wait_for_job_to_finish(transform_name, job_id, task_id, user_id, task_status_callback, audio_progress_callback, entry_key, update_audio_status_callback):
    timeout = datetime.now(timezone.utc)
    # Timer values
    timeout_seconds = 60 * 10
    sleep_interval = 2

    timeout += timedelta(seconds=timeout_seconds)
    client = authenticate_media_client()
    RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
    ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")
    async def poll_for_job_status():
        job = client.jobs.get(RESOURCE_GROUP_NAME, ACCOUNT_NAME, transform_name, job_id)
        
        # Note that you can report the progress for each Job Output if you have more than one. In this case, we only have one output in the Transform
        # that we defined in this sample, so we can check that with the job.outputs[0].progress parameter.
        if job.outputs != None:
            # print(f"Job.outputs[0] is: {job.outputs[0]}")
            # print(f"Job State is: {job.state}, \tProgress: {}%")
            progress = job.outputs[0].progress
            task_status_callback(user_id, task_id, "encoding_file", f"Encoding audio file {progress}%")
            audio_progress_callback(user_id, entry_key, progress)
            update_audio_status_callback(user_id, entry_key, f"Encoding {progress}%")
        if job.state == 'Finished' or job.state == 'Error' or job.state == 'Canceled':
            return job
        elif datetime.now(timezone.utc) > timeout:
            return job
        else:
            await asyncio.sleep(sleep_interval)
            return await poll_for_job_status()

    return await poll_for_job_status()

# def upload_file_to_azure(blob_name, data, user_id=None, metadata=None):
#     blob_client = get_blob_client(blob_name, user_id)
#     blob_client.upload_blob(data, overwrite=True, metadata=metadata)
import re

def sanitize_container_name(entry_id):
    # Ensure all characters are lowercase
    sanitized_name = entry_id.lower()
    # Remove special characters except hyphen
    sanitized_name = re.sub('[^a-z0-9-]', '', sanitized_name)
    # Replace consecutive hyphens with a single hyphen
    sanitized_name = re.sub('-+', '-', sanitized_name)
    # If the string starts or ends with a hyphen, remove it
    if sanitized_name[0] == '-':
        sanitized_name = sanitized_name[1:]
    if sanitized_name[-1] == '-':
        sanitized_name = sanitized_name[:-1]
    # If the first character is not alphanumeric, prefix with 'a'
    if not sanitized_name[0].isalnum():
        sanitized_name = 'a' + sanitized_name
    # Truncate or pad to be within the allowed length
    sanitized_name = sanitized_name[:63].ljust(3, 'a')
    return sanitized_name


def create_media_service_asset(asset_name):
    client = authenticate_media_client()
    RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
    ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")
    sanitized_name = sanitize_container_name(asset_name)
    assetObj = Asset(container=sanitized_name)
    thisAsset = client.assets.create_or_update(ACCOUNT_NAME, RESOURCE_GROUP_NAME, asset_name, assetObj)
    return thisAsset

async def upload_file_to_media_service(asset_name, input_data):
# Set permissions for SAS URL and expiry time (for the sample, we used expiry time to be 1 additional hours from current time)
    print("Setting permissions for SAS URL and expiry time.")
    # Make sure that the expiry time is far enough in the future that you can keep using it until you are done testing.
    input = ListContainerSasInput(permissions="ReadWrite", expiry_time=datetime.now(timezone.utc)+timedelta(hours=24))
    print("Listing the container sas.")
    client = authenticate_media_client()
    RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
    ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")
    list_container_sas = await client.assets.list_container_sas(RESOURCE_GROUP_NAME, ACCOUNT_NAME, asset_name, parameters=input)
    if list_container_sas.asset_container_sas_urls:
        upload_sas_url = list_container_sas.asset_container_sas_urls[0]
        # file_name = os.path.basename(input_file)
        sas_uri = urlparse(upload_sas_url)

        # Get the Blob service client using the Asset's SAS URL
        blob_service_client = BlobServiceClient(upload_sas_url)
        # We need to get the container_name here from the SAS URL path to use later when creating the container client
        # Change the path to the container so that it doesn't make "subdirectories"
        # no_slash = sas_uri.path.replace("/","../")
        # container_name = no_slash
        # print(f"Container name: ", container_name)
        container_client = blob_service_client.get_container_client(container_name)
        # Next, get the block_blob_client needed to use the uploadFile method
        blob_client = container_client.get_blob_client(asset_name)
        # print(f"Block blob client: ", blob_client)

        print(f"Uploading file named {asset_name} to blob in the Asset's container...")
        print("Uploading blob...")
        # file_path = media_folder + file_name
        # print("Video is located in " + file_path)
        # with open(file_path, "rb") as data:
        await blob_client.upload_blob(input_data, max_concurrency=5)
        print(f"File {asset_name} successfully uploaded!")

    print("Closing Blob service client")
    print()
    await blob_service_client.close()

# async def download_result(asset_name, results_folder):
#     input = ListContainerSasInput(permissions="Read", expiry_time=datetime.now(timezone.utc)+timedelta(hours=24))
#     client = authenticate_media_client()
#     RESOURCE_GROUP_NAME = env.get("AZURE_MEDIA_SERVICE_RESOURCE_GROUP")
#     ACCOUNT_NAME = env.get("AZURE_MEDIA_SERVICES_ACCOUNT_NAME")
#     list_container_sas = await client.assets.list_container_sas(RESOURCE_GROUP_NAME, ACCOUNT_NAME, asset_name, parameters=input)

#     if list_container_sas.asset_container_sas_urls:
#         container_sas_url = list_container_sas.asset_container_sas_urls[0]
#         sas_uri = urlparse(container_sas_url)

#         # Get the Blob service client using the Asset's SAS URL
#         blob_service_client = BlobServiceClient(container_sas_url)
#         # We need to get the containerName here from the SAS URL path to use later when creating the container client
#         container_name = sas_uri.path.replace("/", "../")

#         directory = os.path.join(results_folder, asset_name) + '/'
#         print(f"Downloading output into {directory}")

#         # Get the blob container client using the container name on the SAS URL path
#         # to access the block_blob_client needed to use the upload_file method
#         container_client = blob_service_client.get_container_client(container_name)

#         try:
#             os.makedirs(directory, exist_ok=True)
#         except OSError as err:
#             print(err)

#         print(f"Listing blobs in container {container_name}")

#         try:
#             blob_client = container_client.get_blob_client(asset_name)
#             download_file_path = directory + os.path.basename(blob_client.blob_name)
#             try:
#                 with open(download_file_path, 'wb') as file:
#                     file_content = await blob_client.download_blob()
#                     file.write(await file_content.readall())
#                 print("Downloading results complete! Exiting the program now...")
#                 print()

#             except ResourceNotFoundError:
#                 print("No blob found.")

#         except:
#             print("There was an error listing and/or downloading the blobs.")

#     print("Closing blob service client")
#     await blob_service_client.close()
