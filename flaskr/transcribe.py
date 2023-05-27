import json
import math
from flask import Blueprint, request, jsonify
from authlib.integrations.flask_oauth2 import current_token
import openai
import requests
from .auth import require_auth, getUserID
from os import environ as env
import os
import srt
from azure.storage.blob import BlobServiceClient
from flaskr.firebase import COST_PER_SECOND, create_custom_token, create_entry_key, get_audio_info, get_entry, get_entry_by_id, get_tasks, get_transcript_time_taken, get_uploads, mark_task_as_seen, mark_tasks_as_seen, store_file_info
from firebase_admin import db
from flaskr.azure import download_file_from_azure, file_exists_azure, get_blob_client, get_container_sas, getBlobUrl, upload_file_to_azure
from pydub import AudioSegment
import tempfile
import nltk
from nltk.tokenize import word_tokenize

nltk.download('punkt')

bp = Blueprint("transcribe", __name__)

functions_url = env.get("FUNCTIONS_URL")


@bp.route("/init_firebase_auth", methods=["POST"])
@require_auth(None)
def init_firebase_auth():
    user_id = getUserID(current_token)
    firebase_token = create_custom_token(user_id)
    return jsonify(firebase_token.decode())

@bp.route("/transcript_seen", methods=["POST"])
@require_auth(None)
def transcript_seen():
    user_id = getUserID(current_token)
    mark_task_as_seen(user_id, request.json['entryKey'])
    return jsonify({"message": "Transcript marked as seen."})

@bp.route("/transcripts_seen", methods=["POST"])
@require_auth(None)
def transcripts_seen():
    user_id = getUserID(current_token)
    mark_tasks_as_seen(user_id, request.json['taskIds'])
    return jsonify({"message": "Transcripts marked as seen."})

def extract_text_from_srt(subtitles):
    text_content = ' '.join([subtitle.content for subtitle in subtitles])
    return text_content

def transcribe_audio(audio_file):
    # verbose = None
    # temperature = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    # compression_ratio_threshold = 2.4
    # logprob_threshold = -1.0
    # no_speech_threshold = 0.6
    # condition_on_previous_text = True
    # initial_prompt = None
    word_timestamps = True
    # prepend_punctuations = "\"'“¿([{-"
    # append_punctuations = "\"'.。,，!！?？:：”)]}、"
    
    transcript = openai.Audio.transcribe(
        model="whisper-1",
        file=audio_file,
        word_timestamps=word_timestamps,
        response_format="srt"
    )
    
    # print(transcript)
    return transcript


def subtitle_to_dict(subtitle):
    return {
        'section': subtitle.index,
        'startTime': str(subtitle.start),
        'endTime': str(subtitle.end),
        'text': subtitle.content
    }

# transcribe should be srt format
def createTranscribeResponse(blob_name, subtitles, transcript):
    container_name = getUserID(current_token)
    response = {
        'url': {
            'audio': getBlobUrl(container_name, 'audio/'+blob_name),
            'srt': getBlobUrl(container_name, 'subtitle/'+blob_name),
            'txt': getBlobUrl(container_name, 'transcript/'+blob_name),
        },
        'subtitles': subtitles,
        'transcript': transcript
    }
    # return jsonify({'audio': getBlobUrl(container_name, blob_name), 'subtitles': subs_dicts, 'transcript': text})
    return jsonify(response)


def getCost(file_duration):
        # get cost of transcript 
    duration = float(file_duration)
    #remove this if after testing/developing
    if duration > 0:
        estimated_cost = duration * COST_PER_SECOND
        rounded_estimated_cost = round(math.ceil(estimated_cost * 100) / 100, 2)
    else:
        rounded_estimated_cost = 0
    return rounded_estimated_cost


# @bp.route("/test", methods=["POST"])
# def test():
#     # entry_key = 'NV_YH6aYZGzPrbvHN8R'
#     entry_key = request.args.get('entry_key')
#     user_id = 'github13243000'

#     try:
#         info = get_audio_info(entry_key, user_id)
#     except Exception as e:
#         print('error: ', e)

