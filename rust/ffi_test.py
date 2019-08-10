#!/usr/bin/env python3

from ctypes import cdll, c_char, c_int32
import json
import unittest

def load_shared_lib():
    paths = [
        'target/release/libhearts.so',
        'target/release/libhearts.dylib',
    ]
    for path in paths:
        try:
            return cdll.LoadLibrary(path)
        except OSError:
            pass
    raise RuntimeError('Unable to load hearts shared library')


def choose_cards_to_pass(lib, req):
    cards = req['hand'].split()
    req_bytes = json.dumps(req).encode('utf-8')

    buf_len = 13
    char_array_type = c_char * buf_len
    pass_buffer = char_array_type.from_buffer(bytearray(buf_len))
    lib.cards_to_pass_from_json(req_bytes, len(req_bytes), pass_buffer, buf_len)
    # `pass_buffer` now has byte values of 1 corresponding to legal cards to play.
    passed_cards = [card for (card, passed) in zip(cards, pass_buffer) if ord(passed)]
    return passed_cards


def choose_card_to_play(lib, req):
    cards = req['hand'].split()
    req_bytes = json.dumps(req).encode('utf-8')

    buf_len = 13
    char_array_type = c_char * buf_len
    legal_play_buffer = char_array_type.from_buffer(bytearray(buf_len))
    lib.legal_plays_from_json(req_bytes, len(req_bytes), legal_play_buffer, buf_len)
    # `legal_play_buffer` now has byte values of 1 corresponding to legal cards to play.
    legal_cards = [card for (card, legal) in zip(cards, legal_play_buffer) if ord(legal)]

    best_card_index = lib.card_to_play_from_json(req_bytes, len(req_bytes))
    if best_card_index < 0:
        raise RuntimeError('Failed to choose card')
    return cards[best_card_index]


