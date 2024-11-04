from flask import Blueprint, request, jsonify, session, render_template, current_app
from models import get_db_connection, load_hands_from_db
from utils.hand_parser import parse_hand
from werkzeug.utils import secure_filename
from models import *
import json
import os

hand_replayer_bp = Blueprint('hand_replayer', __name__)

@hand_replayer_bp.route('/upload', methods=['POST'])
def upload_hand():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    files = request.files.getlist('file')  # Get all files uploaded as 'file'
    upload_path = current_app.config["UPLOADS_PATH"]
    new_files_uploaded = False

   # Ensure the upload path exists
    os.makedirs(upload_path, exist_ok=True)  # Creates the directory if it doesn't exist

    for file in files:
        if file.filename == '':
            continue  # Skip empty filenames

        file_path = upload_path + secure_filename(file.filename)
        file.save(file_path)  # Save file to uploads directory

        try :
            if add_file_to_db(file.filename, file_path):
                new_files_uploaded = True
        except json.JSONDecodeError as e:
            print("Error: Invalid JSON format in hand history.")
            return jsonify({"error": "Invalid JSON format in hand history"}), 400


    # Update session hands_list only if new files were uploaded
    if new_files_uploaded:
        session["hands_list"] = load_hands_from_db()

    return jsonify({"message": "File uploaded successfully"}), 200



@hand_replayer_bp.route('/select_hand', methods=['POST'])
def select_hand():
    selected_index = request.json.get('hand_index')
    
    print(selected_index)
    # Retrieve the full ohh_data from the database for the selected hand
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ohh_data FROM hands WHERE id=?", (selected_index,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "Invalid hand selection"}), 400
        
        # Load ohh_data and parse it
        ohh_data = json.loads(result["ohh_data"])
        parsed_hand = parse_hand(ohh_data)

        return jsonify({
            "message": "Hand loaded",
            "game_state_table": parsed_hand["game_state_table"],
            "pot_info": parsed_hand.get("pot_info", None)
        }), 200

@hand_replayer_bp.route('/get_hands_list', methods=['GET'])
def get_hands_list():
    if 'hands_list' not in session:
        # Load from the database only if 'hands_list' is not in session
        session['hands_list'] = load_hands_from_db()
    return jsonify({"hands_list": session['hands_list']})


@hand_replayer_bp.route('/')
def hand_replayer():
    return render_template('hand_replayer.html')
