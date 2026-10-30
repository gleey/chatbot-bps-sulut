"""Configuration must work without .env and reject unsafe deployment settings."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests import support  # noqa: F401
import config


class ConfigTests(unittest.TestCase):
    def run_config(self, **environment):
        env = {"PATH": os.environ.get("PATH", ""), "TESTING": "1", **environment}
        return subprocess.run([sys.executable, "-c", "import config, db; print(len(config.GEMINI_API_KEYS)); print(config.MODEL_NAME)"],
                              cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)

    def test_missing_optional_environment_imports(self):
        result = self.run_config()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("0\n"))

    def test_invalid_provider_database_and_numeric_values(self):
        for env in [{"WHATSAPP_PROVIDER": "invalid"}, {"DATABASE_PATH": ""}, {"DATABASE_PATH": "postgresql://unused"},
                    {"DATABASE_PATH": ":memory:"}, {"SESSION_TIMEOUT": "0"}, {"BPS_CACHE_TTL": "bad"}]:
            with self.subTest(env=env):
                self.assertNotEqual(self.run_config(**env).returncode, 0)

    def test_empty_model_fallbacks_and_legacy_single_key(self):
        result = self.run_config(GEMINI_API_KEY="synthetic", GEMINI_API_KEYS="", GEMINI_MODEL="", GEMINI_MODEL_FALLBACKS="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("1\n"))

    def test_startup_missing_secret_error_names_only(self):
        with patch.multiple(config, META_APP_SECRET="", META_ACCESS_TOKEN="sensitive-value"):
            with self.assertRaises(ValueError) as error:
                config.validate_startup()
            self.assertIn("META_APP_SECRET", str(error.exception))
            self.assertNotIn("sensitive-value", str(error.exception))

    def test_production_requires_secure_cookies_and_auth(self):
        with patch.multiple(config, APP_ENV="production", COOKIE_SECURE=False, FLASK_SECRET_KEY="short"):
            self.assertRaises(ValueError, config.validate_startup)
        with patch.multiple(config, APP_ENV="production", COOKIE_SECURE=True, FLASK_SECRET_KEY="x" * 32,
                            OPERATOR_USERNAME="", OPERATOR_PASSWORD_HASH=""):
            self.assertRaises(ValueError, config.validate_startup)
