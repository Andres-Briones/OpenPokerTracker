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
                hero_cards TEXT,
                hero_hand_class TEXT,
                hero_position TEXT,
                hero_profit REAL,
                flop BOOLEAN, -- if there was a flop or not
                players TEXT, -- Players that participated in the hand (hero can be absent of the list if the hand is observed)
                ohh_data TEXT  -- JSON blob to store the full ohh object
            );
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                hands INTEGER, -- player hands
                vpip REAL,
                pfr REAL,
                win_rate REAL,
                af REAL -- Aggressive factor = (raises + bets) / calls
                -- We will add more statistics later
            );
            CREATE TABLE IF NOT EXISTS players_hands (
                player_id INTEGER,
                hand_id INTEGER,
                cards TEXT,
                hand_class TEXT,
                position INT,
                position_name TEXT,
                profit DECIMAL,
                rake DECIMAL,
                participed BOOLEAN,
                vpip BOOLEAN,
                pfr BOOLEAN,
                aggressive INT,
                passive INT,
                two_bet_possibility BOOLEAN,
                limp BOOLEAN,
                two_bet BOOLEAN,
                three_bet_possibility BOOLEAN,
                three_bet BOOLEAN,
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

    hands_dics = []
    players = set()
    players_hands_dics = []

    # Collect data for all hands and players in the batch
    for hand_data in hand_data_list:
        hands_data, players_hands_data = parse_hand_at_upload(hand_data)
        if players_hands_data is None:
            continue  # Skip anonymous hands
        
        # Check if hand already exists in database, if it's the case, skip the hand
        # TODO find a way to do it fast because it causes a lot of delay per file
        #game_number = hands_data["game_number"]
        #site_name = hands_data["game_number"]
        #table_name = hands_data["table_name"]
        #cursor.execute("SELECT id FROM hands WHERE game_number = ? AND site_name = ? AND table_name = ?", (game_number, site_name, table_name))
        #if cursor.fetchone(): continue
        
        hands_data["ohh_data"] = json.dumps(hand_data)
        hands_dics.append(hands_data)
        players_hands_dics.append(players_hands_data)
            
        #Add players name to players set
        for name in players_hands_data.keys(): players.add(name)

    if not players_hands_dics : # If the list is empty it means that all games are annonymous
        return

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Fetch the current max ID from the `hands` table directly
        cursor.execute("SELECT MAX(id) FROM hands")
        max_id = cursor.fetchone()[0] or 0  # Set to 0 if there are no rows

        # Generate hands dataframe from list of dictionaries
        hands_df = pd.DataFrame.from_dict(hands_dics)

        # Insert hands dataframe into hands table
        hands_df.to_sql(
            name = 'hands',# Name of SQL table.
            con = conn, # sqlalchemy.engine.Engine or sqlite3.Connection
            if_exists='append', # How to behave if the table already exists. You can use 'replace', 'append' to replace it.
            index=False, # It means index of DataFrame will save. Set False to ignore the index of DataFrame.
            chunksize= 999 // (len(hands_df.columns)+1), # If DataFrame is big, this parameter is needed 
            method="multi" # For inserting with executemany
        )

        # Calculate new hand IDs starting from max_id + 1
        hand_ids = range(max_id + 1, max_id + 1 + len(hands_dics))

        # Retrieve player_id or insert player and get id
        name_to_id = {}
        for name in players:
            cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
            result = cursor.fetchone()
            if result:
                name_to_id[name] = result[0]  # Existing player ID
            else:
                cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
                name_to_id[name] = cursor.lastrowid  # New player ID

        # Prepare players_hands dataframe by using hands_ids and name_to_id
        players_hands_df_list = []
        for hand_id, players_hands in zip(hand_ids, players_hands_dics) : 
            df = pd.DataFrame(data = players_hands).T.reset_index(names = 'player_id')
            df['player_id'] = df['player_id'].apply(lambda name : name_to_id[name])
            df["hand_id"] = hand_id
            players_hands_df_list.append(df)

        players_hands_df = pd.concat(players_hands_df_list, ignore_index=True)

        # Insert players_hands dataframe into players_hands table
        players_hands_df.to_sql(
            name = 'players_hands',# Name of SQL table.
            con = conn, # sqlalchemy.engine.Engine or sqlite3.Connection
            if_exists='append', # How to behave if the table already exists. You can use 'replace', 'append' to replace it.
            index=False, # It means index of DataFrame will save. Set False to ignore the index of DataFrame.
            chunksize= 999 // (len(players_hands_df.columns)+1), # If DataFrame is big, this parameter is needed 
            method="multi" # For inserting with executemany
        )

        conn.commit()  # Single commit for the entire bulk

    return

def load_hands_from_db(db_path):
    """Loads all hands from the database for display or analysis."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
        SELECT id,
               table_name,
               date_time,
               hero_cards,
               hero_position,
               hero_profit
        FROM hands
        ORDER BY date_time DESC
        """
        cursor.execute(query)
        hands = cursor.fetchall()
        
    return hands

def load_hands_from_db_old(db_path):
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
            vpip = result.VPIP,
            pfr = result.PFR,
            win_rate = result.bb_per_hand,
            af = result.AF
        FROM (SELECT player_id,
                     COUNT(ph.hand_id) AS hands,
                     ROUND(CAST(SUM(ph.vpip) AS FLOAT) / CAST(SUM(ph.participed) AS FLOAT)*100,2) AS VPIP,
                     ROUND(CAST(SUM(ph.pfr) AS FLOAT) / CAST(SUM(ph.participed) AS FLOAT)*100,2) AS PFR,
                     ROUND(CAST(SUM(ph.aggressive) AS FLOAT) / CAST(SUM(ph.passive) AS FLOAT),2) AS AF,
                     ROUND(AVG(profit) / h.big_blind_amount,2) AS bb_per_hand
              FROM players_hands ph JOIN hands h on ph.hand_id == h.id
              GROUP BY player_id)
        AS result
        WHERE players.id = result.player_id
        """)
        conn.commit()

def get_players_list(db_path):
    """Retrieves players from the database."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, hands, vpip, pfr, win_rate from players ORDER BY hands DESC")
        players = cursor.fetchall()
        return players