#     return jsonify(info)
@bp.route("/tasks", methods=["POST"])
@require_auth(None)
def userTasks():
    user_id = getUserID(current_token)
    tasks = get_tasks(user_id)
    return jsonify(tasks)


@bp.route("/transcribeStatus", methods=["POST"])
@require_auth(None)
def check_transcribe_status():
    instance_id = request.json['instanceId']
    # Retrieve the status of the Durable Function using the instance ID
    # Implement the logic to fetch the status based on the instance ID
    url = f"{functions_url}runtime/webhooks/durabletask/instances/{instance_id}" # might need to add the other params to the url
    response = requests.get(url)
    responseJson = json.loads(response.text)
    print(responseJson)
    status = responseJson['runtimeStatus']
    output = responseJson['output']

    return jsonify({"status": status, "output": output})


@bp.route("/translate", methods=["POST"])
@require_auth(None)
def translate():
    entry_keys = request.json['entryKeys']
    target_langs = request.json['targetLangs']

    authorization_header = request.headers.get('Authorization')
    if authorization_header:
        access_token = authorization_header.split(' ')[1]  # Assuming "Bearer <access_token>" format
    else:
        return jsonify({"error": "Missing access token"}), 401
    # print(access_token)

    # make post request here with access token in authorization_header and entry_keys in body
    url = f"{functions_url}api/orchestrators/TaskOrchestrator"
    headers = {'Authorization': 'Bearer ' + access_token}
    data = {'entryKeys': entry_keys, 'task_type': 'translate', 'targetLangs': target_langs}
    response = requests.post(url, headers=headers, json=data)
    # print(response.text)

    # Check the response status
    if response.status_code == 202:
        # status_url = json.loads(response.text)['statusQueryGetUri']
        instanceId = json.loads(response.text)['id']
        # print(status_url)
        #instead of returning instanceId, we should create in firebase tasks/instanceId and update status there
        return jsonify({"message": "Request sent successfully", "instanceId": instanceId}), 202
    else:
        return jsonify({"error": "Failed to send request"}), response.status_code

