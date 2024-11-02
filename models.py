# models.py
from flask import current_app
import sqlite3
from config import Config
import os
import json


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
                hands TEXT,  -- JSON array of hand_ids where the player was present
                statistics TEXT  -- JSON dictionary to store player statistics
            );
            """)
            conn.commit()
            print("Database initialized successfully.")
        except sqlite3.Error as e:
            print("Database initialization failed:", e)

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

# Add or update player in the database
def add_or_update_player(player_name, hand_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check if player already exists
        cursor.execute("SELECT id, hands FROM players WHERE name = ?", (player_name,))
        result = cursor.fetchone()

        if result:
            # Player exists, update their list of hands
            player_id = result["id"]
            hands = json.loads(result["hands"])
            if hand_id not in hands:
                hands.append(hand_id)
            cursor.execute("UPDATE players SET hands = ? WHERE id = ?", (json.dumps(hands), player_id))
        else:
            # Player does not exist, create a new record
            hands = [hand_id]
            cursor.execute(
                "INSERT INTO players (name, hands, statistics) VALUES (?, ?, ?)",
                (player_name, json.dumps(hands), json.dumps({}))  # Empty statistics dictionary
            )
        conn.commit()

# Parse and store data in database
def save_hand_to_db(file_id, parsed_hand, ohh_data):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Insert hand data with full ohh object stored as JSON
        cursor.execute(
            "INSERT INTO hands (file_id, game_code, date_time, hero_cards, ohh_data) VALUES (?, ?, ?, ?, ?)",
            (file_id, parsed_hand['game_code'], parsed_hand['date_time'], parsed_hand['hero_cards'], json.dumps(ohh_data))
        )
        hand_id = cursor.lastrowid

        # Update each player's record or add them if they don’t exist
        #for player in parsed_hand['players']:
        #    add_or_update_player(player['name'], hand_id)
        print(f"Hand {parsed_hand['game_code']} was inserted into the database")
        
        conn.commit()
