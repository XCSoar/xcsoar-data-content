"""Tests for DAeC OpenAir URL discovery used by the airspace URI sync."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script" / "sync"))

from daec_airspace_urls import (  # noqa: E402
    effective_date,
    pick_border,
    pick_national,
)

PAGE = "https://www.daec.de/fachbereiche/luftraum-flugsicherheit-betrieb/luftraumdaten/"
MEDIA = "https://www.daec.de/media/files/Dateien/Fachbereiche/Luftraum_und_Flugsicherheit"


class EffectiveDateTest(unittest.TestCase):
    def test_headers_seen_in_released_files(self):
        # The day of month is not fixed across releases.
        self.assertEqual(effective_date("* effective from 19th March 2026"), "2026-03-19")
        self.assertEqual(effective_date("* effective from 15th June 2026"), "2026-06-15")
        self.assertEqual(effective_date("* effective from 15th September 2026"), "2026-09-15")

    def test_ordinal_suffix_is_optional(self):
        self.assertEqual(effective_date("* effective from 1 May 2027"), "2027-05-01")

    def test_rejects_unreadable_header(self):
        self.assertIsNone(effective_date("* no date here"))
        self.assertIsNone(effective_date("* effective from 15th Smarch 2026"))
        self.assertIsNone(effective_date("* effective from 40th June 2026"))


class PickNationalTest(unittest.TestCase):
    def test_picks_the_newest_release(self):
        html = (
            f'<a href="{MEDIA}/2026_03_Airspace_Germany_OA1.txt">March</a>'
            f'<a href="{MEDIA}/2026_09_Airspace_Germany_OA1.txt">September</a>'
            f'<a href="{MEDIA}/2025_12_Airspace_Germany_OA2.txt">older</a>'
        )
        self.assertEqual(
            pick_national(html, PAGE),
            f"{MEDIA}/2026_09_Airspace_Germany_OA1.txt",
        )

    def test_resolves_a_relative_href(self):
        html = '<a href="/media/x/2026_09_Airspace_Germany_OA1.txt">x</a>'
        self.assertEqual(
            pick_national(html, PAGE),
            "https://www.daec.de/media/x/2026_09_Airspace_Germany_OA1.txt",
        )

    def test_ignores_unrelated_links(self):
        self.assertIsNone(pick_national('<a href="/media/x/UpdateLX7007-DE_ALL25.zip">z</a>', PAGE))


class PickBorderTest(unittest.TestCase):
    def test_finds_the_border_outline(self):
        html = '<a href="/media/files/2012/service/luftraumdaten/Grenze_Deutschland.txt">border</a>'
        self.assertEqual(
            pick_border(html, PAGE),
            "https://www.daec.de/media/files/2012/service/luftraumdaten/Grenze_Deutschland.txt",
        )

    def test_missing_border_link(self):
        self.assertIsNone(pick_border("<a href='/media/x/other.txt'>o</a>", PAGE))


if __name__ == "__main__":
    unittest.main()
