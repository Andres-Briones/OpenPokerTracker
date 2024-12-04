
def cardsListToString(cards):
    return " ".join([getCardSymbol(card) for card in cards])


RANK_ORDER = "23456789TJQKA" 
def cardsToClass(cards):
    cards = cards.split (' ')

    rank1 = cards[0][0]
    rank2 = cards[1][0]

    if RANK_ORDER.index(rank1) >= RANK_ORDER.index(rank2):
        handClass = rank1 + rank2
    else :
        handClass = rank2 + rank1

    if cards[0][1] == cards[1][1] :
        handClass += 's'
    elif cards[0][0] != cards[1][0] :
        handClass += 'o'

    return handClass

def getCardSymbol(card):
    suitSymbols = {
        'h': '♥', 
        's': '♠', 
        'd': '♦', 
        'c': '♣'  
    }
    return card[0]+ suitSymbols[card[1]]
