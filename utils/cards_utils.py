
def cardsListToString(cards):
    return " ".join([getCardSymbol(card) for card in cards])

def cardsToClass(cards):
    cards = cards.split (' ')
    handClass = ''
    if cards[0][1] == cards[1][1] :
        handClass = 's'
    elif cards[0][0] != cards[1][0] :
            handClass = 'o'
    handClass = cards[0][0] + cards[1][0] + handClass
    return handClass

def getCardSymbol(card):
    suitSymbols = {
        'h': '♥', 
        's': '♠', 
        'd': '♦', 
        'c': '♣'  
    }
    return card[0]+ suitSymbols[card[1]]
