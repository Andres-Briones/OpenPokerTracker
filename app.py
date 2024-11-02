from flask import Flask, render_template, request, jsonify, session
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

    # Define the root route
    @app.route('/')
    def index():
        return render_template('index.html')

    # Initialize the database on app startup
    with app.app_context():
        init_db()

    return app
