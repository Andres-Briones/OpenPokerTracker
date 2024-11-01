from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
import json
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

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
        "board_cards": [],
        "pot_info": None
    }

    # Game state table
    game_state_table = []
    current_pot = 0
    board_cards = []
    folded_players = set()

    current_round = None #Stores the actual round

    for round_info in ohh_data["rounds"]:
        # At the start of each street, reset status to "Waiting" for active players
        if current_round != round_info["street"]:
            current_round = round_info["street"]
            for player in parsed_data["players"]:
                player["actual_bet"] = 0
                if player["name"] not in folded_players:
                    player["status"] = "Waiting"
                else :
                    player["status"] = "Folded"

        for action in round_info["actions"]:
            # Generate a description for the action
            action_amount = action.get('amount',0)
            if action_amount == 0:
                action_description = f"{players[action['player_id']]['name']}: {action['action']}"
            else :
                action_description = f"{players[action['player_id']]['name']}: {action['action']} for {action_amount}"

            # Prepare current state snapshot for this action
            action_snapshot = {
                "round": current_round,
                "pot": current_pot,
                "board": board_cards[:],
                "players": [],
                "description": action_description
            }

            # Update players’ states based on the action
            for player in parsed_data["players"]:
                player_state = {
                    "name": player["name"],
                    "status": player["status"],
                    "actual_bet": player["actual_bet"],
                    "cards": player["cards"],
                    "chips": player["chips"]
                }

                # Apply the current action to the relevant player
                if player["name"] == players[action["player_id"]]["name"]:
                    player_state["status"] = action["action"]
                    if action["action"] == "Fold":
                        folded_players.add(player["name"])
                    elif action["action"] == "Dealt cards" or action["action"] == "Shows cards" :
                        player_state["cards"] = " ".join(action.get("cards"))
                        player["cards"] = player_state["cards"]
                    else:
                        # Calculate amount to deduct and update actual_bet
                        player_state["actual_bet"] += action_amount  # Add to existing bet
                        player_state["chips"] -= action_amount  # Directly reduce chips by action amount
                        current_pot += action_amount

                        # Update the player's chips and actual_bet
                        player["chips"] = player_state["chips"]
                        player["actual_bet"] = player_state["actual_bet"]

                # Update the main player state in parsed_data for the next action
                player["status"] = player_state["status"]

                # Append the player state to the action snapshot
                action_snapshot["players"].append(player_state)

            # Track board cards as they appear
            if "cards" in round_info and round_info["cards"]:
                board_cards = round_info["cards"]

            action_snapshot["pot"] = current_pot
            action_snapshot["board"] = board_cards[:]
            game_state_table.append(action_snapshot)

    # Include pot and winnings information if present
    if "pots" in ohh_data:
        parsed_data["pot_info"] = [
            {
                "rake": pot["rake"],
                "amount": pot["amount"],
                "player_wins": [
                    {
                        "name": players[win["player_id"]]["name"],
                        "win_amount": win["win_amount"],
                        "cashout_fee": win.get("cashout_fee", 0.00),
                        "cashout_amount": win.get("cashout_amount", win["win_amount"])
                    }
                    for win in pot["player_wins"]
                ]
            }
            for pot in ohh_data["pots"]
        ]

    parsed_data["game_state_table"] = game_state_table
    return parsed_data

def parse_multiple_hands(hands_data):
    hands_list = []
    for hand_data in hands_data:
        ohh_data = hand_data.get("ohh", {})
        hero_id = ohh_data.get("hero_player_id")
        hero_cards = ""

        # Find hero's dealt cards
        for round_info in ohh_data.get("rounds", []):
            for action in round_info.get("actions", []):
                if action.get("player_id") == hero_id and "cards" in action:
                    hero_cards = " ".join(action["cards"])

        # Append hand info to list
        hands_list.append({
            "game_code": ohh_data.get("game_number"),
            "date_time": ohh_data.get("start_date_utc"),
            "hero_cards": hero_cards
        })

    return hands_list

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
                # Read the entire file content
                content = f.read()

            # Split content by blank lines to separate each hand
            hand_sections = [section.strip() for section in content.split('\n\n') if section.strip()]
            hands_data = []

            # Parse each JSON object individually
            for hand_text in hand_sections:
                try:
                    hand_data = json.loads(hand_text)
                    hands_data.append(hand_data)
                except json.JSONDecodeError as e:
                    print("Failed to parse hand:", hand_text)
                    print("Error:", e)
                    return jsonify({"error": "Invalid JSON format in one of the hand histories"}), 400

            # Parse hands for menu display
            hands_list = parse_multiple_hands(hands_data)
            session['hands_data'] = hands_data
            session['hands_list'] = hands_list
            return jsonify({"message": "File uploaded successfully", "hands_list": hands_list}), 200

        except Exception as e:
            print("Unexpected error:", e)
            return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/select_hand', methods=['POST'])
def select_hand():
    selected_index = request.json.get('hand_index')
    hands_data = session.get('hands_data')
    if hands_data and 0 <= selected_index < len(hands_data):
        selected_hand = hands_data[selected_index]
        # Parse the selected hand for the replayer
        parsed_hand = parse_hand(selected_hand)
        session['parsed_hand'] = parsed_hand
        session['current_action_index'] = 0
        return jsonify({
            "message": "Hand loaded",
            "game_state_table": parsed_hand["game_state_table"],
            "pot_info": parsed_hand.get("pot_info", None)
        }), 200
    return jsonify({"error": "Invalid hand selection"}), 400


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
