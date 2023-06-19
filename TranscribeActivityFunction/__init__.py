import json
import logging
import math
import os
import tempfile
import time
from flaskr.auth import getUserEmail
from flaskr.email import send_transcript_complete_email
import srt
import nltk
from nltk.tokenize import word_tokenize

from flaskr.azure import detect_language, download_file_from_azure, upload_file_to_container
from flaskr.firebase import COST_PER_SECOND, create_task_entry_key, get_audio_info, get_failed_transcribe_task_id, store_file_info, store_transaction_info, update_audio_lang, update_audio_status, update_task_status
from flaskr.stripe import get_balance, update_balance
from flaskr.transcribe import extract_text_from_srt, transcribe_audio
import datetime
from datetime import timedelta
import math
import subprocess
# import shlex

# from pydub import AudioSegment
# from pydub.utils import mediainfo

# path to ffmpeg and ffprobe
# ffmpeg_path = "/home/site/wwwroot/ffmpeg_lib/ffmpeg"
# ffprobe_path = "/home/site/wwwroot/ffmpeg_lib/ffprobe"

# AudioSegment.converter = ffmpeg_path
# AudioSegment.ffprobe = ffprobe_path
# mediainfo.ffprobe = ffprobe_path

nltk.download('punkt')

# def get_audio_duration(audio_file_path):
#     audio_info = mediainfo(audio_file_path)
#     duration = int(float(audio_info["duration"]))  # duration in seconds
#     return timedelta(seconds=duration)

def adjust_srt(srt_text, last_end_time, last_index):
    subs = list(srt.parse(srt_text))

    for sub in subs:
        sub.start += last_end_time
        sub.end += last_end_time
        sub.index += last_index

    return srt.compose(subs), subs[-1].end, subs[-1].index

# def split_audio(audio_file_path):
#     audio = AudioSegment.from_mp3(audio_file_path)

#     # Break audio into chunks of 50 minute chunks
#     # 64kbps = around 53 minutes for 25mb
#     chunk_length = 50 * 60 * 1000  # length in milliseconds
#     chunks = []

#     for i in range(0, len(audio), chunk_length):
#         chunks.append(audio[i:i + chunk_length])

#     return chunks

def split_audio(input_file_path, audio_duration, entry_key):
    segment_duration = 50 * 60  # length in seconds
    # chunks = []
    
    num_segments = math.ceil(audio_duration / segment_duration)

    is_prod = os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT') == 'Production'

    if is_prod:
        ffmpeg_path = '/home/site/wwwroot/ffmpeg_lib/ffmpeg'
        output_directory = f"./tmp/{entry_key}"
    else:
        ffmpeg_path = 'ffmpeg'
        output_directory = f"./{entry_key}"

    output_files = []

    os.makedirs(output_directory, exist_ok=True)

    output_pattern = f"{output_directory}/out%03d.mp3"


    try:
        # Run ffmpeg to create the segments
        cmd = [ffmpeg_path, "-i", input_file_path, "-f", "segment", "-segment_time", str(segment_duration), "-c", "copy", output_pattern]
        subprocess.call(cmd)

        # Generate a list of the output filenames
        output_files = [output_pattern % i for i in range(num_segments)]
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    
    return output_files

    # if os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT') == 'Production':
    #     # Code is running in Azure, use the mounted file share
    #     ffmpeg_path = '/home/site/wwwroot/ffmpeg_lib/ffmpeg'
    #     #tmp directory on linux to read/write files
    #     output_file_name = os.path.join("/tmp", f"{entry_key}.mp3")
    # else:
    #     # Code is running locally, use Windows PATH
    #     ffmpeg_path = FFMPEG
    #     output_file_name = f"{entry_key}.mp3"

    # Get the duration of the input file
    # try:
    #     duration_str = subprocess.check_output([ffmpeg_path, "-i", input_file_path, "-f", "segment", "-segment_time" str(chunk_length), "-c", "copy", output_pattern]).decode()
    #     h, m, s = duration_str.split(":")
    #     total_seconds = int(h) * 3600 + int(m) * 60 + float(s)
    # except subprocess.CalledProcessError as e:
    #     logging.error(f'Error getting duration: {e.output.decode()}')
    #     return None

    # for i in range(0, int(total_seconds), chunk_length):

    #     if is_prod:
    #         output_file_path = os.path.join("/tmp", f"chunk_{i//chunk_length}.mp3")
    #     else:
    #         output_file_path = f"chunk_{i//chunk_length}.mp3"

    #     # start_time = str(timedelta(seconds=i))
    #     cmd = f'{ffmpeg_path} -i "{input_file_path}" - "{output_file_path}"'
    #     try:
    #         subprocess.check_output(cmd, shell=True)
    #         chunks.append(output_file_path)
    #     except subprocess.CalledProcessError as e:
    #         logging.error(f'Error during chunk creation: {e.output.decode()}')
    #         return None

    # return chunks



