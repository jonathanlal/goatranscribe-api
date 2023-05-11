# from os import environ as env
# from dotenv import load_dotenv, find_dotenv
# from flask import Flask, request, jsonify
# from authlib.integrations.flask_oauth2 import ResourceProtector, current_token
# from validator import Auth0JWTBearerTokenValidator
# from create_container import create_container_and_generate_sas, get_blob_sas
# from azure.storage.blob import BlobServiceClient, ContainerSasPermissions, generate_container_sas, ContainerClient, BlobClient
# from pydub import AudioSegment
# import openai
# import io
# import tempfile
# import os
# import srt
# from datetime import datetime
# import math
# from firebase import create_entry_key, store_audio_file_info, store_transcript_info, store_subtitles_info
# from firebase_admin import db
# import nltk
# from nltk.tokenize import word_tokenize

# nltk.download('punkt')

# ENV_FILE = find_dotenv()
# if ENV_FILE:
#     load_dotenv(ENV_FILE)

# require_auth = ResourceProtector()
# validator = Auth0JWTBearerTokenValidator(env.get("AUTH0_DOMAIN"), env.get("AUTH0_IDENTIFIER"))
# require_auth.register_token_validator(validator)

# app = Flask(__name__)
# # app.debug = True

# # access tokens with an Auth0 API audience, excluding the /userinfo endpoint, cannot have private, non-namespaced custom claims
# # https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-token-claims 
# # def getUserID(token):
# #     if not token:
# #         return 'try'
# #     sub_value = token.get('sub', '')
# #     return sub_value.replace('|', '')

# # def getBlobUrl(container_name, blob_name):
# #     sas_token = get_blob_sas(container_name, blob_name)
# #     #change url to custom domain url after fixing https
# #     return 'https://goatranscribe.azureedge.net/'+container_name+'/'+blob_name+'?'+sas_token


# def transcribe_audio(audio_file):
#     # verbose = None
#     # temperature = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
#     # compression_ratio_threshold = 2.4
#     # logprob_threshold = -1.0
#     # no_speech_threshold = 0.6
#     # condition_on_previous_text = True
#     # initial_prompt = None
#     word_timestamps = True
#     # prepend_punctuations = "\"'“¿([{-"
#     # append_punctuations = "\"'.。,，!！?？:：”)]}、"
    
#     transcript = openai.Audio.transcribe(
#         model="whisper-1",
#         file=audio_file,
#         word_timestamps=word_timestamps,
#         response_format="srt"
#     )
    
#     print(transcript)
#     return transcript


# def extract_text_from_srt(subtitles):
#     text_content = ' '.join([subtitle.content for subtitle in subtitles])
#     return text_content

# def subtitle_to_dict(subtitle):
#     return {
#         'section': subtitle.index,
#         'startTime': str(subtitle.start),
#         'endTime': str(subtitle.end),
#         'text': subtitle.content
#     }

# # transcribe should be srt format
# def createTranscribeResponse(blob_name, subtitles, transcript):
#     container_name = getUserID(current_token)
#     response = {
#         'url': {
#             'audio': getBlobUrl(container_name, 'audio/'+blob_name),
#             'srt': getBlobUrl(container_name, 'subtitle/'+blob_name),
#             'txt': getBlobUrl(container_name, 'transcript/'+blob_name),
#         },
#         'subtitles': subtitles,
#         'transcript': transcript
#     }
#     # return jsonify({'audio': getBlobUrl(container_name, blob_name), 'subtitles': subs_dicts, 'transcript': text})
#     return jsonify(response)

# def get_blob_client(blob_name):
#     container_name = getUserID(current_token)
#     blob_service_client = BlobServiceClient.from_connection_string(env.get("AZURE_STORAGE_CONNECTION_STRING"))
#     container_client = blob_service_client.get_container_client(container_name)
#     return container_client.get_blob_client(blob_name)

# # def upload_file_to_azure(blob_name, data):
# #     blob_client = get_blob_client(blob_name)
# #     blob_client.upload_blob(data, overwrite=True)
# # def upload_file_to_azure(blob_name, data, metadata=None):
# #     blob_client = get_blob_client(blob_name)
# #     blob_client.upload_blob(data, overwrite=True, metadata=metadata)

# # def file_exists_azure(blob_name):
# #     blob_client = get_blob_client(blob_name)
# #     return blob_client.exists()

# # def download_file_from_azure(blob_name):
# #     blob_client = get_blob_client(blob_name)
# #     return blob_client.download_blob()


# @app.route("/try/transcribe", methods=["POST"])
# def tryTranscribe():
#     openai.api_key = env.get("OPENAI_API_KEY")
#     blob_name = request.json['entryKey']
    
#     transcript_file_name = f"transcript/{blob_name}"
#     subtitle_file_name = f"subtitle/{blob_name}"
#     audio_file_name = f"audio/{blob_name}"

