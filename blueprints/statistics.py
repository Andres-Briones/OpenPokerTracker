from flask import Blueprint, request, jsonify, session, render_template, current_app, redirect, send_file
from models import * 
from collections import defaultdict
import numpy as np
import json
from matplotlib.figure import Figure
from io import BytesIO
import pandas as pd

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/')
def statistics():
    db_path = session.get("db_path", None)
    if db_path is None : return redirect('/')

    # Update and retrieve overall statistics
    update_players_statistics(session["db_path"])
    stats = get_players_statistics(session["db_path"])
    
    # Get selected player from query parameters
    selected_player = request.args.get('selected_player', None)
    # if selected_player is None: selected_player = stats[0]["name"] # By default select the player with the greater number of hands

    return render_template('statistics.html', stats = stats, selected_player=selected_player)

@statistics_bp.route('/player_stats_plot')
def player_stats_plot():
    db_path = session.get("db_path")
    player_name = request.args.get('name')
    window_size = int(request.args.get('window_size', 10))  # Default window size to 10 if not provided
    if not db_path or not player_name:
        return jsonify({"error": "Database path or player name missing"}), 400

    img = generate_cummulative_profit_plot(player_name, db_path, window_size)
    return send_file(img, mimetype="image/png")

def generate_cummulative_profit_plot(player_name, db_path, window_size = 10):
    player_profits = get_player_profit_historique(player_name, db_path)
    profits_df =  pd.DataFrame(player_profits)
    profits_df["date_time"] =  pd.to_datetime(profits_df['date_time'], format='%Y-%m-%dT%H:%M:%SZ')
    profits_df.sort_values(by='date_time', inplace=True, ignore_index=True)
    profits_df["profit_cum"] = np.cumsum(profits_df["profit"])
    profits_df["profit_cum_smooth"] = profits_df["profit_cum"].rolling(window=window_size).mean()

    # Generate the plot
    fig = Figure(figsize=(12, 6))
    ax = fig.subplots()
    #ax.plot(profits_df["profit_cum"])
    ax.plot(profits_df["profit_cum_smooth"])
    ax.set_title(f"Statistics for {player_name}")
    ax.set_xlabel("Hands")
    ax.set_ylabel("Cumulative profit (€)")

    img = BytesIO()
    fig.savefig(img, format="png")
    img.seek(0)

    return img

def OLD_compute_stats(): # UNUSED !! Becuase not efficient. We keep it as reference for now

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
