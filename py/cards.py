from dataclasses import dataclass
from enum import Enum, IntEnum, unique
import math
import random
from typing import Union

@unique
class Suit(Enum):
    CLUBS = ('C', '♣')
    DIAMONDS = ('D', '♦')
    HEARTS = ('H', '♥')
    SPADES = ('S', '♠')

    def __init__(self, letter, symbol):
        self.letter = letter
        self.symbol = symbol

    @classmethod
    def parse(cls, ch: str):
        for s in cls:
            if s.letter == ch or s.symbol == ch:
                return s
        raise ValueError(f'Bad suit: {ch}')


@unique
class Rank(Enum):
    TWO = (2, '2')
    THREE = (3, '3')
    FOUR = (4, '4')
    FIVE = (5, '5')
    SIX = (6, '6')
    SEVEN = (7, '7')
    EIGHT = (8, '8')
    NINE = (9, '9')
    TEN = (10, 'T')
    JACK = (11, 'J')
    QUEEN = (12, 'Q')
    KING  = (13, 'K')
    ACE = (14, 'A')

    def __init__(self, rank_val, char):
        self.rank_val = rank_val
        self.char = char

    @classmethod
    def parse(cls, val: Union[int, str]):
        for r in cls:
            if r.rank_val == val or r.char == val:
                return r
        raise ValueError(f'Bad rank: {val}')

@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

    def ascii_string(self):
        return self.rank.char + self.suit.letter

    def symbol_string(self):
        return self.rank.char + self.suit.symbol

    @classmethod
    def parse(cls, s: str):
        if len(s) != 2:
            raise ValueError(f'Bad card: {s}')
        return cls(rank=Rank.parse(s[0]), suit=Suit.parse(s[1]))


all_cards = {Card(rank=r, suit=s) for r in Rank for s in Suit}

class Deck:
    def __init__(self):
        self.cards = list(all_cards)

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self, num_players: int, cards_per_player: int=None):
        max_per_player = int(math.floor(len(self.cards) / num_players))
        if cards_per_player is None:
            cards_per_player = max_per_player
        hands = []
        for i in range(num_players):
            lo = cards_per_player * i
            hands.append(self.cards[lo:lo + cards_per_player])
        return hands
