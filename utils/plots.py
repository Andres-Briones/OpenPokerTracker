from models import * 
import pandas as pd
from io import BytesIO
from matplotlib.figure import Figure
import numpy as np
import seaborn as sns


def generate_cummulative_profit_plot(player_name, db_path, window_size = 10):
    player_profits = get_player_profit_historique(player_name, db_path)
    profits_df =  pd.DataFrame(player_profits)
    profits_df["date_time"] =  pd.to_datetime(profits_df['date_time'], format='%Y-%m-%d %H:%M:%S')
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


def cardsToClass(cards):
    cards = cards.split (' ')
    handClass = ''
    if cards[0][1] == cards[1][1] :
        handClass = 's'
    elif cards[0][0] != cards[1][0] :
            handClass = 'o'
    handClass = cards[0][0] + cards[1][0] + handClass
    return handClass

# Returns a dictionnary of the type hand_class : probability
def get_hand_class_stats(player_name, db_path, position = None):
    hands = []
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM players WHERE name == ?", (player_name,))
        hero_id = cursor.fetchone()[0]
        
        data = pd.read_sql(f"SELECT cards, position, vpip, pfr, limp, two_bet, h.number_players FROM players_hands JOIN hands h ON h.id == hand_id WHERE player_id == {hero_id} AND cards IS NOT NULL ",conn)    
        data["hand_class"] = data["cards"].apply(cardsToClass)

        if position :
            data = data[data["position"] == position]

        # Calculating the required metrics
        result = data.groupby("hand_class").agg(
            hand_class_count=("hand_class", "size"),  # Count the occurrences of each hand_class
            vpip_count=("vpip", "sum"),  # Sum vpip for each hand_class
            two_bet_count=("two_bet", "sum"),
            limp_count=("limp", "sum")
        ).reset_index()
        result["pourcentage_vpip"] = result["vpip_count"] / result["hand_class_count"]

        return dict(zip(result['hand_class'], result['pourcentage_vpip']))

hand_structure = [
    ['AA', 'AKs', 'AQs', 'AJs', 'ATs', 'A9s', 'A8s', 'A7s', 'A6s', 'A5s', 'A4s', 'A3s', 'A2s'],
    ['AKo', 'KK', 'KQs', 'KJs', 'KTs', 'K9s', 'K8s', 'K7s', 'K6s', 'K5s', 'K4s', 'K3s', 'K2s'],
    ['AQo', 'KQo', 'QQ', 'QJs', 'QTs', 'Q9s', 'Q8s', 'Q7s', 'Q6s', 'Q5s', 'Q4s', 'Q3s', 'Q2s'],
    ['AJo', 'KJo', 'QJo', 'JJ', 'JTs', 'J9s', 'J8s', 'J7s', 'J6s', 'J5s', 'J4s', 'J3s', 'J2s'],
    ['ATo', 'KTo', 'QTo', 'JTo', 'TT', 'T9s', 'T8s', 'T7s', 'T6s', 'T5s', 'T4s', 'T3s', 'T2s'],
    ['A9o', 'K9o', 'Q9o', 'J9o', 'T9o', '99', '98s', '97s', '96s', '95s', '94s', '93s', '92s'],
    ['A8o', 'K8o', 'Q8o', 'J8o', 'T8o', '98o', '88', '87s', '86s', '85s', '84s', '83s', '82s'],
    ['A7o', 'K7o', 'Q7o', 'J7o', 'T7o', '97o', '87o', '77', '76s', '75s', '74s', '73s', '72s'],
    ['A6o', 'K6o', 'Q6o', 'J6o', 'T6o', '96o', '86o', '76o', '66', '65s', '64s', '63s', '62s'],
    ['A5o', 'K5o', 'Q5o', 'J5o', 'T5o', '95o', '85o', '75o', '65o', '55', '54s', '53s', '52s'],
    ['A4o', 'K4o', 'Q4o', 'J4o', 'T4o', '94o', '84o', '74o', '64o', '54o', '44', '43s', '42s'],
    ['A3o', 'K3o', 'Q3o', 'J3o', 'T3o', '93o', '83o', '73o', '63o', '53o', '43o', '33', '32s'],
    ['A2o', 'K2o', 'Q2o', 'J2o', 'T2o', '92o', '82o', '72o', '62o', '52o', '42o', '32o', '22']
]

def generate_opening_range_plot(player_name, db_path, position = None):
    print("entered generate_opening_range_plot")
    hand_to_proba = get_hand_class_stats(player_name, db_path, position)

    # Create a matrix with pourcentages that follows the same 13x13 structure
    hand_matrix = np.array([[hand_to_proba.get(hand, -1) for hand in row] for row in hand_structure])
    # Create a matrix of annotations


    annotations = np.array([[f"{hand}\n{100*hand_to_proba.get(hand):.0f}%" if hand_to_proba.get(hand) is not None else f"{hand}\n-"
                             for hand in row]
                            for row in hand_structure])

    # Set up a colormap where `NaN` values are gray
    cmap = sns.color_palette("rocket_r", as_cmap=True)
    cmap.set_under(color='gray')  # Set `NaN` values to gray

    # Plotting the heatmap with the annotations
    fig = Figure(figsize=(10, 8))
    ax = fig.subplots()
    sns.heatmap(hand_matrix, ax = ax, annot = annotations, fmt='', cmap=cmap, cbar=False, vmin=0, vmax=2.01)

    # Add title and axis labels
    ax.set_title(f'Opening range for {player_name}')
    ax.set_axis_off()

    img = BytesIO()
    fig.savefig(img, format="png")
    img.seek(0)

    return img