#     user_id = 'try'

#     audio_file = download_file_from_azure(audio_file_name)
#     file_extension = get_blob_client(audio_file_name).get_blob_properties().metadata['fileExtension']

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

        
#     return createTranscribeResponse(blob_name, subs_dicts, transcript)


# @app.route("/api/transcribe", methods=["POST"])
# @require_auth(None)
# def transcribe():
#     openai.api_key = env.get("OPENAI_API_KEY")
#     blob_name = request.json['entryKey']
    
#     transcript_file_name = f"transcript/{blob_name}"
#     subtitle_file_name = f"subtitle/{blob_name}"
#     audio_file_name = f"audio/{blob_name}"

#     user_id = getUserID(current_token)

#     audio_file = download_file_from_azure(audio_file_name)
#     file_extension = get_blob_client(audio_file_name).get_blob_properties().metadata['fileExtension']
    
#     if file_exists_azure(subtitle_file_name):
#         subtitles = download_file_from_azure(subtitle_file_name).content_as_text()
#         transcript = download_file_from_azure(transcript_file_name).content_as_text()
#         subs = list(srt.parse(subtitles))
#         subs_dicts = [subtitle_to_dict(sub) for sub in subs]
#         return createTranscribeResponse(blob_name, subs_dicts, transcript)

#     # Transcribe the audio file
#     if audio_file.size > 25 * 1024 * 1024:
#         # Split the audio file
#         song = AudioSegment.from_file(audio_file.content_as_bytes())
#         chunk_size = 5 * 60 * 1000  # 5 minutes in milliseconds
#         parts = [song[i:i + chunk_size] for i in range(0, len(song), chunk_size)]
        
#         # Transcribe and upload each part
#         transcripts = []
#         for idx, part in enumerate(parts):
#             part_name = f"{blob_name}_part_{idx+1}{file_extension}"
#             part.export(part_name, format="mp3")
            
#             # Upload audio part to Azure
#             audio_part_blob_name = f"{blob_name}/part_{idx+1}{file_extension}"
            
#             with open(part_name, "rb") as audio_part:
#                 upload_file_to_azure(audio_part_blob_name, audio_part)

#             # Check if transcript part exists
#             transcript_part_blob_name = f"{blob_name}/part_{idx+1}.srt"

#             if not file_exists_azure(transcript_part_blob_name):
#                 with open(part_name, "rb") as audio_part:
#                     transcript_part = transcribe_audio(audio_part)
#                 upload_file_to_azure(transcript_part_blob_name, transcript_part)
            
#             transcript_part = download_file_from_azure(transcript_part_blob_name).content_as_text()
#             os.remove(part_name)
#             transcripts.append(transcript_part)
        
#         # Stitch the transcripts and upload to Azure
#         full_transcript = "\n".join(transcripts)
#         upload_file_to_azure(subtitle_file_name, full_transcript)
#     else:
#         audio_content = audio_file.content_as_bytes()
#         with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
#             tmp_file.write(audio_content)
#             tmp_file.seek(0)
#             subtitles = transcribe_audio(tmp_file)

#         os.remove(tmp_file.name)
#         upload_file_to_azure(subtitle_file_name, subtitles)
#         update_subtitle_file_info(blob_name)


#         subs = list(srt.parse(subtitles))
#         transcript = extract_text_from_srt(subs)
#         subs_dicts = [subtitle_to_dict(sub) for sub in subs]
#         tokens = word_tokenize(transcript)
#         word_count = len(tokens)
#         metadata = {
#             'wordCount': str(word_count)
#         }
#         upload_file_to_azure(transcript_file_name, transcript, metadata=metadata) #upload text transcript to azure
#         update_transcript_file_info(blob_name)

        
#     return createTranscribeResponse(blob_name, subs_dicts, transcript)

# def get_user_transcripts(user_id):
#     transcripts_ref = db.reference(f"users/{user_id}/transcripts")
#     transcripts_data = transcripts_ref.get()
#     print(transcripts_data)
#     if transcripts_data is None:
#         return []

#     results = []
#     for transcript_id, transcript_info in transcripts_data.items():
#         if "transcript" in transcript_info:
#             results.append({
#                 "entry_id": transcript_id.lstrip('-'),
#                 "file_name": transcript_info["audio"]["file_name"],
#                 "creation_date": transcript_info["transcript"]["creation_date"],
#                 "word_count": transcript_info["transcript"]["word_count"]
#             })

#     return results

# def convert_size(size_bytes):
#     if size_bytes == 0:
#         return "0B"
#     size_name = ("B", "KB", "MB", "GB")
#     i = int(math.floor(math.log(size_bytes, 1024)))
#     p = math.pow(1024, i)
#     s = round(size_bytes / p, 2)
#     return f"{s} {size_name[i]}"

