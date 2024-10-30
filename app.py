from flask import Flask, render_template, request, jsonify, session
import json
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session handling
app.config['UPLOAD_FOLDER'] = 'uploads'  # Ensure this directory exists

def parse_hand(hand_data):
    if "ohh" not in hand_data:
        return {"error": "Invalid hand data format. Missing 'ohh' key"}
    
    ohh_data = hand_data["ohh"]
    players = {player["id"]: player for player in ohh_data["players"]}
    
    parsed_data = {
        "players": [
            {
                "name": player["name"],
                "seat": player["seat"],
                "starting_stack": player["starting_stack"],
                "cards": "? ?",
                "actual_bet": 0,
                "action": "Waiting"
            }
            for player in ohh_data["players"]
        ],
        "actions": [],  # Flattened list of actions
        "board_cards": []
    }

    for round_info in ohh_data["rounds"]:
        for action in round_info["actions"]:
            # Skip the "Hero Dealt Cards" action
            if action["action"] == "Dealt Cards":
                continue
            
            parsed_data["actions"].append({
                "round": round_info["street"],
                "action_number": action["action_number"],
                "player_name": players[action["player_id"]]["name"],
                "action": action["action"],
                "amount": action.get("amount", 0),
                "is_allin": action.get("is_allin", False)
            })

        if "cards" in round_info and round_info["cards"]:
            parsed_data["board_cards"].extend(round_info["cards"])

    return parsed_data

@app.route('/')
def index():
    return render_template('index.html')

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
            session['parsed_hand'] = parsed_hand
            session['current_action_index'] = 0  # Start from the first action
            session['pot'] = 0  # Initialize the pot
            session['round_pot'] = 0  # Initialize the round-specific pot

            return jsonify({"message": "File uploaded successfully"}), 200

        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON file format"}), 400

@app.route('/action/next', methods=['GET'])
def next_action():
    if 'parsed_hand' not in session:
        return jsonify({"error": "No hand data found in session"}), 400

    parsed_hand = session['parsed_hand']
    current_index = session.get('current_action_index', 0)
    if current_index >= len(parsed_hand['actions']) - 1:
        return jsonify({"message": "No more actions"}), 200
    
    session['current_action_index'] = current_index + 1
    action = parsed_hand['actions'][session['current_action_index']]

    # Detect if we're at the start of a new round to reset actual_bet and player actions
    if session['current_action_index'] == 0 or action['round'] != parsed_hand['actions'][current_index]['round']:
        for player in parsed_hand["players"]:
            player["actual_bet"] = 0  # Reset actual_bet for each player at the start of a new round
            player["action"] = "Waiting"  # Reset action to "Waiting"
        session['round_pot'] = 0  # Reset the round-specific pot

    # Update actual_bet and action only when a new action is taken
    player_status = {}
    player = next((p for p in parsed_hand["players"] if p["name"] == action["player_name"]), None)
    if player:
        player["actual_bet"] += action["amount"]
        player["action"] = action["action"]  # Update with the specific action (e.g., "Fold", "Call")
        session['round_pot'] += action["amount"]  # Add to the round pot
        player_status[action["player_name"]] = {"action": action["action"], "amount": action["amount"]}

    # Only add to the main pot at the end of each round
    if session['current_action_index'] == len(parsed_hand['actions']) - 1 or \
       parsed_hand['actions'][session['current_action_index'] + 1]['round'] != action['round']:
        session['pot'] += session['round_pot']
        session['round_pot'] = 0  # Reset round_pot at the end of the round

    return jsonify({
        "players": parsed_hand["players"],
        "board_cards": parsed_hand["board_cards"][:get_board_cards_count(action["round"])],
        "pot": session['pot'],
        "current_action": action,
        "player_status": player_status
    })

@app.route('/action/prev', methods=['GET'])
def prev_action():
    if 'parsed_hand' not in session:
        return jsonify({"error": "No hand data found in session"}), 400

    parsed_hand = session['parsed_hand']
    current_index = session.get('current_action_index', 0)
    if current_index <= 0:
        return jsonify({"message": "No previous actions"}), 200
    
    session['current_action_index'] = current_index - 1
    action = parsed_hand['actions'][session['current_action_index']]

    # Detect if we're at the start of a new round to reset actual_bet and player actions
    if session['current_action_index'] == 0 or action['round'] != parsed_hand['actions'][current_index]['round']:
        for player in parsed_hand["players"]:
            player["actual_bet"] = 0  # Reset actual_bet for each player at the start of a new round
            player["action"] = "Waiting"  # Reset action to "Waiting"
        session['round_pot'] = 0  # Reset the round-specific pot

    # Calculate player actions and bets up to the current action
    player_status = {}
    player = next((p for p in parsed_hand["players"] if p["name"] == action["player_name"]), None)
    if player:
        player["actual_bet"] += action["amount"]
        player["action"] = action["action"]  # Update with the specific action
        session['round_pot'] += action["amount"]
        player_status[action["player_name"]] = {"action": action["action"], "amount": action["amount"]}

    # Only add to the main pot at the end of each round
    if session['current_action_index'] == len(parsed_hand['actions']) - 1 or \
       parsed_hand['actions'][session['current_action_index'] + 1]['round'] != action['round']:
        session['pot'] += session['round_pot']
        session['round_pot'] = 0  # Reset round_pot at the end of the round

    return jsonify({
        "players": parsed_hand["players"],
        "board_cards": parsed_hand["board_cards"][:get_board_cards_count(action["round"])],
        "pot": session['pot'],
        "current_action": action,
        "player_status": player_status
    })

def get_board_cards_count(street):
    return {"Flop": 3, "Turn": 4, "River": 5}.get(street, 0)

if __name__ == '__main__':
    app.run(debug=True)


