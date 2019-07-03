from ctypes import cdll, c_char, c_int32
import json

# FIXME: Get the right shared library for the platform.
# lib = None
lib = cdll.LoadLibrary('../rust/target/release/libhearts.dylib')


def serialize_cards(cards):
    return ' '.join(c.ascii_string() for c in cards)


def serialize_trick(trick):
    return {
        'leader': trick.leader,
        'cards': serialize_cards(trick.cards),
    }


def json_bytes_for_round(rnd):
    # TODO: passed cards
    r = {
        'hand': serialize_cards(rnd.hands[rnd.current_player()]),
        'prev_tricks': [serialize_trick(t) for t in rnd.prev_tricks],
        'current_trick': serialize_trick(rnd.current_trick),
        'pass_direction': 0,
        'passed_cards': '',
        'received_cards': '',
    }
    return json.dumps(r).encode('utf-8')


def legal_plays(rnd):
    if not lib:
        return rnd.hands[rnd.current_player()][:]

    req_bytes = json_bytes_for_round(rnd)
    hand = rnd.hands[rnd.current_player()]
    buf_len = len(hand)
    arr_type = c_char * buf_len
    legal_play_buffer = arr_type.from_buffer(bytearray(buf_len))
    lib.legal_plays_from_json(req_bytes, len(req_bytes), legal_play_buffer, buf_len)
    # `legal_play_buffer` now has byte values of 1 corresponding to legal cards to play.
    return [card for (card, legal) in zip(hand, legal_play_buffer) if ord(legal)]


def best_play(rnd):
    if not lib:
        return rnd.hands[rnd.current_player()][0]

    req_bytes = json_bytes_for_round(rnd)
    hand = rnd.hands[rnd.current_player()]
    best_card_index = lib.card_to_play_from_json(req_bytes, len(req_bytes))
    return hand[best_card_index]


def points_taken(rnd):
    if not lib:
        return [0] * rnd.rules.num_players

    req = {
        "tricks": [serialize_trick(t) for t in rnd.prev_tricks],
    }
    req_bytes = json.dumps(req).encode('utf-8')
    nump = rnd.rules.num_players
    arr_type = c_int32 * nump
    score_buffer = arr_type.from_buffer(bytearray(nump * 4))
    lib.points_taken_from_json(req_bytes, len(req_bytes), score_buffer, nump)
    return list(score_buffer)
