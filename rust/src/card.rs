use rand::seq::SliceRandom;
use rand::Rng;
use std::collections::HashSet;

#[derive(Debug)]
pub struct CardError {
    pub msg: String,
}

impl CardError {
    pub fn new(s: &str) -> CardError {
        return CardError { msg: s.to_string() };
    }
}

#[derive(Debug, PartialEq, Eq, Hash, Copy, Clone)]
pub enum Suit {
    Clubs,
    Diamonds,
    Hearts,
    Spades,
}

impl Suit {
    pub fn from(s: &str) -> Result<Suit, CardError> {
        return match &s.to_ascii_uppercase()[..] {
            "C" => Ok(Suit::Clubs),
            "D" => Ok(Suit::Diamonds),
            "H" => Ok(Suit::Hearts),
            "S" => Ok(Suit::Spades),
            "♣" => Ok(Suit::Clubs),
            "♦" => Ok(Suit::Diamonds),
            "♥" => Ok(Suit::Hearts),
            "♠" => Ok(Suit::Spades),
            _ => Err(CardError::new("Bad char")),
        };
    }

    pub fn letter(&self) -> &str {
        return match self {
            Suit::Clubs => "C",
            Suit::Diamonds => "D",
            Suit::Hearts => "H",
            Suit::Spades => "S",
        };
    }

    pub fn symbol(&self) -> &str {
        return match self {
            Suit::Clubs => "♣",
            Suit::Diamonds => "♦",
            Suit::Hearts => "♥",
            Suit::Spades => "♠",
        };
    }
}

const RANK_CHARS: [&'static str; 13] = [
    "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A",
];

#[derive(Debug, PartialEq, Eq, Ord, PartialOrd, Hash, Copy, Clone)]
pub struct Rank {
    pub value: u32,
}

impl Rank {
    pub fn num(r: u32) -> Rank {
        assert!(r >= 2 && r <= 14);
        return Rank { value: r };
    }

    pub fn from(s: &str) -> Result<Rank, CardError> {
        return match &s.to_ascii_uppercase()[..] {
            "2" => Ok(Rank::num(2)),
            "3" => Ok(Rank::num(3)),
            "4" => Ok(Rank::num(4)),
            "5" => Ok(Rank::num(5)),
            "6" => Ok(Rank::num(6)),
            "7" => Ok(Rank::num(7)),
            "8" => Ok(Rank::num(8)),
            "9" => Ok(Rank::num(9)),
            "T" => Ok(Rank::num(10)),
            "J" => Ok(Rank::JACK),
            "Q" => Ok(Rank::QUEEN),
            "K" => Ok(Rank::KING),
            "A" => Ok(Rank::ACE),
            _ => Err(CardError::new("Bad char")),
        };
    }

    pub fn rank_char(&self) -> &str {
        return RANK_CHARS[(self.value as usize) - 2];
    }

    pub const TWO: Rank = Rank { value: 2 };
    pub const JACK: Rank = Rank { value: 11 };
    pub const QUEEN: Rank = Rank { value: 12 };
    pub const KING: Rank = Rank { value: 13 };
    pub const ACE: Rank = Rank { value: 14 };
}

#[derive(Debug, PartialEq, Eq, Hash, Copy, Clone)]
pub struct Card {
    pub rank: Rank,
    pub suit: Suit,
}

impl Card {
    pub fn new(r: Rank, s: Suit) -> Card {
        return Card { rank: r, suit: s };
    }

    pub fn from(s: &str) -> Result<Card, CardError> {
        if s.chars().count() == 2 {
            let mut chars = s.chars();
            let r = chars.next().unwrap().to_string();
            let s = chars.next().unwrap().to_string();
            return Ok(Card::new(Rank::from(&r)?, Suit::from(&s)?));
        }
        return Err(CardError::new("Bad string"));
    }

    pub fn ascii_string(&self) -> String {
        let mut s = String::from(self.rank.rank_char());
        s.push_str(self.suit.letter());
        return s;
    }

    pub fn symbol_string(&self) -> String {
        let mut s = String::from(self.rank.rank_char());
        s.push_str(self.suit.symbol());
        return s;
    }
}

pub fn cards_from_str(s: &str) -> Result<Vec<Card>, CardError> {
    let mut cards: Vec<Card> = Vec::new();
    for cs in s.split_whitespace() {
        cards.push(Card::from(&cs)?);
    }
    return Ok(cards);
}

