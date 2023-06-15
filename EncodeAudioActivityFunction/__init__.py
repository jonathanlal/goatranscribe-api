import json
import logging

import subprocess
import azure.functions as func



from flaskr.azure import download_file_from_azure, upload_file_to_container
from flaskr.firebase import create_task_entry_key, get_audio_info, update_audio_encoded, update_task_status
# import ffmpeg
import os
import tempfile


FFMPEG_RELATIVE_PATH = os.environ['FILE_SHARE_MOUNT_PATH']
FFMPEG = "ffmpeg"



def main(input: str, context: func.Context) -> str:

    user_id = input["user_id"]
    entry_key = input["entry_key"]
    
    if os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT') == 'Production':
        # Code is running in Azure, use the mounted file share
        ffmpeg_path = '/home/site/wwwroot/ffmpeg_lib/ffmpeg'
        #tmp directory on linux to read/write files
        output_file_name = os.path.join("/tmp", f"{entry_key}.mp3")
    else:
        # Code is running locally, use Windows PATH
        ffmpeg_path = FFMPEG
        output_file_name = f"{entry_key}.mp3"


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
    logging.info(f"Encoding file {temp_audio_path}")
    
    extract_status = extract_encode_audio(temp_audio_path, output_file_name, ffmpeg_path)
    logging.info("encoding completed")
    if extract_status is None:
        logging.info("extract_encode_audio returned None")
        update_task_status(user_id, task_id, "encoding_failed", f"Encoding failed, user reimbursed.")
        return json.dumps({entry_key: "encoding_failed"})
    logging.info("file successfully encoded is not None")
    new_audio_file_content = read_file_as_bytes(output_file_name)
    upload_file_to_container(new_audio_file_content, user_id, f"encoded/{entry_key}.mp3")

    logging.info("removing temp files")
    # Cleanup: remove the original and new local files
    os.remove(temp_audio_file.name)
    os.remove(output_file_name)
    logging.info("updating task status")
    update_task_status(user_id, task_id, "encoding_file", f"completed")
    update_audio_encoded(user_id, entry_key)


    # update_audio_status(user_id, entry_key, "Ready")

    return json.dumps({entry_key: "encoded_complete"})


def read_file_as_bytes(file_path):
    with open(file_path, 'rb') as file:
        return file.read()
    
def extract_encode_audio(input_file, output_file, ffmpeg_path):
    try:
        subprocess.check_output([ffmpeg_path, '-i', input_file, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '64k', output_file], stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        logging.info(f'Error during audio extraction: {e.output.decode()}')
        return None