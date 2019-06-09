#!/usr/bin/env python3

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
from round import Round, RuleSet

# Card images from https://github.com/hayeah/playing-cards-assets, MIT licensed.

# https://kivy.org/doc/stable/api-kivy.uix.behaviors.html
class ImageButton(ButtonBehavior, Image):
    pass

def sorted_cards_for_display(cards):
    sc = []
    for suit in [Suit.SPADES, Suit.HEARTS, Suit.CLUBS, Suit.DIAMONDS]:
        cards_in_suit = [c for c in cards if c.suit == suit]
        cards_in_suit.sort(key=lambda c: c.rank.rank_val, reverse=True)
        sc.extend(cards_in_suit)
    return sc


def card_image_path(c: Card):
    return f'images/cards/{c.ascii_string()}.png'


class MyApp(App):
    def build(self):
        self.top_box = BoxLayout(orientation='vertical')
        self.trick_layout = FloatLayout(size_hint=(1, 0.8))
        self.top_box.add_widget(self.trick_layout)
        self.cards_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint=(1, 0.2))
        self.top_box.add_widget(self.cards_layout)
        Clock.schedule_once(lambda dt: self.start_game(), 0)
        return self.top_box

    def start_game(self):
        self.hearts_round = Round(RuleSet())
        self.hearts_round.start_play()
        self.update_player_card_display()
        lc = capi.legal_plays(self.hearts_round)
        print(f'Legal plays (hopefully 2c): {" ".join(c.symbol_string() for c in lc)}')
        self.schedule_opponent_play()

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
                Clock.schedule_once(lambda dt: self.schedule_opponent_play(), 2)
            else:
                self.schedule_opponent_play()

    def do_round_finished(self):
        print('Round over')
        print(f'Final points: {capi.points_taken(self.hearts_round)}')
        Clock.schedule_once(lambda dt: self.start_game(), 3)

    def schedule_opponent_play(self):
        def doit():
            if self.hearts_round.is_finished():
                return
            pnum = self.hearts_round.current_player()
            if pnum != 0:
                lc = capi.legal_plays(self.hearts_round)
                best = capi.best_play(self.hearts_round)
                print(f'Legal plays: {" ".join(c.symbol_string() for c in lc)}')
                print(f'Player {pnum} plays {best.symbol_string()}')
                self.play_card(best)

        Clock.schedule_once(lambda dt: doit(), 0.1)

    def update_player_card_display(self):
        self.cards_layout.clear_widgets()
        for c in sorted_cards_for_display(self.hearts_round.hands[0]):
            img_path = card_image_path(c)
            img = ImageButton(source=img_path)
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
        legal = capi.legal_plays(self.hearts_round)
        if self.hearts_round.current_player() == 0:
            if card in legal:
                self.play_card(card)
                self.update_player_card_display()
                self.update_trick_cards_display()
            else:
                print(f'Illegal play!')
        return True

if __name__ == '__main__':
    MyApp().run()
