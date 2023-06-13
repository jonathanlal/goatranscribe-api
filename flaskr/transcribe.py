import json
import math
from flask import Blueprint, request, jsonify
from authlib.integrations.flask_oauth2 import current_token
import openai
import requests
from .auth import require_auth, getUserID
from os import environ as env
import os
from flaskr.firebase import COST_PER_SECOND, create_custom_token, create_entry_key, get_entry, get_tasks, get_uploads, mark_task_as_seen, mark_tasks_as_seen, store_file_info
from firebase_admin import db
from flaskr.azure import download_file_from_azure, get_container_sas, getBlobUrl
# import tempfile
# import nltk



# nltk.download('punkt')

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

def transcribe_audio(audio_file, initial_prompt=None):
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
        response_format="srt",
        initial_prompt=initial_prompt,
    )
    
    # print(transcript)
    return transcript

# def create_summary(text_to_summarize):
#     prompt_with_instruction = [
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user", "content": text_to_summarize},
#         {"role": "user", "content": "Summarize this."},
#     ]
    
#     response = openai.ChatCompletion.create(
#         model="gpt-4", 
#         messages=prompt_with_instruction,
#         temperature=0.3,
#         max_tokens=2000,
#         frequency_penalty=0.0,
#         presence_penalty=0.0,
#     )
    
#     return response

def create_summary(text_to_summarize):
    # Split the input text into chunks of maximum allowed length
    chunk_size = 8000  # Adjust the chunk size as needed
    text_chunks = [text_to_summarize[i:i+chunk_size] for i in range(0, len(text_to_summarize), chunk_size)]
    logging.info('Number of chunks: %s', len(text_chunks))
    summaries = []
    for chunk in text_chunks:
        response = generate_summary_chunk(chunk)
        summary = response['choices'][0]['message']['content']
        summaries.append(summary)
    
    # Combine the summaries into a single summary
    combined_summary = ' '.join(summaries)
    if len(text_chunks) > 1:
        combined_summary = generate_summary_chunk(combined_summary)
    
    return combined_summary


def generate_summary_chunk(chunk):
    prompt_with_instruction = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": chunk},
        {"role": "user", "content": "Summarize this."},
    ]
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=prompt_with_instruction,
        temperature=0.3,
        max_tokens=2000,
        frequency_penalty=0.0,
        presence_penalty=0.0,
    )
    
    return response



#TOO SLOW
# def add_paragraphs(text_to_paragraph):
#     prompt_with_instruction = [
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user", "content": text_to_paragraph},
#         {"role": "user", "content": "Add paragraphs to this."},
#     ]
    
#     response = openai.ChatCompletion.create(
#         model="gpt-4", 
#         messages=prompt_with_instruction,
#         temperature=0.3,
#         frequency_penalty=0.0,
#         presence_penalty=0.0,
#     )
    
#     return response['choices'][0]['message']['content']


def add_paragraphs(text_to_paragraph):
    # Splitting the text into chunks of 500 words
    chunks = text_to_paragraph.split(' ', 500)

    # Initialize an empty string to store the result
    result = ""

    # Process each chunk individually
    for chunk in chunks:
        instruction = "Add paragraphs to the following text without modifying the text, the paragraphs should be added in appropriate places:"
        prompt = f"{instruction}\n\n{chunk}"

        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            temperature=0.7,
            max_tokens=2000,  # Adjust this value based on your needs
        )

        # Append the output to the result string
        result += response.choices[0].text.strip()

    return result
    # return response['choices'][0]['message']['content']



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


# @bp.route("/test", methods=["GET"])
# def test():
    # print(current_token)
    # entry_key = "NWruCdEWMHE2nJAnmE2"
    # user_id = "google-oauth2107710671190499472104"
    # encoded_file_name = get_encoded_file_name_from_asset(entry_key)
    # asset_container_name = sanitize_container_name(entry_key)
    # copy_encoded_asset_to_user_container(asset_container_name, encoded_file_name, f"{entry_key}.mp4", user_id)
    # test_send_email()

    # print(info)
    # return jsonify('hello')


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

