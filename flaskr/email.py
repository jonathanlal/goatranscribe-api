import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
import datetime
import urllib.parse
import jwt

admin_support_confirmation_template_id = "d-d4f15cec4585477d9ac35bfc8392f313"
confirmation_template_id = "d-7a395150f54d481189686ffb35dee8a9"
transcript_complete_template_id = "d-258bdcfe60b94f7f90abe9aa9e6966e9"

#'email_promotional' | 'email_transcripts' | 'email_support_confirmation'
def create_unsubscribe_url(user_id, email_type):
    payload = {
        'user_id': user_id,
        'email_type': email_type,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    token = jwt.encode(payload, os.environ.get('AUTH0_CLIENT_ID'), algorithm='HS256')
    url_token = urllib.parse.quote_plus(token)
    return f"https://api.goatranscribe.com/unsubscribe?token={url_token}"

def send_support_confirmation(message, email, user_id):
    unsubscribe_url = create_unsubscribe_url(user_id, 'email_support_confirmation')
    dynamic_data = {
        "message": message,
        "unsubscribe_url": unsubscribe_url,
    }

    message = Mail(
    from_email=os.environ.get('SUPPORT_EMAIL'),
    to_emails=email,
    )

    message.dynamic_template_data = dynamic_data
    message.template_id = confirmation_template_id
    try:
        key = os.environ.get('SENDGRID_API_KEY')
        sg = SendGridAPIClient(key)
        response = sg.send(message)
        return response.status_code
    except Exception as e:
        logging.info(e.message)
        return 500


def send_support_confirmation_admin(message, reason, email, user_id):
    dynamic_data = {
        "message": message,
        "reason": reason,
        "user_email": email,
        "user_id": user_id,
    }

    message = Mail(
    from_email=os.environ.get('SUPPORT_EMAIL'),
    to_emails=os.environ.get('ADMIN_SUPPORT_EMAIL'),
    )

    message.dynamic_template_data = dynamic_data
    message.template_id = admin_support_confirmation_template_id
    try:
        key = os.environ.get('SENDGRID_API_KEY')
        sg = SendGridAPIClient(key)
        response = sg.send(message)
        return response.status_code
    except Exception as e:
        logging.info(e.message)
        return 500
    



def send_transcript_complete_email(entry_id, email, file_name, user_id):
    unsubscribe_url = create_unsubscribe_url(user_id, 'email_transcripts')
    dynamic_data = {
        "entry_id": entry_id,
        "file_name": file_name,
        "unsubscribe_url": unsubscribe_url,
    }

    message = Mail(
    from_email='noreply@goatranscribe.com',
    to_emails=email,
    )

    message.dynamic_template_data = dynamic_data
    message.template_id = transcript_complete_template_id
    try:
        key = os.environ.get('SENDGRID_API_KEY')
        sg = SendGridAPIClient(key)
        response = sg.send(message)
        return response.status_code
    except Exception as e:
        logging.info(e.message)
        return 500
