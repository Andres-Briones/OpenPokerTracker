# models.py
from flask import current_app
import sqlite3
from config import Config
import os
import json
import pandas as pd
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
            CREATE TABLE IF NOT EXISTS hands (
                id INTEGER PRIMARY KEY,
                game_number TEXT,
                site_name TEXT,
                table_name TEXT,
                date_time TEXT,
                table_size INT,
                number_players INT,
                small_blind_amount DECIMAL,
                big_blind_amount DECIMAL,
                observed BOOLEAN,
                hero_name TEXT, -- The hero name can change for example if user has different usernames in different platforms
                ohh_data TEXT  -- JSON blob to store the full ohh object
            );
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                hands INTEGER, -- player hands
                vpip REAL,
                pfr REAL,
                win_rate REAL
                -- We will add more statistics later
            );
            CREATE TABLE IF NOT EXISTS players_hands (
                player_id INTEGER,
                hand_id INTEGER,
                cards TEXT,
                position INT,
                profit DECIMAL,
                vpip BOOLEAN,
                pfr BOOLEAN,
                limp BOOLEAN,
                two_bet BOOLEAN,
                FOREIGN KEY (player_id) REFERENCES players(id)
                FOREIGN KEY (hand_id) REFERENCES hands(id)
            PRIMARY KEY (player_id, hand_id)  -- Ensures each player can participate in each hand only once
            );
            """)
            conn.commit()
            print("Database initialized successfully.")

            return 1
        except sqlite3.Error as e:
            print("Database initialization failed:", e)
            return 0

def save_hands_bulk(hand_data_list, db_path):
    """Inserts multiple hands and associated player data in a single transaction."""
    hands_data = []
    players_hands_dics = []
    players = set()

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Collect data for all hands and players in the batch
        for hand_data in hand_data_list:
            general_data, stats_data = parse_hand_at_upload(hand_data)
            if stats_data is None:
                print("Warning: stats_data is None for hand:", general_data["game_number"])
                continue  # Skip anonymous hands
            
            game_number = general_data["game_number"]
            site_name = general_data["game_number"]
            table_name = general_data["table_name"]
        
            # Check if hand already exists in database, if it's the case, skip the hand
            # TODO find a way to do it fast because it causes a lot of delay per file
            #cursor.execute("SELECT id FROM hands WHERE game_number = ? AND site_name = ? AND table_name = ?", (game_number, site_name, table_name))
            #if cursor.fetchone(): continue
            
            # Prepare hand data for bulk insert into `hands` table with correct order
            hands_data.append((game_number,
                           general_data["date_time"],
                           site_name,
                           table_name,
                           general_data["table_size"],
                           general_data["number_players"],
                           general_data["hero_name"],
                           general_data["small_blind_amount"],
                           general_data["big_blind_amount"],
                           general_data["observed"],
                           json.dumps(hand_data)))

            players_hands_dics.append(stats_data)
            
            #Add players name to players set
            for name in stats_data.keys(): players.add(name)

        # Fetch the current max ID from the `hands` table directly
        cursor.execute("SELECT MAX(id) AS max_id FROM hands")
        max_id = cursor.fetchone()["max_id"] or 0  # Set to 0 if there are no rows

        # Insert all hands in bulk
        query = """ INSERT INTO hands (
            game_number,
            date_time,
            site_name,
            table_name,
            table_size,
            number_players,
            hero_name,
            small_blind_amount,
            big_blind_amount,
            observed,
            ohh_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        cursor.executemany(query,hands_data)

        # Calculate new hand IDs starting from max_id + 1
        hand_ids = range(max_id + 1, max_id + 1 + len(hands_data))

        # Retrieve player_id or insert player and get id
        name_to_id = {}
        for name in players:
            cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
            result = cursor.fetchone()
            if result:
                name_to_id[name] = result["id"]  # Existing player ID
            else:
                cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
                name_to_id[name] = cursor.lastrowid  # New player ID


        # Prepare `players_hands` data
        players_hands_data = []
        for player_stats, hand_id in zip(players_hands_dics, hand_ids) :
            for name, stats in player_stats.items():
                players_hands_data.append((
                    name_to_id[name],
                    hand_id,
                    stats["cards"],
                    stats["position"],
                    stats["profit"],
                    stats["vpip"],
                    stats["pfr"],
                    stats["limp"],
                    stats["2bet"]
                ))

        # Insert all player-hand links in bulk
        query = """
        INSERT INTO players_hands (player_id, hand_id, cards, position, profit, vpip, pfr, limp, two_bet)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        cursor.executemany(query,players_hands_data)

        conn.commit()  # Single commit for the entire bulk


def load_hands_from_db(db_path):
    """Loads all hands from the database for display or analysis."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
        SELECT h.id AS id,
               h.table_name AS table_name,
               h.date_time AS date_time,
               ph.cards AS hero_cards,
               ph.position AS position,
               ph.profit AS profit
        FROM hands h
             JOIN players_hands ph ON h.id = ph.hand_id
             JOIN players p ON ph.player_id = p.id
        WHERE p.name == hero_name

        UNION

        SELECT id,
               table_name,
               date_time,
               "x x" AS hero_cards,
               "x" AS position,
               "x" AS profit
        FROM hands
        WHERE observed == true

        ORDER BY date_time DESC
        """
        cursor.execute(query)
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
                     AVG(profit)*100 AS win_rate
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
               ph.profit AS profit 
        FROM players p
        JOIN players_hands ph ON p.id = ph.player_id
        JOIN hands h ON ph.hand_id = h.id
        WHERE p.name == ?
        """
        cursor.execute(query, (player_name,))
        result = cursor.fetchall()
        return result

def full_update_players_hands(db_path):
    """Fully updates players_hands table by reparsing all hands. Use this if you update parse_hand_at_upload function with modified or new statistics. All players should already be in the players table."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, ohh_data FROM hands")
        hands = cursor.fetchall()
        
        cursor.execute("SELECT id, name FROM players")
        players = cursor.fetchall()

    name_to_id = {player["name"]:player["id"] for player in players}
    
    players_hands_df_list = []
    for hand in hands:
        ohh = json.loads(hand["ohh_data"])
        general_data, stats_data = parse_hand_at_upload(ohh)
        df = pd.DataFrame(data = stats_data).T.reset_index(names = 'name')
        df['players_id'] = df['name'].apply(lambda name : name_to_id[name])
        df["hand_id"] = hand["id"]
        players_hands_df_list.append(df)

    players_hands_df = pd.concat(players_hands_df_list, ignore_index=True)

    with sqlite3.connect(main_db_path) as conn:
        players_hands_df.to_sql(
            name = 'players_hands',# Name of SQL table.
            con = conn, # sqlalchemy.engine.Engine or sqlite3.Connection
            if_exists='replace', # How to behave if the table already exists. You can use 'replace', 'append' to replace it.
            index=False, # It means index of DataFrame will save. Set False to ignore the index of DataFrame.
            index_label=False, # Depend on index. 
            chunksize=None, # Just means chunksize. If DataFrame is big will need this parameter.
            dtype=None, # Set the columns type of sql table. Usefull when creating the table
        )
        conn.commit()
    
