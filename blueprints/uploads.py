from flask import Blueprint, request, redirect, url_for, render_template, jsonify, current_app, session
from flask_session import Session
from models import list_databases, create_database, add_file_to_db, save_hands_bulk
import os
import json

uploads_bp = Blueprint('uploads', __name__)

@uploads_bp.route('/')
def index():
    """Render the main page with the list of databases and forms for uploading hands and creating databases."""
    databases = list_databases(current_app.config['DB_DIRECTORY'])
    return render_template('index.html', databases=databases)

@uploads_bp.route('/create_database', methods=['POST'])
def create_database_route():
    """Handle creating a new database and redirect to the index page to refresh the list."""
    db_name = request.form.get('db_name')
    if not db_name:
        return jsonify({'error': 'Database name required'}), 400

    create_database(db_name, current_app.config['DB_DIRECTORY'])
    return redirect(url_for('uploads.index'))



@uploads_bp.route('/select_database', methods=['POST'])
def select_database():
    """Set the selected database path in the session and redirect to the replayer."""
    db_name = request.form.get('database')
    db_path = os.path.join(current_app.config['DB_DIRECTORY'], f"{db_name}")
    session["db_path"] = db_path  # Set the session with the selected database path
    return redirect('replayer')  # Redirect to replayer page to display hands

