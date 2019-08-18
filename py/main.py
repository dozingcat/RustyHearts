#!/usr/bin/env python3

from enum import Enum, unique
from typing import Iterable, List

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.settings import Settings

import capi
from cards import Card, Rank, Suit
from hearts import Match, Round, RuleSet

# Card images from https://github.com/hayeah/playing-cards-assets, MIT licensed.
CARD_WIDTH_OVER_HEIGHT = 500.0 / 726

# https://kivy.org/doc/stable/api-kivy.uix.behaviors.html
class ImageButton(ButtonBehavior, Image):
    pass


@unique
class Mode(Enum):
    NOT_STARTED = 0
    PASSING = 1
    PLAYING = 2
    ROUND_FINISHED = 3
    MATCH_FINISHED = 4


def sorted_cards_for_display(cards: Iterable[Card]):
    sc = []
    for suit in [Suit.SPADES, Suit.HEARTS, Suit.CLUBS, Suit.DIAMONDS]:
        cards_in_suit = [c for c in cards if c.suit == suit]
        cards_in_suit.sort(key=lambda c: c.rank.rank_val, reverse=True)
        sc.extend(cards_in_suit)
    return sc


def card_image_path(c: Card):
    return f'images/cards/{c.ascii_string()}.png'


def black_card_image_path():
    return 'images/cards/black.png'


def passing_text(round: Round):
    pi = round.pass_info
    if pi.direction == 0 or pi.num_cards == 0:
        return ''
    cstr = 'card' if pi.num_cards == 1 else 'cards'
    if pi.direction == 1:
        return f'Pass {pi.num_cards} {cstr} left'
    if pi.direction == round.rules.num_players - 1:
        return f'Pass {pi.num_cards} {cstr} right'
    if pi.direction == 2 and round.rules.num_players == 4:
        return f'Pass {pi.num_cards} {cstr} across'
    return f'Pass {pi.num_cards} {cstr} {pi.direction} to the left'


def set_rect_background(widget, color: Iterable[float]):
    with widget.canvas.before:
        Color(*color)
        widget._commands_ = {
            'background': Rectangle(size=widget.size)
        }
    def update(inst, value):
        widget._commands_['background'].pos = inst.pos
        widget._commands_['background'].size = inst.size
    widget.bind(pos=update, size=update)

def make_label(**kwargs):
    '''Creates a label and binds its `text_size` to its `size`, allowing
    alignment to work as expected. Defaults to center alignment.
    See http://inclem.net/2014/07/05/kivy/kivy_label_text/
    '''
    kwargs.setdefault('halign', 'center')
    kwargs.setdefault('valign', 'middle')
    label = Label(**kwargs)
    def update(inst, value):
        label.text_size = label.size
    label.bind(size=update)
    return label

def set_round_rect_background(widget, color: Iterable[float], radius: float):
    diam = 2 * radius
    with widget.canvas.before:
        Color(*color)
        circle_size = (diam, diam)
        widget._commands_ = {
            'left_strip': Rectangle(),
            'right_strip': Rectangle(),
            'main_rect': Rectangle(),
            # 0 degrees is up, 90 is right.
            'bottom_left_corner': Ellipse(size=circle_size, angle_start=180, angle_end=270),
            'bottom_right_corner': Ellipse(size=circle_size, angle_start=90, angle_end=180),
            'top_left_corner': Ellipse(size=circle_size, angle_start=270, angle_end=360),
            'top_right_corner': Ellipse(size=circle_size, angle_start=0, angle_end=90),
        }
    def update(inst, value):
        px, py = inst.pos
        sx, sy = inst.size
        c = widget._commands_
        c['left_strip'].pos = (px, py + radius)
        c['left_strip'].size = (radius, sy - diam)
        c['right_strip'].pos = (px + sx - radius, py + radius)
        c['right_strip'].size = (radius, sy - diam)
        c['main_rect'].pos = (px + radius, py)
        c['main_rect'].size = (sx - diam, sy)
        c['bottom_left_corner'].pos = (px, py)
        c['bottom_right_corner'].pos = (px + sx - diam, py)
        c['top_left_corner'].pos = (px, py + sy - diam)
        c['top_right_corner'].pos = (px + sx - diam, py + sy - diam)
    widget.bind(pos=update, size=update)


def rules_from_preferences(config):
    return RuleSet(
        points_on_first_trick=config.getboolean('Rules', 'points_on_first_trick'),
        queen_breaks_hearts=config.getboolean('Rules', 'queen_breaks_hearts'),
        jd_minus_10=config.getboolean('Rules', 'jd_minus_10'),
    )


