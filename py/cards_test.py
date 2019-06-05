import unittest

from cards import Card, Deck, Rank, Suit

class TestCards(unittest.TestCase):

    def test_suit(self):
        self.assertEqual(Suit.parse('C'), Suit.CLUBS)
        self.assertEqual(Suit.parse('♥'), Suit.HEARTS)
        with self.assertRaises(ValueError):
            Suit.parse('Q')

    def test_rank(self):
        self.assertEqual(Rank.parse(4), Rank.FOUR)
        self.assertEqual(Rank.parse('Q'), Rank.QUEEN)
        with self.assertRaises(ValueError):
            Rank.parse(1)
        with self.assertRaises(ValueError):
            Rank.parse('C')

    def test_card(self):
        c1 = Card(rank=Rank.QUEEN, suit=Suit.SPADES)
        self.assertEqual('QS', c1.ascii_string())
        self.assertEqual('Q♠', c1.symbol_string())
        with self.assertRaises(Exception):
            c1.rank = Rank.KING

        c2 = Card(rank=Rank.TWO, suit=Suit.CLUBS)
        self.assertNotEqual(c1, c2)
        self.assertEqual(c2, Card.parse('2C'))
        self.assertEqual(c2, Card.parse('2♣'))

        with self.assertRaises(ValueError):
            Card.parse('A')
        with self.assertRaises(ValueError):
            Card.parse('9X')

    def test_deck(self):
        deck = Deck()
        deck.shuffle()

        hands = deck.deal(4)
        self.assertTrue({13}, set(len(h) for h in hands))
        self.assertEqual(52, len(set(sum(hands, []))))

        hands = deck.deal(3)
        self.assertTrue({17}, set(len(h) for h in hands))
        self.assertEqual(51, len(set(sum(hands, []))))

        hands = deck.deal(10, 2)
        self.assertTrue({2}, set(len(h) for h in hands))
        self.assertEqual(20, len(set(sum(hands, []))))


if __name__ == '__main__':
    unittest.main()
