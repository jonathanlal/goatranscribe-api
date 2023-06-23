import datetime
import json
import logging
import math
from flaskr.azure import download_file_from_azure, upload_file_to_azure

from flaskr.firebase import COST_PER_CHARACTER, create_task_entry_key, get_audio_info, get_transcript_info, store_transaction_info, update_summary_status, update_task_status
from flaskr.stripe import get_balance, update_balance
from flaskr.transcribe import generate_summary, create_summary_chunk_16k
import tiktoken


def main(input: str) -> str:
    start_time = datetime.datetime.now()
    user_id = input["user_id"]
    user_sub = input["user_sub"]
    entry_key = input["entry_key"]

    transcript_file_name = f"transcript/{entry_key}.txt"
    summary_file_name = f"summary/{entry_key}.txt"

    balance_in_cents = get_balance(user_sub)

    transcript_info = get_transcript_info(entry_key, user_id)
    transcript_chars = int(transcript_info.get("char_count"))
    cost_in_cents = math.ceil(transcript_chars * COST_PER_CHARACTER * 100) 

    reimburse_cents = balance_in_cents + cost_in_cents
    
    audio_info = get_audio_info(entry_key, user_id)
    task_id = create_task_entry_key(user_id, 'summarize', entry_key, audio_info["file_name"])

    update_task_status(user_id, task_id, "downloading_file", "Downloading text from file")

    try:
        transcript = download_file_from_azure(transcript_file_name, user_id)
        # transcript = download_file_from_container(target_container_name, transcript_file_name)
        transcript = transcript.content_as_text()
    except Exception as e:
        store_transaction_info(user_id, "refund", cost_in_cents, cost_in_cents+balance_in_cents)
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "download_failed", f"Download failed, user reimbursed.")
        logging.error('azure error: %s', e)
        return json.dumps({entry_key: "download_failed"})
    

    

    try:

        update_task_status(user_id, task_id, "encoding_text", "Encoding text")
        # encode text into tokens
        gpt3_enc = tiktoken.encoding_for_model("gpt-3.5-turbo-16k")
        transcript_tokens = gpt3_enc.encode_ordinary(transcript)
        transcript_token_count = len(transcript_tokens)

        gpt4_enc = tiktoken.encoding_for_model("gpt-4")
        gpt4_token_count = len(gpt4_enc.encode_ordinary(transcript))

        gpt4_max_tokens = 8192 # 8192 / 600 margin
        safe_max_tokens_limit = 7192 #for chatgpt4 (-1000 for room for final summary response)
        gpt3_max_tokens = 16000
        summary_chunks = []
        logging.info("transcript_token_count: %s", gpt4_token_count)
        logging.info("max_tokens: %s", gpt3_max_tokens)
        if gpt4_token_count > gpt4_max_tokens:
            update_task_status(user_id, task_id, "chunking_text", "Creating chunks of text")
            # split tokens into chunks of 16k tokens (16k tokens would be 16000 * 725)
            token_chunks = (transcript_tokens[i:i + gpt3_max_tokens] for i in range(0, transcript_token_count, gpt3_max_tokens))
            token_chunks = list(token_chunks)
            logging.info("token_chunks: %s", len(token_chunks))
            text_chunks = [gpt3_enc.decode(chunk) for chunk in token_chunks]
            logging.info("text_chunks: %s", len(text_chunks))
            
            
            for index, chunk in enumerate(text_chunks):
                update_task_status(user_id, task_id, "summarizing_text_chunk", f"Summarizing chunk {index}/{len(text_chunks)}")
                # create summary from each text_chunk of 16k tokens
                logging.info("Creating summary of chunk")
                max_tokens_returned = min(int(safe_max_tokens_limit / len(text_chunks)), safe_max_tokens_limit)
                context_tokens = token_chunks[index]
                max_tokens_returned = min(max_tokens_returned, gpt3_max_tokens - len(context_tokens))

                logging.info("max_tokens_returned: %s", max_tokens_returned)
                summary_chunk = create_summary_chunk_16k(chunk, max_tokens_returned)
                logging.info(f"summary_chunk: {summary_chunk}")
                summary_chunks.append(summary_chunk)
            # join summary chunks into one summary
            summaries_to_summarize = " ".join(summary_chunks)
            update_task_status(user_id, task_id, "creating_summary", "Creating final summary")

            # summaries_tokens = gpt3_enc.encode_ordinary(summaries_to_summarize)
            # summaries_token_count = len(summaries_tokens)
            # max_tokens_returned =  safe_max_tokens_limit - summaries_token_count
            # logging.info(f"final max tokens: {max_tokens_returned}")
            final_summary = generate_summary(summaries_to_summarize)
        
        else:
            # create summary directly from transcript
            update_task_status(user_id, task_id, "creating_summary", "Creating summary")
            # max_tokens_returned = safe_max_tokens_limit - transcript_token_count
            # logging.info(f"final max tokens: {max_tokens_returned}")
            final_summary = generate_summary(transcript)

        # logging.info(f"token_approx: {token_approx}")
        # summary = create_summary(transcript)
        update_task_status(user_id, task_id, "uploading_file", "Uploading summary file")

        upload_file_to_azure(summary_file_name, final_summary, user_id)
        

    except Exception as e:
        store_transaction_info(user_id, "refund", cost_in_cents, cost_in_cents+balance_in_cents)
        update_balance(reimburse_cents, user_sub)
        update_task_status(user_id, task_id, "summary_failed", f"Summary failed, user reimbursed.")
        logging.error('summary_failed error: %s', e)
        return json.dumps({entry_key: "summary_failed"})
    
    end_time = datetime.datetime.now()
    time_taken = (end_time - start_time).total_seconds()
    time_taken = math.ceil(time_taken)
    
    update_summary_status(user_id, entry_key)

    update_task_status(user_id, task_id, "completed", "Summary complete", time_taken)

    return json.dumps({entry_key: "complete"})
 