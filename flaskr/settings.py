from flask import Blueprint, request, jsonify, make_response
from authlib.integrations.flask_oauth2 import current_token
from flaskr.email import send_support_confirmation, send_support_confirmation_admin
from flaskr.firebase import get_user_settings, seen_uploads_welcome, update_email_status
from .auth import getUserEmail, require_auth, getUserID
import jwt
from os import environ as env
import urllib.parse



bp = Blueprint("settings", __name__)

SECRET_KEY = env.get("AUTH0_CLIENT_ID") # chose random string for secret key

@bp.route("/get_settings", methods=["POST"])
@require_auth(None)
def get_settings():
    user_id = getUserID(current_token)
    settings = get_user_settings(user_id)
    return jsonify(settings)

@bp.route("/seen_uploads_welcome_page", methods=["POST"])
@require_auth(None)
def seen_uploads_welcome_page():
    user_id = getUserID(current_token)
    seen_uploads_welcome(user_id)
    return jsonify("updated")

@bp.route("/send_support", methods=["POST"])
@require_auth(None)
def send_support():
    user_id = getUserID(current_token)
    message = request.json['message']
    reason = request.json['reason']
    user_email = getUserEmail(current_token.get('sub'))
    send_support_confirmation(message, user_email, user_id)
    send_support_confirmation_admin(message, reason, user_email, user_id)
    return jsonify("emails sent")


@bp.route("/update_email_preferences", methods=["POST"])
@require_auth(None)
def update_user_email_prefs():
    user_id = getUserID(current_token)
    status = request.json['isChecked']
    email_type = request.json['emailType']
    update_email_status(user_id, status, email_type)
    return jsonify("updated")




@bp.route("/unsubscribe", methods=["GET"])
def unsubscribe():
    url_token = request.args.get('token', None)

    if not url_token:
        return make_response(jsonify({'error': 'Missing token'}), 400)

    token = urllib.parse.unquote_plus(url_token)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        user_id = payload['user_id']
        email_type = payload['email_type']
    except jwt.ExpiredSignatureError:
        return make_response(jsonify({'error': 'Token expired'}), 400)
    except jwt.InvalidTokenError:
        return make_response(jsonify({'error': 'Invalid token'}), 400)

    status = False
    update_email_status(user_id, status, email_type)

    if email_type == 'email_promotional':
        return "You have been unsubscribed from promotional emails", 200
    elif email_type == 'email_transcripts':
        return "You have been unsubscribed from completed transcript emails", 200
    elif email_type == 'email_support_confirmation':
        return "You have been unsubscribed from support confirmation emails", 200

    return "You have been unsubscribed from emails", 200