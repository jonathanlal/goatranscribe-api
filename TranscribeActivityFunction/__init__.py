import asyncio
import json
import logging
import math
import os
import tempfile
import time
import srt
import nltk
from nltk.tokenize import word_tokenize

from flaskr.azure import authenticate_media_client, copy_encoded_asset_to_user_container, delete_asset, delete_container, detect_language, download_file_from_azure, download_file_from_container, encode_audio_to_mp3, get_encoded_file_name_from_asset, getBlobUrl, process_audio, sanitize_container_name, upload_file_to_azure, upload_file_to_container, upload_file_to_media_service
from flaskr.firebase import COST_PER_SECOND, create_task_entry_key, get_audio_info, store_file_info, store_transaction_info, update_audio_lang, update_audio_status, update_task_status
from flaskr.stripe import get_balance, update_balance
from flaskr.transcribe import extract_text_from_srt, subtitle_to_dict, transcribe_audio
import datetime
from datetime import timedelta
import math

from pydub import AudioSegment


nltk.download('punkt')


def adjust_srt(srt_text, last_end_time, last_index):
    subs = list(srt.parse(srt_text))

    for sub in subs:
        sub.start += last_end_time
        sub.end += last_end_time
        sub.index += last_index

    return srt.compose(subs), subs[-1].end, subs[-1].index

def split_audio(audio_file_path):
    audio = AudioSegment.from_file(audio_file_path, format="mp3")

    # Break audio into chunks of 50 minute chunks
    # 64kbps = around 53 minutes for 25mb
    chunk_length = 50 * 60 * 1000  # length in milliseconds
    chunks = []

    for i in range(0, len(audio), chunk_length):
        chunks.append(audio[i:i + chunk_length])

    return chunks


#input is the entry_key
def main(input: dict) -> str:
    start_time = datetime.datetime.now()

    user_id = input["user_id"]
    user_sub = input["user_sub"]
    entry_key = input["entry_key"]

    transcript_file_name = f"{entry_key}.txt"
    # transcript_file_name = f"transcript/{entry_key}.txt"
    subtitle_file_name = f"{entry_key}.srt"
    # subtitle_file_name = f"subtitle/{entry_key}.srt"
    # audio_file_name = f"audio/{entry_key}"
    audio_file_name = f"encoded/{entry_key}.mp3"

    audio_info = get_audio_info(entry_key, user_id)

    task_id = create_task_entry_key(user_id, 'transcribe', entry_key, audio_info["file_name"])
    update_audio_status(user_id, entry_key, "processing")

    balance_in_cents = get_balance(user_sub)

    
    encoded = audio_info.get("encoded", False)
    if not encoded:
        update_task_status(user_id, task_id, "encoding", "Encoding audio")
        # Check every 2 seconds if the audio is encoded for a total of up to 5 minutes
        end_time = start_time + datetime.timedelta(minutes=5)
        while datetime.datetime.now() < end_time:
            audio_info = get_audio_info(entry_key, user_id)
            encoded = audio_info.get("encoded", False)
            encoded_progress = audio_info.get("encoded_progress", 0)
            if encoded_progress > 0:
                update_task_status(user_id, task_id, "encoding", f"Encoding audio {encoded_progress}%")
            if encoded:
                break
            else:
                time.sleep(2)  # wait for 2 seconds before the next check
        else:
            logging.error("ENCODING FAILED")
            # If we exit the loop because 5 minutes has passed and not because the audio has been encoded, return failure
            return json.dumps({entry_key: "encoding_failed"})

    audio_duration = float(audio_info["duration"])
    cost_in_cents = math.ceil(audio_duration * COST_PER_SECOND * 100)
    # audio_file_extension = audio_info["file_extension"]
    # audio_file_url = audio_info["file_url"]


    reimburse_cents = balance_in_cents + cost_in_cents

    

    update_task_status(user_id, task_id, "downloading_file", "Downloading audio from file")
    try:
        audio_blob = download_file_from_azure(audio_file_name, user_id)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            temp_audio_file.write(audio_blob.content_as_bytes())
            temp_audio_path = temp_audio_file.name
    except Exception as e:
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "download_failed", f"Download failed, user reimbursed.")
        logging.error('azure error: %s', e)
        return json.dumps({entry_key: "download_failed"})

    try:
        update_task_status(user_id, task_id, "chunking", "Chunking audio file")
        chunks = split_audio(temp_audio_path)
        last_end_time = timedelta(0)
        last_index = 1
        subtitles = []
        last_prompt = None
        for i, chunk in enumerate(chunks):
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                try:
                    chunk.export(tmp_file.name, format="mp3", bitrate="64k")
                    update_task_status(user_id, task_id, "transcribing", f"Transcribing audio chunk {i+1}/{len(chunks)}")
                    
                    # size_in_bytes = os.path.getsize(tmp_file.name)
                    # logging.info(f"CHUNK SIZE: {size_in_bytes}")

                    srt_text = transcribe_audio(tmp_file, initial_prompt=last_prompt)
                    
                    # Adjust the subtitles
                    subs = list(srt.parse(srt_text))
                    adjusted_subs = []
                    for sub in subs:
                        sub.index += last_index
                        sub.start += last_end_time
                        sub.end += last_end_time
                        adjusted_subs.append(sub)
                    
                    # Get the last end time and index for the next chunk
                    if adjusted_subs:
                        last_end_time = adjusted_subs[-1].end
                        last_index += len(adjusted_subs)


                    subtitles += adjusted_subs

                    transcript_chunk = extract_text_from_srt(subs)
                    last_prompt = ' '.join(transcript_chunk.split()[-224:])
                finally:
                    tmp_file.close() 
                    os.remove(tmp_file.name)


        temp_audio_file.close()
        os.remove(temp_audio_path)
        
    except Exception as e:
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "transcribe_failed", f"Transcribe failed, user reimbursed.")
        logging.error('openAI error: %s', e)
        return json.dumps({entry_key: "transcribe_failed"})

    # upload subtitle file to azure & store subtitle file info in firebase
    update_task_status(user_id, task_id, "uploading_subtitles", "Uploading subtitles file")
    
    subtitle_container_name = f"{user_id}/subtitle"

    subtitles = srt.compose(subtitles, reindex=True)

    upload_file_to_container(subtitles, subtitle_container_name, subtitle_file_name)
    store_file_info(entry_key, 'subtitle', subtitle_file_name, user_id)

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
    transcript_container_name = f"{user_id}/transcript"
    upload_file_to_container(transcript, transcript_container_name, transcript_file_name, metadata=metadata)
    store_file_info(entry_key, 'transcript', transcript_file_name, user_id)


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
