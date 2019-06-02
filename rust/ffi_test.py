#!/usr/bin/env python3

from ctypes import cdll
import json
import sys

lib = cdll.LoadLibrary('target/release/libhearts.dylib')

req = {
    "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
    "prev_tricks": [{"leader": 0, "cards": "2C AC KC QC"}],
    "current_trick": {"leader": 1, "cards": "4S 8S 9S"}
}
cards = req['hand'].split()
req_bytes = json.dumps(req).encode('utf-8')
card_index = lib.card_to_play_from_json(req_bytes, len(req_bytes))
if card_index < 0:
    print(f'Got error: {card_index}')
else:
    print(f'Got card: {cards[card_index]}')
