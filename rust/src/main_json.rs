mod card;
mod hearts;
mod hearts_ai;
mod hearts_json;

use std::io;
use std::io::Read;

use rand::Rng;
use rand::thread_rng;

use card::*;
use hearts_ai::MonteCarloParams;
use hearts_ai::CardToPlayStrategy;

/* Example: paste to stdin:
{
    "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
    "prev_tricks": [{"leader": 0, "cards": "2C AC KC QC"}],
    "current_trick": {"leader": 1, "cards": "4S 8S"}
}
*/

fn main() {
    let mut rng = thread_rng();
    let mut buffer = String::new();
    std::io::stdin().read_to_string(&mut buffer);
    let req = hearts_json::parse_card_to_play_request(&buffer).unwrap();
    let ai_strat = CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
        0.1, MonteCarloParams {num_hands: 50, rollouts_per_hand: 20});
    let ai_card = hearts_ai::choose_card(&req, &ai_strat, &mut rng);
    println!("{}", ai_card.symbol_string());
}
