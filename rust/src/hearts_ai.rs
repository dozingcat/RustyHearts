use crate::card::*;
use crate::hearts;

use std::collections::HashMap;
use std::collections::HashSet;
use rand::Rng;
use rand::seq::SliceRandom;

#[derive(Debug, Copy, Clone)]
pub struct MonteCarloParams {
    pub num_hands: i32,
    pub rollouts_per_hand: i32,
}

pub enum CardToPlayStrategy {
    Random,
    AvoidPoints,
    MixedRandomAvoidPoints(f64),
    MonteCarloRandom(MonteCarloParams),
    MonteCarloAvoidPoints(MonteCarloParams),
    MonteCarloMixedRandomAvoidPoints(f64, MonteCarloParams),
}

pub struct CardToPlayRequest  {
    pub rules: hearts::RuleSet,
    pub scores_before_round: Vec<i32>,
    pub hand: Vec<Card>,
    pub prev_tricks: Vec<hearts::Trick>,
    pub current_trick: hearts::TrickInProgress,
    pub pass_direction: u32,
    pub passed_cards: Vec<Card>,
    pub received_cards: Vec<Card>,
}

pub struct CardsToPassRequest {
    pub rules: hearts::RuleSet,
    pub scores_before_round: Vec<i32>,
    pub hand: Vec<Card>,
    pub direction: u32,
    pub num_cards: u32,
}

// Returns the estimated probability of the player at `player_index` eventually
// winning the match.
pub fn match_equity_for_scores(scores: &[i32], max_score: u32, player_index: usize) -> f64 {
    assert!(scores.len() >= 2);
    assert!(player_index < scores.len());
    if scores.iter().any(|&s| s >= (max_score as i32)) {
        let min_score = *scores.iter().min().unwrap();
        if scores[player_index] > min_score {
            return 0.0;
        }
        // An N-way tie for first has an equity of 1/N.
        let num_winners = scores.iter().filter(|&&s| s == min_score).count();
        return 1.0 / (num_winners as f64);
    }
    // Approximate the probability as (player distance to max) / (sum of all distances to max).
    let mut total_dist = 0u32;
    for score in scores.iter() {
        total_dist += ((max_score as i32) - score) as u32;
    }
    return (((max_score as i32) - scores[player_index]) as f64) / (total_dist as f64);
}

pub fn choose_cards_to_pass_random(req: &CardsToPassRequest) -> Vec<Card> {
    return req.hand[0..(req.num_cards as usize)].to_vec();
}

pub fn choose_cards_to_pass(req: &CardsToPassRequest) -> Vec<Card> {
    let result: Vec<Card> = Vec::new();
    let mut suit_ranks: HashMap<Suit, Vec<Rank>> = HashMap::new();
    for suit in vec![Suit::Spades, Suit::Hearts, Suit::Diamonds, Suit::Clubs] {
        suit_ranks.insert(suit, ranks_for_suit(&req.hand, suit));
    }
    let mut card_danger: HashMap<Card, i32> = HashMap::new();

    fn danger_for_card(card: &Card, ranks: &[Rank], req: &CardsToPassRequest) -> i32 {
        assert!(ranks.len() > 0);
        let cval = card.rank.value as i32;
        let lowest_rank_in_suit = ranks[ranks.len() - 1].value as i32;
        match card.suit {
            Suit::Spades => {
                if card.rank < Rank::QUEEN {
                    return 0;
                }
                // Assuming 4 or more spades are safe, probably not true.
                if ranks.len() >= 4 {
                    return 0;
                }
                // Always pass QS.
                if card.rank == Rank::QUEEN {
                    return 100;
                }
                // If we're passing the queen right, it's ok to keep AS and KS
                // because we'll be able to safely play them (as long as we
                // have a lower spade).
                let passing_right = ((req.direction as usize) == req.rules.num_players - 1);
                let has_queen = ranks.contains(&Rank::QUEEN);
                let has_low_spade = (ranks[ranks.len() - 1] < Rank::QUEEN);
                return (if passing_right && has_queen && has_low_spade {cval - 5} else {100});
            }
            Suit::Hearts => {
                return cval + lowest_rank_in_suit;
            }
            Suit::Diamonds => {
                return cval + lowest_rank_in_suit;
            }
            Suit::Clubs => {
                // 2C is "higher" than AC for purposes of passing.
                // TODO: We probably want to pass AC less often because winning
                // the first trick can be helpful and doesn't risk points.
                let adj_rank = (if cval == 2 {14} else {cval - 1});
                if lowest_rank_in_suit == 2 {
                    // Probably pass singleton 2C.
                    if ranks.len() == 1 {
                        return 50;
                    }
                    let second_lowest_club = ranks[ranks.len() - 2].value as i32;
                    return adj_rank + second_lowest_club;
                }
                else {
                    return adj_rank + lowest_rank_in_suit - 1;
                }
            }
        }
    }
    for &c in req.hand.iter() {
        card_danger.insert(c, danger_for_card(&c, suit_ranks.get(&c.suit).unwrap(), req));
    }
    let mut sorted_cards: Vec<Card> = req.hand.clone();
    sorted_cards.sort_by_key(|c| -card_danger.get(c).unwrap());
    return sorted_cards[0..(req.num_cards as usize)].to_vec();
}

