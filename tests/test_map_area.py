"""Tests for country-area inference used by generated map manifests."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script" / "build"))

from map_area import guess_area  # noqa: E402


class GuessAreaTest(unittest.TestCase):
    def test_country_prefixes(self):
        self.assertEqual(guess_area("AUS_ADELAIDE"), "au")
        self.assertEqual(guess_area("US_COLORADO"), "us")
        self.assertEqual(guess_area("FRA_ALPS"), "fr")
        self.assertEqual(guess_area("Timor-Leste"), "tl")
        self.assertEqual(guess_area("Timor-Leste-Dili"), "tl")

    def test_historic_name_overrides(self):
        self.assertEqual(guess_area("UK"), "gb")
        self.assertEqual(guess_area("GER"), "de")
        self.assertEqual(guess_area("IRE"), "ie")
        self.assertEqual(guess_area("BUL"), "bg")
        self.assertEqual(guess_area("POR"), "pt")
        self.assertEqual(guess_area("Turkey"), "tr")

    def test_ambiguous_maps_remain_ungrouped(self):
        self.assertEqual(guess_area("ALPS"), "")
        self.assertEqual(guess_area("BEN_WGER"), "")
        self.assertEqual(guess_area("UNKNOWN_REGION"), "")


if __name__ == "__main__":
    unittest.main()
