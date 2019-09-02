from dataclasses import dataclass
from typing import Generic, TypeVar


@dataclass
class MatchStats:
    num_matches: int = 0
    num_wins: int = 0
    num_ties: int = 0
    total_points: int = 0


@dataclass
class RoundStats:
    num_rounds: int = 0
    total_points: int = 0
    total_opponent_points: int = 0
    num_moonshots: int = 0
    num_opponent_moonshots: int = 0
    num_queen_spades: int = 0
    num_jack_diamonds: int = 0
    num_hearts: int = 0


T = TypeVar('T')

@dataclass(frozen=True)
class StatsWithAndWithoutJD(Generic[T]):
    stats_with_jd: T
    stats_without_jd: T
