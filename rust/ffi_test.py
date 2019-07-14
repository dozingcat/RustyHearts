#!/usr/bin/env python3

from ctypes import cdll, c_char, c_int32
import json
import sys

lib = cdll.LoadLibrary('target/release/libhearts.dylib')

def choose_cards_to_pass(req):
    cards = req['hand'].split()
    req_bytes = json.dumps(req).encode('utf-8')

    buf_len = 13
    char_array_type = c_char * buf_len
    pass_buffer = char_array_type.from_buffer(bytearray(buf_len))
    lib.cards_to_pass_from_json(req_bytes, len(req_bytes), pass_buffer, buf_len)
    # `pass_buffer` now has byte values of 1 corresponding to legal cards to play.
    passed_cards = [card for (card, passed) in zip(cards, pass_buffer) if ord(passed)]
    print(f'Cards to pass: {passed_cards}')

choose_cards_to_pass({
    "scores_before_round": [0, 0, 0, 0],
    "hand": "AS QS JS AH 8H 2H 6D 5D 4D 3D 6C 5C 4C",
    "direction": 1,
    "num_cards": 3,
})

# Don't need to pass AS right when we pass QS.
choose_cards_to_pass({
    "scores_before_round": [0, 0, 0, 0],
    "hand": "AS QS JS AH 8H 2H 6D 5D 4D 3D 6C 5C 4C",
    "direction": 3,
    "num_cards": 3,
})


def choose_card_to_play(req):
    cards = req['hand'].split()
    req_bytes = json.dumps(req).encode('utf-8')

    buf_len = 13
    char_array_type = c_char * buf_len
    legal_play_buffer = char_array_type.from_buffer(bytearray(buf_len))
    lib.legal_plays_from_json(req_bytes, len(req_bytes), legal_play_buffer, buf_len)
    # `legal_play_buffer` now has byte values of 1 corresponding to legal cards to play.
    legal_cards = [card for (card, legal) in zip(cards, legal_play_buffer) if ord(legal)]
    print(f'Legal cards: {legal_cards}')

    best_card_index = lib.card_to_play_from_json(req_bytes, len(req_bytes))
    if best_card_index < 0:
        print(f'Error selecting best card: {best_card_index}')
    else:
        print(f'Best card: {cards[best_card_index]}')

# If the player passed QS to the left (pass_direction=1), a low spade should be
# chosen to play. If the player passed QS to the right (pass_direction=3), the
# king of spades should be played because the queen can't be taken.
choose_card_to_play({
    "scores_before_round": [0, 0, 0, 0],
    "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
    "prev_tricks": [{"leader": 0, "cards": "2C KC AC QC"}],
    "current_trick": {"leader": 1, "cards": "4S 8S"},
    "pass_direction": 1,
    "passed_cards": "AS QS QD",
    "received_cards": "KH 9C 8C",
})

choose_card_to_play({
    "scores_before_round": [0, 0, 0, 0],
    "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
    "prev_tricks": [{"leader": 0, "cards": "2C KC AC QC"}],
    "current_trick": {"leader": 1, "cards": "4S 8S"},
    "pass_direction": 3,
    "passed_cards": "AS QS QD",
    "received_cards": "KH 9C 8C",
})

# Here player 0 has to take the queen, otherwise player 3 will go over the point
# limit and player 1 will win.
choose_card_to_play({
    "scores_before_round": [20, 0, 40, 90],
    "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
    "prev_tricks": [{"leader": 0, "cards": "2C KC AC QC"}],
    "current_trick": {"leader": 1, "cards": "4S 8S QS"},
    "pass_direction": 0,
    "passed_cards": "",
    "received_cards": "",
})

score_req = {
    "tricks": [
        {"leader": 2, "cards": "2C AC QC KC"},
        {"leader": 3, "cards": "2S 5S AS QS"},
        {"leader": 1, "cards": "2D 9H KD AH"},
    ]
}
score_req_bytes = json.dumps(score_req).encode('utf-8')
i32_array_type = c_int32 * 4
score_buffer = i32_array_type.from_buffer(bytearray(16))
lib.points_taken_from_json(score_req_bytes, len(score_req_bytes), score_buffer, 4)
print(f'Scores: {list(score_buffer)}')
