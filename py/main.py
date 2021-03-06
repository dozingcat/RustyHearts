#!/usr/bin/env python3

import collections
from dataclasses import dataclass
from enum import Enum, unique
import random
import threading
import time
from typing import Dict, Iterable, List, OrderedDict
import webbrowser

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.settings import Settings

import capi
from cards import Card, Rank, Suit
from hearts import Match, Round, RuleSet
from storage import Storage
import ui

def debug(*args, **kwargs):
    # print(*args, **kwargs)
    pass

# Card images from https://code.google.com/archive/p/vector-playing-cards/, public domain.
CARD_WIDTH_OVER_HEIGHT = 500.0 / 726

def card_image_path(c: Card):
    return f'assets/cards/{c.ascii_string()}.png'

BLACK_CARD_IMAGE_PATH = 'assets/cards/black.png'
MENU_ICON_PATH = 'assets/menu.png'


# https://kivy.org/doc/stable/api-kivy.uix.behaviors.html
class ImageButton(ButtonBehavior, Image):
    pass


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float


@unique
class GameMode(Enum):
    NOT_STARTED = 0
    PASSING = 1
    PLAYING = 2
    ROUND_FINISHED = 3
    MATCH_FINISHED = 4


@unique
class UIMode(Enum):
    GAME = 1
    MENU = 2
    STATS = 3
    STATS_CLEARING = 4
    HELP = 5


@unique
class AutoplayMode(Enum):
    NONE = 0
    ALL_POINTS_TAKEN = 1
    ALL_HIGH_CARDS = 2


def sorted_cards_for_display(cards: Iterable[Card]):
    sc = []
    for suit in [Suit.SPADES, Suit.HEARTS, Suit.CLUBS, Suit.DIAMONDS]:
        cards_in_suit = [c for c in cards if c.suit == suit]
        cards_in_suit.sort(key=lambda c: c.rank.rank_val, reverse=True)
        sc.extend(cards_in_suit)
    return sc


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


def rules_from_preferences(config):
    return RuleSet(
        points_on_first_trick=config.getboolean('Rules', 'points_on_first_trick'),
        queen_breaks_hearts=config.getboolean('Rules', 'queen_breaks_hearts'),
        jd_minus_10=config.getboolean('Rules', 'jd_minus_10'),
    )


def localize(s):
    return s


