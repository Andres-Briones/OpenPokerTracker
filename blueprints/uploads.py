from flask import Blueprint, request, redirect, url_for, render_template, jsonify, current_app, session
from flask_session import Session
from models import * 
import os
import json

uploads_bp = Blueprint('uploads', __name__)

def ajax_redirect(route):
    return jsonify({'redirect' : url_for(route)})

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
    db_path = os.path.join(current_app.config['DB_DIRECTORY'], f"{db_name}.db")
    if  os.path.exists(db_path):
        return jsonify({'error': 'Database already exists'}), 400

    if not init_db(db_path):  # Initialize with the standard schema
        # TODO check that the database is removed correcly
        os.remove(db_path)
        return jsonify({'error': 'Database initialization failed'}), 400

    return ajax_redirect('uploads.index')

@uploads_bp.route('/load_database', methods=['POST'])
def load_database_route():
    """Set the selected database path in the session and redirect to the replayer."""
    db_name = request.form.get('db_name')
    print("Selected database =", db_name)
    if not db_name:
        # Return a JSON response with an error message if `db_name` is empty
        return jsonify({'error': 'Please select a database'}), 400

    # Build the database path and store it in the session
    db_path = os.path.join(current_app.config['DB_DIRECTORY'], f"{db_name}.db")
    session["db_path"] = db_path  # Set the session with the selected database path
    print("OK")
    return ajax_redirect('hand_replayer.hand_replayer')  # Redirect to replayer page

@uploads_bp.route('/delete_database', methods=['POST'])
def delete_database_route():
    """Set the selected database path in the session and redirect to the replayer."""
    db_name = request.form.get('db_name')
    db_path = os.path.join(current_app.config['DB_DIRECTORY'], f"{db_name}.db")
    os.remove(db_path)
    if session["db_path"] == db_path : session["db_path"] = None # Set the session db_path to None if deleted database was the loaded one 
    return ajax_redirect('uploads.index')  # Redirect to home page 