@bp.route("/get_paragraphed", methods=["POST"])
@require_auth(None)
def get_paragraphed():
    entry_key = request.json['entryKey']
    paragraphed_transcript_file_name = f"paragraphed/{entry_key}.txt"
    paragraphed_transcript = download_file_from_azure(paragraphed_transcript_file_name).content_as_text()
    return jsonify(paragraphed_transcript)

@bp.route("/paragraph", methods=["POST"])
@require_auth(None)
def paragraph_transcript():
    entry_key = request.json['entryKey']
    authorization_header = request.headers.get('Authorization')
    if authorization_header:
        access_token = authorization_header.split(' ')[1]  # Assuming "Bearer <access_token>" format
    else:
        return jsonify({"error": "Missing access token"}), 401

    # make post request here with access token in authorization_header and entry_keys in body
    url = f"{functions_url}api/orchestrators/TaskOrchestrator"
    headers = {'Authorization': 'Bearer ' + access_token}
    data = {'entryKey': entry_key, 'task_type': 'paragraph'}
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

@bp.route("/get_summary", methods=["POST"])
@require_auth(None)
def get_summary():
    entry_key = request.json['entryKey']
    summary_file_name = f"summary/{entry_key}.txt"
    summary_content = download_file_from_azure(summary_file_name).content_as_text()
    return jsonify(summary_content)

@bp.route("/summarize", methods=["POST"])
@require_auth(None)
def summarize():
    entry_key = request.json['entryKey']
    authorization_header = request.headers.get('Authorization')
    if authorization_header:
        access_token = authorization_header.split(' ')[1]  # Assuming "Bearer <access_token>" format
    else:
        return jsonify({"error": "Missing access token"}), 401

    # make post request here with access token in authorization_header and entry_keys in body
    url = f"{functions_url}api/orchestrators/TaskOrchestrator"
    headers = {'Authorization': 'Bearer ' + access_token}
    data = {'entryKey': entry_key, 'task_type': 'summarize'}
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

import logging

@bp.route("/transcribe", methods=["POST"])
@require_auth(None)
def transcribe():
    # Set the logging level to INFO
    logging.basicConfig(level=logging.INFO)

    entry_keys = request.json['entryKeys']
    logging.info('Received entry keys: %s', entry_keys)

    authorization_header = request.headers.get('Authorization')
    if authorization_header:
        access_token = authorization_header.split(' ')[1]  # Assuming "Bearer <access_token>" format
        logging.info('Access token acquired')
    else:
        logging.error('Missing access token')
        return jsonify({"error": "Missing access token"}), 401

    # make post request here with access token in authorization_header and entry_keys in body
    url = f"{functions_url}api/orchestrators/TaskOrchestrator"
    headers = {'Authorization': 'Bearer ' + access_token}
    data = {'entryKeys': entry_keys, 'task_type': 'transcribe'}
    logging.info('Sending POST request to %s with headers %s and data %s', url, headers, data)
    
    try:
        response = requests.post(url, headers=headers, json=data)
        logging.info('Response received from POST request')
    except Exception as e:
        logging.error('Error during POST request: %s', str(e))
        return jsonify({"error": "Failed to send request due to an exception: "+str(e)}), 500

    # print(response.text)

    # Check the response status
    if response.status_code == 202:
        instanceId = json.loads(response.text)['id']
        logging.info('Request sent successfully. Instance ID: %s', instanceId)
        return jsonify({"message": "Request sent successfully", "instanceId": instanceId}), 202
    else:
        logging.error('Failed to send request. Response code: %s', response.status_code)
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
    # print('entry_key: ', entry_key)
    # asset = create_media_service_asset(entry_key)
    # print('asset: ', asset)


    authorization_header = request.headers.get('Authorization')
    if authorization_header:
        access_token = authorization_header.split(' ')[1]  # Assuming "Bearer <access_token>" format
        logging.info('Access token acquired')
    else:
        logging.error('Missing access token')
        return jsonify({"error": "Missing access token"}), 401

    # make post request here with access token in authorization_header and entry_keys in body
    url = f"{functions_url}api/orchestrators/TaskOrchestrator"
    headers = {'Authorization': 'Bearer ' + access_token}
    data = {'entryKey': entry_key, 'task_type': 'encode'}
    logging.info('Sending POST request to %s with headers %s and data %s', url, headers, data)
    
    try:
        response = requests.post(url, headers=headers, json=data)
        logging.info('Response received from POST request')
    except Exception as e:
        logging.error('Error during POST request: %s', str(e))
        return jsonify({"error": "Failed to send request due to an exception: "+str(e)}), 500

    # print(response.text)

    # Check the response status
    if response.status_code == 202:
        instanceId = json.loads(response.text)['id']
        logging.info('Request sent successfully. Instance ID: %s', instanceId)
        return jsonify({"message": "Request sent successfully", "instanceId": instanceId}), 202
    else:
        logging.error('Failed to send request. Response code: %s', response.status_code)
        return jsonify({"error": "Failed to send request"}), response.status_code



    # response = {
    #     "message": "Audio data saved, encoding started.",
    # }
    # return jsonify(response)

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

