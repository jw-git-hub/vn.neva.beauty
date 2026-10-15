import unittest

from bs4 import BeautifulSoup

import check_prices

PAGE = """<div class="pricelist__panel">
  <div class="pricelist__row"><span class="pricelist__price">150 000 đ</span></div>
  <li class="combo"><div class="combo__price">1 600 000 đ</div></li>
  <div class="pricelist__row"><span class="pricelist__price">200 000 đ</span></div>
</div>"""


class PositionTest(unittest.TestCase):
    def test_sequence_follows_document_order(self):
        self.assertEqual(check_prices.price_sequence(BeautifulSoup(PAGE, "html.parser")),
                         ["150 000 đ", "1 600 000 đ", "200 000 đ"])

    def test_equal_sequences_pass(self):
        self.assertEqual(check_prices.position_mismatches(["1 đ", "2 đ"], ["1 đ", "2 đ"]), [])

    def test_swapped_prices_are_named(self):
        self.assertEqual(check_prices.position_mismatches(["1 đ", "2 đ"], ["2 đ", "1 đ"]),
                         [(0, "1 đ", "2 đ"), (1, "2 đ", "1 đ")])

    def test_missing_row_is_named(self):
        self.assertEqual(check_prices.position_mismatches(["1 đ", "2 đ"], ["1 đ"]),
                         [(1, "2 đ", None)])
