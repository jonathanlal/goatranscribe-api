from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=['http://localhost:3000'])  # Replace with the client app's origin
load_dotenv()

def check_and_create_container(blob_service_client, container_name):
    container_client = blob_service_client.get_container_client(container_name)

    try:
        container_client.get_container_properties()
        return True
    except ResourceNotFoundError:
        container_client.create_container()
        return False

def upload_file_to_azure_blob(account_url, account_key, container_name, file):
    # Create a BlobServiceClient object
    blob_service_client = BlobServiceClient(account_url=account_url, credential=account_key)

    # Check and create container if it doesn't exist
    check_and_create_container(blob_service_client, container_name)

    # Get the container client
    container_client = blob_service_client.get_container_client(container_name)

    # Get the blob client
    blob_name = file.filename
    blob_client = container_client.get_blob_client(blob_name)

    # Upload the file
    blob_client.upload_blob(file)

    # Return the uploaded file URL
    return blob_client.url

@app.route('/upload', methods=['POST'])
def upload_file():
    # Get the file & container_name from the request
    file = request.files.get('file')
    container_name = request.form.get('container_name')

    # Set your Azure Storage account URL, key, and container name
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    account_key = os.getenv("AZURE_STORAGE_KEY")
    # container_name = "test"

    # Upload the file to Azure Blob Storage
    file_url = upload_file_to_azure_blob(account_url, account_key, container_name, file)

    # Return a JSON response with the uploaded file URL
    return jsonify({"file_url": file_url})
    # return jsonify({"file_url": "wtf"})

if __name__ == '__main__':
    app.run()
