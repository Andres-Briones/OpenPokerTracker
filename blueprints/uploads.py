from flask import Blueprint, request, url_for, render_template, make_response, current_app, session
from flask_session import Session
from models import * 
import os
import json

uploads_bp = Blueprint('uploads', __name__)

@uploads_bp.route('/')
def index():
    """Render the main page with the list of databases and forms for uploading hands and creating databases."""
    databases = list_databases(current_app.config['DB_DIRECTORY'])
    return render_template('index.html', databases=databases)

@uploads_bp.route('/create_database', methods=['POST'])
def create_database():
    """Handle creating a new database and redirect to the index page to refresh the list."""
    message = None
    db_name = request.form.get('db_name')

    if not db_name:
        message = 'Database name required'
        databases = list_databases(current_app.config['DB_DIRECTORY'])

        return render_template('databases_dropDown.html', databases=databases, message=message)

    db_path = os.path.join(current_app.config['DB_DIRECTORY'], f"{db_name}.db")
    
    if os.path.exists(db_path):
        message = 'Database already exists'

    elif not init_db(db_path):  # Initialize with the standard schema
        # TODO check that the database is removed correcly
        os.remove(db_path)
        message = 'Database initialization failed'

    databases = list_databases(current_app.config['DB_DIRECTORY'])

    return render_template('databases_dropDown.html', databases=databases, message=message)

@uploads_bp.route('/load_database', methods=['POST'])
def load_database():
    """Set the selected database path in the session and redirect to the replayer."""
    db_name = request.form.get('db_name')
    print("Selected database =", db_name)
    if not db_name:
        # Return a same page with an error message if `db_name` is empty
        databases = list_databases(current_app.config['DB_DIRECTORY'])
        return render_template('databases_dropDown.html', databases=databases, message = 'Please select a database')

    # Build the database path and store it in the session
    db_path = os.path.join(current_app.config['DB_DIRECTORY'], f"{db_name}.db")
    session["db_path"] = db_path  # Set the session with the selected database path
    response = make_response('', 200)
    response.headers['HX-Redirect'] = '/replayer'
    return response  # Redirect to replayer page

@uploads_bp.route('/delete_database', methods=['POST'])
def delete_database():
    """Set the selected database path in the session and redirect to the replayer."""
    db_name = request.form.get('db_name')
    if not db_name:
        # Return a same page with an error message if `db_name` is empty
        databases = list_databases(current_app.config['DB_DIRECTORY'])
        return render_template('databases_dropDown.html', databases=databases, message = 'Please select a database')

    db_path = os.path.join(current_app.config['DB_DIRECTORY'], f"{db_name}.db")
    os.remove(db_path)
    if session["db_path"] == db_path : session["db_path"] = None # Set the session db_path to None if deleted database was the loaded one 

    databases = list_databases(current_app.config['DB_DIRECTORY'])

    return render_template('databases_dropDown.html', databases=databases)

