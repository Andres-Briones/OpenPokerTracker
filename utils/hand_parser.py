from collections import defaultdict
import numpy as np
from datetime import datetime

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

def parse_hand_at_upload(ohh_obj):
    #Extract general info necessary for hand insertion in table
    ohh_data = ohh_obj["ohh"]
    hero_id = ohh_data.get("hero_player_id")
    game_number = ohh_data["game_number"]
    date_time = datetime.strptime(ohh_data["start_date_utc"], "%Y-%m-%dT%H:%M:%SZ")
    date_time = date_time.strftime("%Y-%m-%d %H:%M:%S")
    table_size = ohh_data["table_size"]

    # Set players_hands_data to None if anonymous game
    # If players_hands_data is None, the hand will be skipped
    if "Anonymous" in ohh_data.get("flags",[]):
        return {"game_number": game_number}, None 

    # Extract players and rounds
    players = ohh_data['players']
    rounds = ohh_data['rounds']

    # Map player IDs to names for easy reference
    id_to_name = {p['id']: p['name'] for p in players}

    hero_name = id_to_name.get(hero_id, None)
    observed = True if hero_name is None else False
    if observed: print(f"Game {game_number} is observed" )


    # Extract dealer seat
    dealer_seat = ohh_data["dealer_seat"]

    # Extraact players profits and seat 
    player_profit = {}
    player_seat = {}

    for player in players :
        win_amount = float(player.get("final_stack", 0)) - float(player["starting_stack"])
        name = player["name"]
        player_profit[name] = '%g' % win_amount
        player_seat[name] = player["seat"]

            
    # Track preflop participation and actions for each player in the hand
    game_participation = set()

    preflop_participation = set()
    preflop_raisers = set()
    preflop_2bet_possibility = set()
    preflop_limp= set()
    preflop_2bet = set()
    preflop_3bet = set()
    preflop_call_to_2bet = set()

    player_cards = {}
    
    for round_data in rounds:
        street = round_data['street']
        actions = round_data['actions']

        raise_counter = 0
        for action in actions:
            player_id = action.get("player_id")
            player_name = id_to_name.get(player_id)
            action_type = action.get("action")
            game_participation.add(player_name)

            # VPIP: Any call or raise action before the flop
            if street == "Preflop" and action_type in ["Call", "Raise"]:
                preflop_participation.add(player_name)
                if action_type == "Raise":
                    #PFR : Preflop first raises or 3-bet, 4-bet, etc
                    preflop_raisers.add(player_name)
                    if raise_counter == 0 : preflop_2bet.add(player_name)
                    elif raise_counter == 1 : preflop_3bet.add(player_name) 
                    raise_counter += 1
                else: # It's a Call
                    if raise_counter == 0: #  raise_counter is 0 => playerlimps
                        preflop_limp.add(player_name)
                    elif raise_counter == 1:  
                        preflop_call_to_2bet.add(player_name)

            if action.get("cards", 0) : # action containes cards an they are not empty
                player_cards[player_name] = cardsListToString(action.get("cards"))

    number_players = len(game_participation)

    # Generate seats_list for players that participated
    seats_list = []
    for name in game_participation:
        seats_list.append(player_seat[name])
    # We get a position from 0 to 6
    position_list = (np.array(seats_list) - dealer_seat -1)% table_size
    # We transform the position from 0 to 6 to 0 to number_players. 0 is SB and the highest is BU
    real_position_list = np.argsort(np.argsort(position_list))
    seat_to_position = {seat:int(real_position_list[i]) for i, seat in enumerate(seats_list) }


    # Generate dict to store statistical data for each player 
    # TODO add more counters like 3bet, fold/call to 2-bet etc
    # IMPORTANT : players_hands_dics need to have the same  keys as the row names in players_hands table
    players_hands_data = defaultdict(lambda:
                             {"cards": None,
                              "position": 0,
                              "profit": 0,
                              "vpip": 0,
                              "pfr": 0,
                              "limp" : 0,
                              "two_bet": 0
                              })

    for name in game_participation :
        # Generate input for player in players_hands_data if player is not observer
        # positon =  (seat - dealer_seat - 1)% table_size 
        players_hands_data[name]["position"] = seat_to_position[player_seat[name]]
        players_hands_data[name]["profit"] = player_profit[name]
        if name in player_cards : players_hands_data[name]["cards"] = player_cards[name]
    for name in preflop_participation : players_hands_data[name]["vpip"] = 1
    for name in preflop_raisers : players_hands_data[name]["pfr"] = 1
    for name in preflop_limp: players_hands_data[name]["limp"] = 1
    for name in preflop_2bet : players_hands_data[name]["two_bet"] = 1

    players_hands_data = dict(players_hands_data) #Use dict in order to transform the defaultdic object

    # Generate dic for hands data
    # IMPORTANT : this dic need to have exactly the same keys as the row names in hands table
    hands_data = {
        "game_number" : game_number,
        "date_time" : date_time,
        "table_size" : table_size,
        "number_players" : number_players,
        "hero_name" : hero_name,
        "table_name" : ohh_data["table_name"],
        "small_blind_amount" : ohh_data["small_blind_amount"],
        "big_blind_amount" : ohh_data["big_blind_amount"],
        "site_name" : ohh_data["site_name"],
        "observed" : observed
        }

    return hands_data, players_hands_data

def parse_hand(hand_data):
    if "ohh" not in hand_data:
        print("Error", "Invalid hand data format. Missing 'ohh' key")
        return {}

    ohh_data = hand_data["ohh"]
    players = {player["id"]: player for player in ohh_data["players"]}
    hero_id = ohh_data.get("hero_player_id") # Can be null
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

    parsed_data["game_number"] = ohh_data["game_number"]
    parsed_data["date_time"] = ohh_data["start_date_utc"]
    parsed_data["hero_cards"] = hero_cards 

    return parsed_data
