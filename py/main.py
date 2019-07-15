#!/usr/bin/env python3

from enum import Enum, unique
from typing import Iterable, List

import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout

import capi
from cards import Card, Rank, Suit
from round import PassInfo, Round, RuleSet

# Card images from https://github.com/hayeah/playing-cards-assets, MIT licensed.

# https://kivy.org/doc/stable/api-kivy.uix.behaviors.html
class ImageButton(ButtonBehavior, Image):
    pass


class Mode(Enum):
    NOT_STARTED = 0
    PASSING = 1
    PLAYING = 2


def sorted_cards_for_display(cards: Iterable[Card]):
    sc = []
    for suit in [Suit.SPADES, Suit.HEARTS, Suit.CLUBS, Suit.DIAMONDS]:
        cards_in_suit = [c for c in cards if c.suit == suit]
        cards_in_suit.sort(key=lambda c: c.rank.rank_val, reverse=True)
        sc.extend(cards_in_suit)
    return sc


def card_image_path(c: Card):
    return f'images/cards/{c.ascii_string()}.png'


def pass_info_sequence(num_players: int, num_cards: int):
    while True:
        yield PassInfo(direction=1, num_cards=num_cards)
        yield PassInfo(direction=num_players - 1, num_cards=num_cards)
        for d in range(2, num_players - 1):
            yield PassInfo(direction=d, num_cards=num_cards)
        yield PassInfo(direction=0, num_cards=0)


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


class MyApp(App):
    def build(self):
        self.top_box = BoxLayout(orientation='vertical')
        self.trick_layout = FloatLayout(size_hint=(1, 0.8))
        self.top_box.add_widget(self.trick_layout)
        self.cards_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.2))
        self.top_box.add_widget(self.cards_layout)
        self.mode = Mode.NOT_STARTED
        self.cards_to_pass = set()
        self.match = Match(RuleSet())
        Clock.schedule_once(lambda dt: self.start_game(), 0)
        return self.top_box

    def start_game(self):
        self.hearts_round = self.match.next_round()
        self.mode = Mode.PASSING if self.hearts_round.pass_info.direction > 0 else Mode.PLAYING
        self.cards_to_pass = set()
        self.update_player_card_display()
        if self.mode == Mode.PASSING:
            print(f'Pass direction={self.hearts_round.pass_info.direction}')
        elif self.mode == Mode.PLAYING:
            self.start_play()

    def start_play(self):
        self.hearts_round.start_play()
        lc = capi.legal_plays(self.hearts_round)
        print(f'Legal plays (hopefully 2c): {" ".join(c.symbol_string() for c in lc)}')
        self.handle_next_play()

    def play_card(self, card: Card):
        self.hearts_round.play_card(card)
        self.update_trick_cards_display()
        if self.hearts_round.is_finished():
            self.do_round_finished()
        else:
            if self.hearts_round.did_trick_just_finish():
                w = self.hearts_round.last_trick_winner()
                print(f'Player {w} takes the trick')
                print(f'Points: {capi.points_taken(self.hearts_round)}')
                Clock.schedule_once(lambda dt: self.handle_next_play(), 1.5)
            else:
                self.handle_next_play()

    def do_round_finished(self):
        print('Round over')
        round_scores = capi.points_taken(self.hearts_round)
        self.match.record_round_scores(round_scores)
        print(f'Round points: {round_scores}')
        print(f'Total points: {self.match.scores}')
        winners = self.match.winners()
        if winners:
            self.do_match_over(winners)
        else:
            Clock.schedule_once(lambda dt: self.start_game(), 3)

    def do_match_over(self, winners: List[int]):
        print(f'Winners: {winners}')
        self.match = Match(RuleSet())
        Clock.schedule_once(lambda dt: self.start_game(), 3)

    def handle_next_play(self):
        def doit():
            if self.hearts_round.is_finished():
                return
            pnum = self.hearts_round.current_player_index()
            if pnum == 0:
                legal_plays = capi.legal_plays(self.hearts_round)
                self.update_player_card_display(legal_plays)
            if pnum != 0:
                lc = capi.legal_plays(self.hearts_round)
                best = capi.best_play(self.hearts_round)
                print(f'Legal plays: {" ".join(c.symbol_string() for c in lc)}')
                print(f'Player {pnum} plays {best.symbol_string()}')
                self.play_card(best)

        Clock.schedule_once(lambda dt: doit(), 0.1)

    def set_or_unset_card_to_pass(self, card):
        if card in self.cards_to_pass:
            self.cards_to_pass.remove(card)
        else:
            self.cards_to_pass.add(card)
        if len(self.cards_to_pass) == self.hearts_round.pass_info.num_cards:
            self.pass_cards(self.cards_to_pass)
        else:
            highlight = set(self.hearts_round.players[0].hand) - self.cards_to_pass
            self.update_player_card_display(highlight)

    def pass_cards(self, cards):
        passed_cards = [list(self.cards_to_pass)]
        for pnum in range(1, self.hearts_round.rules.num_players):
            pcards = capi.cards_to_pass(self.hearts_round, pnum)
            print(f'Player {pnum} passes {" ".join(c.symbol_string() for c in pcards)}')
            passed_cards.append(pcards)
        self.hearts_round.pass_cards(passed_cards)
        self.update_player_card_display(self.hearts_round.players[0].received_cards)
        self.mode = Mode.PLAYING
        Clock.schedule_once(lambda dt: self.start_play(), 1.5)

    def update_player_card_display(self, highlight_cards=None):
        self.cards_layout.clear_widgets()
        for c in sorted_cards_for_display(self.hearts_round.players[0].hand):
            img_path = card_image_path(c)
            img = ImageButton(source=img_path)
            img.opacity = 1.0 if (highlight_cards is None or c in highlight_cards) else 0.3
            img.bind(on_press=lambda b, c=c: self.handle_image_click(c))
            self.cards_layout.add_widget(img)

    def update_trick_cards_display(self):
        self.trick_layout.clear_widgets()
        ct = self.hearts_round.current_trick
        if ct and len(ct.cards) == 0 and len(self.hearts_round.prev_tricks) > 0:
            ct = self.hearts_round.prev_tricks[-1]
        if ct:
            positions = [
                {'x': 0.4, 'y': 0.1},
                {'x': 0.1, 'y': 0.4},
                {'x': 0.4, 'y': 0.7},
                {'x': 0.7, 'y': 0.4},
            ]
            for i, card in enumerate(ct.cards):
                img_path = card_image_path(card)
                pnum = (ct.leader + i) % self.hearts_round.rules.num_players
                img = ImageButton(source=img_path, pos_hint=positions[pnum], size_hint=(0.2, 0.2))
                self.trick_layout.add_widget(img)

    def handle_image_click(self, card: Card):
        print(f'Click: {card.symbol_string()}')
        if self.mode == Mode.PASSING:
            self.set_or_unset_card_to_pass(card)
        elif self.mode == Mode.PLAYING:
            legal = capi.legal_plays(self.hearts_round)
            if self.hearts_round.current_player_index() == 0:
                if card in legal:
                    self.play_card(card)
                    self.update_player_card_display()
                    self.update_trick_cards_display()
                else:
                    print(f'Illegal play!')
        return True

if __name__ == '__main__':
    MyApp().run()
