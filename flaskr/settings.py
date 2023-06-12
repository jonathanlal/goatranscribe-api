from flask import Blueprint, request, jsonify
from authlib.integrations.flask_oauth2 import current_token
from flaskr.email import send_support_confirmation, send_support_confirmation_admin
from flaskr.firebase import get_user_settings, seen_uploads_welcome, update_email_status
from .auth import getUserEmail, require_auth, getUserID


bp = Blueprint("settings", __name__)


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
    send_support_confirmation(message, user_email)
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