impl CardToPlayRequest {
    pub fn from_round(round: &hearts::Round) -> CardToPlayRequest {
        return CardToPlayRequest {
            rules: round.rules.clone(),
            scores_before_round: round.initial_scores.clone(),
            hand: round.current_player().hand.clone(),
            prev_tricks: round.prev_tricks.clone(),
            current_trick: round.current_trick.clone(),
            pass_direction: round.pass_direction,
            passed_cards: round.current_player().passed_cards.clone(),
            received_cards: round.current_player().received_cards.clone(),
        };
    }

    pub fn current_player_index(&self) -> usize {
        return
            (self.current_trick.leader + self.current_trick.cards.len()) % self.rules.num_players;
    }

    pub fn legal_plays(&self) -> Vec<Card> {
        return hearts::legal_plays(&self.hand, &self.current_trick, &self.prev_tricks, &self.rules);
    }
}

fn is_nonrecursive(strategy: &CardToPlayStrategy) -> bool {
    return match strategy {
        CardToPlayStrategy::Random => true,
        CardToPlayStrategy::AvoidPoints => true,
        CardToPlayStrategy::MixedRandomAvoidPoints(p_random) => true,
        _ => false,
    }
}

fn choose_card_nonrecursive(
        req: &CardToPlayRequest, strategy: &CardToPlayStrategy, mut rng: impl Rng) -> Card {
    return match strategy {
        CardToPlayStrategy::Random => choose_card_random(req, rng),
        CardToPlayStrategy::AvoidPoints => choose_card_avoid_points(req, rng),
        CardToPlayStrategy::MixedRandomAvoidPoints(p_random) =>
            if rng.gen_range(0.0_f64, 1.0_f64) < *p_random
                {choose_card_random(req, rng)}
            else
                {choose_card_avoid_points(req, rng)},
        _ => panic!("Invalid strategy"),
    };
}

pub fn choose_card(
        req: &CardToPlayRequest, strategy: &CardToPlayStrategy, mut rng: impl Rng) -> Card {
    if is_nonrecursive(strategy) {
        return choose_card_nonrecursive(req, strategy, &mut rng)
    }
    match strategy {
        CardToPlayStrategy::MonteCarloRandom(mc_params) =>
            choose_card_monte_carlo(req, *mc_params, &CardToPlayStrategy::Random, &mut rng),

        CardToPlayStrategy::MonteCarloAvoidPoints(mc_params) =>
            choose_card_monte_carlo(req, *mc_params, &CardToPlayStrategy::AvoidPoints, &mut rng),

        CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(p_rand, mc_params) =>
            choose_card_monte_carlo(
                req, *mc_params, &CardToPlayStrategy::MixedRandomAvoidPoints(*p_rand), &mut rng),

        _ => panic!("Unknown strategy"),
    }
}

