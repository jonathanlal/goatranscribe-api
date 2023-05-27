# This function is not intended to be invoked directly. Instead it will be
# triggered by an orchestrator function.
# Before running this sample, please:
# - create a Durable orchestration function
# - create a Durable HTTP starter function
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt

import json
import logging
import math
import os
import tempfile
import srt
import nltk
from nltk.tokenize import word_tokenize

from flaskr.azure import detect_language, download_file_from_azure, upload_file_to_azure
from flaskr.firebase import COST_PER_SECOND, create_task_entry_key, get_audio_info, store_file_info, store_transaction_info, update_audio_lang, update_audio_status, update_task_status
from flaskr.stripe import get_balance, update_balance
from flaskr.transcribe import extract_text_from_srt, subtitle_to_dict, transcribe_audio
import datetime
import math




nltk.download('punkt')





#input is the entry_key
def main(input: dict) -> str:
    start_time = datetime.datetime.now()

    user_id = input["user_id"]
    user_sub = input["user_sub"]
    entry_key = input["entry_key"]

    transcript_file_name = f"transcript/{entry_key}"
    subtitle_file_name = f"subtitle/{entry_key}"
    audio_file_name = f"audio/{entry_key}"

    update_audio_status(user_id, entry_key, "processing")

    balance_in_cents = get_balance(user_sub)

    audio_info = get_audio_info(entry_key, user_id)
    audio_duration = float(audio_info["duration"])
    cost_in_cents = math.ceil(audio_duration * COST_PER_SECOND * 100)
    audio_file_extension = audio_info["file_extension"]

    reimburse_cents = balance_in_cents + cost_in_cents

    task_id = create_task_entry_key(user_id, 'transcribe', entry_key, audio_info["file_name"])



    update_task_status(user_id, task_id, "downloading_file", "Downloading audio from file")
    try:
        audio_file = download_file_from_azure(audio_file_name, user_id)
    except Exception as e:
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "download_failed", f"Download failed, user reimbursed.")
        logging.error('azure error: ', e)
        return json.dumps({entry_key: "download_failed"})
    
    # #TODO prepocess audio file, convert to small file type (only lossless) and post small version to openAI

    update_task_status(user_id, task_id, "transcribing", "Transcribing audio in file")
    is_large_file = audio_file.size > 25 * 1024 * 1024
    try:
        if is_large_file:
            # TODO chunk files into 25MB chunks and transcribe each chunk
            #IMPORTANT respect word boundaries (pydub can help with this)
            update_balance(reimburse_cents, user_sub)
            update_task_status(user_id, task_id, "file_too_large", f"Transcribing large files is not supported yet, user reimbursed.")
            return json.dumps({entry_key: "large_file_not_supported_yet"})

        audio_content = audio_file.content_as_bytes()
        with tempfile.NamedTemporaryFile(suffix=audio_file_extension, delete=False) as tmp_file:
            tmp_file.write(audio_content)
            tmp_file.seek(0)
            subtitles = transcribe_audio(tmp_file)

        os.remove(tmp_file.name)
    except Exception as e:
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "transcribe_failed", f"Transcribe failed, user reimbursed.")
        logging.error('openAI error: ', e)
        return json.dumps({entry_key: "transcribe_failed"})

    # upload subtitle file to azure & store subtitle file info in firebase
    update_task_status(user_id, task_id, "uploading_subtitles", "Uploading subtitles file")
    upload_file_to_azure(subtitle_file_name, subtitles, user_id)
    store_file_info(entry_key, 'subtitle', user_id)

    # # upload transcript file to azure & store transcript file info in firebase
    subs = list(srt.parse(subtitles))
    transcript = extract_text_from_srt(subs)
    tokens = word_tokenize(transcript)
    word_count = len(tokens)
    metadata = {
        'wordCount': str(word_count),
        'charCount': str(len(transcript))
    }
    update_task_status(user_id, task_id, "uploading_transcript", "Uploading transcript file")
    upload_file_to_azure(transcript_file_name, transcript, user_id, metadata=metadata)
    store_file_info(entry_key, 'transcript', user_id)


    MAX_CHAR_COUNT = 5000 #azure lang detect limit
    if len(transcript) > MAX_CHAR_COUNT:
        transcript = transcript[:MAX_CHAR_COUNT]
    update_task_status(user_id, task_id, "detecting_language", "Detecting language")
    lang_result = detect_language(transcript)
    update_audio_lang(user_id, entry_key, lang_result['language'], lang_result['iso'])

    # #update audio file status in firebase
    update_audio_status(user_id, entry_key, "complete")

    #any cleanup here (llike maybe delete the audio file from azure?)

    #send email or push notification to user that transcription is complete

    end_time = datetime.datetime.now()
    time_taken = (end_time - start_time).total_seconds()
    time_taken = math.ceil(time_taken)
    update_task_status(user_id, task_id, "completed", "Transcript complete", time_taken)

    return json.dumps({entry_key: "complete"})
