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
    shooting_disabled: bool = False


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


@dataclass
class Player:
    hand: List[Card]
    passed_cards: List[Card] = field(default_factory=list)
    received_cards: List[Card] = field(default_factory=list)


@dataclass(frozen=True)
class PassInfo:
    direction: int
    num_cards: int


def pass_info_sequence(num_players: int, num_cards: int):
    while True:
        yield PassInfo(direction=1, num_cards=num_cards)
        yield PassInfo(direction=num_players - 1, num_cards=num_cards)
        for d in range(2, num_players - 1):
            yield PassInfo(direction=d, num_cards=num_cards)
        yield PassInfo(direction=0, num_cards=0)


class Round:
    def __init__(self, rules, pass_info, scores, deck=None):
        self.rules = rules
        self.pass_info = pass_info
        self.scores_before_round = scores[:]
        # Could remove any cards specified in rules.removed_cards
        if deck is None:
            deck = Deck()
            deck.shuffle()
        hands = deck.deal(rules.num_players)
        self.players = [Player(hand=h) for h in hands]
        self.prev_tricks = []
        self.current_trick = None

    def pass_cards(self, passes: List[List[Card]]):
        assert self.pass_info.direction > 0
        nump = self.rules.num_players
        assert len(passes) == nump
        assert all(len(p) == self.pass_info.num_cards for p in passes)
        for pnum, cards in enumerate(passes):
            p = self.players[pnum]
            assert all(c in p.hand for c in cards)
            p.passed_cards = cards[:]
            dest = (pnum + self.pass_info.direction) % nump
            self.players[dest].received_cards = cards[:]
        for p in self.players:
            remaining = [c for c in p.hand if c not in p.passed_cards]
            p.hand = remaining + p.received_cards

    def start_play(self):
        c2 = Card(rank=Rank.TWO, suit=Suit.CLUBS)
        leader = [i for i in range(self.rules.num_players) if c2 in self.players[i].hand]
        if len(leader) != 1:
            raise ValueError('2C not found')
        self.current_trick = Trick(leader=leader[0])

    def current_player_index(self):
        ct = self.current_trick
        return (ct.leader + len(ct.cards)) % self.rules.num_players

    def current_player(self):
        return self.players[self.current_player_index()]

    def play_card(self, card: Card):
        cp = self.current_player_index()
        nump = self.rules.num_players
        if card not in self.players[cp].hand:
            raise ValueError(f'Card: {card.ascii_string()} not in hand for player: {cp}')
        self.players[cp].hand.remove(card)
        ct = self.current_trick
        ct.cards.append(card)
        if len(ct.cards) == nump:
            winner = (ct.leader + trick_winner_index(ct.cards)) % nump
            self.prev_tricks.append(Trick(leader=ct.leader, cards=ct.cards, winner=winner))
            num_cards_left = [len(p.hand) for p in self.players]
            assert len(set(num_cards_left)) == 1
            self.current_trick = Trick(leader=winner) if num_cards_left[0] > 0 else None

    def last_trick_winner(self):
        return self.prev_tricks[-1].winner if self.prev_tricks else None

    def did_trick_just_finish(self):
        return (self.current_trick is not None and len(self.current_trick.cards) == 0 and
                len(self.prev_tricks) > 0)

    def is_finished(self):
        return self.current_trick is None and len(self.prev_tricks) > 0


class Match:
    def __init__(self, rules: RuleSet, num_players=4, point_limit=100):
        self.rules = rules
        self.num_players = num_players
        self.point_limit = point_limit
        self.scores = [0] * num_players
        self.score_history = []
        self.pass_info_seq = pass_info_sequence(num_players, 3)

    def next_round(self):
        return Round(self.rules, next(self.pass_info_seq), self.scores)

    def record_round_scores(self, round_scores: List[int]):
        self.score_history.append(round_scores[:])
        self.scores = [s1 + s2 for s1, s2 in zip(self.scores, round_scores)]

    def winners(self):
        if max(self.scores) < self.point_limit:
            return []
        best = min(self.scores)
        return [i for i, s in enumerate(self.scores) if s == best]
