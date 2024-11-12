# models.py
from flask import current_app
import sqlite3
from config import Config
import os
import json
from utils.hand_parser import * 


# Database connection helper
def get_db_connection(db_path, timeout = 0):
    """Establishes and returns a database connection."""
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    return conn

def list_databases(db_directory):
    """Returns a list of available databases in the specified directory."""
    db_files = os.listdir(db_directory)
    return [db[:-3] for db in db_files if db.endswith('.db')]



def init_db(db_path):
    """Initializes the database with necessary tables."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS hands (
                id INTEGER PRIMARY KEY,
                file_id INTEGER,
                game_number TEXT,
                date_time TEXT,
                hero_cards TEXT,
                ohh_data TEXT,  -- JSON blob to store the full ohh object
                FOREIGN KEY (file_id) REFERENCES files(id)
            );
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                hands INTEGER, -- player hands
                vpip REAL,
                pfr REAL,
                win_rate REAL -- $/100 hands (incorrect computation for now)
                -- We will add more statistics later
            );
            CREATE TABLE IF NOT EXISTS players_hands (
                player_id INTEGER,
                hand_id INTEGER,
                vpip BOOLEAN,
                pfr BOOLEAN,
                won DECIMAL,
                FOREIGN KEY (player_id) REFERENCES players(id)
                FOREIGN KEY (hand_id) REFERENCES hands(id)
            PRIMARY KEY (player_id, hand_id)  -- Ensures each player can participate in each hand only once
            );
            """)
            conn.commit()
            print("Database initialized successfully.")
        except sqlite3.Error as e:
            print("Database initialization failed:", e)


def add_file_to_db(filename, file_path, db_path):
    """Adds a new file to the database or returns None if the file already exists."""
    with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Check if the file already exists in the database
            cursor.execute("SELECT id FROM files WHERE filename = ?", (filename,))
            result = cursor.fetchone()
            
            if result:
                return None # File already exists

            # Insert the file record into the database since it doesn't exist
            cursor.execute("INSERT INTO files (filename) VALUES (?)", (filename,))
            file_id = cursor.lastrowid
            conn.commit()

    return file_id

def save_hands_bulk(file_id, hand_data_list, db_path):
    """Inserts multiple hands and associated player data in a single transaction."""
    hands_data = []
    hands_stats = []
    players = set()
    players_hands_data = []

    # Collect data for all hands and players in the batch
    for hand_data in hand_data_list:
        general_data, stats_data = parse_hand_stat(hand_data)
        if stats_data is None:
            print("Warning: stats_data is None for hand:", general_data["game_number"])
            continue  # Skip anonymous hands

        # Prepare hand data for bulk insert into `hands` table
        hands_data.append((file_id, general_data['game_number'], general_data['date_time'], general_data['hero_cards'], json.dumps(hand_data)))
        hands_stats.append(stats_data)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Fetch the current max ID from the `hands` table directly
        cursor.execute("SELECT MAX(id) AS max_id FROM hands")
        max_id = cursor.fetchone()["max_id"] or 0  # Set to 0 if there are no rows

        # Insert all hands in bulk
        cursor.executemany(
            "INSERT INTO hands (file_id, game_number, date_time, hero_cards, ohh_data) VALUES (?, ?, ?, ?, ?)",
            hands_data
        )
        conn.commit()

        # Calculate new hand IDs starting from max_id + 1
        hand_ids = range(max_id + 1, max_id + 1 + len(hands_data))

        # Build the player and player-hand link data with unique hand_ids
        for hand_id, players_stats in zip(hand_ids, hands_stats):
            for name, stats in players_stats.items():
                players_hands_data.append((name, hand_id, stats['vpip'], stats['pfr'], stats['won']))
                players.add(name) # Add player name to players (it's a set so there will be only one entry per player)

        # Retrieve or insert players and build unique `players_hands` data
        name_to_id = {}
        for name in players:
            cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
            result = cursor.fetchone()
            if result:
                name_to_id[name] = result["id"]  # Existing player ID
            else:
                cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
                name_to_id[name] = cursor.lastrowid  # New player ID

        # Prepare `players_hands` data with actual player IDs and unique hand IDs
        players_hands_insert_data = [
            (name_to_id[player], hand_id, vpip, pfr, won)
            for player, hand_id, vpip, pfr, won in players_hands_data
        ]

        # Insert all player-hand links in bulk
        cursor.executemany(
            "INSERT INTO players_hands (player_id, hand_id, vpip, pfr, won) VALUES (?, ?, ?, ?, ?)",
            players_hands_insert_data
        )

        conn.commit()  # Single commit for the entire bulk


def load_hands_from_db(db_path):
    """Loads all hands from the database for display or analysis."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, game_number, date_time, hero_cards FROM hands ORDER BY date_time DESC")
        hands = cursor.fetchall()
        return hands

def update_players_statistics(db_path):
    """Updates player statistics based on records in players_hands."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE players
        SET hands = result.hands,
            vpip = result.vpip,
            pfr = result.pfr,
            win_rate = result.win_rate
        FROM (SELECT player_id,
                     COUNT(player_id) AS hands,
                     AVG(vpip)*100 AS vpip,
                     AVG(pfr)*100 AS pfr,
                     AVG(won)*100 AS win_rate
              FROM players_hands
              GROUP BY player_id)
        AS result
        WHERE players.id = result.player_id
        """)
        conn.commit()

def get_players_statistics(db_path):
    """Retrieves statistics for all players from the database."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, hands, vpip, pfr, win_rate from players ORDER BY hands DESC")
        players_stats = cursor.fetchall()
        return players_stats

def get_player_profit_historique(player_name, db_path):
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
        SELECT h.date_time AS date_time,
               ph.won AS profit 
        FROM players p
        JOIN players_hands ph ON p.id = ph.player_id
        JOIN hands h ON ph.hand_id = h.id
        WHERE p.name == ?
        """
        cursor.execute(query, (player_name,))
        result = cursor.fetchall()
        return result


def full_update_players_hands(db_path):
    """Fully updates players_hands table by reparsing all hands. Use this if you update parse_hand_stat function with modified or new statistics. All players should already be in the players table."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, ohh_data FROM hands")
        hands = cursor.fetchall()

        for hand in hands :
            ohh = json.loads(hand["ohh_data"])
            general_data, stats_data = parse_hand_stat(ohh)

            for name in stats_data.keys():
                vpip, pfr, won = stats_data[name]["vpip"], stats_data[name]["pfr"], stats_data[name]["won"]
                cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
                player_id = cursor.fetchone()["id"]
                
                cursor.execute(""" UPDATE players_hands SET
                vpip = ?, pfr = ?, won = ?
                WHERE player_id = ? AND hand_id = ?""", 
                               (vpip, pfr , won, player_id, hand["id"]))

        conn.commit()

