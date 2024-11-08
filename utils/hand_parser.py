from collections import defaultdict

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

def parse_hand_stat(ohh_obj):
    #Extract general info necessary for hand insertion in table
    ohh_data = ohh_obj["ohh"]
    hero_id = ohh_data.get("hero_player_id")
    game_code = ohh_data["game_number"]
    date_time = ohh_data["start_date_utc"]
    hero_cards = ""

    if "Anonymous" in ohh_data.get("flags",[]):
        return {"game_code": game_code}, None

    # Extract players and rounds
    players = ohh_data['players']
    rounds = ohh_data['rounds']

    # Map player IDs to names for easy reference
    id_to_name = {p['id']: p['name'] for p in players}
            
    # Track preflop participation and actions for each player in the hand
    preflop_participation = set()
    preflop_raisers = set()
    game_participation = set()

    for round_data in rounds:
        street = round_data['street']
        actions = round_data['actions']
        for action in actions:
            player_id = action.get("player_id")
            player_name = id_to_name.get(player_id)
            action_type = action.get("action")
            game_participation.add(player_name)

            # VPIP: Any call or raise action before the flop
            if street == "Preflop" and action_type in ["Call", "Raise"]:
                preflop_participation.add(player_name)
                #PFR : Preflop first raises or 3-bet, 4-bet, etc
                if action_type == "Raise":
                    preflop_raisers.add(player_name)

            # Get hero cards
            if player_id  == hero_id and "cards" in action:
                hero_cards = cardsListToString(action.get("cards"))
    
    # Generate dict to store statistical data for each player 
    stats_data = defaultdict(lambda: {"vpip": 0, "pfr": 0, "won": 0})
    for name in game_participation : stats_data[name] # Generate input for player in stats_data if player is not observer
    for name in preflop_participation : stats_data[name]["vpip"] = 1
    for name in preflop_raisers : stats_data[name]["pfr"] = 1

    for player in players :
        win_amount = float(player.get("final_stack", 0)) - float(player["starting_stack"])
        if win_amount != 0 : 
            name = player["name"]
            stats_data[name]["won"] = '%g' % win_amount

    stats_data = dict(stats_data) #Use dict in order to transform the defaultdic object

    # Generate dic for general data
    general_data = {
        "game_code" : game_code,
        "date_time" : date_time,
        "hero_cards" : hero_cards
        }

    return general_data, stats_data

def parse_hand(hand_data):
    if "ohh" not in hand_data:
        print("Error", "Invalid hand data format. Missing 'ohh' key")
        return {}

    ohh_data = hand_data["ohh"]
    players = {player["id"]: player for player in ohh_data["players"]}
    hero_id = ohh_data.get("hero_player_id")
    hero_cards = ""

    parsed_data = {
        "players": [
            {
                "name": player["name"],
                "seat": player["seat"],
                "starting_stack": player["starting_stack"],
                "cards": "? ?",
                "status": "Active",
                "chips": float(player["starting_stack"])
            }
            for player in ohh_data["players"]
        ],
        "actions": [],
        "board_cards": [],
        "pot_info": None,
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

            if action.get("player_id") == hero_id and "cards" in action:
                hero_cards = cardsListToString(action["cards"])

            # Generate a description for the action
            action_amount = float(action.get('amount',0))
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
                    "chips": float(player["chips"])
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
                "rake": float(pot["rake"]),
                "amount": float(pot["amount"]),
                "player_wins": [
                    {
                        "name": players[win["player_id"]]["name"],
                        "win_amount": float(win["win_amount"]),
                        "cashout_fee": float(win.get("cashout_fee", 0.00)),
                        "cashout_amount": float(win.get("cashout_amount", win["win_amount"]))
                    }
                    for win in pot["player_wins"]
                ]
            }
            for pot in ohh_data["pots"]
        ]

    parsed_data["game_state_table"] = game_state_table

    parsed_data["game_code"] = ohh_data["game_number"]
    parsed_data["date_time"] = ohh_data["start_date_utc"]
    parsed_data["hero_cards"] = hero_cards 

    return parsed_data