# @app.route("/api/userTranscripts", methods=["POST"])
# @require_auth(None)
# def userTranscripts():
#     user_id = getUserID(current_token)
#     transcripts = get_user_transcripts(user_id)
#     return jsonify(transcripts)

# @app.route("/api/newEntry", methods=["POST"])
# @require_auth(None)
# def newEntry():
#     entry_key = create_entry_key(getUserID(current_token))
#     response = {
#         "message": "Entry key created.",
#         "entryKey": entry_key
#     }
#     return jsonify(response)

# def update_audio_file_info(entry_key):
#     user_id = getUserID(current_token)
#     blob = get_blob_client(f"audio/{entry_key}")
#     store_audio_file_info(user_id, entry_key, blob)

# def update_transcript_file_info(entry_key):
#     user_id = getUserID(current_token)
#     blob = get_blob_client(f"transcript/{entry_key}")
#     store_transcript_info(user_id, entry_key, blob)

# def update_subtitle_file_info(entry_key):
#     user_id = getUserID(current_token)
#     blob = get_blob_client(f"subtitle/{entry_key}")
#     store_subtitles_info(user_id, entry_key, blob)

# @app.route("/api/uploadComplete", methods=["POST"])
# @require_auth(None)
# def uploadComplete():
#     entry_key = request.json['entryKey']
#     update_audio_file_info(entry_key)
#     response = {
#         "message": "Audio data saved.",
#     }
#     return jsonify(response)

# @app.route("/try/uploadComplete", methods=["POST"])
# def tryUploadComplete():
#     entry_key = request.json['entryKey']
#     update_audio_file_info(entry_key)
#     response = {
#         "message": "Audio data saved.",
#     }
#     return jsonify(response)


# #returns CDN url with SAS token for a specific file
# @app.route("/api/sasToken", methods=["POST"])
# @require_auth(None)
# def sasToken():
#     blob_name = request.json['fileName']
#     container_name = getUserID(current_token)
#     response = {
#         "message": "Generated SAS URL for File.",
#         "sasUrl": getBlobUrl(container_name, blob_name)
#     }
#     return jsonify(response)


# @app.route('/')
# def index():
#     return jsonify('goatranscribe api')

# @app.route("/api/public", methods=["POST"])
# def public():
#     """No access token required."""
#     response = (
#         "Hello from a public endpoint! You don't need to be"
#         " authenticated to see this."
#     )
#     return jsonify({"message": response})

# @app.route("/api/private", methods=["POST"])
# @require_auth(None)
# def private():
#     """A valid access token is required."""
#     response = (
#         "Hello from a private endpoint! You need to be"
#         " authenticated to see this."
#     )
#     return jsonify(message=response)

# @app.route("/api/private-scoped", methods=["POST"])
# @require_auth("read:messages")
# def private_scoped():
#     """A valid access token and scope are required."""
#     response = (
#         "Hello from a private endpoint! You need to be"
#         " authenticated and have a scope of read:messages to see"
#         " this."
#     )
#     return jsonify(message=response)

# #checks if the container exists and creates it if necessary. Then, generate a SAS token for the container and return it to the client.
# @app.route("/api/sasUrl", methods=["POST"])
# @require_auth(None)
# def sasUrl():

#     # Call the create_container_and_generate_sas function to ensure the container exists and get the SAS token
#     sas_token = create_container_and_generate_sas(getUserID(current_token))

#     # Generate the SAS URL for the container
#     connection_string = env.get("AZURE_STORAGE_CONNECTION_STRING")
#     blob_service_client = BlobServiceClient.from_connection_string(connection_string)
#     account_url = blob_service_client.primary_endpoint
#     sas_url = f"{account_url}?{sas_token}"

#     entry_key = create_entry_key(getUserID(current_token))
    
#     # Return the SAS URL to the client
#     response = {
#         "message": "Generated SAS URL & entry key.",
#         "sasUrl": sas_url,
#         "entryKey": entry_key
#     }
#     return jsonify(response)

# #checks if the container exists and creates it if necessary. Then, generate a SAS token for the container and return it to the client.
# @app.route("/try/sasUrl", methods=["POST"])
# def trySasUrl():

#     # Call the create_container_and_generate_sas function to ensure the container exists and get the SAS token
#     sas_token = create_container_and_generate_sas('try')

#     # Generate the SAS URL for the container
#     connection_string = env.get("AZURE_STORAGE_CONNECTION_STRING")
#     blob_service_client = BlobServiceClient.from_connection_string(connection_string)
#     account_url = blob_service_client.primary_endpoint
#     sas_url = f"{account_url}?{sas_token}"

#     entry_key = create_entry_key('try')
    
#     # Return the SAS URL to the client
#     response = {
#         "message": "Generated SAS URL & entry key.",
#         "sasUrl": sas_url,
#         "entryKey": entry_key
#     }
#     return jsonify(response)

# if __name__ == "__main__":
#     app.run()