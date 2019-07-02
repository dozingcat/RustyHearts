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
    let rules = hearts::RuleSet::default();
    let ai_strat = CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
        0.1, MonteCarloParams {num_hands: 50, rollouts_per_hand: 20});
    deck.shuffle(&mut rng);
    let pass_dir = 1u32;
    let mut round = hearts::Round::deal(&deck, &rules, pass_dir);
    println!("Your hand: {}", all_suit_groups(&round.players[0].hand));
    if pass_dir > 0 {
        let mut passed = false;
        while !passed {
            println!("Enter 3 cards to pass:");
            let mut input = String::new();
            if io::stdin().read_line(&mut input).is_ok() {
                match cards_from_str(&input) {
                    Ok(cards) => {
                        if round.can_pass_cards(0, &cards) {
                            round.set_passed_cards_for_player(0, &cards);
                            passed = true;
                        }
                        else {
                            println!("Cannot pass those cards");
                        }
                    }
                    Err(error) => {
                        println!("Invalid input");
                    }
                };
            }
        }
        for i in 1..round.players.len() {
            let pass_req = hearts_ai::CardsToPassRequest {
                rules: rules.clone(),
                hand: round.players[i].hand.clone(),
                direction: pass_dir,
                num_cards: 3,
            };
            let cards = hearts_ai::choose_cards_to_pass(&pass_req);
            // println!("P{} passes {}", i, symbol_str_from_cards(&cards));
            round.set_passed_cards_for_player(i, &cards);
        }
        round.pass_cards();
        println!("You received: {}", symbol_str_from_cards(&round.players[0].received_cards));
        println!("Your hand: {}", all_suit_groups(&round.players[0].hand));
    }


    fn print_trick_winner(winner: usize) {
        if winner == 0 {
            println!("You take the trick");
        }
        else {
            println!("P{} takes the trick", winner);
        }
        println!("==================");
    }

    while !round.is_over() {
        let ai_card = hearts_ai::choose_card(
            &hearts_ai::CardToPlayRequest::from_round(&round), &ai_strat, &mut rng);
        if round.current_player_index() == 0 {
            println!("Choose a card (AI: {}): {}",
                ai_card.symbol_string(), all_suit_groups(&round.players[0].hand));
            let mut input = String::new();
            if io::stdin().read_line(&mut input).is_ok() {
                match Card::from(&input.trim()) {
                    Ok(card) => {
                        if round.legal_plays().contains(&card) {
                            round.play_card(&card).expect("");
                            println!("You played {}", card.symbol_string());
                            if round.current_trick.cards.is_empty() {
                                let t = round.prev_tricks.last().expect("");
                                print_trick_winner(t.winner);
                            }
                        }
                        else {
                            println!("{} is not a legal card to play", card.symbol_string());
                        }
                    }
                    Err(error) => {
                        println!("Invalid card");
                    }
                };
            }
        }
        else {
            println!("P{} plays {}", round.current_player_index(), ai_card.symbol_string());
            round.play_card(&ai_card).expect("");
            if round.current_trick.cards.is_empty() {
                let t = round.prev_tricks.last().expect("");
                print_trick_winner(t.winner);
            }
        }
    }
    let points = round.points_taken();
    println!("Score: {:?}", points);
}
