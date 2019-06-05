#!/usr/bin/env python3

import kivy

from kivy.app import App
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout

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

class MyApp(App):
    def build(self):
        self.hearts_round = Round(RuleSet())
        hs = ' '.join(c.ascii_string() for c in self.hearts_round.hands[0])

        self.cards_layout = BoxLayout(orientation='horizontal', spacing=10)
        # label = Label(text=hs)
        for c in sorted_cards_for_display(self.hearts_round.hands[0]):
            img_path = f'images/cards/{c.ascii_string()}.png'
            img = ImageButton(source=img_path)
            img.bind(on_press=lambda b, c=c: self.handle_image_click(c))
            self.cards_layout.add_widget(img)

        # self.cards_layout.add_widget(label)
        return self.cards_layout

    def handle_image_click(self, card):
        print(f'Click: {card.symbol_string()}')
        return True

if __name__ == '__main__':
    MyApp().run()
