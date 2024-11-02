def getCardSymbol(card):
    suitSymbols = {
        'h': '♥', 
        's': '♠', 
        'd': '♦', 
        'c': '♣'  
    }
    return card[0]+ suitSymbols[card[1]]

def cardsListToString(cards):
    return " ".join([getCardSymbol(card) for card in cards])

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
    board = []

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

        # Track board cards as they appear
        if "cards" in round_info :
            board_cards += round_info["cards"]

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
                    elif action["action"] == "Dealt Cards" or action["action"] == "Shows Cards" :
                        player_state["cards"] = cardsListToString(action["cards"])
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

            action_snapshot["pot"] = current_pot
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