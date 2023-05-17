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

from flaskr.azure import download_file_from_azure, upload_file_to_azure
from flaskr.firebase import COST_PER_SECOND, get_audio_info, store_file_info, update_audio_status
from flaskr.stripe import get_balance, update_balance
from flaskr.transcribe import extract_text_from_srt, subtitle_to_dict, transcribe_audio


nltk.download('punkt')


#input is the entry_key
def main(input: dict) -> str:
    user_id = input["user_id"]
    user_sub = input["user_sub"]
    entry_key = input["entry_key"]
    logging.info(json.dumps({"user_id": user_id, "entry_key": entry_key}))

    # #azure file locations
    transcript_file_name = f"transcript/{entry_key}"
    subtitle_file_name = f"subtitle/{entry_key}"
    audio_file_name = f"audio/{entry_key}"


    # get user balance
    balance_in_cents = get_balance(user_sub)

    # get cost of transcribing file
    audio_info = get_audio_info(entry_key, user_id)
    logging.info(json.dumps(audio_info))
    audio_duration = float(audio_info["duration"])
    audio_file_extension = audio_info["file_extension"]
    cost_in_cents = math.ceil(audio_duration * COST_PER_SECOND * 100)

    # ## This should never happen if the frontend is working properly
    if(balance_in_cents < cost_in_cents):
        update_audio_status(user_id, entry_key, "missing_funds")
        return json.dumps({entry_key: "missing_funds"})


    # # update firebase audio file status to processing
    update_audio_status(user_id, entry_key, "processing")

    # # get file from azure
    audio_file = download_file_from_azure(audio_file_name, user_id)
    # #TODO prepocess audio file, convert to small file type (only lossless) and post small version to openAI

    is_large_file = audio_file.size > 25 * 1024 * 1024

    data = {
        "user_id": user_id,
        "entry_key": entry_key,
        "user_sub": user_sub,
        "balance_in_cents": balance_in_cents,
        "cost_in_cents": cost_in_cents,
        "audio_duration": audio_duration,
        "audio_file_extension": audio_file_extension,
        "is_large_file": is_large_file,
        "size": audio_file.size,
    }
    
    logging.info(json.dumps(data))
    return json.dumps(data)



    # if is_large_file:
    #     #TODO chunk files into 25MB chunks and transcribe each chunk
    #     #IMPORTANT respect word boundaries (pydub can help with this)
    #     return json.dumps({input: "large_file_not_supported_yet"})

    # audio_content = audio_file.content_as_bytes()
    # with tempfile.NamedTemporaryFile(suffix=audio_file_extension, delete=False) as tmp_file:
    #     tmp_file.write(audio_content)
    #     tmp_file.seek(0)
    #     subtitles = transcribe_audio(tmp_file)

    # os.remove(tmp_file.name)

    # # upload subtitle file to azure & store subtitle file info in firebase
    # upload_file_to_azure(subtitle_file_name, subtitles)
    # store_file_info(input, 'subtitle')

    # # upload transcript file to azure & store transcript file info in firebase
    # subs = list(srt.parse(subtitles))
    # transcript = extract_text_from_srt(subs)
    # tokens = word_tokenize(transcript)
    # word_count = len(tokens)
    # metadata = {
    #     'wordCount': str(word_count)
    # }
    # upload_file_to_azure(transcript_file_name, transcript, metadata=metadata) #upload text transcript to azure
    # store_file_info(input, 'transcript')

    # # update user balance
    # new_balance = balance_in_cents - cost_in_cents
    # stripe_balance = update_balance(new_balance)

    # #this should never happen either
    # if(stripe_balance != new_balance):
    #     update_audio_status(input, "balance_mismatch")
    #     return json.dumps({input: "balance_mismatch"})

    # #update audio file status in firebase
    # update_audio_status(input, "complete")

    #any cleanup here (llike maybe delete the audio file from azure?)

    #send email or push notification to user that transcription is complete

    # return json.dumps({input: "complete"})