pub fn symbol_str_from_cards(cards: &[Card]) -> String {
    let mut s = String::new();
    for (i, c) in cards.iter().enumerate() {
        if i > 0 {
            s.push_str(" ");
        }
        s.push_str(&c.symbol_string());
    }
    return s;
}

pub fn for_each_card(mut f: impl FnMut(&Card)) {
    for r in 2..=14 {
        let rank = Rank::num(r);
        f(&Card::new(rank, Suit::Clubs));
        f(&Card::new(rank, Suit::Diamonds));
        f(&Card::new(rank, Suit::Hearts));
        f(&Card::new(rank, Suit::Spades));
    }
}

pub struct Deck {
    pub cards: Vec<Card>,
}

impl Deck {
    pub fn new() -> Deck {
        let mut cards: Vec<Card> = Vec::new();
        for_each_card(|c| cards.push(*c));
        return Deck { cards: cards };
    }

    pub fn shuffle(&mut self, mut rng: impl Rng) {
        self.cards.shuffle(&mut rng);
    }
}

pub fn suit_group(cards: &[Card], suit: Suit) -> String {
    let mut s = String::from(suit.symbol());
    for r in ranks_for_suit(cards, suit).iter() {
        s.push_str(r.rank_char());
    }
    return s;
}

pub fn all_suit_groups(cards: &[Card]) -> String {
    return format!(
        "{} {} {} {}",
        suit_group(&cards, Suit::Spades),
        suit_group(&cards, Suit::Hearts),
        suit_group(&cards, Suit::Diamonds),
        suit_group(&cards, Suit::Clubs)
    );
}

// Returns the ranks of cards in the given suit, sorted descending.
pub fn ranks_for_suit(cards: &[Card], suit: Suit) -> Vec<Rank> {
    let mut ranks: Vec<Rank> = vec![];
    for &c in cards.iter() {
        if c.suit == suit {
            ranks.push(c.rank);
        }
    }
    ranks.sort();
    ranks.reverse();
    return ranks;
}

pub fn random_from_set<T>(items: &HashSet<T>, mut rng: impl Rng) -> &T {
    let n: usize = rng.gen_range(0, items.len());
    let mut ci = items.iter();
    for _i in 0..n {
        ci.next();
    }
    return ci.next().unwrap();
}

#[derive(Debug)]
pub struct CardDistributionPlayerConstraint {
    pub num_cards: usize,
    pub voided_suits: HashSet<Suit>,
    pub fixed_cards: HashSet<Card>,
}

pub struct CardDistributionRequest {
    pub cards: Vec<Card>,
    pub constraints: Vec<CardDistributionPlayerConstraint>,
    // It is legal if the CardDistributionPlayerConstraint for player i has a
    // fixed card that is not in `cards`.
}

fn _possible_card_distribution(
    req: &CardDistributionRequest,
    mut rng: impl Rng,
) -> Result<Vec<Vec<Card>>, CardError> {
    let num_players = req.constraints.len();
    let mut result: Vec<Vec<Card>> = Vec::new();
    let mut legal_cards: Vec<HashSet<Card>> = Vec::new();
    // Create sets of possible cards for each player.
    for (i, cs) in req.constraints.iter().enumerate() {
        let mut legal_for_player: HashSet<Card> = HashSet::new();
        // Add cards in suits that the player isn't known to be out of.
        for &c in req.cards.iter() {
            if !cs.voided_suits.contains(&c.suit) {
                legal_for_player.insert(c);
            }
        }
        // Remove cards that are fixed to other players.
        for (j, other_cs) in req.constraints.iter().enumerate() {
            if i != j {
                for &c in other_cs.fixed_cards.iter() {
                    legal_for_player.remove(&c);
                }
            }
        }
        legal_cards.push(legal_for_player);
        result.push(Vec::new());
    }
    // Assign cards randomly according to constraints.
    loop {
        let mut took_all = false;
        for i in 0..num_players {
            // If any player's remaining cards are forced, take them all.
            let num_to_fill = req.constraints[i].num_cards - result[i].len();
            if num_to_fill > 0 {
                let num_legal = legal_cards[i].len();
                if num_to_fill > num_legal {
                    return Err(CardError::new("Cannot satisfy constraints"));
                }
                if num_to_fill == num_legal {
                    let taken_cards = legal_cards[i].clone();
                    for &c in taken_cards.iter() {
                        result[i].push(c);
                    }
                    for &c in taken_cards.iter() {
                        for j in 0..num_players {
                            legal_cards[j].remove(&c);
                        }
                    }
                    took_all = true;
                    break;
                }
            }
        }
        if took_all {
            continue;
        }
        // Nobody had a forced pick, choose one card for one player.
        let mut chose_card = false;
        for i in 0..num_players {
            let num_to_fill = req.constraints[i].num_cards - result[i].len();
            if num_to_fill > 0 {
                let c = *random_from_set(&legal_cards[i], &mut rng);
                result[i].push(c);
                for j in 0..num_players {
                    legal_cards[j].remove(&c);
                }
                chose_card = true;
                break;
            }
        }
        if !chose_card {
            // We've have assigned all the cards.
            break;
        }
    }
    return Ok(result);
}

