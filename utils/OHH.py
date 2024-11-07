import json
from decimal import Decimal, getcontext
from typing import List
from pathlib import Path

possible_streets = ["Preflop", "Flop", "Turn", "River", "Showdown"]
possible_actions = [
            "Dealt Cards", #Player is dealt cards.
            "Mucks Cards", #The player mucks/doesn't show their cards.
            "Shows Cards", #The player shows their cards. Should be included in a "Showdown" round.
            "Post Ante", #The player posts an ante.
            "Post SB", #The player posts the small blind.
            "Post BB", #The player posts the big blind.
            "Straddle", #The player posts a straddle to buy the button.
            "Post Dead", #The player posts a dead blind.
            "Post Extra Blind", #The player posts any other type of blind.
            "Fold", #The player folds their cards.
            "Check", #The player checks.
            "Bet", #The player bets in an un-bet/unraised pot.
            "Raise", #The player makes a raise.
            "Call", #The player calls a bet/raise.
            "Added Chips", #Player adds chips to his chip stack (cash game only).
            "Sits Down", #Player sits down at a seat.
            "Stands Up", #Player removes them self from the table.
            "Add to Pot",  #This can be a player or non-player action.  Can be used when the site adds money/chips to the pot to stimulate action, for example.
]

def cards_string_to_list(string): #When cards are given as "AcKs" for example
    if len(string)%2 == 1 :
        raise ValueError("Invalid length of string")
    return [string[i:i+2] for i in range(0, len(string), 2)]

class Action:
    def __init__(self, action_id, player_id: int, action_type: str, amount: Decimal = 0, is_all_in: bool = False, cards : list = None):
        self.action_id = action_id# Starts at 0 for each new round
        self.player_id = player_id
        self.action_type = action_type
        self.amount = amount
        self.is_all_in = is_all_in
        self.cards = None

        if action_type not in possible_actions:
            raise ValueError("Incorrect action_type")

    def add_cards(self, cards): # Used for Dealt Cards action_type
        if type(cards) == str: cards = cards_string_to_list(cards)
        self.cards = cards

    def to_json(self) -> dict:
        """Return a JSON-compatible dictionary for the action."""
        output = { "action_id": self.action_id,
                   "player_id": self.player_id,
                   "action": self.action_type,
                 }
        if float(self.amount) > 0 : output["amount"] = self.amount
        if self.is_all_in : output["is_allin"]: True
        if self.cards is not None: output["cards"] = self.cards

        return output


class Round:
    def __init__(self, round_id: int, street: str):
        if street not in possible_streets:
            raise ValueError("Incorrect street")

        self.round_id = round_id 
        self.street = street
        self.actions: List[Action] = []
        self.cards: List[str] = []

    def add_action(self, action: Action):
        """Add an Action object to the round."""
        self.actions.append(action)

    def set_community_cards(self, cards: List[str]):
        """Set community cards for the round."""
        self.cards = cards

    def to_json(self) -> dict:
        """Return a JSON-compatible dictionary for the round."""
        return {
            "id": self.round_id,
            "street": self.street,
            "actions": [action.to_json() for action in self.actions],
            "cards": self.cards
        }


class Player:
    def __init__(self, player_id : int, name: str, starting_stack: Decimal, final_stack : Decimal, seat: int) :
        self.player_id = player_id
        self.name = name
        self.starting_stack = starting_stack
        self.final_stack = final_stack
        self.seat = seat
        
        # Winnings
        self.win_amount = None 

    def add_winnings(self, win_amount, cashout_amount : Decimal = 0, cashout_fee : Decimal = 0, bonus_amount : Decimal = 0, contributed_rake : Decimal = 0):
        self.win_amount = win_amount
        self.cashout_amount = cashout_amount
        self.cashout_fee = cashout_fee
        self.bonus_amount = bonus_amount
        self.contributed_rake = contributed_rake

    def winnings_to_json(self) -> dict:
        return {
	    "win_amount": self.win_amount,
	    "cashout_amount": self.cashout_amount,
	    "cashout_fee": self.cashout_fee,
            "bonus_amount" : self.bonus_amount,
	    "contributed_rake" : self.contributed_rake 
        }


    def to_json(self) -> dict:
        """Return a JSON-compatible dictionary for the player."""
        return {
            "id": self.player_id,
            "name": self.name,
            "starting_stack": self.starting_stack,
            "final_stack": self.final_stack,
            "seat": self.seat
        }