pub fn choose_card_random(req: &CardToPlayRequest, mut rng: impl Rng) -> Card {
    let legal_plays = req.legal_plays();
    return *legal_plays.choose(&mut rng).unwrap();
}

pub fn choose_card_avoid_points(req: &CardToPlayRequest, mut rng: impl Rng) -> Card {
    let legal_plays = req.legal_plays();
    assert!(legal_plays.len() > 0);
    if legal_plays.len() == 1 {
        return legal_plays[0];
    }
    let mut legal_suits: HashSet<Suit> = HashSet::new();
    for c in legal_plays.iter() {
        legal_suits.insert(c.suit);
    }
    // If leading, play the lowest card in a random suit.
    // If last in a trick and following suit, play high if there are no points.
    // Otherwise play low if following suit, discard highest otherwise (favoring QS).
    let trick = &req.current_trick;
    if trick.cards.is_empty() {
        let suit = *random_from_set(&legal_suits, &mut rng);
        let ranks = ranks_for_suit(&legal_plays, suit);
        let lowest_rank = *ranks.last().unwrap();
        return Card::new(lowest_rank, suit);
    }
    let trick_suit = trick.cards.first().unwrap().suit;
    let is_following_suit = legal_suits.contains(&trick_suit);
    let has_qs = legal_plays.contains(&hearts::QUEEN_OF_SPADES);
    let has_jd = req.rules.jd_minus_10 && legal_plays.contains(&hearts::JACK_OF_DIAMONDS);
    if is_following_suit {
        assert!(legal_suits.len() == 1);
        // Play high on first trick if no points allowed.
        if req.prev_tricks.is_empty() && !req.rules.points_on_first_trick {
            return *legal_plays.iter()
                .filter(|c| **c != hearts::QUEEN_OF_SPADES)
                .max_by(|a, b| a.rank.cmp(&b.rank))
                .unwrap();
        }
        let high_card = hearts::highest_in_trick(&trick.cards);
        // Dump QS if possible.
        if has_qs && high_card.rank > Rank::QUEEN {
            return hearts::QUEEN_OF_SPADES;
        }
        let is_last_play = trick.cards.len() == req.rules.num_players - 1;
        // TODO: Play JD if we know it will win.
        if is_last_play {
            let trick_points = hearts::points_for_cards(&trick.cards, &req.rules);
            // Win with JD if possible (and no QS).
            if has_jd && trick_points < 10 && high_card.rank < Rank::JACK {
                return hearts::JACK_OF_DIAMONDS;
            }
            // Win without taking points if possible.
            if trick_points <= 0 {
                return *legal_plays.iter()
                    .filter(|c| **c != hearts::QUEEN_OF_SPADES)
                    .max_by(|a, b| a.rank.cmp(&b.rank))
                    .unwrap();
            }
            // Avoid taking the trick if we can; if we can't play highest.
            // TODO: If playing with JD rule, don't play it under a higher diamond.
            let highest_nonwinner = legal_plays.iter()
                .filter(|c| c.rank < high_card.rank)
                .max_by(|a, b| a.rank.cmp(&b.rank));
            return match highest_nonwinner {
                Some(c) => *c,
                None => *legal_plays.iter()
                    .filter(|c| **c != hearts::QUEEN_OF_SPADES)
                    .max_by(|a, b| a.rank.cmp(&b.rank))
                    .unwrap(),
            };
        }
        else {
            // Play just under the winner if possible.
            // If we can't, play the lowest (other than QS).
            let highest_nonwinner = legal_plays.iter()
                .filter(|c| c.rank < high_card.rank)
                .max_by(|a, b| a.rank.cmp(&b.rank));
            return match highest_nonwinner {
                Some(c) => *c,
                None => *legal_plays.iter()
                    .filter(|c| **c != hearts::QUEEN_OF_SPADES)
                    .min_by(|a, b| a.rank.cmp(&b.rank))
                    .unwrap(),
            };
        }
    }
    else {
        // Ditch QS if possible, otherwise highest heart, otherwise highest other card.
        if has_qs {
            return hearts::QUEEN_OF_SPADES;
        }
        if legal_suits.contains(&Suit::Hearts) {
            return *legal_plays.iter()
                .filter(|c| c.suit == Suit::Hearts)
                .max_by(|a, b| a.rank.cmp(&b.rank))
                .unwrap();
        }
        // TODO: If playing with JD rule, don't discard it.
        return *legal_plays.iter().max_by(|a, b| a.rank.cmp(&b.rank)).unwrap();
    }
}

