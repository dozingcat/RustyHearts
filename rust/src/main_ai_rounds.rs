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

fn pass_direction_string(dir: u32) -> String {
    return (match dir {
        1 => "left",
        2 => "across",
        3 => "right",
        _ => panic!("Bad direction"),
    }).to_string();
}

fn main() {
    let mut deck = Deck::new();
    let mut rng = thread_rng();
    // let mut deck_rng: StdRng = SeedableRng::seed_from_u64(42);

    let mut total_points: Vec<i64> = Vec::new();
    total_points.resize(4, 0);
    let rules = hearts::RuleSet::default();

    for round_num in 0..1000000 {
        deck.shuffle(&mut rng);
        let pass_dir = ((round_num + 1) % 4) as u32;
        let mut round = hearts::Round::deal(&deck, &rules, pass_dir);
        for i in 0..round.players.len() {
            println!("P{}: {}", i, all_suit_groups(&round.players[i].hand));
        }
        if pass_dir > 0 {
            println!("Pass {}", pass_direction_string(pass_dir));
            for i in 0..round.players.len() {
                let pass_req = hearts_ai::CardsToPassRequest {
                    rules: rules.clone(),
                    hand: round.players[i].hand.clone(),
                    direction: pass_dir,
                    num_cards: 3,
                };
                let cards = hearts_ai::choose_cards_to_pass(&pass_req);
                println!("P{} passes {}", i, symbol_str_from_cards(&cards));
                round.set_passed_cards_for_player(i, &cards);
            }
            round.pass_cards();
            println!("After passing:");
            for i in 0..round.players.len() {
                println!("P{}: {}", i, all_suit_groups(&round.players[i].hand));
            }
        }
        else {
            println!("No passing");
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
        println!("Total: {:?}", total_points);
        println!("===========================\n");
    }
}
