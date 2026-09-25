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
