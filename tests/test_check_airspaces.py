"""Tests for how the airspace check expands its command line arguments."""

from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script" / "check"))

from check_airspaces import iter_airspace_files, main  # noqa: E402

ONE_AIRSPACE = """\
AC R
AN EDR Muenchen
AL GND
AH FL100
DP 50:00:00 N 010:00:00 E
DP 51:00:00 N 011:00:00 E
DP 51:00:00 N 010:00:00 E
"""

# Latitude in degrees/minutes/seconds, longitude in degrees/decimal minutes on
# the same line -- forbidden by the format specification, accepted by XCSoar,
# and the defect the strict check exists for: the file holds real airspace
# beside it, so only the parse errors give it away.
MIXED_COORDINATES = """\
AC Q
AN Klaver_lines
AL GND
AH 5000 FT AGL
DP 31:45:06 S 18:41.3712 E
DP 31:45.2398 S 18:40.2698 E
DP 31:45.7721 S 18:40.4376 E
"""

# What the DAeC server actually served in place of airspace.
TYPO3_ERROR_BODY = "Invalid error handler configuration: t3://page?uid=144"


class IterAirspaceFilesTest(unittest.TestCase):
    def test_a_directory_expands_to_its_txt_files(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.txt").write_text(ONE_AIRSPACE)
            (Path(d) / "nested").mkdir()
            (Path(d) / "nested" / "b.txt").write_text(ONE_AIRSPACE)
            paths, empty = iter_airspace_files([d])
            self.assertEqual([p.name for p in paths], ["a.txt", "b.txt"])
            self.assertEqual(empty, [])

    def test_a_directory_without_txt_is_reported_not_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "readme.md").write_text("nothing here")
            paths, empty = iter_airspace_files([d])
            self.assertEqual(paths, [])
            self.assertEqual(empty, [Path(d)])

    def test_a_file_argument_is_taken_as_given(self):
        paths, empty = iter_airspace_files(["some/file.txt"])
        self.assertEqual(paths, [Path("some/file.txt")])
        self.assertEqual(empty, [])


class MainTest(unittest.TestCase):
    def test_a_file_that_is_not_airspace_fails(self):
        # main() has to carry a check_file() verdict out to the exit status.
        # Everything else here exercises the argument expansion, so a
        # regression that collected the verdicts and then ignored them would
        # leave the rest of this file green.
        with tempfile.TemporaryDirectory() as d:
            broken = Path(d) / "broken.txt"
            broken.write_text(TYPO3_ERROR_BODY)
            self.assertEqual(main([str(broken)]), 1)

    def test_a_damaged_record_beside_a_good_one_fails(self):
        # The file this repository ships has to parse without a single error,
        # which is a stricter promise than "holds some airspace".  Without a
        # file that satisfies the lenient test and fails the strict one,
        # check_file() could be downgraded to looks_like_openair() and every
        # test here would still pass.
        with tempfile.TemporaryDirectory() as d:
            mixed = Path(d) / "mixed.txt"
            mixed.write_text(ONE_AIRSPACE + MIXED_COORDINATES)
            self.assertEqual(main([str(mixed)]), 1)

    def test_an_empty_directory_fails_even_beside_a_good_file(self):
        # The case that prompted this: a readable file could mask a directory
        # that yielded nothing, and the run still reported success.
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "good.txt"
            good.write_text(ONE_AIRSPACE)
            empty = Path(d) / "empty"
            empty.mkdir()
            self.assertEqual(main([str(good), str(empty)]), 1)

    def test_a_good_file_alone_passes(self):
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "good.txt"
            good.write_text(ONE_AIRSPACE)
            self.assertEqual(main([str(good)]), 0)

    def test_no_arguments_at_all(self):
        self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
