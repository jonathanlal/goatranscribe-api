import json
import logging

from azure.functions import Context

from flaskr.azure import download_file_from_azure, upload_file_to_container
from flaskr.firebase import create_task_entry_key, get_audio_info, update_audio_encoded, update_task_status
import ffmpeg
import os
import tempfile

# FFMPEG_LIB_PATH = "../ffmpeg_lib"
FFMPEG_BIN_PATH = "../ffmpeg_lib/ffmpeg"  # Update this to your actual path



def main(context: Context, input: str) -> str:

    ABSOLUTE_FFMPEG_BIN_PATH = os.path.join(str(context.function_directory), FFMPEG_BIN_PATH)

    ffmpeg._run.ffmpeg_cmd = ABSOLUTE_FFMPEG_BIN_PATH


    # Set the path to the ffmpeg and ffprobe binaries
    # function_directory = context.function_directory
    # ffmpeg._run.DEFAULT_FFMPEG_PATH = os.path.join(function_directory, FFMPEG_LIB_PATH, "ffmpeg")
    # ffmpeg._run.DEFAULT_FFPROBE_PATH = os.path.join(function_directory, FFMPEG_LIB_PATH, "ffprobe")


    user_id = input["user_id"]
    entry_key = input["entry_key"]

    audio_file_name = f"audio/{entry_key}"
    audio_info = get_audio_info(entry_key, user_id)
    # update_audio_status(user_id, entry_key, "Encoding")

    task_id = create_task_entry_key(user_id, 'encode', entry_key, audio_info["file_name"])
    update_task_status(user_id, task_id, "downloading_file", "Downloading audio from file")
    try:
        original_audio_blob = download_file_from_azure(audio_file_name, user_id)
    except Exception as e:
        update_task_status(user_id, task_id, "download_failed", f"Download failed, user reimbursed.")
        logging.error('azure error: %s', e)
        return json.dumps({entry_key: "download_failed"})
    

    with tempfile.NamedTemporaryFile(delete=False) as temp_audio_file:
        temp_audio_file.write(original_audio_blob.content_as_bytes())
        temp_audio_path = temp_audio_file.name

    update_task_status(user_id, task_id, "encoding_file", f"Encoding file")
    new_audio_file = extract_encode_audio(temp_audio_path, f"{entry_key}.mp3")
    new_audio_file_content = read_file_as_bytes(new_audio_file)
    upload_file_to_container(new_audio_file_content, user_id, f"encoded/{new_audio_file}")

    # Cleanup: remove the original and new local files
    os.remove(temp_audio_file.name)
    os.remove(new_audio_file)

    update_task_status(user_id, task_id, "encoding_file", f"completed")
    update_audio_encoded(user_id, entry_key)


    # update_audio_status(user_id, entry_key, "Ready")

    return json.dumps({entry_key: "encoded_complete"})


def read_file_as_bytes(file_path):
    with open(file_path, 'rb') as file:
        return file.read()
    
def extract_encode_audio(input_file, output_file):
    try:
        # Extract audio
        ffmpeg.input(input_file).output(output_file, format='mp3', audio_bitrate='64k').run(capture_stdout=True, capture_stderr=True)
        return output_file
    except ffmpeg.Error as e:
        print('Error during audio extraction:', e)
        return None