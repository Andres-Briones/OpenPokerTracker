# models.py
from flask import current_app
import sqlite3
from config import Config
import os
import json
from utils.hand_parser import * 


# Database connection helper
def get_db_connection():
    db_path = current_app.config['DB_PATH']  # Access the DB_PATH from the config
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    return conn

def init_db():
    with get_db_connection() as conn:
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
                game_code TEXT,
                date_time TEXT,
                hero_cards TEXT,
                ohh_data TEXT,  -- JSON blob to store the full ohh object
                FOREIGN KEY (file_id) REFERENCES files(id)
            );
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
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


# Add file to database, returns 1 if new file is added, returns 0 if the file is already in the database, returns -1 if error
def add_file_to_db(filename, file_path):
    with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if the file already exists in the database
            cursor.execute("SELECT id FROM files WHERE filename = ?", (filename,))
            result = cursor.fetchone()
            
            if result:
                return None

            # Insert the file record into the database since it doesn't exist
            cursor.execute("INSERT INTO files (filename) VALUES (?)", (filename,))
            file_id = cursor.lastrowid
            conn.commit()

    return file_id

def add_hands_from_file_to_db(file_path, file_id):
    with open(file_path, 'r') as f:
        content = f.read()
        hand_sections = [section.strip() for section in content.split('\n\n') if section.strip()]
        for hand_text in hand_sections:
            hand_data = json.loads(hand_text)
            save_hand_to_db(file_id, hand_data)  # Save each hand to the database
    return




# Add or update player in the database, returns the id of the player
def add_and_link_player(player_name, hand_id, vpip, pfr, won):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if player already exists
        cursor.execute("SELECT id FROM players WHERE name = ?", (player_name,))
        player = cursor.fetchone()

        if player: #Player exists
            player_id = player["id"]
        else : # Player does not exist, create a new record
            cursor.execute("INSERT INTO players (name) VALUES (?)", (player_name,))
            player_id = cursor.lastrowid
            conn.commit()

        #Link player to hand in players_hand table
        cursor.execute("INSERT INTO players_hands (player_id, hand_id, vpip, pfr, won) VALUES (?,?,?,?,?)",
                       (player_id, hand_id, vpip, pfr, won))

        conn.commit()

    return player_id

# Parse and store data in database
def save_hand_to_db(file_id, ohh_obj):

    general_data, stats_data = parse_hand_stat(ohh_obj)
    if stats_data is None :
        print(f"  Hand {general_data['game_code']} is anonymous, not inserted into the database")
        return


    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Insert hand data with full ohh object stored as JSON
        cursor.execute(
            "INSERT INTO hands (file_id, game_code, date_time, hero_cards, ohh_data) VALUES (?, ?, ?, ?, ?)",
            (file_id, general_data['game_code'], general_data['date_time'], general_data['hero_cards'], json.dumps(ohh_obj))
        )
        hand_id = cursor.lastrowid
        conn.commit()

    # Add play if they don’t exist and link to hand
    for name in stats_data.keys():
        player_id = add_and_link_player(name, hand_id, **stats_data[name])
        #print(f"  Hand {general_data['game_code']} was inserted into the database")


# Load hands data from database on startup
def load_hands_from_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, game_code, date_time, hero_cards FROM hands ORDER BY date_time DESC")
        hands = cursor.fetchall()
        return hands

# Update player statistics from players_hands table
def update_players_statistics():
    with get_db_connection() as conn:
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

def get_players_statistics():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, hands, vpip, pfr, win_rate from players ORDER BY hands DESC")
        players_stats = cursor.fetchall()
        return players_stats


