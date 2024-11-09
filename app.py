from flask import Flask, render_template, request, jsonify, session, current_app
from flask_session import Session
from config import Config
from blueprints.hand_replayer import hand_replayer_bp
from blueprints.statistics import statistics_bp
from models import init_db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Session(app)

    # Register blueprints
    app.register_blueprint(hand_replayer_bp, url_prefix='/replayer')
    app.register_blueprint(statistics_bp, url_prefix='/statistics')

    # Custom startup function
    with app.app_context():
        init_db(current_app.config["DB_PATH"])

    # Define the root route
    @app.route('/')
    def index():
        session["db_path"] = current_app.config['DB_PATH']
        return render_template('index.html')

    return app

