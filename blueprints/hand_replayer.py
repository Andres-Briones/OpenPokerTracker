from flask import Blueprint, request, jsonify, session, render_template, current_app
from models import get_db_connection, load_hands_from_db
from utils.hand_parser import parse_hand
from werkzeug.utils import secure_filename
import time
import models
import json
import os

hand_replayer_bp = Blueprint('hand_replayer', __name__)

@hand_replayer_bp.route('/upload', methods=['POST'])
def upload_hand():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    files = request.files.getlist('file')  # Get all files uploaded as 'file'
    len_files = len(files)
    upload_path = current_app.config["UPLOADS_PATH"]
    new_files_uploaded = False

   # Ensure the upload path exists
    os.makedirs(upload_path, exist_ok=True)  # Creates the directory if it doesn't exist

    for num, file in enumerate(files):
        if file.filename == '':
            continue  # Skip empty filenames
        if file.filename[-4:] != ".OHH":
            print(f"File {file.filename} skipped, it's not an OHH file. ({num+1}/{len_files})")
            continue

        file_path = upload_path + secure_filename(file.filename)
        file.save(file_path)  # Save file to uploads directory

        file_id  = models.add_file_to_db(file.filename, file_path, session["db_path"]) # returns None if file already exists on database
        if file_id is not None:
            new_files_uploaded = True
            print(f"Working on file {file.filename} ... ")
            start_time = time.time()
            models.add_hands_from_file_to_db(file_path, file_id, session["db_path"])
            print(f"done! It took {(time.time()-start_time):.2f} seconds. ({num+1}/{len_files})")
        else :
            print(f"File {file.filename} arleady exists in the database. ({num+1}/{len_files})")

    # Update session hands_list only if new files were uploaded
    if new_files_uploaded:
        session["hands_list"] = models.load_hands_from_db(db_path= session["db_path"])

    return jsonify({"message": "Files uploaded successfully"}), 200



@hand_replayer_bp.route('/select_hand', methods=['POST'])
def select_hand():
    selected_index = request.json.get('hand_index')

    # Retrieve the full ohh_data from the database for the selected hand
    with get_db_connection(session["db_path"]) as conn:
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
        session['hands_list'] = load_hands_from_db(db_path = session["db_path"])
    return jsonify({"hands_list": session['hands_list']})


@hand_replayer_bp.route('/')
def hand_replayer():
    return render_template('hand_replayer.html')
