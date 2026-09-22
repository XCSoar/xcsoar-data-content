"""Tests for the OpenAir content validation shared by the checks and the sync."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script" / "lib"))

from openair_content import (  # noqa: E402
    count_airspace_blocks,
    count_airspaces,
    describe,
    is_clean_openair,
    looks_like_openair,
)

# Latitude in degrees/minutes/seconds, longitude in degrees/decimal minutes on
# the same line -- forbidden by the format specification, accepted by XCSoar,
# and the defect this check has to catch.
MIXED_COORDINATES = """\
AC Q
AN Klaver_lines
AL GND
AH 5000 FT AGL
DP 31:45:06 S 18:41.3712 E
DP 31:45.2398 S 18:40.2698 E
DP 31:45.7721 S 18:40.4376 E
"""

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

    def test_rejects_mixed_coordinate_notations(self):
        # The format specification is explicit: "Do not mix DMS and DDM
        # notations."  XCSoar reads such a file anyway, which is why the check
        # cannot take XCSoar as its standard.
        self.assertFalse(looks_like_openair(MIXED_COORDINATES))
        self.assertEqual(count_airspaces(MIXED_COORDINATES)[0], 0)
        self.assertEqual(count_airspace_blocks(MIXED_COORDINATES), 1)

    def test_rejects_the_typo3_error_body(self):
        self.assertFalse(looks_like_openair(TYPO3_ERROR_BODY))

    def test_rejects_an_html_error_page(self):
        self.assertFalse(looks_like_openair("<html><body><h1>404 Not Found</h1></body></html>"))

    def test_rejects_an_empty_payload(self):
        self.assertFalse(looks_like_openair(""))

    def test_minimum_is_configurable(self):
        self.assertFalse(looks_like_openair(ONE_AIRSPACE, minimum=2))
        self.assertTrue(looks_like_openair(ONE_AIRSPACE * 2, minimum=2))


class IsCleanOpenAirTest(unittest.TestCase):
    def test_a_clean_file_passes_both_tests(self):
        self.assertTrue(looks_like_openair(ONE_AIRSPACE))
        self.assertTrue(is_clean_openair(ONE_AIRSPACE))

    def test_a_damaged_record_fails_only_the_strict_test(self):
        # One good airspace and one with a coordinate no parser accepts: the
        # file still carries airspace, so a third-party URI serving it is not
        # treated as dead, but a file we ship has to be repaired.
        damaged = ONE_AIRSPACE + MIXED_COORDINATES
        self.assertTrue(looks_like_openair(damaged))
        self.assertFalse(is_clean_openair(damaged))

    def test_an_error_page_fails_both(self):
        self.assertFalse(looks_like_openair(TYPO3_ERROR_BODY))
        self.assertFalse(is_clean_openair(TYPO3_ERROR_BODY))


class DescribeTest(unittest.TestCase):
    def test_a_clean_file_reads_plainly(self):
        self.assertEqual(describe(ONE_AIRSPACE), "1 airspaces")

    def test_a_file_aerofiles_cannot_read_says_so(self):
        # How many errors aerofiles reports before giving up on an airspace is
        # its own business; what the log has to carry is that it read none and
        # that the bbox is therefore missing.
        verdict = describe(MIXED_COORDINATES)
        self.assertIn("1 airspace blocks", verdict)
        self.assertIn("aerofiles read 0", verdict)
        self.assertIn("no bbox", verdict)


if __name__ == "__main__":
    unittest.main()
