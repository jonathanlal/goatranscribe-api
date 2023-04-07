from os import environ as env
from dotenv import load_dotenv, find_dotenv
from flask import Flask, request, jsonify
from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
from validator import Auth0JWTBearerTokenValidator
from create_container import create_container_and_generate_sas, get_blob_sas
from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas


ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

require_auth = ResourceProtector()
validator = Auth0JWTBearerTokenValidator(env.get("AUTH0_DOMAIN"), env.get("AUTH0_IDENTIFIER"))
require_auth.register_token_validator(validator)

app = Flask(__name__)
# app.debug = True

# access tokens with an Auth0 API audience, excluding the /userinfo endpoint, cannot have private, non-namespaced custom claims
# https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-token-claims 
def getUserID(token):
    sub_value = token.get('sub', '')
    return sub_value.replace('|', '')

@app.route('/')
def index():
    return jsonify('goatranscribe api')

@app.route("/api/public", methods=["POST"])
def public():
    """No access token required."""
    response = (
        "Hello from a public endpoint! You don't need to be"
        " authenticated to see this."
    )
    return jsonify({"message": response})

@app.route("/api/private", methods=["POST"])
@require_auth(None)
def private():
    """A valid access token is required."""
    response = (
        "Hello from a private endpoint! You need to be"
        " authenticated to see this."
    )
    return jsonify(message=response)

@app.route("/api/private-scoped", methods=["POST"])
@require_auth("read:messages")
def private_scoped():
    """A valid access token and scope are required."""
    response = (
        "Hello from a private endpoint! You need to be"
        " authenticated and have a scope of read:messages to see"
        " this."
    )
    return jsonify(message=response)

#checks if the container exists and creates it if necessary. Then, generate a SAS token for the container and return it to the client.
@app.route("/api/sasUrl", methods=["POST"])
@require_auth('openid')
def sasUrl():

    # Call the create_container_and_generate_sas function to ensure the container exists and get the SAS token
    sas_token = create_container_and_generate_sas(getUserID(current_token))

    # Generate the SAS URL for the container
    connection_string = env.get("AZURE_STORAGE_CONNECTION_STRING")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    account_url = blob_service_client.primary_endpoint
    sas_url = f"{account_url}?{sas_token}"

    # Return the SAS URL to the client
    response = {
        "message": "Generated SAS URL for container.",
        "sasUrl": sas_url
    }
    return jsonify(response)


#returns CDN url with SAS token for a specific file
@app.route("/api/sasToken", methods=["POST"])
@require_auth(None)
def sasToken():
    blob_name = request.json['fileName']
    print(blob_name)
    container_name = getUserID(current_token)
    sas_token = get_blob_sas(container_name, blob_name)
    #change url to custom domain url after fixing https
    url = 'https://goatranscribe.azureedge.net/'+container_name+'/'+blob_name+'?'+sas_token
    response = {
        "message": "Generated SAS URL for File.",
        "sasUrl": url
    }
    return jsonify(response)

if __name__ == "__main__":
    app.run()