class HeartsApp(App):
    def build_config(self, config):
        config.setdefaults('Rules', {
            'jd_minus_10': False,
            'points_on_first_trick': False,
            'queen_breaks_hearts': False,
        })

    def build_settings(self, settings):
        settings.add_json_panel('Rules', self.config, 'settings.json')

    def build(self):
        self.layout = FloatLayout()
        set_rect_background(self.layout, [0, 0.3, 0, 1])
        self.mode = Mode.NOT_STARTED
        self.cards_to_pass = set()
        self.dimmed_cards = []
        self.match = Match(rules_from_preferences(self.config))
        self.finished_match = None
        Clock.schedule_once(lambda dt: self.start_game(), 0)
        Window.on_resize = lambda *args: self.render()
        self.layout.bind(on_touch_down=lambda *args: self.handle_background_click())
        return self.layout

    def handle_background_click(self):
        # This gets *all* clicks/touches, so we have to decide if we really want it.
        if self.mode == Mode.ROUND_FINISHED or self.mode == Mode.MATCH_FINISHED:
            self.finished_match = None
            self.start_game()


    def start_game(self):
        self.hearts_round = self.match.next_round()
        self.mode = Mode.PASSING if self.hearts_round.pass_info.direction > 0 else Mode.PLAYING
        self.cards_to_pass = set()
        self.render()
        if self.mode == Mode.PASSING:
            print(f'Pass direction={self.hearts_round.pass_info.direction}')
        elif self.mode == Mode.PLAYING:
            self.start_play()

    def player(self):
        return self.hearts_round.players[0]

    def start_play(self):
        self.hearts_round.start_play()
        lc = capi.legal_plays(self.hearts_round)
        print(f'Legal plays (hopefully 2c): {" ".join(c.symbol_string() for c in lc)}')
        self.handle_next_play()

    def play_card(self, card: Card):
        self.hearts_round.play_card(card)
        self.render()
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
            self.mode = Mode.ROUND_FINISHED
            self.render()

    def do_match_over(self, winners: List[int]):
        print(f'Winners: {winners}')
        self.mode = Mode.MATCH_FINISHED
        self.finished_match = self.match
        self.match = Match(rules_from_preferences(self.config))
        self.render()

    def handle_next_play(self):
        def doit():
            if self.hearts_round.is_finished():
                return
            pnum = self.hearts_round.current_player_index()
            if pnum == 0:
                legal_plays = capi.legal_plays(self.hearts_round)
                self.dimmed_cards = set(self.player().hand) - set(legal_plays)
                self.render()
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
            self.dimmed_cards = self.cards_to_pass
            self.render()

    def pass_cards(self, cards):
        passed_cards = [list(self.cards_to_pass)]
        for pnum in range(1, self.hearts_round.rules.num_players):
            pcards = capi.cards_to_pass(self.hearts_round, pnum)
            print(f'Player {pnum} passes {" ".join(c.symbol_string() for c in pcards)}')
            passed_cards.append(pcards)
        self.hearts_round.pass_cards(passed_cards)
        self.dimmed_cards = set(self.player().hand) - set(self.player().received_cards)
        self.render()
        self.mode = Mode.PLAYING
        Clock.schedule_once(lambda dt: self.start_play(), 1.5)

    def default_font_size(self):
        return min(self.layout.width, self.layout.height) * 0.07

    def render(self):
        print(f'render: {self.layout.width} {self.layout.height}')
        self.layout.clear_widgets()
        self.render_hand()
        self.render_trick()
        self.render_message()
        self.render_score()

    def render_hand(self):
        hand = sorted_cards_for_display(self.hearts_round.players[0].hand)
        if self.layout.height > self.layout.width and len(hand) > 7:
            # For an odd number of cards, the top row should have the extra card.
            odd = (len(hand) % 2 == 1)
            split = len(hand) // 2 + (1 if odd else 0)
            top_cards = hand[:split]
            bottom_cards = hand[split:]
            if odd:
                bottom_cards.append(None)
            self.render_cards(top_cards, y=0.125)
            self.render_cards(bottom_cards, y=0.05, x_offset=0.5 if odd else 0)
        else:
            self.render_cards(hand)

    def render_cards(self, cards: List[Card], y=0.05, x_offset=0):
        height_frac = 0.2
        height_px = height_frac * self.layout.height
        width_px = height_px * CARD_WIDTH_OVER_HEIGHT
        width_frac = width_px / self.layout.width
        x_start = 0.05
        x_end = 0.95
        x_incr = (
            0 if len(cards) <= 1
            else (x_end - x_start - width_px / self.layout.width) / (len(cards) - 1))
        if len(cards) == 1:
            x_start = 0.5 - width_frac / 2
        elif 0 < x_incr < width_frac / 4:
            # Not enough of each card's horizontal portion is visible, shrink so it is.
            shrink_ratio = x_incr * 4 / width_frac
            height_frac *= shrink_ratio
            width_frac *= shrink_ratio
            width_px *= shrink_ratio
            x_incr = (x_end - x_start - width_px / self.layout.width) / (len(cards) - 1)
        elif x_incr > width_frac:
            # Get rid of the space between cards.
            hand_width = len(cards) * width_frac
            x_incr = width_frac
            x_start = 0.5 - hand_width / 2
            x_end = x_start + hand_width
        size = (width_frac, height_frac)
        for i, c in enumerate(cards):
            if c is None:
                continue
            x = x_start + ((i + x_offset) * x_incr)
            pos = {'x': x, 'y': y}
            img_path = card_image_path(c)
            opacity = 0.3 if c in self.dimmed_cards else 1.0
            if opacity < 1.0:
                black = Image(source=black_card_image_path(), size_hint=size, pos_hint=pos)
                self.layout.add_widget(black)
            img = ImageButton(source=img_path, size_hint=size, pos_hint=pos)
            img.opacity = opacity
            img.bind(on_press=lambda b, c=c: self.handle_image_click(c))
            self.layout.add_widget(img)

    def render_trick(self):
        ct = self.hearts_round.current_trick
        if ct and len(ct.cards) == 0 and len(self.hearts_round.prev_tricks) > 0:
            ct = self.hearts_round.prev_tricks[-1]
        if ct:
            # (0, 0) puts the bottom left of the card at the bottom left of the display.
            positions = [
                {'x': 0.4, 'y': 0.35},
                {'x': 0.1, 'y': 0.55},
                {'x': 0.4, 'y': 0.75},
                {'x': 0.7, 'y': 0.55},
            ]
            for i, card in enumerate(ct.cards):
                img_path = card_image_path(card)
                pnum = (ct.leader + i) % self.hearts_round.rules.num_players
                img = ImageButton(source=img_path, pos_hint=positions[pnum], size_hint=(0.2, 0.2))
                self.layout.add_widget(img)

    def render_message(self):
        if self.mode == Mode.PASSING:
            font_size = self.default_font_size()
            label_height_px = font_size * 1.8
            label_height_frac = label_height_px / self.layout.height
            pass_label = make_label(
                text=passing_text(self.hearts_round),
                font_size=font_size,
                pos_hint={'x': 0.1, 'y': 0.5 - label_height_frac / 2},
                size_hint=(0.8, label_height_frac))
            set_round_rect_background(pass_label, [0, 0, 0, 0.5], 20)
            self.layout.add_widget(pass_label)

    def render_score(self):
        if self.mode == Mode.ROUND_FINISHED or self.mode == Mode.MATCH_FINISHED:
            font_size = self.default_font_size()
            label_height_px = font_size * 1.8
            label_height_frac = label_height_px / self.layout.height

            def make_score_row(text, scores):
                row_layout = BoxLayout(orientation='horizontal')
                # Spacers on left and right so text doesn't go to the edge.
                def make_spacer():
                    return Label(text='', size_hint=(0.2, None))
                row_layout.add_widget(make_spacer())
                label = make_label(
                    text=text,
                    font_size=font_size,
                    size_hint=(len(scores), 1),
                    halign='right')
                row_layout.add_widget(label)
                for s in scores:
                    point_label = make_label(text=str(s), font_size=font_size, halign='right')
                    row_layout.add_widget(point_label)
                row_layout.add_widget(make_spacer())
                return row_layout

            winners = self.finished_match.winners() if self.finished_match else []
            num_labels = 3 if winners else 2
            score_layout = BoxLayout(
                orientation='vertical',
                pos_hint={'x': 0.05, 'y': 0.5 - (num_labels * label_height_frac) / 2},
                size_hint=(0.9, num_labels * label_height_frac))
            set_round_rect_background(score_layout, [0, 0, 0, 0.5], 20)
            self.layout.add_widget(score_layout)
            if winners:
                if 0 in winners:
                    score_text = 'You win!' if len(winners) == 1 else 'You tied for the win!'
                else:
                    score_text = 'You lost :('
                result_label = make_label(text=score_text, font_size=font_size)
                score_layout.add_widget(result_label)
            round_scores = capi.points_taken(self.hearts_round)
            match_scores = (self.finished_match or self.match).scores
            score_layout.add_widget(make_score_row('Round score:', round_scores))
            score_layout.add_widget(make_score_row('Total score:', match_scores))

    def handle_image_click(self, card: Card):
        print(f'Click: {card.symbol_string()}')
        if self.mode == Mode.PASSING:
            self.set_or_unset_card_to_pass(card)
        elif self.mode == Mode.PLAYING:
            if self.hearts_round.current_trick:
                legal = capi.legal_plays(self.hearts_round)
                if self.hearts_round.current_player_index() == 0:
                    if card in legal:
                        self.play_card(card)
                        self.highlighted_cards = []
                        self.render()
                    else:
                        print(f'Illegal play!')
        return True


if __name__ == '__main__':
    HeartsApp().run()