pub fn possible_card_distribution(
    req: &CardDistributionRequest,
    mut rng: impl Rng,
) -> Result<Vec<Vec<Card>>, CardError> {
    for _ in 0..10000 {
        let result = _possible_card_distribution(req, &mut rng);
        if result.is_ok() {
            return result;
        }
    }
    println!("cards: {}", all_suit_groups(&req.cards));
    println!("constraints: {:?}", &req.constraints);
    return Err(CardError::new(
        "Cannot satisfy constraints after 10000 attempts",
    ));
}

#[cfg(test)]
mod test {
    use super::*;
    use rand::rngs::StdRng;
    use rand::SeedableRng;

    fn c(s: &str) -> Card {
        Card::from(s).unwrap()
    }

    fn cv(s: &str) -> Vec<Card> {
        cards_from_str(s).unwrap()
    }

    #[test]
    fn test_parse() {
        assert_eq!(
            Card::from("6H").unwrap(),
            Card::new(Rank::num(6), Suit::Hearts)
        );
        assert_eq!(
            Card::from("tc").unwrap(),
            Card::new(Rank::num(10), Suit::Clubs)
        );
        assert_eq!(
            Card::from("Q♠").unwrap(),
            Card::new(Rank::QUEEN, Suit::Spades)
        );
    }

    #[test]
    fn test_parse_multiple() {
        let actual = cards_from_str(" 2C TD  AS\tQ♥\n ").unwrap();
        let expected = vec![
            Card::new(Rank::num(2), Suit::Clubs),
            Card::new(Rank::num(10), Suit::Diamonds),
            Card::new(Rank::ACE, Suit::Spades),
            Card::new(Rank::QUEEN, Suit::Hearts),
        ];
        assert_eq!(actual, expected);
    }

    #[test]
    fn test_bad_parse() {
        let bad = vec!["J", "1H", "ZH", "S5", "AA", "DD"];
        for &bs in bad.iter() {
            match Card::from(bs) {
                Ok(_c) => assert!(false),
                Err(_e) => {}
            }
        }
    }

    #[test]
    fn test_card() {
        let c1 = Card::new(Rank::num(3), Suit::Clubs);
        let c2 = Card::new(Rank::num(3), Suit::Clubs);
        let c3 = Card::new(Rank::num(3), Suit::Hearts);
        let c4 = Card::new(Rank::QUEEN, Suit::Clubs);
        assert_eq!(c1, c2);
        assert_ne!(c1, c3);
        assert_ne!(c1, c4);
        assert_eq!(c1.rank.rank_char(), "3");
        assert_eq!(c1.ascii_string(), "3C");
        assert_eq!(c1.symbol_string(), "3♣");
        assert_eq!(c4.ascii_string(), "QC");
        assert_eq!(c4.symbol_string(), "Q♣");
    }

    #[test]
    fn test_hand_suits() {
        let c1 = Card::new(Rank::num(7), Suit::Hearts);
        let c2 = Card::new(Rank::ACE, Suit::Hearts);
        let c3 = Card::new(Rank::KING, Suit::Spades);
        let c4 = Card::new(Rank::num(2), Suit::Hearts);
        let c5 = Card::new(Rank::num(10), Suit::Hearts);
        let hand = vec![c1, c2, c3, c4, c5];
        assert_eq!(ranks_for_suit(&hand, Suit::Diamonds).len(), 0);
        assert_eq!(ranks_for_suit(&hand, Suit::Spades), [Rank::KING]);
        assert_eq!(
            ranks_for_suit(&hand, Suit::Hearts),
            [Rank::ACE, Rank::num(10), Rank::num(7), Rank::num(2)]
        );
    }