class HeartsApiTest(unittest.TestCase):
    def setUp(self):
        self.lib = load_shared_lib()

    def test_pass_left(self):
        cards = choose_cards_to_pass(self.lib, {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "AS QS JS AH 8H 2H 6D 5D 4D 3D 6C 5C 4C",
            "direction": 1,
            "num_cards": 3,
        })
        self.assertEqual(set(cards), {"AS", "QS", "AH"})

    def test_pass_right(self):
        # Don't need to pass AS right when we pass QS.
        cards = choose_cards_to_pass(self.lib, {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "AS QS JS AH 8H 2H 6D 5D 4D 3D 6C 5C 4C",
            "direction": 3,
            "num_cards": 3,
        })
        self.assertEqual(set(cards), {"QS", "AH", "8H"})

    def test_dump_queen(self):
        card = choose_card_to_play(self.lib, {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "KS QS JS TS AH 9H 6H 3H AD KD QD JD",
            "prev_tricks": [{"leader": 0, "cards": "2C QC KC AC"}],
            "current_trick": {"leader": 3, "cards": "4C"},
            "pass_direction": 0,
            "passed_cards": "",
            "received_cards": "",
        })
        self.assertIn(card, ["QS"])

    def test_high_spade(self):
        card = choose_card_to_play(self.lib, {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "KS JS AH 9H 6H 5H 4H 3H AD KD QD 2D",
            "prev_tricks": [{"leader": 0, "cards": "2C QC KC AC"}],
            "current_trick": {"leader": 3, "cards": "4C"},
            "pass_direction": 0,
            "passed_cards": "",
            "received_cards": "",
        })
        self.assertIn(card, ["KS"])

    def test_avoid_queen(self):
        card = choose_card_to_play(self.lib, {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
            "prev_tricks": [{"leader": 0, "cards": "2C KC AC QC"}],
            "current_trick": {"leader": 1, "cards": "4S 8S"},
            "pass_direction": 1,
            "passed_cards": "AS QS QD",
            "received_cards": "KH 9C 8C",
        })
        self.assertIn(card, ["9S", "2S"])

    def test_play_safe_high_spade(self):
        # KS is safe to play because we passed the queen right.
        card = choose_card_to_play(self.lib, {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
            "prev_tricks": [{"leader": 0, "cards": "2C KC AC QC"}],
            "current_trick": {"leader": 1, "cards": "4S 8S"},
            "pass_direction": 3,
            "passed_cards": "AS QS QD",
            "received_cards": "KH 9C 8C",
        })
        self.assertEqual(card, "KS")

    def test_take_queen_to_avoid_losing(self):
        # Player 0 has to take the queen, otherwise player 3 will go over the
        # point limit and player 1 will win.
        card = choose_card_to_play(self.lib, {
            "scores_before_round": [20, 0, 40, 90],
            "hand": "AS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
            "prev_tricks": [{"leader": 0, "cards": "2C KC AC QC"}],
            "current_trick": {"leader": 1, "cards": "4S 8S QS"},
            "pass_direction": 0,
            "passed_cards": "",
            "received_cards": "",
        })
        self.assertEqual(card, "AS")

    def test_take_jack_of_diamonds_if_minus_10(self):
        req = {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "AS JS 6S AH JH 6H AD JD 3D 2D 4C 3C",
            "prev_tricks": [{"leader": 0, "cards": "2C QC KC AC"}],
            "current_trick": {"leader": 3, "cards": "4D 8D KH"},
            "pass_direction": 0,
            "passed_cards": "",
            "received_cards": "",
        }
        card = choose_card_to_play(self.lib, req)
        self.assertEqual(card, "AD")
        # If the jack of diamonds is -10 points, we should take it.
        req["rules"] = {"jd_minus_10": True}
        card = choose_card_to_play(self.lib, req)
        self.assertEqual(card, "JD")

    def test_dont_expect_opponent_to_drop_jd(self):
        req = {
            "rules": {"jd_minus_10": True},
            "scores_before_round": [0, 0, 0, 0],
            "hand": "AD TD 9D 8D JS TS 9S 8S KH 4H JC TC",
            "prev_tricks": [{"leader": 0, "cards": "2C QC KC AC"}],
            "current_trick": {"leader": 3, "cards": ""},
            "pass_direction": 0,
            "passed_cards": "",
            "received_cards": "",
        }
        card = choose_card_to_play(self.lib, req)
        # Make sure that we don't model our opponents as wanting to play JD
        # if we lead a higher diamond. A spade is the only reasonable lead.
        self.assertIn(card, ["JS", "TS", "9S", "8S"])

    def test_block_shoot(self):
        # Basic shooting defense. Contrived hand:
        # P0: ♠ ♥AQT954 ♦ ♣8765432
        # P1: ♠87532 ♥K73 ♦76542 ♣
        # P2 (shooter): ♠AKQJT ♥ ♦AKQJT ♣AJT
        # P3 (defender): ♠964 ♥J862 ♦983 ♣KQ9
        # P2 gets down to the AJ of clubs and P3 has Q9. When P2 plays the ace,
        # P3 must play the 9 so that the Q will take a heart on the last trick.
        card = choose_card_to_play(self.lib, {
            "scores_before_round": [0, 0, 0, 0],
            "hand": "QC 9C",
            "prev_tricks": [
                {"leader": 0, "cards": "2C 7D TC KC"},
                {"leader": 3, "cards": "9S 4H 8S AS"},
                {"leader": 2, "cards": "AD 3D AH 5D"},
                {"leader": 2, "cards": "KD 8D QH 6D"},
                {"leader": 2, "cards": "QD 9D TH 4D"},
                {"leader": 2, "cards": "JD JH 9H 2D"},
                {"leader": 2, "cards": "TD 8H 5H KH"},
                {"leader": 2, "cards": "KS 6S 8C 7S"},
                {"leader": 2, "cards": "QS 4S 7C 5S"},
                {"leader": 2, "cards": "JS 6H 6C 3S"},
                {"leader": 2, "cards": "TS 2H 5C 2S"},
            ],
            "current_trick": {"leader": 2, "cards": "AC"},
            "pass_direction": 0,
            "passed_cards": "",
            "received_cards": "",
        })
        self.assertEqual(card, "9C")

    def test_count_points(self):
        score_req = {
            "tricks": [
                {"leader": 2, "cards": "2C AC QC KC"},
                {"leader": 3, "cards": "2S 5S AS QS"},
                {"leader": 1, "cards": "2D 9H KD AH"},
            ]
        }
        req_bytes = json.dumps(score_req).encode('utf-8')
        i32_array_type = c_int32 * 4
        score_buffer = i32_array_type.from_buffer(bytearray(16))
        self.lib.points_taken_from_json(req_bytes, len(req_bytes), score_buffer, 4)
        self.assertEqual(list(score_buffer), [0, 13, 0, 2])


if __name__ == '__main__':
    unittest.main()
