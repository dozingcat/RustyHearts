from dataclasses import dataclass, field
import itertools
from typing import List, Set

from cards import Card, Deck, Rank, Suit
import capi

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

    def is_in_progress(self):
        return self.current_trick is not None

    def is_finished(self):
        return self.current_trick is None and len(self.prev_tricks) > 0


class Match:
    def __init__(self, rules: RuleSet, num_players=4, point_limit=100):
        self.rules = rules
        self.num_players = num_players
        self.point_limit = point_limit
        self.score_history = []
        self.pass_direction_seq = itertools.cycle(
            [1, num_players - 1] + list(range(2, num_players - 1)) + [0])
        self.current_round = None

    def total_scores(self):
        if not self.score_history:
            return [0] * self.num_players
        # [[1,2,3,4], [2,3,4,5], [10, 20, 30, 40]] -> [13, 25, 37, 49]
        return list(map(sum, zip(*self.score_history)))

    def finish_round(self):
        assert self.current_round and self.current_round.is_finished()
        self.score_history.append(capi.points_taken(self.current_round))
        self.current_round = None

    def start_next_round(self):
        assert not self.current_round
        assert not self.winners()
        passinfo = PassInfo(direction=next(self.pass_direction_seq), num_cards=3)
        self.current_round = Round(self.rules, passinfo, self.total_scores())

    def winners(self):
        scores = self.total_scores()
        if max(scores) < self.point_limit:
            return []
        best = min(scores)
        return [i for i, s in enumerate(scores) if s == best]
