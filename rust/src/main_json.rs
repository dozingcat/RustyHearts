mod card;
mod hearts;
mod hearts_ai;

use std::io;

use rand::Rng;
use rand::thread_rng;
use rand::SeedableRng;
use rand::rngs::StdRng;
use serde_json;

use card::*;
use hearts_ai::MonteCarloParams;
use hearts_ai::ChooseCardStrategy;

fn main() {
    let j: serde_json::Value = serde_json::from_str("[1, 2, 3]").unwrap();
    println!("{}", j[0]);
}
