import math
import os
import json
import firebase_admin
from dotenv import load_dotenv, find_dotenv
from firebase_admin import credentials, db, auth
from authlib.integrations.flask_oauth2 import current_token
from flaskr.auth import getUserID
from flaskr.azure import get_blob_client
import datetime

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

def create_custom_token(user_id):
    # additional_claims = {
    #     'premiumAccount': True
    # }
    custom_token = auth.create_custom_token(user_id)
    # print('customToken: ', custom_token)
    return custom_token


def get_audio_info(entry_key, user_id):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/audio')
    audio_info = ref.get()
    return audio_info

def get_transcript_info(entry_key, user_id):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/transcript')
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

def update_audio_lang(user_id, entry_key, lang, iso):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/audio')
    ref.update({"language": lang, "iso": iso})

# for subtitles: users/user_id/transcripts/-entry_key/translations/subtitles/en
# for transcript: users/user_id/transcripts/-entry_key/translations/transcript/en
def store_subtitles_translation_info(entry_key, target_lang, user_id=None):
    if user_id is None:
        user_id = getUserID(current_token)

    blob = get_blob_client(f"subtitle/{entry_key}-{target_lang}", user_id)
    blob_properties = blob.get_blob_properties()
    file_type = blob_properties.content_settings.content_type
    file_size = blob_properties.size
    creation_date = blob_properties.creation_time.strftime("%Y-%m-%d %H:%M:%S")
    file_url = f"https://goatranscribe.blob.core.windows.net/{user_id}/subtitle/{entry_key}-{target_lang}"

    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/translation/subtitle/{target_lang}')
    info = {
        "file_name": entry_key,
        "file_url": file_url,
        "file_type": file_type,
        "file_size": file_size,
        "creation_date": creation_date,
    }

    ref.update(info)

def store_transcript_translation_info(entry_key, target_lang, user_id=None):
    if user_id is None:
        user_id = getUserID(current_token)

    blob = get_blob_client(f"transcript/{entry_key}-{target_lang}", user_id)
    blob_properties = blob.get_blob_properties()
    file_type = blob_properties.content_settings.content_type
    file_size = blob_properties.size
    creation_date = blob_properties.creation_time.strftime("%Y-%m-%d %H:%M:%S")
    file_url = f"https://goatranscribe.blob.core.windows.net/{user_id}/transcript/{entry_key}-{target_lang}"

    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/translation/transcript/{target_lang}')
    info = {
        "file_name": entry_key,
        "file_url": file_url,
        "file_type": file_type,
        "file_size": file_size,
        "creation_date": creation_date,
    }

    ref.update(info)

def update_transcript_translations(user_id, entry_key, new_lang):
    ref = db.reference(f'users/{user_id}/transcripts/-{entry_key}/transcript')
    data = ref.get()
    translations = data.get("translations", [])
    translations.append(new_lang)
    ref.update({"translations": translations})

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
        info[file_category]["char_count"] = metadata['charCount']
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


def create_task_entry_key(user_id, task_type, entry_key, file_name):
    ref = db.reference(f'users/{user_id}/tasks')
    new_entry = ref.push()
    date_started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry.set({
        "file_name": file_name,
        "date_started": date_started,
        "task_type": task_type,
        "entry_key": entry_key,
        "status": "started",
        "seen": False
    })
    return new_entry.key[1:]

def mark_task_as_seen(user_id, entry_key):
    ref = db.reference(f'users/{user_id}/tasks')
    tasks = ref.get()

    if tasks:
        for task_id, task_data in tasks.items():
            if task_data.get('entry_key') == entry_key and not task_data.get('seen'):
                task_ref = db.reference(f'users/{user_id}/tasks/{task_id}')
                task_ref.update({"seen": True})

def mark_tasks_as_seen(user_id, task_ids):
    ref = db.reference(f'users/{user_id}/tasks')
    tasks = ref.get()

    if tasks:
        for task_id in task_ids:
            task_data = tasks.get(task_id)
            if task_data and not task_data.get('seen'):
                task_ref = db.reference(f'users/{user_id}/tasks/{task_id}')
                task_ref.update({"seen": True})

def get_transcript_time_taken(user_id, entry_key):
    ref = db.reference(f'users/{user_id}/tasks')
    tasks = ref.get()

    if tasks:
        for task_id, task_data in tasks.items():
            if task_data.get('entry_key') == entry_key and task_data.get('task_type') == 'transcribe':
                return task_data.get('time_taken')

def update_task_status(user_id, task_id, status, description=None, time_taken=None):
    ref = db.reference(f'users/{user_id}/tasks/-{task_id}')
    updates = {"status": status}
    if description:
        updates["description"] = description
    if time_taken:
        updates["time_taken"] = time_taken

    ref.update(updates)

def check_already_transcribed(user_id, entry_key):
    ref = db.reference(f'users/{user_id}/tasks')
    tasks = ref.get()

    if tasks:
        for task_id, task_data in tasks.items():
            if task_data.get('task_type') == 'transcribe' and task_data.get('entry_key') == entry_key:
                return True
    return False


def get_tasks(user_id):
    ref = db.reference(f'users/{user_id}/tasks')
    tasks = ref.get()

    all_tasks = []
    if tasks:
        for task_key, task_data in tasks.items():
            if not isinstance(task_data, dict):
                print(f"Warning: task_data for key {task_key} is not a dictionary.")
                continue
            all_tasks.append({
                "file_name": task_data["file_name"],
                "status": task_data["status"],
                "entry_key": task_data["entry_key"],
                "task_type": task_data["task_type"],
                "date_started": task_data["date_started"],
                "seen": task_data["seen"],
            })
    return all_tasks

def store_transaction_info(user_id, transaction_type, amount, new_balance):
    ref = db.reference(f'users/{user_id}/transactions')
    new_entry = ref.push()
    if transaction_type == "transcribe":
        description = "Transcribe audio file"
        is_cost = True
    elif transaction_type == "translate":
        description = "Translate transcript"
        is_cost = True
    elif transaction_type == "add_funds":
        description = "Add funds to wallet"
        is_cost = False
    elif transaction_type == "summary":
        description = "Summary of transcript"
        is_cost = True
    elif transaction_type == "paragraph":
        description = "Generate paragraphs in transcript"
        is_cost = True
    else:
        description = "unknown type"

    new_entry.set({
        "description": description,
        "amount": amount,
        "new_balance": new_balance,
        "is_cost": is_cost
    })

def get_transactions(user_id):
    ref = db.reference(f'users/{user_id}/transactions')
    transactions = ref.get()

    all_transactions = []
    if transactions:
        for transaction_key, transaction_data in transactions.items():
            if not isinstance(transaction_data, dict):
                print(f"Warning: transaction_data for key {transaction_key} is not a dictionary.")
                continue
            all_transactions.append({
                "description": transaction_data["description"],
                "amount": transaction_data["amount"],
                "new_balance": transaction_data["new_balance"],
                "is_cost": transaction_data["is_cost"],
            })
    return all_transactions



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
COST_PER_CHARACTER = 10 / 500_000

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
            # if 'transcript' not in entry_data:
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
                    "status": audio["status"],
                    "language": audio.get("language"),
                    "iso": audio.get("iso")
                })
                # else:
                #     continue
    return incomplete_uploads