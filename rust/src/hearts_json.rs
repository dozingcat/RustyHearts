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

    fn to_tricks(jts: &[JsonTrick]) -> Result<Vec<hearts::Trick>, CardError> {
        let mut tricks: Vec<hearts::Trick> = Vec::new();
        for jt in jts.iter() {
            tricks.push(jt.to_trick()?);
        }
        return Ok(tricks);
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
        return Ok(hearts_ai::CardToPlayRequest {
            rules: hearts::RuleSet::default(),
            hand: cards_from_str(&self.hand)?,
            prev_tricks: JsonTrick::to_tricks(&self.prev_tricks)?,
            current_trick: self.current_trick.to_trick_in_progress()?,
        });
    }
}

pub struct TrickHistory {
    pub rules: hearts::RuleSet,
    pub tricks: Vec<hearts::Trick>,
}

impl TrickHistory {
    pub fn points_taken(&self) -> Vec<i32> {
        return hearts::points_taken(&self.tricks, &self.rules);
    }
}

#[derive(Deserialize)]
struct JsonTrickHistory {
    // TODO: rules
    tricks: Vec<JsonTrick>,
}

impl JsonTrickHistory {
    fn to_history(&self) -> Result<TrickHistory, ParseError> {
        return Ok(TrickHistory {
            rules: hearts::RuleSet::default(),
            tricks: JsonTrick::to_tricks(&self.tricks)?,
        });
    }
}

pub fn parse_card_to_play_request(s: &str) -> Result<hearts_ai::CardToPlayRequest, ParseError> {
    let req: JsonCardToPlayRequest = serde_json::from_str(s)?;
    return Ok(req.to_request()?);
}

pub fn parse_trick_history(s: &str) -> Result<TrickHistory, ParseError> {
    let j: JsonTrickHistory = serde_json::from_str(s)?;
    return Ok(j.to_history()?);
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

    #[test]
    fn test_parse_tricks() {
        let empty = parse_trick_history(r#"{"tricks": []}"#).unwrap();
        assert_eq!(empty.points_taken(), vec![0, 0, 0, 0]);

        let history = parse_trick_history(r#"
            {
                "tricks": [
                    {"leader": 2, "cards": "2C AC QC KC"},
                    {"leader": 3, "cards": "2S 5S AS QS"},
                    {"leader": 1, "cards": "2D 9H KD AH"}
                ]
            }
        "#).unwrap();
        assert_eq!(history.points_taken(), vec![0, 13, 0, 2]);
    }
}
