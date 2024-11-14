from models import * 
import pandas as pd
from io import BytesIO
from matplotlib.figure import Figure
import numpy as np

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