@bp.route("/transcribe", methods=["POST"])
@require_auth(None)
def transcribe():
    # openai.api_key = env.get("OPENAI_API_KEY")
    entry_keys = request.json['entryKeys']

    authorization_header = request.headers.get('Authorization')
    if authorization_header:
        access_token = authorization_header.split(' ')[1]  # Assuming "Bearer <access_token>" format
    else:
        return jsonify({"error": "Missing access token"}), 401
    # print(access_token)

    # make post request here with access token in authorization_header and entry_keys in body
    url = f"{functions_url}api/orchestrators/TaskOrchestrator"
    headers = {'Authorization': 'Bearer ' + access_token}
    data = {'entryKeys': entry_keys, 'task_type': 'transcribe'}
    response = requests.post(url, headers=headers, json=data)
    # print(response.text)

    # Check the response status
    if response.status_code == 202:
        # status_url = json.loads(response.text)['statusQueryGetUri']
        instanceId = json.loads(response.text)['id']
        # print(status_url)
        #instead of returning instanceId, we should create in firebase tasks/instanceId and update status there
        return jsonify({"message": "Request sent successfully", "instanceId": instanceId}), 202
    else:
        return jsonify({"error": "Failed to send request"}), response.status_code


    # transcript_file_name = f"transcript/{blob_name}"
    # subtitle_file_name = f"subtitle/{blob_name}"
    # audio_file_name = f"audio/{blob_name}"

    # get file info from firebase
    # entry = get_entry_by_id(getUserID(current_token), blob_name)
    # audio_data = entry['audio']

    # print(entry_keys)
    # return jsonify(entry_keys)
    



        # inside task worker we send email when finished and update usfer balance in stripe



    # user_id = getUserID(current_token)

    # audio_file = download_file_from_azure(audio_file_name)
    # file_properties = get_blob_client(audio_file_name).get_blob_properties().metadata
    # file_extension = file_properties['fileExtension']
    # duration = 


    
    # if file_exists_azure(subtitle_file_name):
    #     subtitles = download_file_from_azure(subtitle_file_name).content_as_text()
    #     transcript = download_file_from_azure(transcript_file_name).content_as_text()
    #     subs = list(srt.parse(subtitles))
    #     subs_dicts = [subtitle_to_dict(sub) for sub in subs]
    #     return createTranscribeResponse(blob_name, subs_dicts, transcript)

    # # Transcribe the audio file
    # if audio_file.size > 25 * 1024 * 1024:
    #     # Split the audio file
    #     song = AudioSegment.from_file(audio_file.content_as_bytes())
    #     chunk_size = 5 * 60 * 1000  # 5 minutes in milliseconds
    #     parts = [song[i:i + chunk_size] for i in range(0, len(song), chunk_size)]
        
    #     # Transcribe and upload each part
    #     transcripts = []
    #     for idx, part in enumerate(parts):
    #         part_name = f"{blob_name}_part_{idx+1}{file_extension}"
    #         part.export(part_name, format="mp3")
            
    #         # Upload audio part to Azure
    #         audio_part_blob_name = f"{blob_name}/part_{idx+1}{file_extension}"
            
    #         with open(part_name, "rb") as audio_part:
    #             upload_file_to_azure(audio_part_blob_name, audio_part)

    #         # Check if transcript part exists
    #         transcript_part_blob_name = f"{blob_name}/part_{idx+1}.srt"

    #         if not file_exists_azure(transcript_part_blob_name):
    #             with open(part_name, "rb") as audio_part:
    #                 transcript_part = transcribe_audio(audio_part)
    #             upload_file_to_azure(transcript_part_blob_name, transcript_part)
            
    #         transcript_part = download_file_from_azure(transcript_part_blob_name).content_as_text()
    #         os.remove(part_name)
    #         transcripts.append(transcript_part)
        
    #     # Stitch the transcripts and upload to Azure
    #     full_transcript = "\n".join(transcripts)
    #     upload_file_to_azure(subtitle_file_name, full_transcript)
    # else:
    #     audio_content = audio_file.content_as_bytes()
    #     with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
    #         tmp_file.write(audio_content)
    #         tmp_file.seek(0)
    #         subtitles = transcribe_audio(tmp_file)

    #     os.remove(tmp_file.name)
    #     upload_file_to_azure(subtitle_file_name, subtitles)
    #     store_file_info(blob_name, 'subtitle')


    #     subs = list(srt.parse(subtitles))
    #     transcript = extract_text_from_srt(subs)
    #     subs_dicts = [subtitle_to_dict(sub) for sub in subs]
    #     tokens = word_tokenize(transcript)
    #     word_count = len(tokens)
    #     metadata = {
    #         'wordCount': str(word_count)
    #     }
    #     upload_file_to_azure(transcript_file_name, transcript, metadata=metadata) #upload text transcript to azure
    #     store_file_info(blob_name, ')
    
    # return createTranscribeResponse(blob_name, subs_dicts, transcript)

def get_user_transcripts(user_id):
    transcripts_ref = db.reference(f"users/{user_id}/transcripts")
    transcripts_data = transcripts_ref.get()
    # print(transcripts_data)
    if transcripts_data is None:
        return []

    results = []
    for transcript_id, transcript_info in transcripts_data.items():
        if "transcript" in transcript_info:
            results.append({
                "entry_id": transcript_id.lstrip('-'),
                "file_name": transcript_info["audio"]["file_name"],
                "creation_date": transcript_info["transcript"]["creation_date"],
                "word_count": transcript_info["transcript"]["word_count"]
            })

    return results

@bp.route("/userTranscripts", methods=["POST"])
@require_auth(None)
def userTranscripts():
    user_id = getUserID(current_token)
    transcripts = get_user_transcripts(user_id)
    return jsonify(transcripts)

@bp.route("/newEntry", methods=["POST"])
@require_auth(None)
def newEntry():
    entry_key = create_entry_key(getUserID(current_token))
    response = {
        "message": "Entry key created.",
        "entryKey": entry_key
    }
    return jsonify(response)

@bp.route("/uploadComplete", methods=["POST"])
@require_auth(None)
def uploadComplete():
    entry_key = request.json['entryKey']
    store_file_info(entry_key, "audio")
    response = {
        "message": "Audio data saved.",
    }
    return jsonify(response)

