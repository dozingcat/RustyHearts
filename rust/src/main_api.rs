mod card;
mod hearts;
mod hearts_ai;
mod hearts_json;

use std::ffi::CStr;
use std::io;
use std::io::Read;
use std::ptr;
use std::slice;

use rand::thread_rng;
use rand::Rng;

use card::*;
use hearts_ai::MonteCarloParams;
use hearts_ai::{CardToPlayRequest, CardToPlayStrategy, CardsToPassRequest};

/* Example: paste to stdin:
{
    "hand": "KS 9S 2S KH 3H 2H 9D 8D 7D 9C 8C 3C",
    "prev_tricks": [{"leader": 0, "cards": "2C AC KC QC"}],
    "current_trick": {"leader": 1, "cards": "4S 8S"},
    "pass_direction": 0,
    "passed_cards": "",
    "received_cards": ""
}
*/

fn main() {
    let mut rng = thread_rng();
    let mut buffer = String::new();
    std::io::stdin().read_to_string(&mut buffer);
    let req = hearts_json::parse_card_to_play_request(&buffer).unwrap();
    let ai_strat = CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
        0.1,
        MonteCarloParams {
            num_hands: 50,
            rollouts_per_hand: 20,
        },
    );
    let ai_card = hearts_ai::choose_card(&req, &ai_strat, &mut rng);
    println!("{}", ai_card.symbol_string());
}

fn string_from_ptr(s: *const u8, len: u32) -> String {
    assert!(!s.is_null());
    let bytes = unsafe { slice::from_raw_parts(s, len as usize) };
    return String::from_utf8(bytes.to_vec()).unwrap();
}

fn cards_to_pass_req_from_json(s: *const u8, len: u32) -> CardsToPassRequest {
    let r_str = string_from_ptr(s, len);
    return hearts_json::parse_cards_to_pass_request(&r_str).unwrap();
}

fn card_to_play_req_from_json(s: *const u8, len: u32) -> CardToPlayRequest {
    let r_str = string_from_ptr(s, len);
    return hearts_json::parse_card_to_play_request(&r_str).unwrap();
}

// Parses `len` bytes of `s` as a JSON-encoded CardsToPassRequest.
// Determines the best cards to pass, and for each card at index i in the hand,
// writes 1 to `pass_out[i]` if the card should be passed and 0 if not.
// The size of `pass_out` must be at least the number of cards in the hand.
// See ffi_test.py for an example of how to call.
#[no_mangle]
pub extern "C" fn cards_to_pass_from_json(s: *const u8, len: u32, pass_out: *mut u8, out_len: u32) {
    let req = unsafe { cards_to_pass_req_from_json(s, len) };
    let cards_to_pass = hearts_ai::choose_cards_to_pass(&req);
    if req.hand.len() > (out_len as usize) {
        panic!(
            "`out_len` is {} but hand has {} cards",
            out_len,
            req.hand.len()
        );
    }
    for (i, card) in req.hand.iter().enumerate() {
        let val: u8 = if cards_to_pass.contains(card) { 1 } else { 0 };
        unsafe {
            std::ptr::write_unaligned(pass_out.offset(i as isize), val);
        }
    }
}

// Parses `len` bytes of `s` as a JSON-encoded CardToPlayRequest.
// Returns the best card to play as an index into the "hand" field of the request.
// See ffi_test.py for an example of how to call.
#[no_mangle]
pub extern "C" fn card_to_play_from_json(s: *const u8, len: u32) -> i32 {
    let req = unsafe { card_to_play_req_from_json(s, len) };
    let ai_strat = CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
        0.1,
        MonteCarloParams {
            num_hands: 50,
            rollouts_per_hand: 20,
        },
    );
    let mut rng = thread_rng();
    let ai_card = hearts_ai::choose_card(&req, &ai_strat, &mut rng);
    return match req.hand.iter().position(|&c| c == ai_card) {
        Some(i) => i as i32,
        None => -1,
    };
}

// Parses `len` bytes of `s` as a JSON-encoded CardToPlayRequest.
// Determines the legal cards to play for the hand in the request, and for each
// card at index i in the hand writes 1 to `legal_out[i]` if the card is legal
// to play and writes 0 if not. The size of `legal_out` must be at least the
// number of cards in the hand.
// See ffi_test.py for an example of how to call.
#[no_mangle]
pub extern "C" fn legal_plays_from_json(s: *const u8, len: u32, legal_out: *mut u8, out_len: u32) {
    let req = unsafe { card_to_play_req_from_json(s, len) };
    let legal_plays = req.legal_plays();
    if req.hand.len() > (out_len as usize) {
        panic!(
            "`out_len` is {} but hand has {} cards",
            out_len,
            req.hand.len()
        );
    }
    for (i, card) in req.hand.iter().enumerate() {
        let val: u8 = if legal_plays.contains(card) { 1 } else { 0 };
        unsafe {
            std::ptr::write_unaligned(legal_out.offset(i as isize), val);
        }
    }
}

// Parses `len` bytes of `s` as a JSON-encoded trick history.
// Writes the points taken by each player to `points_out`, whose size must be
// at least the number of players.
// See ffi_test.py for an example of how to call.
#[no_mangle]
pub extern "C" fn points_taken_from_json(
    s: *const u8,
    len: u32,
    points_out: *mut i32,
    out_len: u32,
) {
    let r_str = string_from_ptr(s, len);
    let history = hearts_json::parse_trick_history(&r_str).unwrap();
    if history.rules.num_players > (out_len as usize) {
        panic!(
            "`out_len` is {} but there are {} players",
            out_len, history.rules.num_players
        );
    }
    let points = history.points_taken();
    for (i, player_points) in points.iter().enumerate() {
        unsafe {
            std::ptr::write_unaligned(points_out.offset(i as isize), *player_points);
        }
    }
}
