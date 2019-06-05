mod card;
mod hearts;
mod hearts_ai;
mod hearts_json;

use std::ffi::CStr;
use std::io;
use std::io::Read;
use std::slice;
use std::ptr;

use rand::Rng;
use rand::thread_rng;

use card::*;
use hearts_ai::MonteCarloParams;
use hearts_ai::{CardToPlayRequest, CardToPlayStrategy};

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

unsafe fn card_to_play_req_from_json(s: *const u8, len: u32) -> CardToPlayRequest {
    assert!(!s.is_null());
    let bytes = unsafe {slice::from_raw_parts(s, len as usize)};
    let r_str = String::from_utf8(bytes.to_vec()).unwrap();
    return hearts_json::parse_card_to_play_request(&r_str).unwrap();
}

// Parses `len` bytes of `s` as a JSON-encoded CardToPlayRequest.
// Returns the best card to play as an index into the "hand" field of the request.
// See ffi_test.py for an example of how to call.
#[no_mangle]
pub extern fn card_to_play_from_json(s: *const u8, len: u32) -> i32 {
    let req = unsafe {card_to_play_req_from_json(s, len)};
    let ai_strat = CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
        0.1, MonteCarloParams {num_hands: 50, rollouts_per_hand: 20});
    let mut rng = thread_rng();
    let ai_card = hearts_ai::choose_card(&req, &ai_strat, &mut rng);
    return match req.hand.iter().position(|&c| c == ai_card) {
        Some(i) => i as i32,
        None => -1,
    };
}

// Parses `len` bytes of `s` as a JSON-encoded CardToPlayRequest.
// Determines the legal cards to play for the hand in the request, and for each
// card at index i in the hand writes a 1 to `legal_out[i]` if the card is legal
// to play and writes 0 if not. The size of `legal_out` must be at least the
// number of cards in the hand.
#[no_mangle]
pub extern fn legal_plays_from_json(s: *const u8, len: u32, legal_out: *mut u8, out_len: u32) {
    let req = unsafe {card_to_play_req_from_json(s, len)};
    let legal_plays = req.legal_plays();
    if req.hand.len() > (out_len as usize) {
        panic!("`out_len` is {} but hand has {} cards", out_len, req.hand.len());
    }
    for (i, card) in req.hand.iter().enumerate() {
        let val: u8 = if legal_plays.contains(card) {1} else {0};
        unsafe {
            std::ptr::write_unaligned(legal_out.offset(i as isize), val);
        }
    }
}