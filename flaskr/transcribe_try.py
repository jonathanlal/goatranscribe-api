from flask import Blueprint, request, jsonify
import openai
from os import environ as env
import os
import srt
from azure.storage.blob import BlobServiceClient
from flaskr.firebase import create_entry_key, store_file_info
from firebase_admin import db
from flaskr.azure import download_file_from_azure, get_blob_client, get_container_sas, get_container_client, upload_file_to_azure
import tempfile
import nltk
from nltk.tokenize import word_tokenize

from flaskr.transcribe import createTranscribeResponse, extract_text_from_srt, subtitle_to_dict, transcribe_audio


bp = Blueprint("transcribe_try", __name__, url_prefix="/try")

@bp.route("/transcribe", methods=["POST"])
def tryTranscribe():
    openai.api_key = env.get("OPENAI_API_KEY")
    entry_key = request.json['entryKey']
    
    transcript_file_name = f"transcript/{entry_key}"
    subtitle_file_name = f"subtitle/{entry_key}"
    audio_file_name = f"audio/{entry_key}"

    audio_file = download_file_from_azure(audio_file_name)
    file_extension = get_blob_client(audio_file_name).get_blob_properties().metadata['fileExtension']

    audio_content = audio_file.content_as_bytes()
    with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
        tmp_file.write(audio_content)
        tmp_file.seek(0)
        subtitles = transcribe_audio(tmp_file)

    os.remove(tmp_file.name)
    upload_file_to_azure(subtitle_file_name, subtitles)
    store_file_info(entry_key, 'subtitle')


    subs = list(srt.parse(subtitles))
    transcript = extract_text_from_srt(subs)
    subs_dicts = [subtitle_to_dict(sub) for sub in subs]
    tokens = word_tokenize(transcript)
    word_count = len(tokens)
    metadata = {
        'wordCount': str(word_count)
    }
    upload_file_to_azure(transcript_file_name, transcript, metadata=metadata) #upload text transcript to azure
    store_file_info(entry_key, 'transcript')

        
    return createTranscribeResponse(entry_key, subs_dicts, transcript)

@bp.route("/uploadComplete", methods=["POST"])
def tryUploadComplete():
    entry_key = request.json['entryKey']
    store_file_info(entry_key, 'audio')
    response = {
        "message": "Audio data saved.",
    }
    return jsonify(response)

@bp.route("/sasUrl", methods=["POST"])
def trySasUrl():
    sas_url = get_container_sas()
    entry_key = create_entry_key('try')
    
    # Return the SAS URL to the client
    response = {
        "message": "Generated SAS URL & entry key.",
        "sasUrl": sas_url,
        "entryKey": entry_key
    }
    return jsonify(response)