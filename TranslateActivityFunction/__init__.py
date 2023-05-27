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
import time
import srt
# import nltk
# from nltk.tokenize import word_tokenize

from flaskr.azure import create_container_and_sas, delete_container, detect_language, download_file_from_azure, download_file_from_container, get_blob_sas_test, translate_docs, upload_file_to_azure, upload_file_to_container
from flaskr.firebase import COST_PER_CHARACTER, COST_PER_SECOND, create_task_entry_key, get_audio_info, get_transcript_info, store_file_info, store_subtitles_translation_info, store_transaction_info, store_transcript_translation_info, update_audio_lang, update_audio_status, update_task_status, update_transcript_translations
from flaskr.stripe import get_balance, update_balance
from flaskr.transcribe import extract_text_from_srt, subtitle_to_dict, transcribe_audio
import datetime
import math


# nltk.download('punkt')


#input is the entry_key
def main(input: dict) -> str:
    start_time = datetime.datetime.now()

    user_id = input["user_id"]
    user_sub = input["user_sub"]
    entry_key = input["entry_key"]
    target_lang = input["target_lang"] #fr, es, de, etc.

    logging.info("UPLOADING FILE!!!!!!!!!!!!!!!!!!!!!!!!")
    # transcript_file_name = f"transcript/{entry_key}"
    subtitle_file_name = f"subtitle/{entry_key}"
    translated_subtitle_file_name = f"subtitle/{entry_key}-{target_lang}"
    translated_transcript_file_name = f"transcript/{entry_key}-{target_lang}"

    balance_in_cents = get_balance(user_sub)

    transcript_info = get_transcript_info(entry_key, user_id)
    transcript_chars = int(transcript_info.get("char_count"))
    cost_in_cents = math.ceil(transcript_chars * COST_PER_CHARACTER * 100) 

    reimburse_cents = balance_in_cents + cost_in_cents

    task_id = create_task_entry_key(user_id, 'translate', entry_key, target_lang)


    update_task_status(user_id, task_id, "downloading_file", "Downloading text from file")
    try:
        subtitles_file = download_file_from_azure(subtitle_file_name, user_id)
    except Exception as e:
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "download_failed", f"Download failed, user reimbursed.")
        logging.error('azure error: %s', e)
        return json.dumps({entry_key: "download_failed"})
    
    subtitles = subtitles_file.content_as_text()
    logging.info("SUBTITLES FILE: %s", subtitles)

    update_task_status(user_id, task_id, "translating", "Translating text in file")
    # task_id = "nwnhxh2bo0kzauip9lx"
    compliant_task_id_name = task_id.lower().replace("_", "x0x")
    source_container_name = f"{compliant_task_id_name}-source"
    target_container_name = f"{compliant_task_id_name}-target"
    source_translation_container = get_blob_sas_test(source_container_name, target_lang)
    source_translation_container = create_container_and_sas(source_container_name)
    target_translation_container = create_container_and_sas(target_container_name)
    # upload subtitle file to azure container (required for translation) # it translates all the files in a container
    logging.info("UPLOADING FILE!!!!!!!!!!!!!!!!!!!!!!!!")
    logging.info("UPLOADING FILE!!!!!!!!!!!!!!!!!!!!!!!!")
    logging.info("UPLOADING FILE!!!!!!!!!!!!!!!!!!!!!!!!")
    upload_file_to_container(subtitles, source_container_name, f"{target_lang}.txt") # needs valid file format like .txt jesus christ
    # start translation (stores translated file in target)
    logging.info("Creating translation job...")
    logging.info("target_language: %s", target_lang)
    logging.info("sourceUrl: %s", source_translation_container)
    logging.info("targetUrl: %s", target_translation_container)

    # time.sleep(10)
    try:

        poller = translate_docs(target_lang, source_translation_container, target_translation_container)
        result = poller.result()
        # logging.info("Status: {}".format(poller.status()))
        # logging.info("Created on: {}".format(poller.details.created_on))
        # logging.info("Last updated on: {}".format(poller.details.last_updated_on))
        # logging.info("Total number of translations on documents: {}".format(poller.details.documents_total_count))

        # logging.info("\nOf total documents...")
        # logging.info("{} failed".format(poller.details.documents_failed_count))
        # logging.info("{} succeeded".format(poller.details.documents_succeeded_count))

        for document in result:
            # logging.info("Document ID: {}".format(document.id))
            # logging.info("Document status: {}".format(document.status))
            if document.status == "Succeeded":
                update_task_status(user_id, task_id, "downloading_file", "Downloading translated file")
                # download translated file from stored location after translation is done
                logging.info("EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE")
                translated_subtitle_file = download_file_from_container(target_container_name, f"{target_lang}.txt")
                translated_subtitle_file = translated_subtitle_file.content_as_text()
                logging.info("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
                logging.info(translated_subtitle_file)
                logging.info("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
                upload_file_to_azure(translated_subtitle_file_name, translated_subtitle_file, user_id)
                store_subtitles_translation_info(entry_key, target_lang, user_id)


                subs = list(srt.parse(translated_subtitle_file))
                transcript = extract_text_from_srt(subs)
                logging.info(transcript)
                logging.info("OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO")
                upload_file_to_azure(translated_transcript_file_name, transcript, user_id)
                store_transcript_translation_info(entry_key, target_lang, user_id)

                #update firebase transcript info with available translation
                update_transcript_translations(user_id, entry_key, target_lang)
                logging.info("ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZz")
                #delete containers
                delete_container(source_container_name)
                delete_container(target_container_name)

                # logging.info("Source document location: {}".format(document.source_document_url))
                # logging.info("Translated document location: {}".format(document.translated_document_url))
                # logging.info("Translated to language: {}\n".format(document.translated_to))
            # else:
                # logging.error("Error Code: {}, Message: {}\n".format(document.error.code, document.error.message))

        
        end_time = datetime.datetime.now()
        time_taken = (end_time - start_time).total_seconds()
        time_taken = math.ceil(time_taken)
        update_task_status(user_id, task_id, "completed", "Translation complete", time_taken)
        

    except Exception as e:
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "translate_failed", f"Translate failed, user reimbursed.")
        logging.error('translation error: %s', str(e))
        return json.dumps({entry_key: "translate_failed"})

 

    return json.dumps({entry_key: "complete"})
