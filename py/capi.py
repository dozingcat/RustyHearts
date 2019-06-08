from ctypes import cdll, c_char
import json

lib = cdll.LoadLibrary('../rust/target/release/libhearts.dylib')

def json_bytes_for_round(rnd):
    def serialize_cards(cards):
        return ' '.join(c.ascii_string() for c in cards)

    def serialize_trick(trick):
        return {
            'leader': trick.leader,
            'cards': serialize_cards(trick.cards),
        }

    r = {
        'hand': serialize_cards(rnd.hands[rnd.current_player()]),
        'prev_tricks': [serialize_trick(t) for t in rnd.prev_tricks],
        'current_trick': serialize_trick(rnd.current_trick),
    }
    return json.dumps(r).encode('utf-8')


def legal_plays(rnd):
    req_bytes = json_bytes_for_round(rnd)
    hand = rnd.hands[rnd.current_player()]
    buf_len = len(hand)
    arr_type = c_char * buf_len
    legal_play_buffer = arr_type.from_buffer(bytearray(buf_len))
    lib.legal_plays_from_json(req_bytes, len(req_bytes), legal_play_buffer, buf_len)
    # `legal_play_buffer` now has byte values of 1 corresponding to legal cards to play.
    return [card for (card, legal) in zip(hand, legal_play_buffer) if ord(legal)]


def best_play(rnd):
    req_bytes = json_bytes_for_round(rnd)
    hand = rnd.hands[rnd.current_player()]
    best_card_index = lib.card_to_play_from_json(req_bytes, len(req_bytes))
    return hand[best_card_index]
