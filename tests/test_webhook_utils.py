"""Tests untuk webhook_utils — validasi dan rate limit."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from webhook_utils import validate_message, check_rate_limit, _last_msg_ts


class TestValidateMessage(unittest.TestCase):

    def test_valid_message(self):
        text, err = validate_message("halo")
        self.assertEqual(text, "halo")
        self.assertIsNone(err)

    def test_empty_string(self):
        text, err = validate_message("")
        self.assertIsNone(text)
        self.assertIsNotNone(err)

    def test_none(self):
        text, err = validate_message(None)
        self.assertIsNone(text)
        self.assertIsNotNone(err)

    def test_whitespace_only(self):
        text, err = validate_message("   ")
        self.assertIsNone(text)
        self.assertIsNotNone(err)

    def test_strips_whitespace(self):
        text, err = validate_message("  halo  ")
        self.assertEqual(text, "halo")

    def test_truncate_long_message(self):
        long_msg = "x" * 5000
        text, err = validate_message(long_msg)
        self.assertEqual(len(text), 4096)
        self.assertIsNone(err)

    def test_non_string(self):
        text, err = validate_message(12345)
        self.assertIsNone(text)
        self.assertIsNotNone(err)


class TestRateLimit(unittest.TestCase):

    def setUp(self):
        _last_msg_ts.clear()

    def test_first_message_allowed(self):
        self.assertTrue(check_rate_limit("08111"))

    def test_rapid_message_blocked(self):
        check_rate_limit("08111")
        self.assertFalse(check_rate_limit("08111"))

    def test_after_delay_allowed(self):
        check_rate_limit("08111")
        _last_msg_ts["08111"] = time.time() - 3  # simulate 3 sec ago
        self.assertTrue(check_rate_limit("08111"))

    def test_different_phones_independent(self):
        check_rate_limit("081")
        self.assertTrue(check_rate_limit("082"))


if __name__ == "__main__":
    unittest.main()