def ATC(text, **kwargs):
    return ui.AutosizeTableCell(text=text, **kwargs)


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
        self.storage = Storage(self.user_data_dir)
        self.time_fn = time.time
        self.sleep_fn = time.sleep
        self.layout = FloatLayout()
        ui.set_rect_background(self.layout, [0, 0.3, 0, 1])
        Window.on_resize = lambda *args: Clock.schedule_once(lambda dt: self.do_resize())
        self.resize_render_event = None
        self.cards_to_pass = set()
        self.ui_mode = UIMode.GAME
        self.autoplay_mode = AutoplayMode.NONE
        self.round_stats = None
        self.match_stats = None
        self.help_text = None
        self.use_kivy_settings = False
        # Keep track of the last animated card so we don't repeat the animation
        # if the window is re-rendered.
        self.last_animated_card = None
        # And where the card the player clicked on should animate from.
        self.played_card_position = None
        self.animating_trick_winner = None
        self.match = self.storage.load_current_match()
        if self.match:
            Clock.schedule_once(lambda dt: self.render(), 0)
            # In case it's an AI opponent's turn.
            self.handle_next_play(1.0)
        else:
            Clock.schedule_once(lambda dt: self.start_match(), 0)
        return self.layout

    def do_resize(self):
        # When running on a phone, this method is called when the screen
        # orientation changes. Calling render() right away doesn't correctly
        # update the UI; it seems we have to wait a bit for the orientation to
        # be fully recongized. So we call render() immediately for desktop,
        # and again after a delay, and hopefully at least one of them will work.
        # Also cancel any previous pending render() so we don't make redundant
        # calls if the size is rapidly changing.
        if self.resize_render_event:
            self.resize_render_event.cancel()
        self.render()
        self.resize_render_event = Clock.schedule_once(lambda dt: self.render(), 1)

    def on_pause(self):
        debug('Pause!')
        self.storage.store_current_match(self.match)

    def on_stop(self):
        debug('Stop!')
        self.storage.store_current_match(self.match)

    def on_resume(self):
        debug('Resume!')

    def game_mode(self):
        if not self.match:
            return GameMode.NOT_STARTED
        if self.match.is_finished():
            return GameMode.MATCH_FINISHED
        rnd = self.match.current_round
        if not rnd:
            return GameMode.ROUND_FINISHED
        elif rnd.is_awaiting_pass():
            return GameMode.PASSING
        else:
            return GameMode.PLAYING

    def start_match(self):
        self.match = Match(rules_from_preferences(self.config))
        self.start_round()

    def start_round(self):
        self.match.start_next_round()
        rnd = self.match.current_round
        self.cards_to_pass = set()
        if rnd.is_awaiting_pass():
            debug(f'Pass direction={rnd.pass_info.direction}')
        else:
            self.start_play()
        self.render()

    def player(self):
        return self.match.current_round.players[0]

    def start_play(self):
        self.match.current_round.start_play()
        lc = capi.legal_plays(self.match.current_round)
        debug(f'Legal plays (hopefully 2c): {" ".join(c.symbol_string() for c in lc)}')
        self.handle_next_play(0)

    def start_trick_winner_animation(self, winner: int, expected_cards_played: int):
        rnd = self.match.current_round
        # Only animate if we're at the expected point in the round. It's
        # possible that the user could have made a play before the previous
        # animation finished, in which case we should skip this.
        if rnd is not None and rnd.num_cards_played() == expected_cards_played:
            self.animating_trick_winner = winner
            self.render()
            self.animating_trick_winner = None

    def card_play_animation_duration(self):
        return 0.25 if self.autoplay_mode == AutoplayMode.NONE else 0.1

    def delay_between_cards_in_trick(self):
        after_anim_delay = 0.25 if self.autoplay_mode == AutoplayMode.NONE else 0.05
        return self.card_play_animation_duration() + after_anim_delay

    def delay_before_trick_winner_animation(self):
        return 1.0 if self.autoplay_mode == AutoplayMode.NONE else 0.25

    def trick_winner_animation_duration(self):
        return 0.25 if self.autoplay_mode == AutoplayMode.NONE else 0.1

    def delay_between_tricks(self):
        return (0.05 +
            self.delay_before_trick_winner_animation() +
            self.trick_winner_animation_duration())

    def play_card(self, card: Card):
        # Record where this card was so we can animate from it. This is ugly.
        self.played_card_position = self._hand_card_positions().get(card)
        rnd = self.match.current_round
        rnd.play_card(card)
        nc = rnd.num_cards_played()
        if rnd.did_trick_just_finish():
            w = rnd.last_trick_winner()
            debug(f'Player {w} takes the trick')
            debug(f'Points: {capi.points_taken(rnd)}')
            if self.autoplay_mode == AutoplayMode.NONE and len(rnd.players[w].hand) > 1:
                if rnd.are_all_points_taken():
                    debug('All points taken')
                    self.autoplay_mode = AutoplayMode.ALL_POINTS_TAKEN
                elif rnd.will_leader_take_all_tricks():
                    debug(f'Player {w} takes the rest')
                    self.autoplay_mode = AutoplayMode.ALL_HIGH_CARDS
            Clock.schedule_once(lambda dt: self.start_trick_winner_animation(w, nc),
                self.delay_before_trick_winner_animation())
            self.handle_next_play(self.delay_between_tricks())
        else:
            self.handle_next_play(self.delay_between_cards_in_trick())
        self.render()

    def do_round_finished(self):
        assert self.match.current_round
        self.round_stats = None
        self.match_stats = None
        self.autoplay_mode = AutoplayMode.NONE
        self.storage.record_round_stats(self.match.current_round)
        debug(f'Round stats: {self.storage.load_round_stats()}')
        debug('Round over')
        self.match.finish_round()
        round_scores = self.match.score_history[-1]
        debug(f'Round points: {round_scores}')
        debug(f'Total points: {self.match.total_scores()}')
        if self.match.is_finished():
            debug(f'Winners: {self.match.winners()}')
            self.storage.record_match_stats(self.match)
            self.storage.remove_current_match()
            debug(f'Match stats: {self.storage.load_match_stats()}')
        self.render()

    # `min_delay` is the minimum number of seconds to wait before making the
    # next AI play. This is used to allow thinking while the animation for the
    # previous play is in progress, while guaranteeing that the animation can
    # finish before the next play executes.
    def handle_next_play(self, min_delay: float):
        rnd = self.match.current_round
        if rnd and rnd.is_finished():
            Clock.schedule_once(lambda dt: self.do_round_finished(), min_delay)
        if not rnd or not rnd.is_in_progress():
            return
        pnum = rnd.current_player_index()
        if pnum == 0 and rnd.num_cards_played() == 0:
            # Needed to highlight legal plays for the first trick.
            # Only do this on the first play; otherwise render() will
            # incorrectly redraw cards in the last trick that were already
            # animated to the trick winner.
            self.render()
        if pnum != 0 or self.autoplay_mode != AutoplayMode.NONE:
            # Compute the best card to play in a separate thread so the UI
            # stays responsive and animation timers work as expected.
            self._make_ai_play_in_thread(rnd, min_delay)

    def _make_ai_play_in_thread(self, rnd: Round, min_delay: float):
        @mainthread
        def play_card_in_main_thread(card):
            debug(f'Main thread: playing {card.symbol_string()}')
            if self.match is None or self.match.current_round != rnd:
                debug(f'Round changed!')
                return
            pnum = rnd.current_player_index()
            if card not in rnd.players[pnum].hand:
                debug(f'Player {pnum} does not have {card.symbol_string()}!')
                return
            self.play_card(card)

        def run_ai_thread():
            t = self.time_fn()
            pnum = rnd.current_player_index()
            if self.autoplay_mode == AutoplayMode.NONE:
                best = capi.best_play(rnd)
            else:
                lc = capi.legal_plays(rnd)
                best = lc[0]
            debug(f'Player {pnum} plays {best.symbol_string()}')
            elapsed = self.time_fn() - t
            debug(f'AI took {elapsed} seconds')
            if elapsed < min_delay:
                self.sleep_fn(min_delay - elapsed)
            play_card_in_main_thread(best)

        t = threading.Thread(target=run_ai_thread)
        t.daemon = True
        t.start()

    def set_or_unset_card_to_pass(self, card):
        if card in self.cards_to_pass:
            self.cards_to_pass.remove(card)
        else:
            self.cards_to_pass.add(card)
        if len(self.cards_to_pass) == self.match.current_round.pass_info.num_cards:
            self.pass_cards(self.cards_to_pass)
        else:
            self.render()

    def pass_cards(self, cards):
        passed_cards = [list(self.cards_to_pass)]
        for pnum in range(1, self.match.current_round.rules.num_players):
            pcards = capi.cards_to_pass(self.match.current_round, pnum)
            debug(f'Player {pnum} passes {" ".join(c.symbol_string() for c in pcards)}')
            passed_cards.append(pcards)
        self.match.current_round.pass_cards(passed_cards)
        Clock.schedule_once(lambda dt: self.start_play(), 1.5)
        self.render()

    def default_font_size(self):
        return min(self.layout.width, self.layout.height) * 0.07

    def render(self):
        debug(f'render: {self.layout.width} {self.layout.height}')
        self.layout.clear_widgets()
        self.render_hand()
        self.render_trick()
        self.render_message()
        self.render_score()
        self.render_stats()
        self.render_controls()
        self.render_help()

    def _hand_card_positions(self) -> OrderedDict[Card, Rect]:

        def add_card_positions(positions, cards: List[Card], y=0.05, x_offset=0):
            height_frac = 0.2
            height_px = height_frac * self.layout.height
            width_px = height_px * CARD_WIDTH_OVER_HEIGHT
            width_frac = width_px / self.layout.width
            max_hand_width = 0.9
            x_start = (1 - max_hand_width) / 2
            x_incr = (
                0 if len(cards) <= 1
                else (max_hand_width - width_px / self.layout.width) / (len(cards) - 1))
            if len(cards) <= 1:
                x_start = 0.5 - width_frac / 2
            elif 0 < x_incr < width_frac / 4:
                # Not enough of each card's horizontal portion is visible, shrink so it is.
                shrink_ratio = x_incr * 4 / width_frac
                height_frac *= shrink_ratio
                width_frac *= shrink_ratio
                width_px *= shrink_ratio
                x_incr = (max_hand_width - width_px / self.layout.width) / (len(cards) - 1)
            elif x_incr > width_frac:
                # Get rid of the space between cards.
                hand_width = len(cards) * width_frac
                x_incr = width_frac
                x_start = 0.5 - hand_width / 2
            for i, c in enumerate(cards):
                if c is None:
                    continue
                x = x_start + ((i + x_offset) * x_incr)
                positions[c] = Rect(x=x, y=y, width=width_frac, height=height_frac)

        positions = collections.OrderedDict()
        if not self.match.current_round:
            return positions
        hand = sorted_cards_for_display(self.match.current_round.players[0].hand)
        if self.layout.height > self.layout.width and len(hand) > 7:
            # For an odd number of cards, the top row should have the extra card.
            odd = (len(hand) % 2 == 1)
            split = len(hand) // 2 + (1 if odd else 0)
            top_cards = hand[:split]
            bottom_cards = hand[split:]
            if odd:
                bottom_cards.append(None)
            add_card_positions(positions, top_cards, y=0.125)
            add_card_positions(positions, bottom_cards, y=0.05, x_offset=0.5 if odd else 0)
        else:
            add_card_positions(positions, hand)
        return positions

    def _hand_card_opacities(self) -> Dict[Card, float]:
        if self.game_mode() == GameMode.PASSING:
            # Highlight cards selected to be passed, or received cards.
            if self.player().received_cards:
                dimmed = set(self.player().hand) - set(self.player().received_cards)
            else:
                dimmed = self.cards_to_pass
            return {c: 0.3 for c in dimmed}
        rnd = self.match.current_round
        if rnd and rnd.is_in_progress():
            if rnd.current_player_index() == 0:
                # Highlight legal plays.
                legal = capi.legal_plays(self.match.current_round)
                dimmed = set(self.player().hand) - set(legal)
                return {c: 0.3 for c in dimmed}
            else:
                # Slightly dim all cards since it's not our turn.
                return {c: 0.6 for c in self.player().hand}
        return {}

    def render_hand(self):
        if not self.match.current_round:
            return
        positions = self._hand_card_positions()
        opacities = self._hand_card_opacities()
        for card, rect in positions.items():
            pos = {'x': rect.x, 'y': rect.y}
            size = (rect.width, rect.height)
            img_path = card_image_path(card)
            opacity = opacities.get(card, 1.0)
            if opacity < 1.0:
                black = Image(source=BLACK_CARD_IMAGE_PATH, size_hint=size, pos_hint=pos)
                self.layout.add_widget(black)
            img = ImageButton(source=img_path, size_hint=size, pos_hint=pos)
            img.opacity = opacity
            img.bind(on_press=lambda b, c=card: self.handle_card_click(c))
            self.layout.add_widget(img)

    def render_trick(self):
        if not self.match.current_round:
            return
        ct = self.match.current_round.current_trick
        if (ct is None or len(ct.cards) == 0) and len(self.match.current_round.prev_tricks) > 0:
            ct = self.match.current_round.prev_tricks[-1]
        if ct:
            # (0, 0) puts the bottom left of the card at the bottom left of the display.
            # Have player's cards start from where they were last drawn in the hand.
            played_card_pos = self.played_card_position or Rect(x=0.4, y=0.05, width=0, height=0)
            start_positions = [
                [lambda: played_card_pos.x, lambda: played_card_pos.y],
                [lambda: -0.2, lambda: random.uniform(0.35, 0.75)],
                [lambda: random.uniform(0.2, 0.6), lambda: 1.0],
                [lambda: 1.0, lambda: random.uniform(0.35, 0.75)],
            ]
            end_positions = [[0.4, 0.35], [0.1, 0.55], [0.4, 0.75], [0.7, 0.55]]
            for i, card in enumerate(ct.cards):
                img_path = card_image_path(card)
                pnum = (ct.leader + i) % self.match.current_round.rules.num_players
                end_pos = (
                    end_positions[pnum][0] * self.layout.width,
                    end_positions[pnum][1] * self.layout.height)
                show_anim_from_hand = (
                    self.animating_trick_winner is None and
                    self.last_animated_card != card and
                    i == len(ct.cards) - 1)
                if show_anim_from_hand:
                    start_pos = (
                        start_positions[pnum][0]() * self.layout.width,
                        start_positions[pnum][1]() * self.layout.height)
                    img = ImageButton(source=img_path, pos=start_pos, size_hint=(0.2, 0.2))
                    self.layout.add_widget(img)
                    anim = Animation(x=end_pos[0], y=end_pos[1], t='out_cubic',
                        duration=self.card_play_animation_duration())
                    anim.start(img)
                    self.last_animated_card = card
                else:
                    img = ImageButton(source=img_path, pos=end_pos, size_hint=(0.2, 0.2))
                    self.layout.add_widget(img)
                    if self.animating_trick_winner is not None:
                        # Animate to trick winner's position.
                        tx, ty = [
                            (0.4, -0.2), (-0.2, 0.55), (0.4, 1.0), (1.0, 0.55)
                        ][self.animating_trick_winner]
                        anim = Animation(
                            x = tx * self.layout.width,
                            y = ty * self.layout.height,
                            t='out_cubic',
                            duration=self.trick_winner_animation_duration())
                        anim.start(img)


    def render_message(self):
        def get_message():
            if self.ui_mode != UIMode.GAME:
                return ''
            elif self.game_mode() == GameMode.PASSING:
                return passing_text(self.match.current_round)
            elif self.autoplay_mode == AutoplayMode.ALL_POINTS_TAKEN:
                return localize('All points taken')
            elif self.autoplay_mode == AutoplayMode.ALL_HIGH_CARDS:
                return localize('Remaining tricks claimed')

        msg = get_message()
        if msg:
            font_size = self.default_font_size()
            label_height_px = font_size * 1.8
            label_height_frac = label_height_px / self.layout.height
            pass_label = ui.make_label(
                text=msg,
                font_size=font_size,
                pos_hint={'x': 0.1, 'y': 0.5 - label_height_frac / 2},
                size_hint=(0.8, label_height_frac))
            ui.set_round_rect_background(pass_label, [0, 0, 0, 0.5], 20)
            self.layout.add_widget(pass_label)

    def render_score(self):
        if self.ui_mode != UIMode.GAME:
            return
        mode = self.game_mode()
        if mode in [GameMode.ROUND_FINISHED, GameMode.MATCH_FINISHED]:
            round_scores = self.match.score_history[-1]
            match_scores = self.match.total_scores()
            winners = self.match.winners()
            num_players = len(round_scores)

            cells = []
            if winners:
                if 0 in winners:
                    result_text = localize(
                        'You won!' if len(winners) == 1 else 'You tied for the win!')
                else:
                    result_text = localize('You lost :(')
                cells.append([ATC(result_text, relative_font_size=1.5)])
            cells.append(
                [ATC(' ')] +
                [ATC(localize(s)) for s in ('You', 'West', 'North', 'East')]
            )
            cells.append(
                [ATC(localize('Round'), halign='left')] +
                [ATC(str(s)) for s in round_scores]
            )
            cells.append(
                [ATC(localize('Match'), halign='left')] +
                [ATC(str(s)) for s in match_scores]
            )

            button_height_frac = 0.25 if winners else 0.33
            avail_width = 0.9 * self.layout.width
            avail_height = 0.9 * (1 - button_height_frac) * self.layout.height
            autotable = ui.create_autosize_table(cells, avail_width, avail_height)
            width_frac = autotable.width / self.layout.width
            height_frac = autotable.height / self.layout.height

            container_height_frac = height_frac * (1 / (1 - button_height_frac))
            pos = {'x': 0.5 - width_frac / 2, 'y': 0.5 - container_height_frac / 2}
            score_container = FloatLayout(
                pos_hint=pos, size_hint=(width_frac, container_height_frac))
            score_layout = autotable.layout
            score_layout.pos_hint={'x': 0, 'y': button_height_frac}
            score_layout.size_hint=(1, 1 - button_height_frac)
            score_container.add_widget(score_layout)

            def close_scores():
                mode = self.game_mode()
                if mode == GameMode.MATCH_FINISHED:
                    self.start_match()
                elif mode == GameMode.ROUND_FINISHED:
                    self.start_round()

            close_button = Button(
                text=localize('New match' if winners else 'Continue'),
                font_size=autotable.base_font_size,
                pos_hint={'x': 0.3, 'y': button_height_frac / 6},
                size_hint=(0.4, button_height_frac * 2 / 3))
            close_button.bind(on_release=lambda *args: close_scores())
            score_container.add_widget(close_button)
            ui.set_round_rect_background(score_container, [0, 0, 0, 0.5], 20)
            self.layout.add_widget(score_container)


    def handle_card_click(self, card: Card):
        if self.ui_mode != UIMode.GAME or self.autoplay_mode != AutoplayMode.NONE:
            return
        debug(f'Click: {card.symbol_string()}')
        mode = self.game_mode()
        if mode == GameMode.PASSING:
            self.set_or_unset_card_to_pass(card)
        elif mode == GameMode.PLAYING:
            if self.match.current_round.current_trick:
                legal = capi.legal_plays(self.match.current_round)
                if self.match.current_round.current_player_index() == 0:
                    if card in legal:
                        self.play_card(card)
                    else:
                        debug(f'Illegal play!')
        return True

    def render_controls(self):
        if self.ui_mode == UIMode.MENU:
            self.render_menu()
        else:
            self.render_menu_icon()

    def render_menu_icon(self):
        pos = {'x': 0.0, 'y': 0.9}
        size = [0.1, 0.1]
        ratio = self.layout.width / self.layout.height
        if ratio > 1:
            size[0] /= ratio
        else:
            size[1] *= ratio
            pos['y'] = 1 - size[1]
        img = ImageButton(source=MENU_ICON_PATH, pos_hint=pos, size_hint=size)

        img.bind(on_press=lambda b: self.show_menu())
        self.layout.add_widget(img)

    def render_menu(self):
        menu_container = BoxLayout(orientation='vertical', pos_hint={'x': 0.1, 'y': 0.1}, size_hint=(0.8, 0.8))
        ui.set_round_rect_background(menu_container, [0, 0, 0, 0.9], 20)
        font_size = min(self.layout.height / 15, self.layout.width / 12)

        def start_match():
            self.ui_mode = UIMode.GAME
            self.start_match()

        resume_button = Button(text=localize('Resume Match'), font_size=font_size)
        resume_button.bind(on_release=lambda *args: self.return_to_game())
        menu_container.add_widget(resume_button)

        new_match_button = Button(text=localize('New Match'), font_size=font_size)
        new_match_button.bind(on_release=lambda *args: start_match())
        menu_container.add_widget(new_match_button)

        def open_settings():
            self.return_to_game()
            self.open_settings()

        settings_button = Button(text=localize('Preferences'), font_size=font_size)
        settings_button.bind(on_release=lambda *args: open_settings())
        menu_container.add_widget(settings_button)
        self.layout.add_widget(menu_container)

        def show_stats():
            self.ui_mode = UIMode.STATS
            self.render()

        resume_button = Button(text=localize('Statistics'), font_size=font_size)
        resume_button.bind(on_release=lambda *args: show_stats())
        menu_container.add_widget(resume_button)

        def show_help():
            self.ui_mode = UIMode.HELP
            self.render()

        help_button = Button(text=localize('About / Help'), font_size=font_size)
        help_button.bind(on_release=lambda *args: show_help())
        menu_container.add_widget(help_button)


    def render_stats(self):
        if self.ui_mode != UIMode.STATS and self.ui_mode != UIMode.STATS_CLEARING:
            return
        if self.round_stats is None:
            self.round_stats = self.storage.load_round_stats()
        if self.match_stats is None:
            self.match_stats = self.storage.load_match_stats()
        round_jd = self.round_stats.stats_with_jd
        round_nojd = self.round_stats.stats_without_jd
        match_jd = self.match_stats.stats_with_jd
        match_nojd = self.match_stats.stats_without_jd

        def avg_str(fmt, n, d):
            return '--' if d == 0 else (fmt % (n / d))

        cells = []
        cells.append([
            ATC(' ', layout_weight=2),
            ATC(localize('Total')),
            ATC(localize('No JD')),
            ATC(localize('With JD')),
        ])
        cells.append([
            ATC(localize('Matches'), layout_weight=2, halign='left'),
            ATC(str(match_nojd.num_matches + match_jd.num_matches)),
            ATC(str(match_nojd.num_matches)),
            ATC(str(match_jd.num_matches)),
        ])
        cells.append([
            ATC(localize('Wins'), layout_weight=2, halign='left'),
            ATC(str(match_nojd.num_wins + match_jd.num_wins)),
            ATC(str(match_nojd.num_wins)),
            ATC(str(match_jd.num_wins)),
        ])
        cells.append([
            ATC(localize('Ties'), layout_weight=2, halign='left'),
            ATC(str(match_nojd.num_ties + match_jd.num_ties)),
            ATC(str(match_nojd.num_ties)),
            ATC(str(match_jd.num_ties)),
        ])
        cells.append([
            ATC(localize('Avg points/match'), layout_weight=2, halign='left'),
            ATC(avg_str('%.1f',
                match_nojd.total_points + match_jd.total_points,
                match_nojd.num_matches + match_jd.num_matches)),
            ATC(avg_str('%.1f', match_nojd.total_points, match_nojd.num_matches)),
            ATC(avg_str('%.1f', match_jd.total_points, match_jd.num_matches)),
        ])
        cells.append([ATC(' ', relative_font_size=0.5)])
        cells.append([
            ATC(localize('Rounds'), layout_weight=2, halign='left'),
            ATC(str(round_nojd.num_rounds + round_jd.num_rounds)),
            ATC(str(round_nojd.num_rounds)),
            ATC(str(round_jd.num_rounds)),
        ])
        cells.append([
            ATC(localize('Avg points/round'), layout_weight=2, halign='left'),
            ATC(avg_str('%.2f',
                round_nojd.total_points + round_jd.total_points,
                round_nojd.num_rounds + round_jd.num_rounds)),
            ATC(avg_str('%.2f', round_nojd.total_points, round_nojd.num_rounds)),
            ATC(avg_str('%.2f', round_jd.total_points, round_jd.num_rounds)),
        ])
        cells.append([
            ATC(localize('Moonshots'), layout_weight=2, halign='left'),
            ATC(str(round_nojd.num_moonshots + round_jd.num_moonshots)),
            ATC(str(round_nojd.num_moonshots)),
            ATC(str(round_jd.num_moonshots)),
        ])
        cells.append([
            ATC(localize('Opp. moonshots'), layout_weight=2, halign='left'),
            ATC(str(round_nojd.num_opponent_moonshots + round_jd.num_opponent_moonshots)),
            ATC(str(round_nojd.num_opponent_moonshots)),
            ATC(str(round_jd.num_opponent_moonshots)),
        ])
        cells.append([
            ATC(localize('Queens taken'), layout_weight=2, halign='left'),
            ATC(str(round_nojd.num_queen_spades + round_jd.num_queen_spades)),
            ATC(str(round_nojd.num_queen_spades)),
            ATC(str(round_jd.num_queen_spades)),
        ])
        cells.append([
            ATC(localize('Jacks taken'), layout_weight=2, halign='left'),
            ATC(str(round_jd.num_jack_diamonds)),
            ATC('--'),
            ATC(str(round_jd.num_jack_diamonds)),
        ])

        button_height_frac = 0.15
        avail_width = 0.9 * self.layout.width
        avail_height = 0.9 * (1 - button_height_frac) * self.layout.height
        autotable = ui.create_autosize_table(cells, avail_width, avail_height)
        width_frac = autotable.width / self.layout.width
        height_frac = autotable.height / self.layout.height

        container_height_frac = height_frac * (1 / (1 - button_height_frac))
        pos = {'x': 0.5 - width_frac / 2, 'y': 0.5 - container_height_frac / 2}
        stats_container = FloatLayout(pos_hint=pos, size_hint=(width_frac, container_height_frac))
        stats_layout = autotable.layout
        stats_layout.pos_hint={'x': 0, 'y': button_height_frac}
        stats_layout.size_hint=(1, 1 - button_height_frac)
        stats_container.add_widget(stats_layout)

        def close_stats():
            self.ui_mode = UIMode.GAME
            self.render()

        def ask_to_clear_stats():
            self.ui_mode = UIMode.STATS_CLEARING
            self.render()

        def cancel_clear_stats():
            self.ui_mode = UIMode.STATS
            self.render()

        def confirm_clear_stats():
            self.storage.clear_stats()
            self.round_stats = None
            self.match_stats = None
            self.ui_mode = UIMode.STATS
            self.render()

        button_y_pos = button_height_frac / 6
        button_height = button_height_frac * 2 / 3

        if self.ui_mode == UIMode.STATS:
            close_button = Button(
                text=localize('Continue'),
                font_size=autotable.base_font_size,
                pos_hint={'x': 0.05, 'y': button_y_pos},
                size_hint=(0.4, button_height))
            close_button.bind(on_release=lambda *args: close_stats())
            stats_container.add_widget(close_button)

            clear_button = Button(
                text=localize('Clear statistics'),
                font_size=autotable.base_font_size,
                pos_hint={'x': 0.55, 'y': button_y_pos},
                size_hint=(0.4, button_height))
            clear_button.bind(on_release=lambda *args: ask_to_clear_stats())
            stats_container.add_widget(clear_button)
        else:
            assert self.ui_mode == UIMode.STATS_CLEARING
            confirm_label = ui.make_label(
                text=localize('Really clear stats?'),
                font_size=autotable.base_font_size,
                pos_hint={'x': 0, 'y': button_y_pos},
                size_hint=(0.45, button_height),
                halign='right'
            )
            stats_container.add_widget(confirm_label)

            cancel_button = Button(
                text=localize('Cancel'),
                font_size=autotable.base_font_size,
                pos_hint={'x': 0.5, 'y': button_y_pos},
                size_hint=(0.2, button_height))
            cancel_button.bind(on_release=lambda *args: cancel_clear_stats())
            stats_container.add_widget(cancel_button)

            confirm_button = Button(
                text=localize('Clear'),
                font_size=autotable.base_font_size,
                pos_hint={'x': 0.75, 'y': button_y_pos},
                size_hint=(0.2, button_height))
            confirm_button.bind(on_release=lambda *args: confirm_clear_stats())
            stats_container.add_widget(confirm_button)

        ui.set_round_rect_background(stats_container, [0, 0, 0, 0.7], 20)
        self.layout.add_widget(stats_container)

    def show_menu(self):
        self.ui_mode = UIMode.MENU
        self.render()

    def return_to_game(self):
        self.ui_mode = UIMode.GAME
        self.render()

    def render_help(self):
        if self.ui_mode != UIMode.HELP:
            return
        about_height = 0.9 * self.layout.height
        about_width = min(0.9 * self.layout.width, 1.5 * about_height)
        about_width_frac = about_width / self.layout.width
        about_height_frac = about_height / self.layout.height
        about_container = FloatLayout(
            pos_hint={'x': 0.5 - about_width_frac / 2, 'y': 0.5 - about_height_frac / 2},
            size_hint=(about_width_frac, about_height_frac))
        ui.set_round_rect_background(about_container, [0, 0, 0, 0.9], 20)
        self.layout.add_widget(about_container)

        if self.help_text is None:
            with open('assets/about.txt') as f:
                self.help_text = f.read()

        def handle_ref_click(instance, ref):
            debug(f'Clicked on ref: {ref}')
            if ref == 'source':
                webbrowser.open('https://github.com/dozingcat/RustyHearts')
            elif ref == 'wikipedia':
                webbrowser.open('https://en.wikipedia.org/wiki/Hearts_(card_game)')
            elif ref == 'gpl3':
                webbrowser.open('https://www.gnu.org/licenses/gpl-3.0.en.html')
            elif ref == 'thirdparty':
                webbrowser.open('https://www.dozingcatsoftware.com/Hearts/thirdparty.html')

        scrollview_height_frac = 0.85
        sv = ScrollView(
            size_hint=(1, None),
            size=(about_width, scrollview_height_frac * about_height),
            pos_hint={'x': 0.0, 'y': 1 - scrollview_height_frac})
        about_container.add_widget(sv)
        font_size = max(about_width, about_height) / 40
        label = Label(
            text=self.help_text,
            markup=True,
            font_size=font_size,
            size_hint=(None, None),
            text_size=(about_width, None),
            padding=(20, 20))
        def update_label(*args):
            label.size = label.texture_size
        label.bind(pos=update_label)
        sv.add_widget(label)
        label.bind(on_ref_press=handle_ref_click)

        button_height_frac = (1 - scrollview_height_frac) * 2 / 3
        button_y = (1 - scrollview_height_frac) / 6
        button_font_size = font_size * 1.5
        button = Button(
            text=localize('Continue'),
            font_size=button_font_size,
            size_hint=(0.4, button_height_frac),
            pos_hint={'x': 0.3, 'y': button_y})
        button.bind(on_release=lambda *args: self.return_to_game())
        about_container.add_widget(button)

if __name__ == '__main__':
    HeartsApp().run()
