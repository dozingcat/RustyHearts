#!/usr/bin/env python3

from ctypes import cdll, c_char
import json
import sys

lib = cdll.LoadLibrary('target/release/libhearts.dylib')

req = {
    "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
    "prev_tricks": [{"leader": 0, "cards": "2C AC KC QC"}],
    "current_trick": {"leader": 1, "cards": "4S 8S QS"}
}
cards = req['hand'].split()
req_bytes = json.dumps(req).encode('utf-8')

buf_len = 13
arr_type = c_char * buf_len
legal_play_buffer = arr_type.from_buffer(bytearray(buf_len))
lib.legal_plays_from_json(req_bytes, len(req_bytes), legal_play_buffer, buf_len)
# `legal_cards` now has byte values of 1 corresponding to legal cards to play.
legal_cards = [card for (card, legal) in zip(cards, legal_play_buffer) if ord(legal)]
print(f'Legal cards: {legal_cards}')

best_card_index = lib.card_to_play_from_json(req_bytes, len(req_bytes))
if best_card_index < 0:
    print(f'Error selecting best card: {best_card_index}')
else:
    print(f'Best card: {cards[best_card_index]}')
