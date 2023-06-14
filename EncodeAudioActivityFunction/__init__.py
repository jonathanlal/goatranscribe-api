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

    
    if os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT') == 'Production':
        # Code is running in Azure, use the mounted file share
        ffmpeg_path = "/..".join([str(context.function_directory), FFMPEG_RELATIVE_PATH, FFMPEG])
    else:
        # Code is running locally, use Windows PATH
        ffmpeg_path = FFMPEG


    # try:
  
    #     test = "/..".join([str(context.function_directory), FFMPEG_RELATIVE_PATH])
    #     logging.info(f"PATH: {test}")

    #     files2 = os.listdir(test)
    #     logging.info(f"Files2 in {test}: {files2}")
    # except Exception as e:
    #     logging.error(f"Error listing files in {test}: {str(e)}")



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
    new_audio_file = extract_encode_audio(temp_audio_path, f"{entry_key}.mp3", ffmpeg_path)
    if new_audio_file is None:
        update_task_status(user_id, task_id, "encoding_failed", f"Encoding failed, user reimbursed.")
        return json.dumps({entry_key: "encoding_failed"})
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
    
def extract_encode_audio(input_file, output_file, ffmpeg_path):
    try:
        # Extract audio
        # ffmpeg.input(input_file).output(output_file, format='mp3', audio_bitrate='64k').run(capture_stdout=True, capture_stderr=True)
        # subprocess.check_output([ffmpeg_path, '-i', input_file, '-b:a', '64k', output_file])
        subprocess.check_output([ffmpeg_path, '-i', input_file, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '64k', output_file])
        return output_file
    # except ffmpeg.Error as e:
    except Exception as e:
        print('Error during audio extraction:', e)
        return None