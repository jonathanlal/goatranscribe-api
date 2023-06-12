from flask import Blueprint, request, jsonify
from authlib.integrations.flask_oauth2 import ResourceProtector
from os import environ as env
from auth0.authentication import GetToken
from auth0.management import Auth0
from authlib.integrations.flask_oauth2 import current_token
import json
from urllib.request import urlopen

from authlib.oauth2.rfc7523 import JWTBearerTokenValidator
from authlib.jose.rfc7517.jwk import JsonWebKey
import firebase_admin
from firebase_admin import credentials


bp = Blueprint("auth", __name__)

class Auth0JWTBearerTokenValidator(JWTBearerTokenValidator):
    def __init__(self, domain, audience):
        issuer = f"https://{domain}/"
        jsonurl = urlopen(f"{issuer}.well-known/jwks.json")
        public_key = JsonWebKey.import_key_set(
            json.loads(jsonurl.read())
        )
        super(Auth0JWTBearerTokenValidator, self).__init__(
            public_key
        )
        self.claims_options = {
            "exp": {"essential": True},
            "aud": {"essential": True, "value": audience},
            "iss": {"essential": True, "value": issuer},
        }


require_auth = ResourceProtector()
validator = Auth0JWTBearerTokenValidator(env.get("AUTH0_DOMAIN"), env.get("AUTH0_IDENTIFIER"))
require_auth.register_token_validator(validator)



# access tokens with an Auth0 API audience, excluding the /userinfo endpoint, cannot have private, non-namespaced custom claims
# https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-token-claims 
def getUserID(token):
    if not token:
        return 'try'
    sub_value = token.get('sub', '')
    return sub_value.replace('|', '')


def getAuth0Client():
    domain = env.get("AUTH0_DOMAIN")
    get_token = GetToken(domain, env.get("AUTH0_CLIENT_ID"), client_secret=env.get("AUTH0_CLIENT_SECRET"))
    token = get_token.client_credentials('https://{}/api/v2/'.format(domain))
    return Auth0(domain, token.get('access_token'))    

def getUserAppMetadata(user_sub):
    auth0 = getAuth0Client()
    return auth0.users.get(user_sub)['app_metadata']

def getUserEmail(user_sub):
    auth0 = getAuth0Client()
    return auth0.users.get(user_sub)['email']

# @bp.route("/refresh_token", methods=["POST"])
# def refresh_token():
#     client_id = env.get("AUTH0_CLIENT_ID")
#     client_secret = env.get("AUTH0_CLIENT_SECRET")
#     refresh_token = request.json.get("refresh_token")

#     get_token = GetToken(env.get("AUTH0_DOMAIN"))
#     try:
#         token = get_token.refresh_token(
#             client_id, client_secret, refresh_token
#         )
#         return jsonify(token)
#     except Exception as e:
#         return jsonify({"error": str(e)}), 400

# def get_user_metadata():
#     # Get the user_id from the current_token
#     user_id = current_token["sub"]

#     # Set the API URL to get the user's information from Auth0
#     api_url = f'https://{AUTH0_DOMAIN}/api/v2/users/{user_id}'

#     # Set the headers with the access token
#     headers = {
#         'Authorization': f'Bearer {current_token.access_token}'
#     }

#     # Make a GET request to the Auth0 API
#     response = requests.get(api_url, headers=headers)

#     if response.status_code == 200:
#         # If the request was successful, retrieve the user_metadata
#         user_data = response.json()
#         user_metadata = user_data.get('user_metadata', {})
#         return user_metadata
#     else:
#         # Handle errors here
#         return None