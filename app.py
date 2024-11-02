from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename
from handParser import parse_hand, cardsListToString
from pathlib import Path
import json
import os
import sqlite3

app = Flask(__name__)
app.secret_key = 'sdfp2q984hgaelcan'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.expanduser("~"), ".config/poker/sessions")
app.config['SESSION_PERMANENT'] = False  # Non-permanent session; session will expire when the browser closes
app.config['SESSION_USE_SIGNER'] = True  # Adds an extra layer of security for session data
Session(app)

# Define paths for configuration and database
home_dir = Path.home()
config_dir = home_dir / ".config/poker"
uploads_dir = config_dir / "uploads"
config_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
uploads_dir.mkdir(parents=True, exist_ok=True)  # Create uploads folder
db_path = config_dir / "poker.db"

# Database connection helper
def get_db_connection():
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS hands (
                id INTEGER PRIMARY KEY,
                file_id INTEGER,
                game_code TEXT,
                date_time TEXT,
                hero_cards TEXT,
                ohh_data TEXT,  -- JSON blob to store the full ohh object
                FOREIGN KEY (file_id) REFERENCES files(id)
            );
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                hands TEXT,  -- JSON array of hand_ids where the player was present
                statistics TEXT  -- JSON dictionary to store player statistics
            );
            """)
            conn.commit()
            print("Database initialized successfully.")
        except sqlite3.Error as e:
            print("Database initialization failed:", e)
            
# Load hands data from database on startup
def load_hands_from_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hands ORDER BY date_time DESC")
        hands = cursor.fetchall()
        hands_list = []
        for hand in hands:
            hands_list.append({
                "id": hand["id"],
                "game_code": hand["game_code"],
                "date_time": hand["date_time"],
                "hero_cards": hand["hero_cards"]
            })
        return hands_list

# Add or update player in the database
def add_or_update_player(player_name, hand_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if player already exists
        cursor.execute("SELECT id, hands FROM players WHERE name = ?", (player_name,))
        result = cursor.fetchone()

        if result:
            # Player exists, update their list of hands
            player_id = result["id"]
            hands = json.loads(result["hands"])
            if hand_id not in hands:
                hands.append(hand_id)
            cursor.execute("UPDATE players SET hands = ? WHERE id = ?", (json.dumps(hands), player_id))
        else:
            # Player does not exist, create a new record
            hands = [hand_id]
            cursor.execute(
                "INSERT INTO players (name, hands, statistics) VALUES (?, ?, ?)",
                (player_name, json.dumps(hands), json.dumps({}))  # Empty statistics dictionary
            )
        conn.commit()

# Parse and store data in database
def save_hand_to_db(file_id, parsed_hand, ohh_data):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Insert hand data with full ohh object stored as JSON
        cursor.execute(
            "INSERT INTO hands (file_id, game_code, date_time, hero_cards, ohh_data) VALUES (?, ?, ?, ?, ?)",
            (file_id, parsed_hand['game_code'], parsed_hand['date_time'], parsed_hand['hero_cards'], json.dumps(ohh_data))
        )
        hand_id = cursor.lastrowid

        # Update each player's record or add them if they don’t exist
        #for player in parsed_hand['players']:
        #    add_or_update_player(player['name'], hand_id)
        print(f"Hand {parsed_hand['game_code']} was inserted into the database")
        
        conn.commit()

@app.route('/upload', methods=['POST'])
def upload_hand():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    files = request.files.getlist('file')  # Get all files uploaded as 'file'
    new_files_uploaded = False

    for file in files:
        if file.filename == '':
            continue  # Skip empty filenames

        file_path = uploads_dir / secure_filename(file.filename)
        file.save(file_path)  # Save file to uploads directory

        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if the file already exists in the database
            cursor.execute("SELECT id FROM files WHERE filename = ?", (file.filename,))
            result = cursor.fetchone()
            
            if result:
                # File already exists, skip adding hands for this file
                continue
            
            # Insert the file record into the database since it doesn't exist
            cursor.execute("INSERT INTO files (filename) VALUES (?)", (file.filename,))
            file_id = cursor.lastrowid
            conn.commit()
            new_files_uploaded = True

        # If file is new, read and add hands to the database
        with open(file_path, 'r') as f:
            content = f.read()

        hand_sections = [section.strip() for section in content.split('\n\n') if section.strip()]
        for hand_text in hand_sections:
            try:
                hand_data = json.loads(hand_text)
                parsed_hand = parse_hand(hand_data)
                save_hand_to_db(file_id, parsed_hand, hand_data)  # Save each hand to the database
            except json.JSONDecodeError as e:
                print("Error: Invalid JSON format in hand history.")
                return jsonify({"error": "Invalid JSON format in hand history"}), 400

    # Update session hands_list only if new files were uploaded
    if new_files_uploaded:
        session["hands_list"] = load_hands_from_db()

    return jsonify({"message": "File uploaded successfully"}), 200


@app.route('/select_hand', methods=['POST'])
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

@app.route('/get_hands_list', methods=['GET'])
def get_hands_list():
    if 'hands_list' not in session:
        # Load from the database only if 'hands_list' is not in session
        session['hands_list'] = load_hands_from_db()
    return jsonify({"hands_list": session['hands_list']})

@app.route('/')
def index():
    return render_template('index.html')

# Initialize the database when the app starts
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True)