@bp.route("/sasToken", methods=["POST"])
@require_auth(None)
def sasToken():
    blob_name = request.json['fileName']
    container_name = getUserID(current_token)
    response = {
        "message": "Generated SAS URL for File.",
        "sasUrl": getBlobUrl(container_name, blob_name)
    }
    return jsonify(response)

# @bp.route("/private", methods=["POST"])
# @require_auth(None)
# def private():
#     # ... code for private function ...

# @bp.route("/private-scoped", methods=["POST"])
# @require_auth("read:messages")
# def private_scoped():
#     # ... code for private_scoped function ...

# @bp.route("/sasUrl", methods=["POST"])
# @require_auth(None)
# def sasUrl():
#     sas_url = get_container_sas()
#     entry_key = create_entry_key(getUserID(current_token))
#     response = {
#         "message": "Generated SAS URL & entry key.",
#         "sasUrl": sas_url,
#         "entryKey": entry_key
#     }
#     print('endpoint hit: ', entry_key)
#     return jsonify(response)
@bp.route("/sasUrl", methods=["POST"])
@require_auth(None)
def sasUrl():
    num_files = request.json.get('numFiles', 1)
    sas_url = get_container_sas()
    entry_keys = [create_entry_key(getUserID(current_token)) for _ in range(num_files)]
    response = {
        "message": "Generated SAS URL & entry keys.",
        "sasUrl": sas_url,
        "entryKeys": entry_keys
    }
    print('endpoint hit: ', entry_keys)
    return jsonify(response)


@bp.route("/transcript", methods=["POST"])
@require_auth(None)
def transcript():
    entry_key = request.json['entry_id']
    lang = request.json['lang'] #if lang is default then run code as normal
    user_id = getUserID(current_token)
    entry = get_entry(user_id, entry_key)

    print('lang: ', lang)
    # transcribe_time_taken = get_transcript_time_taken(user_id, entry_key)

    audio_data = entry['audio']
    audio_duration = audio_data['duration']
    audio_file_size = audio_data['file_size']
    language = audio_data.get('language')
    iso = audio_data.get('iso')
    transcript_data = entry['transcript']
    file_name = audio_data['file_name']
    transcript_creation_date = transcript_data['creation_date']
    word_count = transcript_data['word_count']
    char_count = transcript_data['char_count']
    # subtitles_data = entry['subtitles']
    audio_duration = float(audio_duration)
    # cost = math.ceil(audio_duration * COST_PER_SECOND)
    # cost = audio_duration * COST_PER_SECOND
    # print(transcript_data['file_url'])
    estimated_cost = audio_duration * COST_PER_SECOND
    cost = round(math.ceil(estimated_cost * 100) / 100, 2)
    transcript_file_name = f"transcript/{entry_key}"
    subtitle_file_name = f"subtitle/{entry_key}"
    audio_file_name = f"audio/{entry_key}"
    translations = transcript_data.get('translations', [])
    print(translations)

    if lang != 'default' and lang in translations:
        print('works!')
        subtitle_file_name = f"subtitle/{entry_key}-{lang}"
        transcript_file_name = f"transcript/{entry_key}-{lang}"

    # transcript_blob_name = f"transcript/{entry_key}"


    try:
        transcript_content = download_file_from_azure(transcript_file_name).content_as_text()
        subtitles_content = download_file_from_azure(subtitle_file_name).content_as_text()
        print(transcript_content)

        return jsonify({"transcript_content": transcript_content, 
                        "subtitles_content": subtitles_content,
                        "transcript_creation_date": transcript_creation_date,
                        "word_count": word_count,
                        # "transcribe_time_taken": transcribe_time_taken,
                        "char_count": char_count,
                        "language": language,
                        "translations": translations,
                        "iso": iso,
                        "audio_duration": audio_duration,
                        "audio_file_size": audio_file_size,
                        "file_name": file_name,
                        "cost": cost})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch transcript file: {str(e)}"}), 500
    
@bp.route("/uploads", methods=["POST"])
@require_auth(None)
def uploads():
    uploads = get_uploads(getUserID(current_token))
    print(uploads)
    return jsonify(uploads)
 