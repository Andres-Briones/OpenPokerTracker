from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename
from handParser import parse_hand, cardsListToString
import json
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

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
                    hero_cards = cardsListToString(action["cards"])

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

if __name__ == '__main__':
    app.run(debug=True)