@bp.route("/get_download_link", methods=["POST"])
@require_auth(None)
def get_download_link():
    entry_key = request.json['entryKey']
    target_lang = request.json['targetLang']
    format = request.json['format']
    container_name = getUserID(current_token)

    file_prefix = "subtitle" if format == 'srt' else "transcript"
    lang_suffix = "" if target_lang == 'default' else f"-{target_lang}"
    file_name = f"{file_prefix}/{entry_key}{lang_suffix}.{format}"

    download_link = getBlobUrl(container_name, file_name)
    return jsonify(download_link)


@bp.route("/transcript", methods=["POST"])
@require_auth(None)
def transcript():
    entry_key = request.json['entry_id']
    lang = request.json['lang'] #if lang is default then run code as normal
    user_id = getUserID(current_token)
    entry = get_entry(user_id, entry_key)

    # print('lang: ', lang)
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
    hasSummary = transcript_data.get('hasSummary', False)
    hasParagraphs = transcript_data.get('hasParagraphs', False)
    # print('hasSummary: ', hasSummary)
    # subtitles_data = entry['subtitles']
    audio_duration = float(audio_duration)
    # cost = math.ceil(audio_duration * COST_PER_SECOND)
    # cost = audio_duration * COST_PER_SECOND
    # print(transcript_data['file_url'])
    estimated_cost = audio_duration * COST_PER_SECOND
    cost = round(math.ceil(estimated_cost * 100) / 100, 2)
    transcript_file_name = f"transcript/{entry_key}.txt"
    subtitle_file_name = f"subtitle/{entry_key}.srt"
    summary_file_name = f"summary/{entry_key}.txt"
    paragraphed_file_name = f"paragraphed/{entry_key}.txt"
    audio_file_name = f"audio/{entry_key}"
    translations = transcript_data.get('translations', [])
    # print(translations)

    if lang != 'default' and lang in translations:
        # print('works!')
        subtitle_file_name = f"subtitle/{entry_key}-{lang}.srt"
        transcript_file_name = f"transcript/{entry_key}-{lang}.txt"
   

    # transcript_blob_name = f"transcript/{entry_key}"


    try:
        transcript_content = download_file_from_azure(transcript_file_name).content_as_text()
        subtitles_content = download_file_from_azure(subtitle_file_name).content_as_text()
        summary_content = "" if not hasSummary else download_file_from_azure(summary_file_name).content_as_text()
        paragraph_content = "" if not hasParagraphs else download_file_from_azure(paragraphed_file_name).content_as_text()
        # print(transcript_content)

        return jsonify({"transcript_content": transcript_content, 
                        "subtitles_content": subtitles_content,
                        "transcript_creation_date": transcript_creation_date,
                        "word_count": word_count,
                        # "transcribe_time_taken": transcribe_time_taken,
                        "hasSummary": hasSummary,
                        "hasParagraphs": hasParagraphs,
                        "summary_content": summary_content,
                        "paragraph_content": paragraph_content,
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
    # print(uploads)
    return jsonify(uploads)
 