import math
from flask import Blueprint, request, jsonify
from authlib.integrations.flask_oauth2 import current_token
import openai
from .auth import require_auth, getUserID
from os import environ as env
import os
import srt
from azure.storage.blob import BlobServiceClient
from flaskr.create_container import create_container_and_generate_sas, get_blob_sas
from flaskr.firebase import COST_PER_SECOND, create_entry_key, get_entry, get_entry_by_id, get_uploads, store_audio_file_info, store_transcript_info, store_subtitles_info
from firebase_admin import db
from flaskr.azure import download_file_from_azure, file_exists_azure, get_blob_client, getBlobUrl, upload_file_to_azure
from pydub import AudioSegment
import tempfile
import nltk
from nltk.tokenize import word_tokenize

nltk.download('punkt')

bp = Blueprint("transcribe", __name__)

def update_transcript_file_info(entry_key):
    user_id = getUserID(current_token)
    blob = get_blob_client(f"transcript/{entry_key}")
    store_transcript_info(user_id, entry_key, blob)

def extract_text_from_srt(subtitles):
    text_content = ' '.join([subtitle.content for subtitle in subtitles])
    return text_content

def update_subtitle_file_info(entry_key):
    user_id = getUserID(current_token)
    blob = get_blob_client(f"subtitle/{entry_key}")
    store_subtitles_info(user_id, entry_key, blob)

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


@bp.route("/transcribe", methods=["POST"])
@require_auth(None)
def transcribe():
    openai.api_key = env.get("OPENAI_API_KEY")
    entry_keys = request.json['entryKeys']

    authorization_header = request.headers.get('Authorization')
    if authorization_header:
        access_token = authorization_header.split(' ')[1]  # Assuming "Bearer <access_token>" format
    else:
        return jsonify({"error": "Missing access token"}), 401
    print(access_token)
    # transcript_file_name = f"transcript/{blob_name}"
    # subtitle_file_name = f"subtitle/{blob_name}"
    # audio_file_name = f"audio/{blob_name}"

    # get file info from firebase
    # entry = get_entry_by_id(getUserID(current_token), blob_name)
    # audio_data = entry['audio']

    print(entry_keys)
    return jsonify(entry_keys)
    


    # get file from azure

    # get user balance

    # get cost of file (check cost in firebase vs estimated cost)

    # check if user balance is suffifient. 

    # deploy task worker 


        # inside task worker we send email when finished and update user balance in stripe



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
    #     update_subtitle_file_info(blob_name)


    #     subs = list(srt.parse(subtitles))
    #     transcript = extract_text_from_srt(subs)
    #     subs_dicts = [subtitle_to_dict(sub) for sub in subs]
    #     tokens = word_tokenize(transcript)
    #     word_count = len(tokens)
    #     metadata = {
    #         'wordCount': str(word_count)
    #     }
    #     upload_file_to_azure(transcript_file_name, transcript, metadata=metadata) #upload text transcript to azure
    #     update_transcript_file_info(blob_name)
    
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


def update_audio_file_info(entry_key):
    user_id = getUserID(current_token)
    blob = get_blob_client(f"audio/{entry_key}")
    store_audio_file_info(user_id, entry_key, blob)

@bp.route("/uploadComplete", methods=["POST"])
@require_auth(None)
def uploadComplete():
    entry_key = request.json['entryKey']
    update_audio_file_info(entry_key)
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

@bp.route("/sasUrl", methods=["POST"])
@require_auth(None)
def sasUrl():

    # Call the create_container_and_generate_sas function to ensure the container exists and get the SAS token
    sas_token = create_container_and_generate_sas(getUserID(current_token))

    # Generate the SAS URL for the container
    connection_string = env.get("AZURE_STORAGE_CONNECTION_STRING")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    account_url = blob_service_client.primary_endpoint
    sas_url = f"{account_url}?{sas_token}"

    entry_key = create_entry_key(getUserID(current_token))
    
    # Return the SAS URL to the client
    response = {
        "message": "Generated SAS URL & entry key.",
        "sasUrl": sas_url,
        "entryKey": entry_key
    }
    return jsonify(response)


@bp.route("/transcript", methods=["POST"])
@require_auth(None)
def transcript():
    entry_key = request.json['entry_id']
    entry = get_entry(getUserID(current_token), entry_key)


    audio_data = entry['audio']
    subtitles_data = entry['subtitles']
    transcript_data = entry['transcript']
    print(transcript_data['file_url'])

    transcript_blob_name = f"transcript/{entry_key}"

    try:
        transcript_content_blob = download_file_from_azure(transcript_blob_name)
        transcript_content = transcript_content_blob.content_as_text()
        return jsonify({"transcript_content": transcript_content})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch transcript file: {str(e)}"}), 500
    
@bp.route("/uploads", methods=["POST"])
@require_auth(None)
def uploads():
    uploads = get_uploads(getUserID(current_token))
    print(uploads)
    return jsonify(uploads)
 