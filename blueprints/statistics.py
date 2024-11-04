from flask import Blueprint, request, jsonify, session, render_template
from models import get_db_connection, load_hands_from_db
from collections import defaultdict
import json

statistics_bp = Blueprint('statistics', __name__)

def compute_stats():

    # Generates a default dict. When calling the fist time stats_data["player"], this will set all the defaults counters for player to zero.
    stats_data = defaultdict(lambda: {
        "vpip": 0, "pfr": 0, "af_aggressive": 0, "af_passive": 0, "ats": 0, 
        "fold_to_steal": 0, "three_bet": 0, "fold_to_three_bet": 0, 
        "wtsd": 0, "flop_cbet": 0, "fold_to_cbet": 0, "hands": 0,
        "late_position": 0, "fold_to_raise": 0, "call_to_raise":0
    })

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT json_extract(ohh_data, '$.ohh') AS hand FROM hands")
        results = cursor.fetchall()

        for ohh in results:
            hand = json.loads(ohh["hand"])

            players = hand['players']
            N_players = len(players)
            rounds = hand['rounds']
            dealer_seat = hand['dealer_seat']
            sorted_players = sorted(players, key=lambda x: (x["seat"] - dealer_seat - 1) % 6) # First is SB, then BB, etc

            # Map player IDs to names for easy reference
            player_names = {p['id']: p['name'] for p in players}
            # Map player IDs to position for easy reference
            player_position = {p['id']:i for i,p in enumerate(sorted_players)} #Position 0 is SB, 1 for BB, etc

            # Track preflop participation and actions for each player in the hand
            preflop_participation = set()
            preflop_raisers = set()
            three_bet_attempts = set()
            late_position_raisers = set()

            # Detect sequences for 3-bets and ATS during preflop
            raise_count = 0  # Counter to track the sequence of raises
            for round_data in rounds:
                street = round_data['street']
                actions = round_data['actions']

                for action in actions:
                    player_id = action.get("player_id")
                    player_name = player_names.get(player_id)
                    action_type = action.get("action")
                    position = player_position.get(player_id)

                    # VPIP: Any call or raise action before the flop
                    if street == "Preflop" and action_type in ["Call", "Raise"]:
                        preflop_participation.add(player_id)
                        if action_type == "Raise":
                            preflop_raisers.add(player_id)
                            raise_count += 1
                            # Detect if this is the third raise (3-bet)
                            if raise_count == 2:  # First raise already occurred, second raise = 3-bet
                                three_bet_attempts.add(player_id)

                    # ATS: Raising from late position (CU or BU)
                    if position in [N_players-3, N_players-2]:
                        stats_data[player_name]["late_position"] += 1
                        if street == "Preflop" and action_type == "Raise": 
                            late_position_raisers.add(player_id)

                    # AF: Track aggression factor by counting aggressive vs passive actions postflop
                    if street in ["Flop", "Turn", "River"]:
                        if action_type in ["Bet", "Raise"]:
                            stats_data[player_name]["af_aggressive"] += 1
                        elif action_type == "Call":
                            stats_data[player_name]["af_passive"] += 1

                    ########## NEED TO CORRECT FOR DOUBLE COUNTING ########3
                    # Track call to raise
                    if action_type == "Call" and raise_count >= 1:
                        stats_data[player_name]["call_to_raise"] += 1

                    # Track fold to raise
                    if action_type == "Fold" and raise_count >= 1:
                        stats_data[player_name]["fold_to_raise"] += 1
                                            
                    # Track folds to 3-bet
                    if action_type == "Fold" and raise_count >= 2:
                        stats_data[player_name]["fold_to_three_bet"] += 1

                        

                # Update stats for each player in this hand
                for player_id, player_name in player_names.items():
                    stats_data[player_name]["hands"] += 1
                    
                    # VPIP and PFR calculations
                    if player_id in preflop_participation:
                        stats_data[player_name]["vpip"] += 1
                    if player_id in preflop_raisers:
                        stats_data[player_name]["pfr"] += 1

                    # ATS calculation
                    if player_id in late_position_raisers:
                        stats_data[player_name]["ats"] += 1

                    # 3-Bet calculation
                    if player_id in three_bet_attempts:
                        stats_data[player_name]["three_bet"] += 1
                        

    # Calculating final statistics
    final_stats = []
    for player, data in stats_data.items():
        hands = data["hands"]
        hands_late_position = data["late_position"]
        hands_against_raise = data["three_bet"] + data["fold_to_raise"] + data["call_to_raise"]
        if hands > 0:
            vpip = (data["vpip"] / hands) * 100
            pfr = (data["pfr"] / hands) * 100
            af = (data["af_aggressive"] / max(1, data["af_passive"]))  # Avoid division by zero
            ats = (data["ats"] / hands_late_position) * 100 if hands_late_position > 0 else 0
            fold_to_three_bet = (data["fold_to_three_bet"] / hands_against_raise) * 100 if hands_against_raise > 0 else 0 
            three_bet = (data["three_bet"] / hands_against_raise) * 100 if hands_against_raise > 0 else 0 
            final_stats.append({
                "Name": player,
                "Hands" : hands,
                "VPIP": f"{vpip:.1f}",
                "PFR": f"{pfr:.1f}",
                "AF": f"{af:.1f}",
                "ATS": f"{ats:.1f}",
                "FoldToThreeBet": f"{fold_to_three_bet:.1f}",
                "ThreeBet": f"{three_bet:.1f}"
            })

    final_stats_sorted = sorted(final_stats, key=lambda x: x["Hands"], reverse=True)
    return final_stats_sorted

@statistics_bp.route('/')
def statistics():
    stats = compute_stats()
    return render_template('statistics.html', stats = stats)
