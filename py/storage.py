import contextlib
import json
import os
import time
from typing import Iterable, List

from cards import Card, Rank, Suit
from hearts import Match, PassInfo, Player, Round, RuleSet, Trick
from stats import MatchStats, RoundStats, StatsWithAndWithoutJD

def debug(*args, **kwargs):
    # debug(*args, **kw)
    pass

def cards_to_string(cards: Iterable[Card]) -> str:
    return " ".join(c.ascii_string() for c in cards)

def cards_from_string(s: str) -> List[Card]:
    return [Card.parse(p) for p in s.split()]

# Short keys since serialized rules may be written often in history files.
RULES_NUM_PLAYERS_KEY = "np"
RULES_REMOVED_CARDS_KEY = "rc"
RULES_POINT_LIMIT_KEY = "p"
RULES_POINTS_ON_FIRST_TRICK_KEY = "p1"
RULES_QUEEN_BREAKS_HEARTS_KEY = "qb"
RULES_JD_MINUS_10_KEY = "jd"
RULES_SHOOTING_DISABLED_KEY = "sd"

def rules_to_dict(rules: RuleSet):
    return {
        RULES_NUM_PLAYERS_KEY: rules.num_players,
        RULES_REMOVED_CARDS_KEY: cards_to_string(rules.removed_cards),
        RULES_POINT_LIMIT_KEY: rules.point_limit,
        RULES_POINTS_ON_FIRST_TRICK_KEY: int(rules.points_on_first_trick),
        RULES_QUEEN_BREAKS_HEARTS_KEY: int(rules.queen_breaks_hearts),
        RULES_JD_MINUS_10_KEY: int(rules.jd_minus_10),
        RULES_SHOOTING_DISABLED_KEY: int(rules.shooting_disabled),
    }

def rules_from_dict(d) -> RuleSet:
    return RuleSet(
        num_players=d[RULES_NUM_PLAYERS_KEY],
        removed_cards=cards_from_string(d[RULES_REMOVED_CARDS_KEY]),
        point_limit=d[RULES_POINT_LIMIT_KEY],
        points_on_first_trick=bool(d[RULES_POINTS_ON_FIRST_TRICK_KEY]),
        queen_breaks_hearts=bool(d[RULES_QUEEN_BREAKS_HEARTS_KEY]),
        jd_minus_10=bool(d[RULES_JD_MINUS_10_KEY]),
        shooting_disabled=bool(d[RULES_SHOOTING_DISABLED_KEY]),
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
        return os.path.join(self.base_dir, "current_match.json")

    def store_current_match(self, match: Match):
        mdict = match_to_dict(match)
        match_filename = self.current_match_filename()
        match_temp_filename = match_filename + ".tmp"
        with open(match_temp_filename, "w") as f:
            f.write(json.dumps(mdict))
        os.rename(match_temp_filename, match_filename)
        debug(f"Wrote match json to {match_filename}")

    def load_current_match(self) -> Match:
        try:
            match_filename = self.current_match_filename()
            if not os.path.isfile(match_filename):
                return None
            with open(match_filename) as f:
                mj = json.load(f)
            return match_from_dict(mj)
        except Exception as ex:
            print(f"Failed to read stored match: {ex}")
            return None

    def remove_current_match(self):
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.current_match_filename())

    def match_history_filename(self):
        return os.path.join(self.base_dir, "matches.json")

    def record_match_stats(self, match: Match, time_fn=time.time):
        winners = match.winners()
        result = "lose"
        if winners == [0]:
            result = "win"
        elif 0 in winners:
            result = "tie"
        match_info = {
            "time": int(time_fn()),
            "rules": rules_to_dict(match.rules),
            "scores": match.total_scores(),
            "result": result,
        }
        with open(self.match_history_filename(), "a") as f:
            f.write(json.dumps(match_info, separators=(',', ':')))
            f.write('\n')

    def load_match_stats(self) -> StatsWithAndWithoutJD[MatchStats]:
        with_jd = MatchStats()
        without_jd = MatchStats()
        mfile = self.match_history_filename()
        if os.path.isfile(mfile):
            with open(self.match_history_filename()) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        m = json.loads(line)
                        rules = rules_from_dict(m["rules"])
                        scores = m["scores"]
                        result = m["result"]
                        stats = with_jd if rules.jd_minus_10 else without_jd
                        stats.num_matches += 1
                        stats.num_wins += (1 if result == "win" else 0)
                        stats.num_ties += (1 if result == "tie" else 0)
                        stats.total_points += scores[0]
                    except Exception as ex:
                        print(f"Error reading match stats: {ex}")
        return StatsWithAndWithoutJD(with_jd, without_jd)

    def round_history_filename(self):
        return os.path.join(self.base_dir, "rounds.json")

    def record_round_stats(self, rnd: Round, time_fn=time.time):
        queen = Card(Rank.QUEEN, Suit.SPADES)
        jack = Card(Rank.JACK, Suit.DIAMONDS)
        cards_taken = rnd.cards_taken()
        shooter = None
        for i, cards in enumerate(cards_taken):
            if queen in cards and sum(1 for c in cards if c.suit == Suit.HEARTS) == 13:
                shooter = i
                break
        round_info = {
            "time": int(time_fn()),
            "rules": rules_to_dict(rnd.rules),
            "points": rnd.points_taken(),
            "qs": int(queen in cards_taken[0]),
            "jd": int(jack in cards_taken[0]),
            "hearts": sum(1 for c in cards_taken[0] if c.suit == Suit.HEARTS),
            "shoot": shooter,
        }
        with open(self.round_history_filename(), "a") as f:
            f.write(json.dumps(round_info, separators=(',', ':')))
            f.write('\n')

    def load_round_stats(self) -> StatsWithAndWithoutJD[RoundStats]:
        with_jd = RoundStats()
        without_jd = RoundStats()
        rfile = self.round_history_filename()
        if os.path.isfile(rfile):
            with open(rfile) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        r = json.loads(line)
                        rules = rules_from_dict(r["rules"])
                        points = r["points"]
                        took_qs = bool(r["qs"])
                        took_jd = bool(r["jd"])
                        hearts = r["hearts"]
                        shooter = r["shoot"]
                        stats = with_jd if rules.jd_minus_10 else without_jd
                        stats.num_rounds += 1
                        stats.total_points += points[0]
                        stats.total_opponent_points += (sum(points) - points[0])
                        stats.num_moonshots += (1 if shooter == 0 else 0)
                        stats.num_opponent_moonshots += (
                            1 if shooter is not None and shooter != 0 else 0)
                        # Don't count hearts or queen if the player shot.
                        stats.num_queen_spades += (1 if took_qs and shooter != 0 else 0)
                        stats.num_hearts += (hearts if shooter != 0 else 0)
                        stats.num_jack_diamonds += (1 if took_jd else 0)
                    except Exception as ex:
                        print(f"Error reading round stats: {ex}")
        return StatsWithAndWithoutJD(with_jd, without_jd)

    def clear_stats(self):
        for path in [self.match_history_filename(), self.round_history_filename()]:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
