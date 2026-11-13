# Built-in tools let us test the real CLI without installing extra packages.
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


# Locate files from this test's own path so tests do not depend on the working folder.
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
TIMESTAMP = "2026-11-13T17:00:00Z"


# Group related checks so unittest can discover and run them automatically.
class PreflightTests(unittest.TestCase):
    # Launch only our fixed Python CLI; fixture contents never become commands.
    def run_cli(self, permit, action=None):
        if action is None:
            action = FIXTURES / "proposed_action.json"
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "preflight.py"),
             "--action", str(action), "--permit", str(permit), "--at", TIMESTAMP],
            capture_output=True, text=True, timeout=5, check=False,
        )

    # Check the complete public result, including the timestamp and exit code.
    def assert_result(self, result, status, reason, exit_code):
        self.assertEqual(result.returncode, exit_code)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {
            "status": status, "reason": reason, "evaluated_at": TIMESTAMP,
        })
        self.assertEqual(len(result.stdout.splitlines()), 1)

    # A matching identity must pass this one check.
    def test_matching_executor(self):
        result = self.run_cli(FIXTURES / "matching_permit.json")
        self.assert_result(result, "PASS", "EXECUTOR_MATCH", 0)

    # A different identity must receive the documented rejection reason.
    def test_wrong_executor(self):
        result = self.run_cli(FIXTURES / "wrong_executor_permit.json")
        self.assert_result(result, "REJECT", "EXECUTOR_MISMATCH", 1)

    # Temporary files exercise bad inputs without modifying the approved fixtures.
    def test_invalid_records_in_either_position(self):
        invalid_records = [
            "{", "[]", "null", "{}", '{"executor_id": null}',
            '{"executor_id": 7}', '{"executor_id": true}',
            '{"executor_id": ""}', '{"executor_id": "   "}',
        ]
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            for content in invalid_records:
                invalid.write_text(content, encoding="utf-8")
                for position in ("action", "permit"):
                    # A subtest identifies exactly which bad input failed a check.
                    with self.subTest(content=content, position=position):
                        permit = FIXTURES / "matching_permit.json"
                        action = FIXTURES / "proposed_action.json"
                        if position == "action":
                            action = invalid
                        else:
                            permit = invalid
                        result = self.run_cli(permit, action)
                        self.assert_result(result, "REJECT", "INVALID_INPUT", 1)

    # A missing file must be rejected rather than treated as an empty permit.
    def test_unreadable_record(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(Path(directory) / "missing.json")
            self.assert_result(result, "REJECT", "INVALID_INPUT", 1)

    # Invalid UTF-8 means the bytes cannot be read as the required text format.
    def test_invalid_text_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_bytes(b"\xff")
            self.assert_result(self.run_cli(invalid), "REJECT", "INVALID_INPUT", 1)

    # Byte-for-byte comparison proves these runs leave all three fixtures unchanged.
    def test_fixtures_unchanged(self):
        before = {path: path.read_bytes() for path in FIXTURES.glob("*.json")}
        self.assertEqual(len(before), 3)
        self.assert_result(self.run_cli(FIXTURES / "matching_permit.json"),
                           "PASS", "EXECUTOR_MATCH", 0)
        self.assert_result(self.run_cli(FIXTURES / "wrong_executor_permit.json"),
                           "REJECT", "EXECUTOR_MISMATCH", 1)
        after = {path: path.read_bytes() for path in FIXTURES.glob("*.json")}
        self.assertEqual(after, before)


# Support running this test file directly as well as through test discovery.
if __name__ == "__main__":
    unittest.main()