fn do_rollout(round: &mut hearts::Round, strategy: &CardToPlayStrategy, mut rng: impl Rng) {
    /*
    println!("Rollout:");
    for (i, p) in round.players.iter().enumerate() {
        println!("P{}: {}", i, all_suit_groups(&p.hand));
    }
    */
    while !round.is_over() {
        let legal_plays = round.legal_plays();
        if legal_plays.len() == 0 {
            println!("No legal plays!?");
            println!("Current player: {}", round.current_player_index());
            println!("Hand: {}", all_suit_groups(&round.current_player().hand));
            println!("Trick: {:?}", round.current_trick);
        }
        assert!(legal_plays.len() > 0);
        // We have to split the strategies into recursive and nonrecursive, otherwise the compiler
        // tries to infinitely recurse.
        let card_to_play = choose_card_nonrecursive(
            &CardToPlayRequest::from_round(&round), strategy, &mut rng);
        round.play_card(&card_to_play).expect("");
    }
}

fn max_index<T: PartialOrd>(vals: &[T]) -> usize {
    let mut max = &vals[0];
    let mut max_index: usize = 0;
    for i in 1..vals.len() {
        if vals[i] > *max {
            max = &vals[i];
            max_index = i;
        }
    }
    return max_index;
}

fn make_card_distribution_req(req: &CardToPlayRequest) -> CardDistributionRequest {
    let num_players = req.rules.num_players;
    let mut seen_cards: HashSet<Card> = HashSet::new();
    for &c in req.hand.iter() {
        seen_cards.insert(c);
    }
    let mut voided_suits: Vec<HashSet<Suit>> = Vec::new();
    for _ in 0..num_players {
        voided_suits.push(HashSet::new());
    }
    let mut hearts_broken = false;

    let mut process_trick = |trick_cards: &[Card], leader: usize| {
        let trick_suit = trick_cards[0].suit;
        if !hearts_broken && trick_suit == Suit::Hearts {
            // Led hearts when they weren't broken, so must have had no other choice.
            hearts_broken = true;
            voided_suits[leader].insert(Suit::Spades);
            voided_suits[leader].insert(Suit::Hearts);
            voided_suits[leader].insert(Suit::Clubs);
        }
        seen_cards.insert(trick_cards[0]);
        for i in 1..trick_cards.len() {
            let c = trick_cards[i];
            seen_cards.insert(c);
            if c.suit != trick_suit {
                voided_suits[(leader + i) % num_players].insert(trick_suit);
            }
            if c.suit == Suit::Hearts ||
                    (req.rules.queen_breaks_hearts && c == hearts::QUEEN_OF_SPADES) {
                hearts_broken = true;
            }
        }
    };

    for t in req.prev_tricks.iter() {
        process_trick(&t.cards, t.leader);
    }
    if !req.current_trick.cards.is_empty() {
        process_trick(&req.current_trick.cards, req.current_trick.leader);
    }

    let mut cards_to_assign: Vec<Card> = Vec::new();
    for_each_card(|c| {
        if !req.rules.removed_cards.contains(c) && !seen_cards.contains(c) {
            cards_to_assign.push(*c);
        }
    });
    let mut counts: Vec<usize> = Vec::new();
    let base_count: usize = 13 - req.prev_tricks.len();
    counts.resize(num_players, base_count);
    for i in 0..req.current_trick.cards.len() {
        let pi = (req.current_trick.leader + i) % num_players;
        counts[pi] -= 1;
    }
    counts[req.current_player_index()] = 0;
    let mut constraints: Vec<CardDistributionPlayerConstraint> = Vec::new();
    for i in 0..num_players {
        constraints.push(CardDistributionPlayerConstraint {
            num_cards: counts[i],
            voided_suits: voided_suits[i].clone(),
            fixed_cards: HashSet::new(),
        });
    }
    if (req.passed_cards.len() > 0) {
        let passed_to = (req.current_player_index() + (req.pass_direction as usize)) % num_players;
        for c in req.passed_cards.iter() {
            constraints[passed_to].fixed_cards.insert(*c);
        }
    }
    return CardDistributionRequest {
        cards: cards_to_assign,
        constraints: constraints,
    };
}

