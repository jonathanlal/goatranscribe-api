
import logging
import json
import azure.functions as func
import azure.durable_functions as df


def orchestrator_function(context: df.DurableOrchestrationContext):
    data = context.get_input()
    user_id = data['user_id']
    user_sub = data['user_sub']
    task_type = data['task_type']
    results = []

    if task_type == 'transcribe':
        for entry_key in data['entryKeys']:
            input_data = {"user_id": user_id, "entry_key": entry_key, "user_sub": user_sub, "email_on_finish": data["email_on_finish"]}
            result = yield context.call_activity('TranscribeActivityFunction', input_data)
            results.append(result)

    elif task_type == 'translate':
        for entry_key in data['entryKeys']:
            for target_lang in data['targetLangs']:
                input_data = {"user_id": user_id, "entry_key": entry_key, "user_sub": user_sub, "target_lang": target_lang}
                result = yield context.call_activity('TranslateActivityFunction', input_data)
                results.append(result)

    elif task_type == 'summarize':
            input_data = {"user_id": user_id, "entry_key": data['entryKey'], "user_sub": user_sub}
            result = yield context.call_activity('SummarizeActivityFunction', input_data)
            results.append(result)

    elif task_type == 'paragraph':
            input_data = {"user_id": user_id, "entry_key": data['entryKey'], "user_sub": user_sub}
            result = yield context.call_activity('ParagraphActivityFunction', input_data)
            results.append(result)

    elif task_type == 'encode':
        input_data = {"user_id": user_id, "entry_key": data['entryKey'], "user_sub": user_sub}
        result = yield context.call_activity('EncodeAudioActivityFunction', input_data)
        results.append(result)
        
    return results

main = df.Orchestrator.create(orchestrator_function)