def get_player_statistics_per_position(db_path, player_name, min_players=2, max_players=6):
    """Retrieves statistics grouped by position for the given players from the database."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = f"""
        SELECT 
        ph.position_name AS position,
        COUNT(ph.hand_id) AS hands,
        ROUND(CAST(SUM(ph.vpip) AS FLOAT) / CAST(SUM(ph.participed) AS FLOAT)*100,2) AS VPIP,
        ROUND(CAST(SUM(ph.pfr) AS FLOAT) / CAST(SUM(ph.participed) AS FLOAT)*100,2) AS PFR,
        ROUND(CAST(SUM(ph.aggressive) AS FLOAT) / CAST(SUM(ph.passive) AS FLOAT),2) AS AF,
        ROUND(CAST(SUM(ph.two_bet) AS FLOAT) / CAST(SUM(ph.two_bet_possibility) AS FLOAT)*100,2) AS two_bet,
        ROUND(CAST(SUM(ph.limp) AS FLOAT) / CAST(SUM(ph.two_bet_possibility) AS FLOAT)*100,2) AS limp,
        ROUND(CAST(SUM(ph.three_bet) AS FLOAT) / CAST(SUM(ph.three_bet_possibility) AS FLOAT)*100,2) AS three_bet,
        ROUND(AVG(profit) / h.big_blind_amount,2) AS bb_per_hand
        FROM players_hands ph JOIN hands h ON h.id == ph.hand_id JOIN players p ON p.id == ph.player_id
        WHERE p.name == "{player_name}" AND h.number_players >= {min_players} AND  h.number_players <= {max_players} 
        GROUP BY position_name 
        ORDER BY MAX(ph.position) DESC
        """
        cursor.execute(query)
        player_stats = cursor.fetchall()
        return player_stats


def get_player_full_statistics(db_path, player_name, min_players=2, max_players=6):
    """Retrieves statistics grouped by position for the given players from the database."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        query = f"""
        SELECT 
        COUNT(ph.hand_id) AS hands,
        ROUND(CAST(SUM(ph.vpip) AS FLOAT) / CAST(SUM(ph.participed) AS FLOAT)*100,2) AS VPIP,
        ROUND(CAST(SUM(ph.pfr) AS FLOAT) / CAST(SUM(ph.participed) AS FLOAT)*100,2) AS PFR,
        ROUND(CAST(SUM(ph.aggressive) AS FLOAT) / CAST(SUM(ph.passive) AS FLOAT),2) AS AF,
        ROUND(CAST(SUM(ph.two_bet) AS FLOAT) / CAST(SUM(ph.two_bet_possibility) AS FLOAT)*100,2) AS two_bet,
        ROUND(CAST(SUM(ph.limp) AS FLOAT) / CAST(SUM(ph.two_bet_possibility) AS FLOAT)*100,2) AS limp,
        ROUND(CAST(SUM(ph.three_bet) AS FLOAT) / CAST(SUM(ph.three_bet_possibility) AS FLOAT)*100,2) AS three_bet,
        ROUND(SUM(CASE WHEN profit > 0 THEN profit ELSE 0 END) + SUM(rake), 2) AS total_won,
        ROUND(SUM(CASE WHEN profit < 0 THEN profit ELSE 0 END),2) AS total_lost,
        ROUND(SUM(rake),2) AS total_rake,
        ROUND(SUM(profit),2) AS profit,
        ROUND(AVG(rake)/h.big_blind_amount*100,2) AS rake_bb_per_100hand,
        ROUND(AVG(profit)/h.big_blind_amount,2) AS bb_per_hand
        FROM players_hands ph JOIN hands h ON h.id == ph.hand_id JOIN players p ON p.id == ph.player_id
        WHERE p.name == "{player_name}" AND h.number_players >= {min_players} AND  h.number_players <= {max_players} 
        """
        cursor.execute(query)
        player_stats = cursor.fetchone()

        return player_stats



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

        # We can't update a table directly with df.to_sql() and by replacing it we loose the types information. For simplicity and generality we will remove the old table, recreate one empty with init_db and append to the table with to_sql().
        cursor.execute("DROP TABLE players_hands")

        conn.commit()

    init_db(db_path) # Recreates players_hands table

    name_to_id = {player["name"]:player["id"] for player in players}
    
    players_hands_df_list = []
    for hand in hands:
        ohh = json.loads(hand["ohh_data"])
        hands_data, players_hands_data = parse_hand_at_upload(ohh)
        df = pd.DataFrame(data = players_hands_data).T.reset_index(names = 'player_id')
        df['player_id'] = df['player_id'].apply(lambda name : name_to_id[name])
        df["hand_id"] = hand["id"]
        players_hands_df_list.append(df)

    players_hands_df = pd.concat(players_hands_df_list, ignore_index=True)

    with sqlite3.connect(db_path) as conn:

        players_hands_df.to_sql(
            name = 'players_hands',# Name of SQL table.
            con = conn, # sqlalchemy.engine.Engine or sqlite3.Connection
            if_exists='append', # How to behave if the table already exists. You can use 'replace', 'append' to replace it.
            index=False, # It means index of DataFrame will save. Set False to ignore the index of DataFrame.
            chunksize= 999 // (len(players_hands_df.columns)+1), # If DataFrame is big, this parameter is needed 
            method="multi", # For inserting with executemany
            dtype=None, # Set the columns type of sql table. Usefull when creating the table
        )
        conn.commit()
    
