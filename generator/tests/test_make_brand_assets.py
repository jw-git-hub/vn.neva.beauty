import unittest
from types import SimpleNamespace
from unittest import mock

import make_brand_assets


class MainDispatchTest(unittest.TestCase):
    def run_main(self, card):
        with mock.patch("make_brand_assets.parse_args", return_value=SimpleNamespace(card=card)), \
                mock.patch("make_brand_assets.build_card_of_language") as one_card, \
                mock.patch("make_brand_assets.build_all_assets") as everything:
            make_brand_assets.main()
        return one_card, everything

    def test_card_option_builds_only_card_of_that_language(self):
        one_card, everything = self.run_main("en")
        one_card.assert_called_once_with("en")
        everything.assert_not_called()

    def test_no_option_builds_all_assets(self):
        one_card, everything = self.run_main(None)
        everything.assert_called_once_with()
        one_card.assert_not_called()

    def test_unknown_language_is_named_in_the_error(self):
        with self.assertRaisesRegex(SystemExit, "'xx'"):
            make_brand_assets.build_card_of_language("xx")
