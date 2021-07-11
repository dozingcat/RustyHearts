mod card;
mod hearts;
mod hearts_ai;

use rand::thread_rng;

use card::*;
use hearts_ai::CardToPlayStrategy;
use hearts_ai::MonteCarloParams;

fn pass_direction_string(dir: u32) -> String {
    return (match dir {
        1 => "left",
        2 => "across",
        3 => "right",
        _ => panic!("Bad direction"),
    })
    .to_string();
}

fn get_victory_points(scores: &[i32]) -> Vec<u64> {
    let best = *scores.iter().min().unwrap();
    let mut vp: Vec<u64> = Vec::new();
    let num_winners = scores.iter().filter(|&s| *s == best).count();
    for s in scores.iter() {
        vp.push(if *s == best {
            (12 / num_winners) as u64
        } else {
            0
        });
    }
    return vp;
}

fn main() {
    let mut deck = Deck::new();
    let mut rng = thread_rng();
    // let mut deck_rng: StdRng = SeedableRng::seed_from_u64(42);

    let rules = hearts::RuleSet::default();
    // 12 points for win, 6 for 2-way tie, 4 for 3-way, 3 for 4-way.
    let mut victory_points: Vec<u64> = Vec::new();
    victory_points.resize(rules.num_players, 0);
    let mut total_rounds = 0u32;

    for match_num in 0..10 {
        println!("Match {}", match_num + 1);
        let mut match_scores: Vec<i32> = Vec::new();
        match_scores.resize(rules.num_players, 0);
        let mut round_num = 0u32;
        while *match_scores.iter().max().unwrap() < (rules.point_limit as i32) {
            round_num += 1;
            total_rounds += 1;
            println!("Round {} (total {})", round_num, total_rounds);
            deck.shuffle(&mut rng);
            let pass_dir = round_num % 4;
            let mut round = hearts::Round::deal(&deck, &rules, &match_scores, pass_dir);
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
                        scores_before_round: match_scores.clone(),
                    };
                    let cards = if i == 3 {
                        hearts_ai::choose_cards_to_pass(&pass_req)
                    } else {
                        hearts_ai::choose_cards_to_pass_random(&pass_req)
                    };
                    println!("P{} passes {}", i, symbol_str_from_cards(&cards));
                    round.set_passed_cards_for_player(i, &cards);
                }
                round.pass_cards();
                println!("After passing:");
                for i in 0..round.players.len() {
                    println!("P{}: {}", i, all_suit_groups(&round.players[i].hand));
                }
            } else {
                println!("No passing");
            }
            let strategies = vec![
                CardToPlayStrategy::AvoidPoints,
                CardToPlayStrategy::MonteCarloMixedRandomAvoidPoints(
                    0.2,
                    MonteCarloParams {
                        num_hands: 50,
                        rollouts_per_hand: 20,
                    },
                ),
                CardToPlayStrategy::MonteCarloRandom(MonteCarloParams {
                    num_hands: 50,
                    rollouts_per_hand: 20,
                }),
                CardToPlayStrategy::MonteCarloAvoidPoints(
                    MonteCarloParams {
                        num_hands: 50,
                        rollouts_per_hand: 20,
                    },
                ),
            ];

            while !round.is_over() {
                let card_to_play = hearts_ai::choose_card(
                    &round,
                    &strategies[round.current_player_index()],
                    &mut rng,
                );
                println!(
                    "P{} plays {}",
                    round.current_player_index(),
                    card_to_play.symbol_string()
                );
                round.play_card(&card_to_play);
                if round.current_trick.cards.is_empty() {
                    let t = round.prev_tricks.last().expect("");
                    println!("P{} takes the trick", t.winner);
                }
            }
            let round_points = round.points_taken();
            println!("Scores for round: {:?}", round_points);
            for i in 0..match_scores.len() {
                match_scores[i] += round_points[i];
            }
            println!("Scores for match: {:?}", match_scores);
            println!("");
        }
        println!("Match over");
        let vp = get_victory_points(&match_scores);
        println!("Victory points for match: {:?}", vp);
        for i in 0..vp.len() {
            victory_points[i] += vp[i];
        }
        println!("Total victory points: {:?}", victory_points);
        println!("\n===========================\n");
    }
}
