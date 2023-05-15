# This function is not intended to be invoked directly. Instead it will be
# triggered by an orchestrator function.
# Before running this sample, please:
# - create a Durable orchestration function
# - create a Durable HTTP starter function
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt

import logging
# import time


#input is the entry_key
def main(input: str) -> str:

    

    # get file from azure

    # get user balance

    # get cost of file (check cost in firebase vs estimated cost)

    # check if user balance is suffifient. 

    #TODO prepocess audio file, convert to small file type (maybe even downscale if it doesn;t fuck with quality) and post small version to openAI

    #TODO chunk files here with dfunction

    # openAI.transcribe

    # update user balance


    # time.sleep(5)
    return f"Hello {input}!"
