use crate::card::*;

use std::collections::HashSet;

pub const QUEEN_OF_SPADES: Card = Card {
    rank: Rank::QUEEN,
    suit: Suit::Spades,
};
pub const TWO_OF_CLUBS: Card = Card {
    rank: Rank::TWO,
    suit: Suit::Clubs,
};
pub const JACK_OF_DIAMONDS: Card = Card {
    rank: Rank::JACK,
    suit: Suit::Diamonds,
};

#[derive(Debug, Clone)]
pub struct Player {
    pub hand: Vec<Card>,
    pub passed_cards: Vec<Card>,
    pub received_cards: Vec<Card>,
}

impl Player {
    pub fn new(hand: &[Card]) -> Player {
        return Player {
            hand: hand.to_vec(),
            passed_cards: Vec::new(),
            received_cards: Vec::new(),
        };
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MoonShooting {
    DISABLED,
    OPPONENTS_PLUS_26,
    // TODO: Allow option of subtracting 26 from the shooter's score.
}

#[derive(Debug, Clone, PartialEq)]
pub struct RuleSet {
    pub num_players: usize,
    pub removed_cards: Vec<Card>,
    pub point_limit: u32,
    pub points_on_first_trick: bool,
    pub queen_breaks_hearts: bool,
    pub jd_minus_10: bool,
    pub moon_shooting: MoonShooting,
}

impl RuleSet {
    pub fn default_num_players() -> usize {
        4
    }
    pub fn default_point_limit() -> u32 {
        100
    }
}

impl Default for RuleSet {
    fn default() -> RuleSet {
        return Self {
            num_players: RuleSet::default_num_players(),
            removed_cards: Vec::new(),
            point_limit: RuleSet::default_point_limit(),
            points_on_first_trick: false,
            queen_breaks_hearts: false,
            jd_minus_10: false,
            moon_shooting: MoonShooting::OPPONENTS_PLUS_26,
        };
    }
}

pub fn points_for_card(c: &Card, rules: &RuleSet) -> i32 {
    if c.suit == Suit::Hearts {
        return 1;
    } else if *c == QUEEN_OF_SPADES {
        return 13;
    } else if rules.jd_minus_10 && *c == JACK_OF_DIAMONDS {
        return -10;
    }
    return 0;
}

pub fn points_for_cards(cards: &[Card], rules: &RuleSet) -> i32 {
    let mut points = 0;
    for &c in cards.iter() {
        points += points_for_card(&c, rules);
    }
    return points;
}

// This takes shooting the moon into account. If you don't want that, set
// rules.moon_shooting to `MoonShooting::DISABLED`.
pub fn points_for_tricks(tricks: &[Trick], rules: &RuleSet) -> Vec<i32> {
    let mut points: Vec<i32> = Vec::new();
    points.resize(rules.num_players, 0);
    for t in tricks.iter() {
        points[t.winner as usize] += points_for_cards(&t.cards, rules);
    }
    if rules.moon_shooting != MoonShooting::DISABLED {
        if let Some(shooter) = moon_shooter(tricks, &points, rules) {
            for p in 0..rules.num_players {
                points[p] += if (p == shooter) { -26 } else { 26 };
            }
        }
    }
    return points;
}

// Returns the index of the player who has taken all hearts and the queen of spades.
fn moon_shooter(tricks: &[Trick], points: &[i32], rules: &RuleSet) -> Option<usize> {
    fn find_shooter(pts: &[i32]) -> Option<usize> {
        for p in 0..pts.len() {
            if pts[p] == 26 {
                return Some(p);
            }
        }
        return None;
    }

    if rules.jd_minus_10 {
        // Undo the -10 points for JD. We have to do this rather than just
        // looking at the point totals because [16, 0, 0, 0] may or may not be
        // a shoot, depending on whether one of the players with zero took
        // ten hearts along with the jack of diamonds and also ten hearts.
        let mut points_without_jd = points.to_vec();
        for t in tricks.iter() {
            if t.cards.contains(&JACK_OF_DIAMONDS) {
                points_without_jd[t.winner as usize] += 10;
                break;
            }
        }
        return find_shooter(&points_without_jd);
    } else {
        return find_shooter(points);
    }
}

pub fn highest_in_trick(cards: &[Card]) -> &Card {
    let suit = cards[0].suit;
    return cards
        .iter()
        .filter(|c| c.suit == suit)
        .max_by(|a, b| a.rank.cmp(&b.rank))
        .unwrap();
}

#[derive(Debug, Clone)]
pub struct Trick {
    pub leader: usize,
    pub cards: Vec<Card>,
    pub winner: usize,
}

#[derive(Debug, Clone)]
pub struct TrickInProgress {
    pub leader: usize,
    pub cards: Vec<Card>,
}

impl TrickInProgress {
    pub fn new(leader: usize) -> TrickInProgress {
        return TrickInProgress {
            leader: leader,
            cards: Vec::new(),
        };
    }
}

fn find_card(players: &[Player], target: &Card) -> usize {
    for (i, p) in players.iter().enumerate() {
        for c in p.hand.iter() {
            if c == target {
                return i;
            }
        }
    }
    panic!("Didn't find {}", target.symbol_string());
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RoundStatus {
    Passing,
    Playing,
}

#[derive(Debug, Clone)]
pub struct Round {
    pub rules: RuleSet,
    pub players: Vec<Player>,
    // This is a bit ugly, we only need the scores for hearts_ai::CardToPlayeRequest::from_round.
    pub initial_scores: Vec<i32>,
    // e.g. 1 for passing left, rules.num_players-1 for passing right, 0 for no passing.
    pub pass_direction: u32,
    pub num_passed_cards: u32,
    pub status: RoundStatus,
    pub current_trick: TrickInProgress,
    pub prev_tricks: Vec<Trick>,
}

impl Round {
    pub fn deal(deck: &Deck, rules: &RuleSet, scores: &[i32], pass_direction: u32) -> Round {
        let mut players: Vec<Player> = Vec::new();
        // TODO: Don't hardcode to 4 players and 13 cards.
        for i in 0..4 {
            let start = 13 * i;
            let end = 13 * (i + 1);
            players.push(Player::new(&deck.cards[start..end]));
        }
        let current_player_index = find_card(&players, &TWO_OF_CLUBS);
        let status = if pass_direction == 0 {
            RoundStatus::Playing
        } else {
            RoundStatus::Passing
        };
        return Round {
            rules: rules.clone(),
            players: players,
            initial_scores: scores.to_vec(),
            num_passed_cards: 3,
            pass_direction: pass_direction,
            status: status,
            current_trick: TrickInProgress::new(current_player_index),
            prev_tricks: Vec::new(),
        };
    }

    pub fn is_over(&self) -> bool {
        return self.players.iter().all(|p| p.hand.is_empty());
    }

    pub fn points_taken(&self) -> Vec<i32> {
        return points_for_tricks(&self.prev_tricks, &self.rules);
    }

    pub fn legal_plays(&self) -> Vec<Card> {
        return legal_plays(
            &self.current_player().hand,
            &self.current_trick,
            &self.prev_tricks,
            &self.rules,
        );
    }

    pub fn are_hearts_broken(&self) -> bool {
        return are_hearts_broken(&self.current_trick, &self.prev_tricks, &self.rules);
    }

    pub fn can_pass_cards(&self, player_index: usize, cards: &[Card]) -> bool {
        if cards.len() != (self.num_passed_cards as usize) {
            return false;
        }
        let cs: HashSet<Card> = cards.iter().cloned().collect();
        for c in cs {
            if !self.players[player_index].hand.contains(&c) {
                return false;
            }
        }
        return true;
    }

    pub fn set_passed_cards_for_player(&mut self, player_index: usize, cards: &[Card]) {
        assert!(self.status == RoundStatus::Passing);
        assert!((player_index as usize) < self.rules.num_players);
        assert!(self.can_pass_cards(player_index, cards));
        self.players[player_index as usize].passed_cards = cards.to_vec();
    }

    pub fn ready_to_pass_cards(&self) -> bool {
        if self.status != RoundStatus::Passing {
            return false;
        }
        for p in self.players.iter() {
            if p.passed_cards.len() != (self.num_passed_cards as usize) {
                return false;
            }
        }
        return true;
    }

    pub fn pass_cards(&mut self) {
        assert!(self.ready_to_pass_cards());
        let num_players = self.rules.num_players as usize;
        for pnum in 0..num_players {
            let pass_dest = (pnum + (self.pass_direction as usize)) % num_players;
            self.players[pass_dest].received_cards = self.players[pnum].passed_cards.clone();
        }
        for pnum in 0..num_players {
            let mut p = &mut self.players[pnum];
            let n = p.hand.len();
            let mut new_hand: Vec<Card> = p.received_cards.clone();
            for &c in p.hand.iter() {
                if !p.passed_cards.contains(&c) {
                    new_hand.push(c);
                }
            }
            p.hand = new_hand;
            assert_eq!(p.hand.len(), n);
        }
        self.current_trick.leader = find_card(&self.players, &TWO_OF_CLUBS);
        self.status = RoundStatus::Playing;
    }

    pub fn play_card(&mut self, card: &Card) -> Result<(), ()> {
        let pos = self.current_player().hand.iter().position(|&c| c == *card);
        if let Some(index) = pos {
            self.current_player_mut().hand.remove(index);
            self.current_trick.cards.push(*card);
            if self.current_trick.cards.len() == self.players.len() {
                let winner_index = trick_winner_index(&self.current_trick.cards);
                let winner = (self.current_trick.leader + winner_index) % self.players.len();
                self.prev_tricks.push(Trick {
                    leader: self.current_trick.leader,
                    cards: self.current_trick.cards.clone(),
                    winner: winner,
                });
                self.current_trick = TrickInProgress::new(winner);
            }
            return Ok(());
        } else {
            return Err(());
        }
    }

    pub fn current_player_index(&self) -> usize {
        let ct = &self.current_trick;
        return (ct.leader + ct.cards.len()) % self.rules.num_players;
    }

    pub fn current_player(&self) -> &Player {
        return &self.players[self.current_player_index()];
    }

    fn current_player_mut(&mut self) -> &mut Player {
        let index = self.current_player_index();
        return &mut self.players[index];
    }
}

fn are_hearts_broken(
    current_trick: &TrickInProgress,
    prev_tricks: &[Trick],
    rules: &RuleSet,
) -> bool {
    let qb = rules.queen_breaks_hearts;
    for t in prev_tricks.iter() {
        for &c in t.cards.iter() {
            if c.suit == Suit::Hearts || (qb && c == QUEEN_OF_SPADES) {
                return true;
            }
        }
    }
    for &c in current_trick.cards.iter() {
        if c.suit == Suit::Hearts || (qb && c == QUEEN_OF_SPADES) {
            return true;
        }
    }
    return false;
}

pub fn legal_plays(
    hand: &[Card],
    current_trick: &TrickInProgress,
    prev_tricks: &[Trick],
    rules: &RuleSet,
) -> Vec<Card> {
    if prev_tricks.is_empty() {
        // First trick.
        if current_trick.cards.is_empty() {
            // First play must be 2C.
            if hand.contains(&TWO_OF_CLUBS) {
                return vec![TWO_OF_CLUBS];
            }
            return Vec::new();
        } else {
            // Follow suit if possible.
            let lead = current_trick.cards[0].suit;
            let suit_matches: Vec<Card> = hand.iter().filter(|c| c.suit == lead).cloned().collect();
            if !suit_matches.is_empty() {
                return suit_matches;
            } else {
                // No points unless rule is set.
                if !rules.points_on_first_trick {
                    let non_points: Vec<Card> = hand
                        .iter()
                        .filter(|c| points_for_card(c, rules) <= 0)
                        .cloned()
                        .collect();
                    if !non_points.is_empty() {
                        return non_points;
                    }
                }
                // Either points are allowed or we have nothing but points.
                return hand.to_vec();
            }
        }
    }
    if current_trick.cards.is_empty() {
        // Leading a new trick; remove hearts unless hearts are broken or there's no choice.
        if !are_hearts_broken(current_trick, prev_tricks, rules) {
            let non_hearts: Vec<Card> = hand
                .iter()
                .filter(|c| c.suit != Suit::Hearts)
                .cloned()
                .collect();
            if !non_hearts.is_empty() {
                return non_hearts;
            }
        }
        return hand.to_vec();
    } else {
        // Follow suit if possible; otherwise play anything.
        let lead = current_trick.cards[0].suit;
        let suit_matches: Vec<Card> = hand.iter().filter(|c| c.suit == lead).cloned().collect();
        return if suit_matches.is_empty() {
            hand.to_vec()
        } else {
            suit_matches
        };
    }
}

pub fn trick_winner_index(cards: &[Card]) -> usize {
    let mut best_index: usize = 0;
    let mut best_rank = cards[0].rank;
    for i in 1..cards.len() {
        if cards[i].suit == cards[0].suit && cards[i].rank > best_rank {
            best_index = i;
            best_rank = cards[i].rank;
        }
    }
    return best_index;
}

#[cfg(test)]
mod test {
    use super::*;

    fn c(s: &str) -> Vec<Card> {
        cards_from_str(s).unwrap()
    }

    fn make_trick(leader: usize, cards: &str, winner: usize) -> Trick {
        return Trick {
            leader: leader,
            cards: c(cards),
            winner: winner,
        };
    }

    #[test]
    fn test_possible_leads() {
        let rules = RuleSet::default();
        let hand = c("AS QH 4C");
        let cur_trick = TrickInProgress::new(0);

        let prev_tricks_no_hearts = vec![make_trick(0, "8S 7S 6S 5S", 0)];
        assert_eq!(
            legal_plays(&hand, &cur_trick, &prev_tricks_no_hearts, &rules),
            c("AS 4C")
        );

        let prev_tricks_hearts = vec![make_trick(0, "8S 7S KH 5S", 0)];
        assert_eq!(
            legal_plays(&hand, &cur_trick, &prev_tricks_hearts, &rules),
            c("AS QH 4C")
        );
    }

    #[test]
    fn test_possible_follows() {
        let rules = RuleSet::default();
        let hand = c("AS 2S QH 4C");
        // Need a previous trick to not trigger the "no points on first trick" rule.
        let prev_tricks = vec![Trick {
            leader: 0,
            cards: c("2C JC QC KC"),
            winner: 3,
        }];

        let spade_lead = TrickInProgress {
            leader: 0,
            cards: c("3S KH"),
        };
        assert_eq!(
            legal_plays(&hand, &spade_lead, &prev_tricks, &rules),
            c("AS 2S")
        );

        let diamond_lead = TrickInProgress {
            leader: 0,
            cards: c("3D KH"),
        };
        assert_eq!(
            legal_plays(&hand, &diamond_lead, &prev_tricks, &rules),
            c("AS 2S QH 4C")
        );
    }

    #[test]
    fn test_first_trick_2c_lead() {
        let rules = RuleSet::default();
        let hand = c("AS 2S QH 3C 2C");
        let cur_trick = TrickInProgress::new(0);

        assert_eq!(legal_plays(&hand, &cur_trick, &vec![], &rules), c("2C"));
    }

    #[test]
    fn test_first_trick_follow() {
        let rules = RuleSet::default();
        let hand = c("AS 2S AC QH 3C");
        let cur_trick = TrickInProgress {
            leader: 0,
            cards: c("2C JC"),
        };

        assert_eq!(legal_plays(&hand, &cur_trick, &vec![], &rules), c("AC 3C"));
    }

    #[test]
    fn test_first_trick_no_points() {
        let mut rules = RuleSet::default();
        let hand = c("AS QS 7S 7H 7D");
        let cur_trick = TrickInProgress {
            leader: 0,
            cards: c("2C JC"),
        };

        assert_eq!(
            legal_plays(&hand, &cur_trick, &vec![], &rules),
            c("AS 7S 7D")
        );

        rules.points_on_first_trick = true;
        assert_eq!(
            legal_plays(&hand, &cur_trick, &vec![], &rules),
            c("AS QS 7S 7H 7D")
        );
    }

    #[test]
    fn test_first_trick_only_points() {
        let mut rules = RuleSet::default();
        let hand = c("AH TH QS 7H");
        let cur_trick = TrickInProgress {
            leader: 0,
            cards: c("2C JC"),
        };

        assert_eq!(
            legal_plays(&hand, &cur_trick, &vec![], &rules),
            c("AH TH QS 7H")
        );
    }

    #[test]
    fn test_trick_winner() {
        assert_eq!(trick_winner_index(&c("9D 8D 7D 6D")), 0);
        assert_eq!(trick_winner_index(&c("9D TD JD QD")), 3);
        assert_eq!(trick_winner_index(&c("9D TD JD QS")), 2);
        assert_eq!(trick_winner_index(&c("9D TD JC QS")), 1);
        assert_eq!(trick_winner_index(&c("9D TH JC QS")), 0);
    }

    #[test]
    fn test_trick_points() {
        let mut rules = RuleSet::default();
        let tricks = vec![
            make_trick(0, "2C AC KC QC", 1),
            make_trick(1, "3D 6D QS 5D", 2),
            make_trick(2, "4D JD AH KD", 1),
        ];
        assert_eq!(points_for_tricks(&tricks, &rules), vec![0, 1, 13, 0]);

        rules.jd_minus_10 = true;
        assert_eq!(points_for_tricks(&tricks, &rules), vec![0, -9, 13, 0]);
    }

    #[test]
    fn test_shooting_points() {
        let mut rules = RuleSet::default();
        let tricks = vec![
            make_trick(0, "2C AC KC QC", 1),
            make_trick(1, "AD QS JD JH", 1),
            make_trick(1, "AH 2H 3H 4H", 1),
            make_trick(1, "KH 5H 6H 7H", 1),
            make_trick(1, "QH 8H 9H TH", 1),
        ];
        assert_eq!(points_for_tricks(&tricks, &rules), vec![26, 0, 26, 26]);

        rules.jd_minus_10 = true;
        assert_eq!(points_for_tricks(&tricks, &rules), vec![26, -10, 26, 26]);
    }
}
