import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from envlens.snapshots import CaptureError, capture, compare, load_all, parse_environment, save


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "XDG_DATA_HOME": self.temp.name + "/data",
            "XDG_STATE_HOME": self.temp.name + "/state",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_parse_nul_delimited_values(self):
        self.assertEqual(parse_environment(b"A=1\0B=two=three\0\0"), {"A": "1", "B": "two=three"})

    def test_capture_secret_is_never_persisted(self):
        record = capture(b"PATH=/usr/bin\0API_TOKEN=top-secret-value\0", "Terminal")
        serialized = json.dumps(record)
        self.assertNotIn("top-secret-value", serialized)
        self.assertEqual(record["variables"]["API_TOKEN"]["secret"], True)
        self.assertEqual(record["redacted_count"], 1)

    def test_secret_comparison_only_shows_equality(self):
        a = capture(b"API_TOKEN=same-value\0", "Terminal")
        b = capture(b"API_TOKEN=same-value\0", "IDE")
        c = capture(b"API_TOKEN=other-value\0", "Other")
        self.assertEqual(compare(a, b)[0][1], "same secret")
        self.assertEqual(compare(a, c)[0][1], "secret differs")
        self.assertNotIn("same-value", str(compare(a, b)))

    def test_capture_permissions_and_roundtrip(self):
        record = capture(b"PATH=/usr/bin\0", "Terminal")
        path = save(record)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(path.parent).stat().st_mode & 0o777, 0o700)
        self.assertEqual(load_all()[0]["label"], "Terminal")

    def test_compare_values_and_missing_variables(self):
        a = capture(b"PATH=/bin\0PWD=/work\0", "Shell")
        b = capture(b"PATH=/usr/bin\0NODE_OPTIONS=--trace-warnings\0", "IDE")
        rows = {row[0]: row[1] for row in compare(a, b)}
        self.assertEqual(rows, {"NODE_OPTIONS": "added", "PATH": "changed", "PWD": "missing"})

    def test_reject_bad_label_and_oversized_capture(self):
        with self.assertRaises(CaptureError):
            capture(b"A=1", " ")
        with self.assertRaises(CaptureError):
            parse_environment(b"A=" + b"x" * 1_048_577)


if __name__ == "__main__":
    unittest.main()