#input is the entry_key
def main(input: dict) -> str:
    start_time = datetime.datetime.now()

    user_id = input["user_id"]
    user_sub = input["user_sub"]
    entry_key = input["entry_key"]
    is_retry = input["retry"]
    email_on_finish = input["email_on_finish"]

    transcript_file_name = f"{entry_key}.txt"
    # transcript_file_name = f"transcript/{entry_key}.txt"
    subtitle_file_name = f"{entry_key}.srt"
    # subtitle_file_name = f"subtitle/{entry_key}.srt"
    # audio_file_name = f"audio/{entry_key}"
    audio_file_name = f"encoded/{entry_key}.mp3"

    audio_info = get_audio_info(entry_key, user_id)

    logging.info(f"is_retry: {is_retry}")

    if is_retry:
        task_id = get_failed_transcribe_task_id(user_id, entry_key, audio_info["file_name"])
        update_task_status(user_id, task_id, "retrying", "Retrying transcription")
    else:
        task_id = create_task_entry_key(user_id, 'transcribe', entry_key, audio_info["file_name"])
    
    update_audio_status(user_id, entry_key, "processing")

    balance_in_cents = get_balance(user_sub)

    


    audio_duration = float(audio_info["duration"])
    cost_in_cents = math.ceil(audio_duration * COST_PER_SECOND * 100)
    # audio_file_extension = audio_info["file_extension"]
    # audio_file_url = audio_info["file_url"]


    reimburse_cents = balance_in_cents + cost_in_cents


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
            store_transaction_info(user_id, "refund", cost_in_cents, reimburse_cents)
            update_balance(reimburse_cents, user_sub)
            update_task_status(user_id, task_id, "encoding_failed", f"Encoding failed, user reimbursed.")
            # If we exit the loop because 5 minutes has passed and not because the audio has been encoded, return failure
            return json.dumps({entry_key: "encoding_failed"})

    

    update_task_status(user_id, task_id, "downloading_file", "Downloading audio from file")
    try:
        logging.info(f"Downloading file: {audio_file_name}")
        audio_blob = download_file_from_azure(audio_file_name, user_id)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
            logging.info(f"Writing file: {audio_file_name}")
            temp_audio_file.write(audio_blob.content_as_bytes())
            temp_audio_path = temp_audio_file.name
    except Exception as e:
        store_transaction_info(user_id, "refund", cost_in_cents, reimburse_cents)
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "download_failed", f"Download failed, user reimbursed.")
        logging.error('azure error: %s', e)
        return json.dumps({entry_key: "download_failed"})

    try:
        logging.info(f"getting audio duration from path: {temp_audio_path}")
        duration = int(float(audio_info["duration"]))  # duration in seconds
#     return timedelta(seconds=duration)
        # audio_duration = get_audio_duration(temp_audio_path)
        split_threshold = timedelta(minutes=50)
        is_split = timedelta(seconds=duration) > split_threshold
        logging.info(f"is_split: {is_split}")

        if is_split:
            update_task_status(user_id, task_id, "chunking", "Chunking audio file")
            logging.info(f"splottomg audio file if")
            chunks = split_audio(temp_audio_path, duration, entry_key)
        else:
            logging.info(f"segmenting audio file else")
            # audio = AudioSegment.from_mp3(temp_audio_path)
            chunks = [temp_audio_path]
            # chunks = split_audio(temp_audio_path, duration, entry_key)
        
        # chunks = split_audio(temp_audio_path)
        logging.info(f"passed splitting audio file")
        logging.info(f"chunks: {chunks}")
        last_end_time = timedelta(0)
        last_index = 1
        subtitles = []
        last_prompt = None
        for i, chunk in enumerate(chunks):
        # with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as tmp_file:
            try:
                with open(chunk, "rb") as tmp_file:
                    # chunk.export(tmp_file.name, format="mp3", bitrate="64k")
                    if is_split:
                        update_task_status(user_id, task_id, "transcribing", f"Transcribing audio chunk {i+1}/{len(chunks)}")
                    else:
                        update_task_status(user_id, task_id, "transcribing", f"Transcribing audio in file")
                    # size_in_bytes = os.path.getsize(tmp_file.name)
                    # logging.info(f"CHUNK SIZE: {size_in_bytes}")
                    logging.info(f"Transcribing audio chunk {i+1}/{len(chunks)}")
                    srt_text = transcribe_audio(tmp_file, initial_prompt=last_prompt)
                    logging.info(f"Transcribed finished {i+1}/{len(chunks)}")
                    # Adjust the subtitles
                    logging.info("adjusting subtitles")
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
                    logging.info("adjusting subtitles finished")
                    transcript_chunk = extract_text_from_srt(subs)
                    last_prompt = ' '.join(transcript_chunk.split()[-224:])
                    logging.info("about to pass chunk")
                    pass
                logging.info("removing chunk")
                os.remove(chunk)
            except Exception as e:
                store_transaction_info(user_id, "refund", cost_in_cents, reimburse_cents)
                update_balance(reimburse_cents, user_sub)
                update_task_status(user_id, task_id, "transcribe_failed", f"Transcribe failed, user reimbursed.")
                logging.error('segment file error: %s', e)
                return json.dumps({entry_key: "transcribe_failed"})
            # finally:
            #     tmp_file.close() 
            #     os.remove(tmp_file.name)

        logging.info("removing temp audio file")
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        # temp_audio_file.close()
        # os.remove(temp_audio_path)
        
    except Exception as e:
        store_transaction_info(user_id, "refund", cost_in_cents, reimburse_cents)
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

    if email_on_finish:
        user_email = getUserEmail(user_sub)
        send_transcript_complete_email(entry_key, user_email, audio_info["file_name"])


    end_time = datetime.datetime.now()
    time_taken = (end_time - start_time).total_seconds()
    time_taken = math.ceil(time_taken)
    update_task_status(user_id, task_id, "completed", "Transcript complete", time_taken)

    return json.dumps({entry_key: "complete"})
