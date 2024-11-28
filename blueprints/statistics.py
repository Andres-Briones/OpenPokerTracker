from flask import Blueprint, request, jsonify, session, render_template, current_app, redirect, send_file
from models import *
from utils.plots import *
from collections import defaultdict
import json

statistics_bp = Blueprint('statistics', __name__)

@statistics_bp.route('/')
def statistics():
    db_path = session.get("db_path", None)
    if db_path is None : return redirect('/')

    # Update and retrieve overall statistics
    update_players_statistics(session["db_path"])
    players = get_players_list(session["db_path"])
    
    # Get selected player from query parameters
    selected_player = request.args.get('selected_player', None)

    player_stats = None
    position_stats = None
    player_stats_short = None
    position_stats_short = None

    if selected_player :
        position_stats = get_player_statistics_per_position(db_path, selected_player, min_players = 4)
        position_stats_short = get_player_statistics_per_position(db_path, selected_player, max_players = 3)
        player_stats = get_player_full_statistics(db_path, selected_player, min_players = 4)
        player_stats_short = get_player_full_statistics(db_path, selected_player, max_players = 3)

    # if selected_player is None: selected_player = stats[0]["name"] # By default select the player with the greater number of hands

    return render_template('statistics.html',
                           players = players,
                           selected_player=selected_player,
                           player_stats = player_stats,
                           position_stats = position_stats,
                           player_stats_short = player_stats_short,
                           position_stats_short = position_stats_short,
                           )

@statistics_bp.route('/player_stats_plot')
def player_stats_plot():
    db_path = session.get("db_path")
    player_name = request.args.get('name')
    window_size = int(request.args.get('window_size', 10))  # Default window size to 10 if not provided
    if not db_path or not player_name:
        return jsonify({"error": "Database path or player name missing"}), 400

    img = generate_cummulative_profit_plot(player_name, db_path, window_size)
    return send_file(img, mimetype="image/png")

@statistics_bp.route('/player_opening_range_plot')
def player_opening_range_plot():
    db_path = session.get("db_path")
    player_name = request.args.get('name')
    if not player_name:
        return jsonify({"error": "Player name missing"}), 400
    img = generate_opening_range_plot(player_name, db_path)
    return send_file(img, mimetype="image/png")


