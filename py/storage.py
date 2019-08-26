import json
import os
from typing import Iterable, List

from cards import Card
from hearts import Match, PassInfo, Player, Round, RuleSet, Trick

def cards_to_string(cards: Iterable[Card]) -> str:
    return ' '.join(c.ascii_string() for c in cards)

def cards_from_string(s: str) -> List[Card]:
    return [Card.parse(p) for p in s.split()]

def rules_to_dict(rules: RuleSet):
    return {
        "num_players": rules.num_players,
        "removed_cards": cards_to_string(rules.removed_cards),
        "point_limit": rules.point_limit,
        "points_on_first_trick": rules.points_on_first_trick,
        "queen_breaks_hearts": rules.queen_breaks_hearts,
        "jd_minus_10": rules.jd_minus_10,
        "shooting_disabled": rules.shooting_disabled,
    }

def rules_from_dict(d) -> RuleSet:
    return RuleSet(
        num_players=d["num_players"],
        removed_cards=cards_from_string(d["removed_cards"]),
        point_limit=d["point_limit"],
        points_on_first_trick=d["points_on_first_trick"],
        queen_breaks_hearts=d["queen_breaks_hearts"],
        jd_minus_10=d["jd_minus_10"],
        shooting_disabled=d["shooting_disabled"],
    )

def player_to_dict(player: Player):
    return {
        "hand": cards_to_string(player.hand),
        "passed_cards": cards_to_string(player.passed_cards),
        "received_cards": cards_to_string(player.received_cards),
    }

def player_from_dict(d) -> Player:
    return Player(
        hand=cards_from_string(d["hand"]),
        passed_cards=cards_from_string(d["passed_cards"]),
        received_cards=cards_from_string(d["received_cards"]),
    )

def trick_to_dict(trick: Trick):
    return {
        "leader": trick.leader,
        "cards": cards_to_string(trick.cards),
        "winner": trick.winner,
    }

def trick_from_dict(d) -> Trick:
    return Trick(
        leader=d["leader"],
        cards=cards_from_string(d["cards"]),
        winner=d["winner"],
    )

def round_to_dict(rnd: Round):
    # Skip rules and scores_before_round since those can be copied from Match.
    return {
        "pass_info": {
            "direction": rnd.pass_info.direction,
            "num_cards": rnd.pass_info.num_cards,
        },
        "players": [player_to_dict(p) for p in rnd.players],
        "prev_tricks": [trick_to_dict(t) for t in rnd.prev_tricks],
        "current_trick": trick_to_dict(rnd.current_trick) if rnd.current_trick else None,
    }

def match_to_dict(match: Match):
    return {
        "rules": rules_to_dict(match.rules),
        "score_history": match.score_history,
        "current_round": round_to_dict(match.current_round) if match.current_round else None,
    }

def match_from_dict(d) -> Match:
    rules = rules_from_dict(d["rules"])
    match = Match(rules)
    match.score_history = d["score_history"]
    rdict = d["current_round"]
    if rdict:
        pi = rdict["pass_info"]
        pass_info = PassInfo(direction=pi["direction"], num_cards=pi["num_cards"])
        # TODO: Avoid needlessly creating players and dealing cards in the Round constructor.
        rnd = Round(rules, pass_info, match.total_scores())
        rnd.players = [player_from_dict(pd) for pd in rdict["players"]]
        rnd.prev_tricks = [trick_from_dict(td) for td in rdict["prev_tricks"]]
        if rdict["current_trick"]:
            rnd.current_trick = trick_from_dict(rdict["current_trick"])
        match.current_round = rnd
    return match

class Storage:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def current_match_filename(self):
        return os.path.join(self.base_dir, 'current_match.json')

    def store_current_match(self, match: Match):
        mdict = match_to_dict(match)
        match_filename = self.current_match_filename()
        match_temp_filename = match_filename + '.tmp'
        with open(match_temp_filename, 'w') as f:
            f.write(json.dumps(mdict))
        os.rename(match_temp_filename, match_filename)
        print(f'Wrote match json to {match_filename}')

    def load_current_match(self) -> Match:
        try:
            match_filename = self.current_match_filename()
            if not os.path.isfile(match_filename):
                return None
            with open(match_filename) as f:
                mj = json.load(f)
            return match_from_dict(mj)
        except Exception as ex:
            print(f'Failed to read stored match: {ex}')
            return None

    def remove_current_match(self):
        os.unlink(self.current_match_filename())

    def record_match_stats(self, match: Match):
        pass

    def record_round_stats(self, round: Round):
        pass
