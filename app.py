from flask import Flask, render_template, request, jsonify, session
import json
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['UPLOAD_FOLDER'] = 'uploads'

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
                "status": "Active",
                "chips": player["starting_stack"]
            }
            for player in ohh_data["players"]
        ],
        "actions": [],
        "board_cards": []
    }

    # Game state table
    game_state_table = []
    current_pot = 0
    round_pot = 0
    board_cards = []
    folded_players = set()

    for round_info in ohh_data["rounds"]:
        # At the start of each new round, reset status to "Waiting" for active players
        for player in parsed_data["players"]:
            if player["name"] not in folded_players:
                player["actual_bet"] = 0
                player["status"] = "Waiting"

        for action in round_info["actions"]:
            # Generate a description for the action
            action_description = f"{players[action['player_id']]['name']} {action['action']} for {action.get('amount', 0)}"

            # Prepare current state snapshot for this action
            action_snapshot = {
                "round": round_info["street"],
                "pot": current_pot,
                "board": board_cards[:],  
                "players": [],
                "description": action_description
            }

            # Update players’ states based on the action
            for player in parsed_data["players"]:
                player_state = {
                    "name": player["name"],
                    "status": "Folded" if player["name"] in folded_players else player["status"],
                    "actual_bet": player["actual_bet"],
                    "cards": player["cards"],
                    "chips": player["chips"]
                }

                # Apply the current action to the relevant player
                if player["name"] == players[action["player_id"]]["name"]:
                    if action["action"] == "Fold":
                        player_state["status"] = "Folded"
                        folded_players.add(player["name"])
                    elif action["action"] == "Dealt Cards":
                        player_state["cards"] = " ".join(action.get("cards", ["? ?"]))
                        player["cards"] = player_state["cards"]
                    else:
                        player_state["status"] = action["action"]

                        # Calculate amount to deduct and update actual_bet
                        action_amount = action.get("amount", 0)
                        player_state["actual_bet"] += action_amount  # Add to existing bet
                        player_state["chips"] -= action_amount  # Directly reduce chips by action amount
                        round_pot += action_amount

                        # Update the player's chips and actual_bet
                        player["chips"] = player_state["chips"]
                        player["actual_bet"] = player_state["actual_bet"]

                # Update the main player state in parsed_data for the next action
                player["status"] = player_state["status"]

                # Append the player state to the action snapshot
                action_snapshot["players"].append(player_state)

            # At the end of the round, add round_pot to current_pot and reset round_pot
            if action == round_info["actions"][-1]:
                current_pot += round_pot
                round_pot = 0

            # Track board cards as they appear
            if "cards" in round_info and round_info["cards"]:
                board_cards = round_info["cards"]

            action_snapshot["pot"] = current_pot
            action_snapshot["board"] = board_cards[:]
            game_state_table.append(action_snapshot)

    parsed_data["game_state_table"] = game_state_table
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
            session['current_action_index'] = 0  

            return jsonify({"message": "File uploaded successfully", "game_state_table": parsed_hand["game_state_table"]}), 200

        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON file format"}), 400

@app.route('/action/next', methods=['GET'])
def next_action():
    parsed_hand = session.get('parsed_hand')
    if not parsed_hand:
        return jsonify({"error": "No hand data found in session"}), 400

    current_index = session.get('current_action_index', 0)
    if current_index >= len(parsed_hand["game_state_table"]) - 1:
        return jsonify({"message": "No more actions"}), 200

    session['current_action_index'] = current_index + 1
    return jsonify(parsed_hand["game_state_table"][session['current_action_index']])

@app.route('/action/prev', methods=['GET'])
def prev_action():
    parsed_hand = session.get('parsed_hand')
    if not parsed_hand:
        return jsonify({"error": "No hand data found in session"}), 400

    current_index = session.get('current_action_index', 0)
    if current_index <= 0:
        return jsonify({"message": "No previous actions"}), 200

    session['current_action_index'] = current_index - 1
    return jsonify(parsed_hand["game_state_table"][session['current_action_index']])

def get_board_cards_count(street):
    return {"Flop": 3, "Turn": 4, "River": 5}.get(street, 0)

if __name__ == '__main__':
    app.run(debug=True)