class Pot:
    def __init__(self, pot_number: int, amount : Decimal, rake : Decimal = 0 ,jackpot : Decimal = 0):
        self.pot_number = pot_number
        self.amount = amount
        self.rake = rake
        self.jackpot = jackpot
        self.players = []

    def add_player(self, player_: Player):
        self.players.append(player_)
            

    def to_json(self) -> dict:
        """Return a JSON-compatible dictionary for the hand, using session info for context."""
        return {"pot_number": self.pot_number,
                "amount": self.amount,
                "rake": self.rake,
                "jackpot": self.jackpot,
                "players_wins": [player_.winnings_to_json() for player_ in self.players]}
    

class Hand:
    def __init__(self):
        self.table_name = None
        self.table_size = None
        self.hands: List[Hand] = []
        self.tournament = False # Not supported yet
        self.game_type ="Holdem" # Only game_type supported for now
        self.bet_limit: {"bet_type": "NL", "bet_cap": 0} # Only supported limits for now
        self.game_number = None
        self.start_date_utc = None
        self.dealer_seat = None
        self.hero_player_id = None
        self.small_blind_amount = None
        self.big_blind_amount = None
        self.ante_amount = None
        self.flags = []
        self.players = []
        self.rounds: List[Round] = []
        self.pots: List[Pot] = []

    def add_round(self, round_: Round):
        """Add a Round object to the hand."""
        self.rounds.append(round_)

    def add_player(self, player_data: dict):
        """Add player information to the hand."""
        self.players.append(player_data)

    def add_pot(self, pot_: Pot):
        """Set pot information for the hand."""
        self.pots.append(pot_)

    def to_json(self, session) -> dict:
        """Return a JSON-compatible dictionary for the hand, using session info for context."""
        if self.small_blind_amount % 1 == 0 :
            Decimal = lambda x: str(int(x)) 
        return { "ohh" :
                {
                    "spec_version": session.spec_version,
                    "site_name": session.site_name,
                    "network_name": session.network_name,
                    "internal_version": session.internal_version,
                    "tournament": self.tournament, # Not supported yet
                    "game_number": self.game_number,
                    "start_date_utc": self.start_date_utc,
                    "table_name": self.table_name,
                    "table_size": self.table_size,
                    "game_type" : self.game_type,
                    "hero_player_id": self.hero_player_id,
                    "small_blind_amount" : self.small_blind_amount,
                    "big_blind_amount" : self.big_blind_amount,
                    "ante_amount" : self.ante_amount,
                    "flags": self.flags,
                    "players": [player_.to_json() for player_ in self.players],
                    "rounds": [round_.to_json() for round_ in self.rounds],
                    "pots" : [pot_.to_json() for pot_ in self.pots]
                 }
                }

    def parse_template(self, input_file: str, format_type: str):
        """
        Template function
        Parse the hand data based on the input file format.
        
        :param input_file: Path to the input file
        :param format_type: Type of format (e.g., 'swisscasinos' ,'pluribus-logs', 'pokerstars')
        :return: None
        """
        # Parsing logic to be implemented
        pass


class Session:
    def __init__(self, session_id: str, site_name: str = "Unknown", network_name: str = "Unknown", internal_version: str = "Unkwown", spec_version: str = "1.4.6"):
        self.session_id = session_id
        self.site_name = site_name
        self.network_name = network_name
        self.internal_version = internal_version
        self.spec_version = spec_version
        self.hands : List[Hand] = []

    def add_hand(self, hand: Hand):
        """Add a Hand object to the session."""
        self.hands.append(hand)

    def save_to_OHH(self, output_dir: str, output_stem = None):
        """Save the session data as an OHHfile."""
        if output_stem is None: output_stem = "session_" + str(self.session_id)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{output_stem}.OHH"
        with open(output_file, "w") as outfile:
            for hand in self.hands :
                json.dump(hand.to_json(self), outfile, indent=2, default=str)
                outfile.write("\n\n")
