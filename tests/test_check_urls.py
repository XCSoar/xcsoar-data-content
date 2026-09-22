"""Tests for repository manifest parsing used by the URI check."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script" / "check"))

from check_urls import _BLOCKED_STATUS, is_airspace_text, iter_records  # noqa: E402

MANIFEST = """\
# Data location: remote, type: airspace, geography: country.

name=DE-ASP-National-DAEC.txt
uri=https://www.daec.de/media/x/2026_09_Airspace_Germany_OA1.txt
type=airspace
area=de
update=2026-09-15
description=Airspace Germany from DAEC

name=DE-WPT-National-XCSoar.cup
uri=http://download.xcsoar.org/content/waypoint/country/DE-WPT-National-XCSoar.cup
type=waypoint
area=de
update=2026-01-01
"""


class IterRecordsTest(unittest.TestCase):
    def test_splits_on_name_and_keeps_fields(self):
        records = list(iter_records(MANIFEST.splitlines()))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["name"], "DE-ASP-National-DAEC.txt")
        self.assertEqual(records[0]["type"], "airspace")
        self.assertEqual(records[0]["description"], "Airspace Germany from DAEC")
        self.assertEqual(records[1]["type"], "waypoint")

    def test_ignores_comments_and_blank_lines(self):
        self.assertEqual(len(list(iter_records(["# comment", "", "  "]))), 0)

    def test_keeps_a_value_containing_an_equals_sign(self):
        records = list(iter_records(["name=x", "uri=https://e.org/a?b=c&d=e"]))
        self.assertEqual(records[0]["uri"], "https://e.org/a?b=c&d=e")


class IsAirspaceTextTest(unittest.TestCase):
    def test_airspace_txt_is_content_checked(self):
        self.assertTrue(
            is_airspace_text({"type": "airspace", "uri": "https://e.org/a.txt"})
        )

    def test_query_string_does_not_hide_the_suffix(self):
        self.assertTrue(
            is_airspace_text({"type": "airspace", "uri": "https://e.org/a.txt?v=2"})
        )

    def test_other_types_are_left_to_head(self):
        self.assertFalse(
            is_airspace_text({"type": "waypoint", "uri": "https://e.org/a.txt"})
        )

    def test_non_text_airspace_is_left_to_head(self):
        # Airspace also ships as .sua and other formats this parser does not read.
        self.assertFalse(
            is_airspace_text({"type": "airspace", "uri": "https://e.org/a.sua"})
        )


class BlockedStatusTest(unittest.TestCase):
    def test_waf_refusals_are_not_dead_links(self):
        # gliding.co.nz answers 403 to every path including / and /robots.txt
        # from a data centre; aip.net.nz answers 200 with an Incapsula block
        # page.  Only the first is visible in the status code.
        self.assertIn(403, _BLOCKED_STATUS)
        self.assertIn(429, _BLOCKED_STATUS)

    def test_real_errors_still_fail(self):
        self.assertNotIn(404, _BLOCKED_STATUS)
        self.assertNotIn(500, _BLOCKED_STATUS)


if __name__ == "__main__":
    unittest.main()
