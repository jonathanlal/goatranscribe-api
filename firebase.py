import os
import json
import firebase_admin
from dotenv import load_dotenv, find_dotenv
from firebase_admin import credentials
from firebase_admin import db

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

def create_entry_key(user_id):
    ref = db.reference(f'users/{user_id}/transcripts')
    new_entry = ref.push()
    return new_entry.key[1:]

def get_entry(user_id, entry_key):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}')
    return ref.get()

def store_transcript_info(user_id, entry_key, blob):
    blob_properties = blob.get_blob_properties()
    metadata = blob_properties.metadata
    file_type = blob_properties.content_settings.content_type
    file_size = blob_properties.size
    creation_date = blob_properties.creation_time.strftime("%Y-%m-%d %H:%M:%S")
    file_extension = '.txt'
    file_url = f"https://goatranscribe.blob.core.windows.net/{user_id}/transcript/{entry_key}"
    word_count = blob_properties.metadata['wordCount']

    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}')
    info = {
        "transcript": {
            "file_name": entry_key,
            "file_url": file_url,
            "file_type": file_type,
            "file_size": file_size,
            "word_count": word_count,
            "creation_date": creation_date
        }
    }
    ref.update(info)

def store_subtitles_info(user_id, entry_key, blob):
    blob_properties = blob.get_blob_properties()
    file_type = blob_properties.content_settings.content_type
    file_size = blob_properties.size
    creation_date = blob_properties.creation_time.strftime("%Y-%m-%d %H:%M:%S")
    file_extension = '.srt'
    file_url = f"https://goatranscribe.blob.core.windows.net/{user_id}/subtitle/{entry_key}"

    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}')
    info = {
        "subtitles": {
            "file_name": entry_key,
            "file_url": file_url,
            "file_type": file_type,
            "file_size": file_size,
            "creation_date": creation_date
        }
    }
    ref.update(info)

def store_audio_file_info(user_id, entry_key, blob):
    blob_properties = blob.get_blob_properties()
    metadata = blob_properties.metadata
    file_type = blob_properties.content_settings.content_type
    file_size = blob_properties.size
    creation_date = blob_properties.creation_time.strftime("%Y-%m-%d %H:%M:%S")
    file_name = blob_properties.metadata['fileName']
    file_extension = blob_properties.metadata['fileExtension']
    file_url = f"https://goatranscribe.blob.core.windows.net/{user_id}/audio/{entry_key}"

    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}')
    info = {
        "audio": {
            "file_name": file_name,
            "file_url": file_url,
            "file_type": file_type,
            "file_size": file_size,
            "file_extension": file_extension,
            "creation_date": creation_date
        }
    }
    ref.update(info)

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