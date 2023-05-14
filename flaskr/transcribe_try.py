from flask import Blueprint, request, jsonify
import openai
from os import environ as env
import os
import srt
from azure.storage.blob import BlobServiceClient
from flaskr.create_container import create_container_and_generate_sas
from flaskr.firebase import create_entry_key
from firebase_admin import db
from flaskr.azure import download_file_from_azure, get_blob_client, upload_file_to_azure
import tempfile
import nltk
from nltk.tokenize import word_tokenize

from flaskr.transcribe import createTranscribeResponse, extract_text_from_srt, subtitle_to_dict, transcribe_audio, update_audio_file_info, update_subtitle_file_info, update_transcript_file_info


bp = Blueprint("transcribe_try", __name__, url_prefix="/try")

@bp.route("/transcribe", methods=["POST"])
def tryTranscribe():
    openai.api_key = env.get("OPENAI_API_KEY")
    blob_name = request.json['entryKey']
    
    transcript_file_name = f"transcript/{blob_name}"
    subtitle_file_name = f"subtitle/{blob_name}"
    audio_file_name = f"audio/{blob_name}"

    user_id = 'try'

    audio_file = download_file_from_azure(audio_file_name)
    file_extension = get_blob_client(audio_file_name).get_blob_properties().metadata['fileExtension']

    audio_content = audio_file.content_as_bytes()
    with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
        tmp_file.write(audio_content)
        tmp_file.seek(0)
        subtitles = transcribe_audio(tmp_file)

    os.remove(tmp_file.name)
    upload_file_to_azure(subtitle_file_name, subtitles)
    update_subtitle_file_info(blob_name)


    subs = list(srt.parse(subtitles))
    transcript = extract_text_from_srt(subs)
    subs_dicts = [subtitle_to_dict(sub) for sub in subs]
    tokens = word_tokenize(transcript)
    word_count = len(tokens)
    metadata = {
        'wordCount': str(word_count)
    }
    upload_file_to_azure(transcript_file_name, transcript, metadata=metadata) #upload text transcript to azure
    update_transcript_file_info(blob_name)

        
    return createTranscribeResponse(blob_name, subs_dicts, transcript)

@bp.route("/uploadComplete", methods=["POST"])
def tryUploadComplete():
    entry_key = request.json['entryKey']
    update_audio_file_info(entry_key)
    response = {
        "message": "Audio data saved.",
    }
    return jsonify(response)

@bp.route("/sasUrl", methods=["POST"])
def trySasUrl():

    # Call the create_container_and_generate_sas function to ensure the container exists and get the SAS token
    sas_token = create_container_and_generate_sas('try')

    # Generate the SAS URL for the container
    connection_string = env.get("AZURE_STORAGE_CONNECTION_STRING")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    account_url = blob_service_client.primary_endpoint
    sas_url = f"{account_url}?{sas_token}"

    entry_key = create_entry_key('try')
    
    # Return the SAS URL to the client
    response = {
        "message": "Generated SAS URL & entry key.",
        "sasUrl": sas_url,
        "entryKey": entry_key
    }
    return jsonify(response)