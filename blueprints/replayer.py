from flask import Blueprint, request, jsonify, session, render_template, current_app, redirect
from models import get_db_connection, load_hands_from_db
from utils.hand_parser import get_data_for_replayer
from werkzeug.utils import secure_filename
import time
import models
import json
import os

replayer_bp = Blueprint('replayer', __name__)


def get_hands_count(db_path, q = None):
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = f"""
        SELECT COUNT(id) AS count
        FROM hands
        """
        if q is not None:
            query += f"WHERE players GLOB '*{q}*' OR table_name GLOB '*{q}*' OR hero_hand_class GLOB '*{q}*'"
        cursor.execute(query)
        count = cursor.fetchone()["count"]
    return count 

def get_hands_list(db_path, page = 1, q = None, return_count = True):
    # q is the search filter

    limit = 50                              # Default items per page
    offset = (page - 1) * limit             # Calculate offset
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = f"""
        SELECT id,
        table_name,
        date_time,
        hero_cards AS cards,
        hero_position AS position,
        hero_profit AS profit,
        players
        FROM hands
        """
        if q is not None:
            query += f"WHERE players GLOB '*{q}*' OR table_name GLOB '*{q}*' OR hero_hand_class GLOB '*{q}*'"
        query += f"ORDER BY date_time DESC LIMIT {limit} OFFSET {offset}"
        cursor.execute(query)
        results = cursor.fetchall()

    if return_count:
        count = get_hands_count(db_path, q)
        return results, count

    return results

@replayer_bp.route('/')
def replayer():
    db_path = session.get("db_path", None)
    if db_path is None : return redirect('/')
    session["page"] = 1
    session["filter"] = None
    hands_list, count = get_hands_list(db_path, session["page"])
    return render_template('replayer_page.html', hands_list = hands_list, total_count = count)

@replayer_bp.route('/upload', methods=['POST'])
def upload():
    message = None
    db_path = session["db_path"]

    files = request.files.getlist('file')  # Get all files uploaded as 'file'
    len_files = len(files)
    upload_path = current_app.config["UPLOADS_PATH"]

    for num, file in enumerate(files):
        print(type(file))
        if file.filename == '':
            continue  # Skip empty filenames

        if file.filename.split('.')[-1] != ".OHH":
            print(f"File {file.filename} skipped, it's not an OHH file. ({num+1}/{len_files})")
            message = "Some files were skipped because their file extension was not OHH"
            continue
        
        file_path = upload_path + "tmp.OHH"
        file.save(file_path)  # Save file to uploads directory

        with open(file_path, 'r') as f:
            hand_data_list = [json.loads(hand.strip()) for hand in f.read().split('\n\n') if hand.strip()]
            models.save_hands_bulk(hand_data_list, session["db_path"])
            new_files_uploaded = True
            print(f"File {file.filename} was uploaded. ({num+1}/{len_files})")

    hands_list, count = get_hands_list(db_path, session["page"], session["filter"]) 

    return render_template("hands_table.html", hands_list=hands_list, total_count = count, message = message) 



@replayer_bp.route("/search")
def search():
    db_path = session.get("db_path", None)
    search_filter = request.args.get("filter")
    session["filter"] = search_filter
    session["page"] = 1
    hands_list, count = get_hands_list(db_path, 1, search_filter) 
    return render_template("hands_table.html", hands_list=hands_list, total_count = count)


@replayer_bp.route("/load_next_page")
def load_next_page():
    db_path = session.get("db_path", None)
    page = session["page"] +1
    session["page"] = page
    hands_list = get_hands_list(db_path, page, session.get("filter", None), return_count = False) 
    return render_template("hands_list.html", hands_list=hands_list)

@replayer_bp.route('/select_hand')
def select_hand():
    selected_index = request.args.get('selected_hand')

    # Retrieve the full ohh_data from the database for the selected hand
    with get_db_connection(session["db_path"]) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ohh_data FROM hands WHERE id=?", (selected_index,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "Invalid hand selection"}), 400
        
        # Load ohh_data and parse it
        ohh_data = json.loads(result["ohh_data"])
        general_data, game_states = get_data_for_replayer(ohh_data)

    session["general_data"] = general_data
    session["game_states"] = game_states
    session["current_state"] = 0 # Change here the default loaded state

    return render_template("hand_replayer.html", general_data=general_data, gamestate=game_states[session["current_state"]]) 

@replayer_bp.route("/beginning")
def beginning():
    session["current_state"] = 0
    return render_template("hand_replayer.html",
                           general_data=session["general_data"],
                           gamestate=session["game_states"][0])

@replayer_bp.route("/previous")
def previous():
    if session["current_state"] > 0 :
        session["current_state"] -= 1
    return render_template("hand_replayer.html",
                           general_data=session["general_data"],
                           gamestate=session["game_states"][session["current_state"]])


@replayer_bp.route("/next")
def next():
    if session["current_state"] < len(session["game_states"]) -1 :
        session["current_state"] += 1
    return render_template("hand_replayer.html",
                           general_data=session["general_data"],
                           gamestate=session["game_states"][session["current_state"]])

@replayer_bp.route("/end")
def end():
    session["current_state"] = len(session["general_data"]) -1
    return render_template("hand_replayer.html",
                           general_data=session["general_data"],
                           gamestate=session["game_states"][-1])
