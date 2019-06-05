from dataclasses import dataclass, field
from typing import List, Set

from cards import Card, Deck, Rank, Suit

@dataclass(frozen=True)
class RuleSet:
    num_players: int = 4
    removed_cards: Set[Card] = frozenset()
    point_limit: int = 100
    points_on_first_trick: bool = False
    queen_breaks_hearts: bool = False
    jd_minus_10: bool = False


def trick_winner_index(cards: List[Card]):
    hi = 0
    for i in range(1, len(cards)):
        c = cards[i]
        if c.suit == cards[hi].suit and c.rank.rank_val > cards[hi].rank.rank_val:
            hi = i
    return hi


@dataclass
class Trick:
    leader: int
    cards: List[Card] = field(default_factory=list)
    winner: int = None


class Round:
    def __init__(self, rules, deck=None):
        self.rules = rules
        # Could remove any cards specified in rules.removed_cards
        if deck is None:
            deck = Deck()
            deck.shuffle()
        self.hands = deck.deal(rules.num_players)
        self.prev_tricks = []
        self.current_trick = None

    # TODO: Passing cards.

    def start_play(self):
        c2 = Card(rank=Rank.TWO, suit=Suit.CLUBS)
        leader = [i for i in range(self.rules.num_players) if c2 in self.hands[i]]
        if len(leader) != 1:
            raise ValueError('2C not found')
        self.current_trick = Trick(leader=leader[0])

    def current_player(self):
        ct = self.current_trick
        return (ct.leader + len(ct.cards)) % self.rules.num_players

    def play_card(self, card: Card):
        cp = self.current_player()
        nump = self.rules.num_players
        if card not in self.hands[cp]:
            raise ValueError(f'Card: {card.ascii_string()} not in hand for player: {cp}')
        self.hands[cp].remove(card)
        ct = self.current_trick
        ct.cards.append(card)
        if len(ct.cards) == nump:
            winner = (ct.leader + trick_winner_index(ct.cards)) % nump
            self.prev_tricks.append(Trick(leader=ct.leader, cards=ct.cards, winner=winner))
            num_cards_left = [len(h) for h in self.hands]
            assert len(set(num_cards_left)) == 1
            self.current_trick = Trick(leader=winner) if num_cards_left[0] > 0 else None

    def is_finished(self):
        return self.current_trick is None and len(self.prev_tricks) > 0