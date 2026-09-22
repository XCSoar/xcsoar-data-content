"""Tests for the OpenAir content validation shared by the checks and the sync."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script" / "lib"))

from openair_content import (  # noqa: E402
    count_airspaces,
    describe,
    looks_like_openair,
)

ONE_AIRSPACE = """\
AC R
AN EDR Muenchen
AL GND
AH FL100
DP 50:00:00 N 010:00:00 E
DP 51:00:00 N 011:00:00 E
DP 51:00:00 N 010:00:00 E
"""

# daec.de answers a missing file with HTTP 200 and exactly this body.
TYPO3_ERROR_BODY = "Invalid error handler configuration: t3://page?uid=144"


class CountAirspacesTest(unittest.TestCase):
    def test_counts_a_single_airspace(self):
        self.assertEqual(count_airspaces(ONE_AIRSPACE), (1, 0))

    def test_counts_repeated_airspaces(self):
        self.assertEqual(count_airspaces(ONE_AIRSPACE * 3)[0], 3)

    def test_error_page_holds_no_airspace(self):
        airspaces, errors = count_airspaces(TYPO3_ERROR_BODY)
        self.assertEqual(airspaces, 0)
        self.assertGreater(errors, 0)

    def test_empty_payload(self):
        self.assertEqual(count_airspaces(""), (0, 0))


class LooksLikeOpenAirTest(unittest.TestCase):
    def test_accepts_a_single_airspace_file(self):
        # data/content/airspace/country/DE-ASP-Military-Low-Flying.txt holds one.
        self.assertTrue(looks_like_openair(ONE_AIRSPACE))

    def test_rejects_the_typo3_error_body(self):
        self.assertFalse(looks_like_openair(TYPO3_ERROR_BODY))

    def test_rejects_an_html_error_page(self):
        self.assertFalse(looks_like_openair("<html><body><h1>404 Not Found</h1></body></html>"))

    def test_rejects_an_empty_payload(self):
        self.assertFalse(looks_like_openair(""))

    def test_minimum_is_configurable(self):
        self.assertFalse(looks_like_openair(ONE_AIRSPACE, minimum=2))
        self.assertTrue(looks_like_openair(ONE_AIRSPACE * 2, minimum=2))


class DescribeTest(unittest.TestCase):
    def test_reports_counts(self):
        self.assertEqual(describe(ONE_AIRSPACE), "1 airspaces, 0 parse errors")


if __name__ == "__main__":
    unittest.main()
