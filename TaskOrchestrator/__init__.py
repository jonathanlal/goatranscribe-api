# This function is not intended to be invoked directly. Instead it will be
# triggered by an HTTP starter function.
# Before running this sample, please:
# - create a Durable activity function (default name is "Hello")
# - create a Durable HTTP starter function
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt

import logging
import json

import azure.functions as func
import azure.durable_functions as df
from flaskr.firebase import create_task_entry_key


def orchestrator_function(context: df.DurableOrchestrationContext):
    data = context.get_input()
    user_id = data['user_id']
    user_sub = data['user_sub']
    task_type = data['task_type']
    results = []

    if task_type == 'transcribe':
        for entry_key in data['entryKeys']:
            # logging.info(f"task_id: {task_id}")
            input_data = {"user_id": user_id, "entry_key": entry_key, "user_sub": user_sub}
            result = yield context.call_activity('TranscribeActivityFunction', input_data)
            results.append(result)

    elif task_type == 'translate':
        for entry_key in data['entryKeys']:
            for target_lang in data['targetLangs']:
                input_data = {"user_id": user_id, "entry_key": entry_key, "user_sub": user_sub, "target_lang": target_lang}
                result = yield context.call_activity('TranslateActivityFunction', input_data)
                results.append(result)
        
    return results

main = df.Orchestrator.create(orchestrator_function)