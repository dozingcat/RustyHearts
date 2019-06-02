mod card;
mod hearts;
mod hearts_ai;
mod hearts_json;

use std::ffi::CStr;
use std::io;
use std::io::Read;
use std::slice;

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

// Parses `len` bytes of `s` as a JSON-encoded CardToPlayRequest.
#[no_mangle]
pub extern fn card_to_play_from_json(s: *const u8, len: u32) -> i32 {
    assert!(!s.is_null());
    let bytes = unsafe {slice::from_raw_parts(s, len as usize)};
    let r_str = String::from_utf8(bytes.to_vec()).unwrap();
    let req = hearts_json::parse_card_to_play_request(&r_str).unwrap();
    let ai_strat = CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
        0.1, MonteCarloParams {num_hands: 50, rollouts_per_hand: 20});
    let mut rng = thread_rng();
    let ai_card = hearts_ai::choose_card(&req, &ai_strat, &mut rng);
    return match req.hand.iter().position(|&c| c == ai_card) {
        Some(i) => i as i32,
        None => -1,
    };
}