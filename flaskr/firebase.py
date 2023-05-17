import math
import os
import json
import firebase_admin
from dotenv import load_dotenv, find_dotenv
from firebase_admin import credentials
from firebase_admin import db
from authlib.integrations.flask_oauth2 import current_token
from flaskr.auth import getUserID
from flaskr.azure import get_blob_client

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

service_account_json = os.environ['FIREBASE_SERVICE_ACCOUNT']
service_account_info = json.loads(service_account_json)

# Initialize the Firebase Admin SDK
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://goatranscribe-default-rtdb.europe-west1.firebasedatabase.app/'
})

def get_audio_info(entry_key, user_id):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/audio')
    audio_info = ref.get()
    return audio_info

def create_entry_key(user_id):
    ref = db.reference(f'users/{user_id}/transcripts')
    new_entry = ref.push()
    return new_entry.key[1:]

def get_entry(user_id, entry_key):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}')
    return ref.get()

def update_audio_status(user_id, entry_key, new_status):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/audio')
    ref.update({"status": new_status})


def store_file_info(entry_key, file_category, user_id=None):
    if user_id is None:
        user_id = getUserID(current_token)

    blob = get_blob_client(f"{file_category}/{entry_key}", user_id)
    blob_properties = blob.get_blob_properties()
    metadata = blob_properties.metadata
    file_type = blob_properties.content_settings.content_type
    file_size = blob_properties.size
    creation_date = blob_properties.creation_time.strftime("%Y-%m-%d %H:%M:%S")
    file_url = f"https://goatranscribe.blob.core.windows.net/{user_id}/{file_category}/{entry_key}"

    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}')
    info = {
        file_category: {
            "file_name": entry_key,
            "file_url": file_url,
            "file_type": file_type,
            "file_size": file_size,
            "creation_date": creation_date,
        }
    }

    if file_category == "transcript":
        info[file_category]["word_count"] = metadata['wordCount']
    elif file_category == "audio":
        info[file_category]["file_name"] = metadata['fileName']
        info[file_category]["file_extension"] = metadata['fileExtension']
        info[file_category]["duration"] = metadata['duration']
        info[file_category]["status"] = "pending"

    ref.update(info)


def store_payment_intent(user_id, payment_id):
    ref = db.reference(f'users/{user_id}/payments')
    new_payment = ref.push()
    new_payment.set({
        "payment_id": payment_id
    })

def check_payment_intent_exists(user_id, payment_id):
    ref = db.reference(f'users/{user_id}/payments')
    payments = ref.get()

    if payments:
        for payment_key, payment_data in payments.items():
            if payment_data.get('payment_id') == payment_id:
                return True
    return False

COST_PER_MINUTE = 0.017  # dollars per minute
COST_PER_SECOND = COST_PER_MINUTE / 60  # dollars per second


def get_entry_by_id(user_id, entry_id):
    ref = db.reference(f'users/{user_id}/transcripts')
    entry = ref.child(entry_id).get()

    if not isinstance(entry, dict):
        print(f"Warning: entry_data for key {entry_id} is not a dictionary.")
        return None
    
    return entry



def get_uploads(user_id):
    ref = db.reference(f'users/{user_id}/transcripts')
    transcripts = ref.get()

    incomplete_uploads = []
    if transcripts:
        for entry_key, entry_data in transcripts.items():
            if not isinstance(entry_data, dict):
                print(f"Warning: entry_data for key {entry_key} is not a dictionary.")
                continue
            if 'transcript' not in entry_data:
                audio = entry_data.get('audio')
                if audio is not None:
                    duration = float(audio.get("duration", 0))
                    if duration > 0:
                        estimated_cost = duration * COST_PER_SECOND
                        rounded_estimated_cost = round(math.ceil(estimated_cost * 100) / 100, 2)
                    else:
                        rounded_estimated_cost = 0
                    
                    incomplete_uploads.append({
                        "entry_id": entry_key.replace('-', '', 1), # careful with this shit holy crap... only remove first '-'
                        "creation_date": audio["creation_date"],
                        "file_type": audio["file_type"],
                        "file_size": audio["file_size"],
                        "file_name": audio["file_name"],
                        "file_extension": audio["file_extension"],
                        "file_url": audio["file_url"],
                        "duration": duration,
                        "cost": rounded_estimated_cost,
                        "status": audio["status"] 
                    })
                else:
                    continue
    return incomplete_uploads

# def store_file_info(user_id, audio_info=None, transcript_info=None, subtitles_info=None):
#     ref = db.reference(f'users/{user_id}/transcripts')

#     # Create an empty dictionary for file information
#     info = {}

#     # Add file information for each type if provided
#     if audio_info:
#         info["audio"] = audio_info
#     if transcript_info:
#         info["transcript"] = transcript_info
#     if subtitles_info:
#         info["subtitles"] = subtitles_info

#     # Push the info dictionary to the user's transcripts node
#     ref.push(info)

# Usage
# user_id = 'example_user_id'
# file_name = 'example_filename.txt'
# file_size = 123456
# file_url = 'aweadadsasdasdasd.com'
# file_type = 'test'
# creation_date = '2023-04-07T12:34:56'
# word_count = 1234
# entry_key = '-NSaAs2QUov0M-hTaMau'
# entry_key = create_entry_key(user_id)
# store_audio_file_info(user_id, entry_key, file_name, file_size, file_url, file_type, creation_date)
# store_transcript_info(user_id, entry_key, file_name, file_size, file_url, file_type, word_count, creation_date)
# store_subtitles_info(user_id, entry_key, file_name, file_size, file_url, file_type, creation_date)
# user_id = 'github13243000'
# entry_key = '-NSaAs2QUov0M-hTaMau'
# print(get_entry(user_id, entry_key))
# store_file_info(user_id, audio_info={"file_name": file_name, "file_size": file_size, "file_url": file_url, "file_type": file_type, "creation_date": creation_date}, transcript_info={"file_name": file_name, "file_size": file_size, "file_url": file_url, "file_type": file_type, "word_count": word_count, "creation_date": creation_date}, subtitles_info={"file_name": file_name, "file_size": file_size, "file_url": file_url, "file_type": file_type, "creation_date": creation_date})