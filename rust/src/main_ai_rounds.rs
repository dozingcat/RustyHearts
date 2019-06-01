mod card;
mod hearts;
mod hearts_ai;

use std::io;

use rand::Rng;
use rand::thread_rng;
use rand::SeedableRng;
use rand::rngs::StdRng;

use card::*;
use hearts_ai::MonteCarloParams;
use hearts_ai::CardToPlayStrategy;

// TODO:
// pass cards
// match with multiple rounds to 100 points

fn main() {
    let mut deck = Deck::new();
    let mut rng = thread_rng();
    // let mut deck_rng: StdRng = SeedableRng::seed_from_u64(42);

    let mut total_points: Vec<i64> = Vec::new();
    total_points.resize(4, 0);

    for _ in 0..1000000 {
        deck.shuffle(&mut rng);
        let mut round = hearts::Round::deal(&deck, hearts::RuleSet::default());
        for i in 0..round.players.len() {
            println!("P{}: {}", i, all_suit_groups(&round.players[i].hand));
        }
        let strategies = vec![
            CardToPlayStrategy::AvoidPoints,
            CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
                0.1, MonteCarloParams {num_hands: 50, rollouts_per_hand: 20}),
            CardToPlayStrategy::MonteCarloRandom(
                MonteCarloParams {num_hands: 50, rollouts_per_hand: 20}),
            CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
                0.1, MonteCarloParams {num_hands: 50, rollouts_per_hand: 20}),
        ];

        while !round.is_over() {
            let card_to_play = hearts_ai::choose_card(
                &hearts_ai::CardToPlayRequest::from_round(&round),
                &strategies[round.current_player_index()], &mut rng);
            println!("P{} plays {}", round.current_player_index(), card_to_play.symbol_string());
            round.play_card(&card_to_play).expect("");
            if round.current_trick.cards.is_empty() {
                let t = round.prev_tricks.last().expect("");
                println!("P{} takes the trick", t.winner);
            }
        }
        let points = round.points_taken();
        println!("Score: {:?}", points);
        for (j, p) in points.iter().enumerate() {
            total_points[j] += *p as  i64;
        }
        println!("Total: {:?}\n", total_points);
    }
}
