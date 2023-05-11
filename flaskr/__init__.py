from flask import Flask
from dotenv import load_dotenv, find_dotenv
from flask_cors import CORS

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    CORS(app, supports_credentials=True, origins=['http://localhost:3000'])  # Replace with the client app's origin


    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    from . import auth, transcribe, transcribe_try, stripe
    app.register_blueprint(auth.bp)
    app.register_blueprint(transcribe.bp)
    app.register_blueprint(transcribe_try.bp)
    app.register_blueprint(stripe.bp)

    return app
