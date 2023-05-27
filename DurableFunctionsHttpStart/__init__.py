# This function an HTTP starter function for Durable Functions.
# Before running this sample, please:
# - create a Durable orchestration function
# - create a Durable activity function (default name is "Hello")
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt
 
import logging
import math
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

from flaskr.firebase import COST_PER_CHARACTER, COST_PER_SECOND, check_already_transcribed, get_audio_info, get_transcript_info, store_transaction_info
from flaskr.stripe import get_balance, update_balance


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
        # logging.error(f"Authorization validation failed.")
        return func.HttpResponse("Unauthorized", status_code=401)

    user_sub = claims.get('sub')

    data = req.get_json()
    user_id = user_sub.replace('|', '')
    data["user_id"] = user_id
    data["user_sub"] = user_sub

    balance_in_cents = get_balance(user_sub)

    total_cost_in_cents = 0

    task_type = data["task_type"]
    if task_type == "transcribe":
        # for each entry get cost
        non_transcribed_keys = []
        for entry_key in data['entryKeys']:
            already_transcribed = check_already_transcribed(user_id, entry_key)
            if already_transcribed is False:
                audio_info = get_audio_info(entry_key, user_id)
                audio_duration = float(audio_info["duration"])
                cost_in_cents = math.ceil(audio_duration * COST_PER_SECOND * 100)
                total_cost_in_cents += cost_in_cents
                non_transcribed_keys.append(entry_key)

        data['entryKeys'] = non_transcribed_keys
    elif task_type == "translate":
         # for each entry get cost
        # non_translated_langs = []
        #for the moment user will only pass 1 entry key
        for entry_key in data['entryKeys']:
            transcript_info = get_transcript_info(entry_key, user_id)
            translations = transcript_info.get("translations") # ["fr", "de", "es" etc..]
            if translations is None:
                translations = []
            target_langs = data['targetLangs'] # ["ch", "fr", "de" etc..]
            # if targetLang already exists in translations, remove targetLang from targetLangs
            target_langs = [lang for lang in target_langs if lang not in translations]

            transcript_chars = int(transcript_info.get("char_count"))
            translation_cost_per_lang_in_cents = math.ceil(transcript_chars * COST_PER_CHARACTER * 100)  # cost in cents for one language
            total_cost_in_cents += translation_cost_per_lang_in_cents * len(target_langs)  # multiply by the number of target languages
            data['targetLangs'] = target_langs


    if(balance_in_cents < total_cost_in_cents):
        return func.HttpResponse("Not enough funds in account", status_code=402)
    
    new_balance = balance_in_cents - total_cost_in_cents
    stripe_balance = update_balance(new_balance, user_sub)
 
    # #this should never happen
    if(stripe_balance != new_balance):
        return func.HttpResponse("Balance mismatch, contact support", status_code=402)

    client = df.DurableOrchestrationClient(starter)
    instance_id = await client.start_new(req.route_params["functionName"], None, data)

    logging.info(f"Started orchestration with IDENTIFICATION = '{instance_id}'.")

    return client.create_check_status_response(req, instance_id)