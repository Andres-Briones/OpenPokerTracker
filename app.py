from flask import Flask, render_template, request, jsonify
import json
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'  # Make sure this directory exists

# Ensure UPLOAD_FOLDER exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Parser function for Open Hand History JSON format
def parse_hand(hand_data):
    if "ohh" not in hand_data:
        return {"error": "Invalid hand data format. Missing 'ohh' key"}
    
    ohh_data = hand_data["ohh"]
    parsed_data = {
        "game_info": {
            "network": ohh_data["network_name"],
            "site": ohh_data["site_name"],
            "game_type": ohh_data["game_type"],
            "table": ohh_data["table_name"],
            "table_size": ohh_data["table_size"]
        },
        "players": [
            {
                "name": player["name"],
                "seat": player["seat"],
                "starting_stack": player["starting_stack"]
            }
            for player in ohh_data["players"]
        ],
        "rounds": [
            {
                "street": round_info["street"],
                "actions": [
                    {
                        "action_number": action["action_number"],
                        "player_id": action["player_id"],
                        "action": action["action"],
                        "amount": action.get("amount", 0),
                        "is_allin": action.get("is_allin", False)
                    }
                    for action in round_info["actions"]
                ]
            }
            for round_info in ohh_data["rounds"]
        ],
        "pots": [
            {
                "amount": pot["amount"],
                "rake": pot["rake"],
                "winner": [
                    {
                        "player_id": winner["player_id"],
                        "win_amount": winner["win_amount"]
                    }
                    for winner in pot["player_wins"]
                ]
            }
            for pot in ohh_data["pots"]
        ]
    }
    return parsed_data

# Route to display the main interface
@app.route('/')
def index():
    return render_template('index.html')

# Route to upload and parse a hand history file
@app.route('/upload', methods=['POST'])
def upload_hand():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(file_path)

        try:
            with open(file_path, 'r') as f:
                hand_data = json.load(f)
            
            parsed_hand = parse_hand(hand_data)
            return jsonify(parsed_hand), 200

        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON file format"}), 400

if __name__ == '__main__':
    app.run(debug=True)
