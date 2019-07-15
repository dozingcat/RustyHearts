from ctypes import cdll, c_char, c_int32
import json

from round import Round

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


def cards_to_pass(rnd: Round, player_index: int):
    if not lib:
        return rnd.current_player().hand[:rnd.pass_info.num_cards]
    hand = rnd.players[player_index].hand
    req = {
        'scores_before_round': rnd.scores_before_round,
        'hand': serialize_cards(hand),
        'direction': rnd.pass_info.direction,
        'num_cards': rnd.pass_info.num_cards,
    }
    req_bytes = json.dumps(req).encode('utf-8')
    buf_len = len(hand)
    arr_type = c_char * buf_len
    pass_buffer = arr_type.from_buffer(bytearray(buf_len))
    lib.cards_to_pass_from_json(req_bytes, len(req_bytes), pass_buffer, buf_len)
    # `pass_buffer` now has byte values of 1 corresponding to cards to pass.
    return [card for (card, passed) in zip(hand, pass_buffer) if ord(passed)]


def json_bytes_for_round(rnd: Round):
    p = rnd.current_player()
    r = {
        'scores_before_round': rnd.scores_before_round,
        'hand': serialize_cards(p.hand),
        'prev_tricks': [serialize_trick(t) for t in rnd.prev_tricks],
        'current_trick': serialize_trick(rnd.current_trick),
        'pass_direction': rnd.pass_info.direction,
        'passed_cards': serialize_cards(p.passed_cards),
        'received_cards': serialize_cards(p.received_cards),
    }
    return json.dumps(r).encode('utf-8')


def legal_plays(rnd: Round):
    if not lib:
        return rnd.hands[rnd.current_player()][:]
    req_bytes = json_bytes_for_round(rnd)
    hand = rnd.current_player().hand
    buf_len = len(hand)
    arr_type = c_char * buf_len
    legal_play_buffer = arr_type.from_buffer(bytearray(buf_len))
    lib.legal_plays_from_json(req_bytes, len(req_bytes), legal_play_buffer, buf_len)
    # `legal_play_buffer` now has byte values of 1 corresponding to legal cards to play.
    return [card for (card, legal) in zip(hand, legal_play_buffer) if ord(legal)]


def best_play(rnd: Round):
    if not lib:
        return rnd.hands[rnd.current_player()][0]
    req_bytes = json_bytes_for_round(rnd)
    hand = rnd.current_player().hand
    best_card_index = lib.card_to_play_from_json(req_bytes, len(req_bytes))
    return hand[best_card_index]


def points_taken(rnd: Round):
    if not lib:
        return [0] * rnd.rules.num_players
    req = {
        'tricks': [serialize_trick(t) for t in rnd.prev_tricks],
    }
    req_bytes = json.dumps(req).encode('utf-8')
    nump = rnd.rules.num_players
    arr_type = c_int32 * nump
    score_buffer = arr_type.from_buffer(bytearray(nump * 4))
    lib.points_taken_from_json(req_bytes, len(req_bytes), score_buffer, nump)
    return list(score_buffer)