fn possible_round(cc_req: &CardToPlayRequest, dist_req: &CardDistributionRequest,
                  rng: impl Rng) -> Option<hearts::Round> {
    let maybe_dist = possible_card_distribution(&dist_req, rng);
    if maybe_dist.is_err() {
        return None;
    }
    let dist = maybe_dist.unwrap();
    let cur_player = cc_req.current_player_index();
    let mut result_players: Vec<hearts::Player> = Vec::new();
    for i in 0..cc_req.rules.num_players {
        let h = (if i == cur_player {&cc_req.hand} else {&dist[i]});
        result_players.push(hearts::Player::new(h));
    }
    return Some(hearts::Round {
        rules: cc_req.rules.clone(),
        players: result_players,
        initial_scores: cc_req.scores_before_round.clone(),
        current_trick: cc_req.current_trick.clone(),
        prev_tricks: cc_req.prev_tricks.clone(),
        status: hearts::RoundStatus::Playing,
        // Ignore passed cards.
        pass_direction: 0,
        num_passed_cards: 0,
    });
}

pub fn choose_card_monte_carlo(
        req: &CardToPlayRequest,
        mc_params: MonteCarloParams,
        rollout_strategy: &CardToPlayStrategy,
        mut rng: impl Rng) -> Card {
    let legal_plays = req.legal_plays();
    assert!(legal_plays.len() > 0);
    if legal_plays.len() == 1 {
        return legal_plays[0];
    }
    let pnum = req.current_player_index();
    let mut equity_per_play: Vec<f64> = Vec::new();
    equity_per_play.resize(legal_plays.len(), 0.0);

    /*
    print!("P{} options: ", pnum);
    for c in legal_plays.iter() {
        print!("{} ", c.symbol_string());
    }
    println!("");
    */

    let cur_points = hearts::points_for_tricks(&req.prev_tricks, &req.rules)[pnum as usize];
    let dist_req = make_card_distribution_req(&req);
    for _s in 0..mc_params.num_hands {
        let maybe_hypo_round = possible_round(req, &dist_req, &mut rng);
        if maybe_hypo_round.is_none() {
            println!("MC failed, defaulting to choose_card_avoid_points");
            return choose_card_avoid_points(req, &mut rng);
        }
        let hypo_round = maybe_hypo_round.unwrap();
        for ci in 0..legal_plays.len() {
            let mut hypo_copy = hypo_round.clone();
            hypo_copy.play_card(&legal_plays[ci]);
            // println!("Card: {}", legal_plays[ci].symbol_string());
            for _r in 0..mc_params.rollouts_per_hand {
                let mut rh = hypo_copy.clone();
                do_rollout(&mut rh, &rollout_strategy, &mut rng);
                let round_points = rh.points_taken();
                let mut scores_after_round = req.scores_before_round.clone();
                for p in 0..req.rules.num_players {
                    scores_after_round[p] += round_points[p];
                }
                equity_per_play[ci] += match_equity_for_scores(
                    &scores_after_round, req.rules.point_limit, pnum);
                // println!("Scores: {:?}", &scores_after_round);
            }
        }
    }
    // println!("MC equities: {:?}", equity_per_play);
    return legal_plays[max_index(&equity_per_play)];
}

