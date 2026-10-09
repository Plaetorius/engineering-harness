import unittest
from example import discounted_price


class PriceTest(unittest.TestCase):
    def test_twenty_percent_discount(self):
        self.assertEqual(discounted_price(100, 20), 80)
