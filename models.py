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
    conn.row_factory = sqlite3.Row
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
                vpip REAL,
                pfr REAL, 
                win_rate REAL -- We will add more statistics later
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
                       (player_id, hand_id, vpip, pfr, won)
                       )

        conn.commit()

    return player_id

# Parse and store data in database
def save_hand_to_db(file_id, ohh_obj):

    general_data, stats_data = parse_hand_stat(ohh_obj)

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
        print(f"Hand {general_data['game_code']} was inserted into the database")
        

# Load hands data from database on startup
def load_hands_from_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hands ORDER BY date_time DESC")
        hands = cursor.fetchall()
        hands_list = []
        for hand in hands:
            hands_list.append({
                "id": hand["id"],
                "game_code": hand["game_code"],
                "date_time": hand["date_time"],
                "hero_cards": hand["hero_cards"]
            })
        return hands_list
