use crate::card::*;
use crate::hearts;
use crate::hearts_ai;

use serde::{Serialize, Deserialize};
use serde_json;

#[derive(Debug)]
pub struct ParseError {
    pub msg: String,
}

impl ParseError {
    pub fn new(s: &str) -> Self {
        return ParseError {msg: s.to_string()};
    }
}

impl From<CardError> for ParseError {
    fn from(error: CardError) -> Self {
        return ParseError::new(&error.msg);
    }
}

impl From<serde_json::error::Error> for ParseError {
    fn from(error: serde_json::error::Error) -> Self {
        return ParseError::new(&format!("{}", error));
    }
}


#[derive(Deserialize)]
struct JsonTrick {
    leader: usize,
    cards: String,
}

impl JsonTrick {
    fn to_trick(&self) -> Result<hearts::Trick, CardError> {
        let cards = cards_from_str(&self.cards)?;
        let winner = (self.leader + hearts::trick_winner_index(&cards)) % cards.len();
        return Ok(hearts::Trick {
            leader: self.leader,
            cards: cards,
            winner: winner,
        });
    }

    fn to_trick_in_progress(&self) -> Result<hearts::TrickInProgress, CardError> {
        return Ok(hearts::TrickInProgress {
            leader: self.leader,
            cards: cards_from_str(&self.cards)?,
        });
    }
}

#[derive(Deserialize)]
struct JsonCardToPlayRequest {
    // TODO: rules, passed cards, match score.
    hand: String,
    prev_tricks: Vec<JsonTrick>,
    current_trick: JsonTrick,
}

impl JsonCardToPlayRequest {
    fn to_request(&self) -> Result<hearts_ai::CardToPlayRequest, CardError> {
        let mut prev_tricks: Vec<hearts::Trick> = Vec::new();
        for jt in self.prev_tricks.iter() {
            prev_tricks.push(jt.to_trick()?);
        }
        return Ok(hearts_ai::CardToPlayRequest {
            rules: hearts::RuleSet::default(),
            hand: cards_from_str(&self.hand)?,
            prev_tricks: prev_tricks,
            current_trick: self.current_trick.to_trick_in_progress()?,
        });
    }
}

pub fn parse_card_to_play_request(s: &str) -> Result<hearts_ai::CardToPlayRequest, ParseError> {
    let req: JsonCardToPlayRequest = serde_json::from_str(s)?;
    return Ok(req.to_request()?);
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn test_parse_request() {
        let req = parse_card_to_play_request(r#"
            {
                "hand": "2C 8D AS",
                "prev_tricks": [],
                "current_trick": {"leader": 0, "cards": ""}
            }
        "#).unwrap();
        assert_eq!(req.hand.len(), 3);
    }
}
