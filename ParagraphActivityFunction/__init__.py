import datetime
import json
import logging
import math
from flaskr.azure import download_file_from_azure, upload_file_to_azure
from flaskr.firebase import COST_PER_CHARACTER, create_task_entry_key, get_audio_info, get_transcript_info, store_transaction_info, update_paragraph_status, update_task_status
from flaskr.stripe import get_balance, update_balance
from flaskr.transcribe import add_paragraphs


def main(input: str) -> str:
    start_time = datetime.datetime.now()
    user_id = input["user_id"]
    user_sub = input["user_sub"]
    entry_key = input["entry_key"]

    transcript_file_name = f"transcript/{entry_key}.txt"
    paragraphed_file_name = f"paragraphed/{entry_key}.txt"

    balance_in_cents = get_balance(user_sub)

    transcript_info = get_transcript_info(entry_key, user_id)
    transcript_chars = int(transcript_info.get("char_count"))
    cost_in_cents = math.ceil(transcript_chars * COST_PER_CHARACTER * 100) 

    reimburse_cents = balance_in_cents + cost_in_cents
    
    audio_info = get_audio_info(entry_key, user_id)
    task_id = create_task_entry_key(user_id, 'paragraph', entry_key, audio_info["file_name"])

    update_task_status(user_id, task_id, "downloading_file", "Downloading text from file")

    try:
        transcript = download_file_from_azure(transcript_file_name, user_id)
        transcript = transcript.content_as_text()
    except Exception as e:
        store_transaction_info(user_id, "refund", cost_in_cents, cost_in_cents+balance_in_cents)
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "download_failed", f"Download failed, user reimbursed.")
        logging.error('azure error: %s', e)
        return json.dumps({entry_key: "download_failed"})
    

    update_task_status(user_id, task_id, "adding_paragraphs", "Adding paragraphs to transcript")

    try:
        paragraphed_transcript = add_paragraphs(transcript)
        # logging.info(paragraphed_transcript)
        # paragraphed_transcript = paragraphed_transcript.choices[0].text.strip()

        update_task_status(user_id, task_id, "uploading_file", "Uploading transcript with paragraphs")

        upload_file_to_azure(paragraphed_file_name, paragraphed_transcript, user_id)
        

    except Exception as e:
        store_transaction_info(user_id, "refund", cost_in_cents, cost_in_cents+balance_in_cents)
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "adding_paragraphs_failed", f"Adding paragraphs failed, user reimbursed.")
        logging.error('openai error: %s', e)
        return json.dumps({entry_key: "download_failed"})
    
    end_time = datetime.datetime.now()
    time_taken = (end_time - start_time).total_seconds()
    time_taken = math.ceil(time_taken)
    
    update_paragraph_status(user_id, entry_key)

    update_task_status(user_id, task_id, "completed", "Adding paragraphs to transcript complete", time_taken)

    return json.dumps({entry_key: "complete"})
 