    fn make_constraints(n: usize, num_cards: usize) -> Vec<CardDistributionPlayerConstraint> {
        let mut c: Vec<CardDistributionPlayerConstraint> = Vec::new();
        for i in 0..n {
            c.push(CardDistributionPlayerConstraint {
                num_cards: num_cards,
                voided_suits: HashSet::new(),
                fixed_cards: HashSet::new(),
            });
        }
        return c;
    }

    #[test]
    fn test_card_distribution_no_constraints() {
        let mut rng: StdRng = SeedableRng::seed_from_u64(42);
        let deck = Deck::new();
        let req = CardDistributionRequest {
            cards: deck.cards.clone(),
            constraints: make_constraints(4, 13),
        };
        let dist = possible_card_distribution(&req, &mut rng).unwrap();
        assert_eq!(dist.len(), 4);
        for cards in dist.iter() {
            assert_eq!(cards.len(), 13);
        }
    }

    #[test]
    fn test_card_distribution_void_suits() {
        let mut rng: StdRng = SeedableRng::seed_from_u64(42);
        let cards = cv("2C 2D 2H 2S 3C 3D 3H 3S 4C 4D 4H 4S");
        let mut constraints = make_constraints(4, 3);
        constraints[0].voided_suits.insert(Suit::Spades);
        constraints[2].voided_suits.insert(Suit::Spades);
        constraints[2].voided_suits.insert(Suit::Hearts);
        constraints[2].voided_suits.insert(Suit::Diamonds);
        let req = CardDistributionRequest {
            cards: cards,
            constraints: constraints,
        };
        let dist = _possible_card_distribution(&req, &mut rng).unwrap();
        assert_eq!(dist.len(), 4);
        for cards in dist.iter() {
            assert_eq!(cards.len(), 3);
        }
        assert_eq!(ranks_for_suit(&dist[0], Suit::Spades), []);
        assert_eq!(
            ranks_for_suit(&dist[2], Suit::Clubs),
            [Rank::num(4), Rank::num(3), Rank::num(2)]
        );
    }

    #[test]
    fn test_card_distribution_fixed_cards() {
        let mut rng: StdRng = SeedableRng::seed_from_u64(42);
        let cards = cv("2C 2D 2H 2S 3C 3D 3H 3S 4C 4D 4H 4S");
        let mut constraints = make_constraints(4, 3);
        constraints[1].fixed_cards.insert(c("2H"));
        constraints[3].fixed_cards.insert(c("3D"));
        constraints[3].fixed_cards.insert(c("4D"));
        constraints[3].fixed_cards.insert(c("AD"));
        let req = CardDistributionRequest {
            cards: cards,
            constraints: constraints,
        };
        let dist = possible_card_distribution(&req, &mut rng).unwrap();
        assert_eq!(dist.len(), 4);
        for cards in dist.iter() {
            assert_eq!(cards.len(), 3);
        }
        assert!(dist[1].contains(&c("2H")));
        assert!(dist[3].contains(&c("3D")));
        assert!(dist[3].contains(&c("4D")));
        assert!(!dist[3].contains(&c("AD")));
    }

    #[test]
    #[ignore]
    fn test_card_distribution_combination() {
        let mut rng: StdRng = SeedableRng::seed_from_u64(42);
        let cards = cv("AS KS QS JS TS 9S AH KH QH");
        let mut constraints = make_constraints(3, 3);
        constraints[1].voided_suits.insert(Suit::Hearts);
        constraints[2].voided_suits.insert(Suit::Hearts);
        let req = CardDistributionRequest {
            cards: cards,
            constraints: constraints,
        };
        // Players 1 and 2 have no hearts, so they must have all the spades
        // between them, so player 0 can't have spades. Unfortunately the
        // algorithm can't determine this yet.
        let dist = _possible_card_distribution(&req, &mut rng).unwrap();
        assert!(dist[0].contains(&c("AH")));
        assert!(dist[0].contains(&c("KH")));
        assert!(dist[0].contains(&c("QH")));
    }
}
