from flask import Blueprint
from authlib.integrations.flask_oauth2 import ResourceProtector
from os import environ as env
from auth0.authentication import GetToken
from auth0.management import Auth0
import json
from urllib.request import urlopen
from authlib.oauth2.rfc7523 import JWTBearerTokenValidator
from authlib.jose.rfc7517.jwk import JsonWebKey


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