// Tests for what card to play are in ffi_test.py.
#[cfg(test)]
mod test {
    use super::*;

    fn c(s: &str) -> Vec<Card> {cards_from_str(s).unwrap()}

    #[test]
    fn test_match_equity() {
        assert_eq!(1.0, match_equity_for_scores(&vec![50, 60, 100, 60], 100, 0));
        assert_eq!(0.0, match_equity_for_scores(&vec![50, 60, 100, 60], 100, 1));
        assert_eq!(1.0, match_equity_for_scores(&vec![104, 103, 102, 101], 100, 3));
        assert_eq!(0.0, match_equity_for_scores(&vec![104, 103, 102, 101], 100, 2));

        assert_eq!(0.5, match_equity_for_scores(&vec![50, 60, 100, 50], 100, 3));
        assert_eq!(0.25, match_equity_for_scores(&vec![0, 0, 0, 0], 100, 3));
        assert_eq!(0.25, match_equity_for_scores(&vec![100, 100, 100, 100], 100, 3));

        let e1 = match_equity_for_scores(&vec![50, 60, 70, 80], 100, 0);
        let e2 = match_equity_for_scores(&vec![51, 59, 70, 80], 100, 0);
        assert!(e2 > 0.25);
        assert!(e1 > e2);

        let e3 = match_equity_for_scores(&vec![50, 60, 70, 80], 100, 2);
        let e4 = match_equity_for_scores(&vec![50, 60, 70, 80], 100, 3);
        assert!(e3 < 0.25);
        assert!(e4 < e3);
    }

    #[test]
    fn test_pass_high_cards() {
        let rules = hearts::RuleSet::default();
        let req = CardsToPassRequest {
            rules: rules.clone(),
            scores_before_round: vec![0, 0, 0, 0],
            hand: c("JS 5S 4S 3S 8H 5H 3H AD KD TD 7C 6C 4C"),
            direction: 1,
            num_cards: 3,
        };
        assert_eq!(choose_cards_to_pass(&req), c("AD KD TD"));
    }

    #[test]
    fn test_pass_bad_spades() {
        let rules = hearts::RuleSet::default();
        let req = CardsToPassRequest {
            rules: rules.clone(),
            scores_before_round: vec![0, 0, 0, 0],
            hand: c("AS QS JS AH 8H 2H 6D 5D 4D 3D 6C 5C 4C"),
            direction: 1,
            num_cards: 3,
        };
        assert_eq!(choose_cards_to_pass(&req), c("AS QS AH"));
    }

    #[test]
    fn test_keep_spades_above_queen_passing_right() {
        let rules = hearts::RuleSet::default();
        let req = CardsToPassRequest {
            rules: rules.clone(),
            scores_before_round: vec![0, 0, 0, 0],
            hand: c("AS QS JS AH 8H 2H 6D 5D 4D 3D 6C 5C 4C"),
            direction: 3,
            num_cards: 3,
        };
        assert_eq!(choose_cards_to_pass(&req), c("QS AH 8H"));
    }

    #[test]
    fn pass_high_spades_right_without_queen() {
        let rules = hearts::RuleSet::default();
        let req = CardsToPassRequest {
            rules: rules.clone(),
            scores_before_round: vec![0, 0, 0, 0],
            hand: c("AS KS JS AH 8H 2H 6D 5D 4D 3D 6C 5C 4C"),
            direction: 3,
            num_cards: 3,
        };
        assert_eq!(choose_cards_to_pass(&req), c("AS KS AH"));
    }
}
