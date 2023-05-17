# This function an HTTP starter function for Durable Functions.
# Before running this sample, please:
# - create a Durable orchestration function
# - create a Durable activity function (default name is "Hello")
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt
 
import logging
import time
from urllib.error import URLError

import azure.functions as func
import azure.durable_functions as df
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError
from urllib.request import urlopen
import json
import os
import requests


class Auth0JWTBearerTokenValidator():
    def __init__(self, domain, audience):
        self.issuer = f"https://{domain}/"
        try:
            response = requests.get(f"{self.issuer}.well-known/jwks.json")
            response.raise_for_status()
            self.public_key = JsonWebKey.import_key_set(response.json())
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to open URL: {e}")
            raise
        self.jwt = JsonWebToken('RS256')
        self.audience = audience

    def extract_and_validate(self, token):
        if not token or not token.startswith("Bearer "):
            return None
        return self.validate(token[7:])

    def validate(self, token):
        try:
            claims = self.jwt.decode(
                token, 
                self.public_key
            )
            if not self._validate_claims(claims):
                return None
            return claims
        except JoseError as e:
            logging.error(f"Token validate failed: {e}")
            return None

    def _validate_claims(self, claims):
        if time.time() > claims.get('exp', 0):
            return False
        aud = claims.get('aud', '')
        if isinstance(aud, list):
            if self.audience not in aud:
                return False
        else:
            if self.audience != aud:
                return False
        if self.issuer != claims.get('iss', ''):
            return False
        return True


async def main(req: func.HttpRequest, starter: str) -> func.HttpResponse:
    validator = Auth0JWTBearerTokenValidator(os.getenv("AUTH0_DOMAIN"), os.getenv("AUTH0_IDENTIFIER"))
    claims = validator.extract_and_validate(req.headers.get("Authorization"))

    if not claims:
        logging.error(f"Authorization validation failed.")
        return func.HttpResponse("Unauthorized", status_code=401)

    user_sub = claims.get('sub')

    data = req.get_json()
    data["user_id"] = user_sub.replace('|', '')
    data["user_sub"] = user_sub

    client = df.DurableOrchestrationClient(starter)
    instance_id = await client.start_new(req.route_params["functionName"], None, data)

    logging.info(f"Started orchestration with ID = '{instance_id}'.")

    return client.create_check_status_response(req, instance_id)