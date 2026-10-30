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
    def run_config(self, script="import config, db; print(len(config.GEMINI_API_KEYS)); print(config.MODEL_NAME)", **environment):
        env = {"PATH": os.environ.get("PATH", ""), "TESTING": "1", **environment}
        return subprocess.run([sys.executable, "-c", script],
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
        with patch.multiple(config, META_APP_SECRET="", META_ACCESS_TOKEN="sensitive-value",
                            APP_ENV="production", COOKIE_SECURE=True, FLASK_SECRET_KEY="x" * 32,
                            OPERATOR_USERNAME="synthetic", OPERATOR_PASSWORD_HASH="scrypt:32768:8:1$synthetic$synthetic"):
            with self.assertRaises(ValueError) as error:
                config.validate_startup()
            self.assertIn("META_APP_SECRET", str(error.exception))
            self.assertNotIn("sensitive-value", str(error.exception))

    def test_legacy_meta_environment_starts_server_with_safe_webhook_disabled(self):
        script = """
import os
import tempfile
from unittest.mock import patch
import config
config.validate_startup()
assert config.META_API_VERSION == 'v23.0'
assert config.COOKIE_SECURE is False
with tempfile.TemporaryDirectory(prefix='bps-legacy-startup-') as directory:
    os.environ['DATABASE_PATH'] = os.path.join(directory, 'test.db')
    with patch('logging_setup.setup_logging'):
        import wa_webhook as web
    with patch('message_queue.start_worker'), patch.object(web, 'start_prewarm_thread'), patch.object(web, 'start_session_timeout_thread'), patch('waitress.serve') as serve:
        web.run_server()
        serve.assert_called_once()
    with web.app.test_client() as client:
        assert client.get('/health').status_code == 200
        assert client.post('/webhook', json={'entry': []}).status_code == 503
print('legacy-startup-ok')
"""
        result = self.run_config(script=script, WHATSAPP_PROVIDER="meta",
                                 META_ACCESS_TOKEN="synthetic", META_PHONE_NUMBER_ID="123456789",
                                 META_VERIFY_TOKEN="synthetic", GEMINI_API_KEYS="synthetic",
                                 GEMINI_MODEL="legacy-configured-model", GEMINI_MODEL_FALLBACKS="",
                                 ROTATOR_COOLDOWN_SECONDS="300", FONNTE_TOKEN="synthetic", BPS_API_KEY="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("legacy-startup-ok", result.stdout)

    def test_legacy_fonnte_environment_and_production_cookie_default(self):
        result = self.run_config(script="import config; config.validate_startup(); assert config.FONNTE_WEBHOOK_SECRET == config.FONNTE_TOKEN",
                                 WHATSAPP_PROVIDER="fonnte", FONNTE_TOKEN="synthetic")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_config(script="import config; assert config.COOKIE_SECURE is True", APP_ENV="production")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_requires_secure_cookies_and_auth(self):
        with patch.multiple(config, APP_ENV="production", COOKIE_SECURE=False, FLASK_SECRET_KEY="short"):
            self.assertRaises(ValueError, config.validate_startup)
        with patch.multiple(config, APP_ENV="production", COOKIE_SECURE=True, FLASK_SECRET_KEY="x" * 32,
                            OPERATOR_USERNAME="", OPERATOR_PASSWORD_HASH=""):
            self.assertRaises(ValueError, config.validate_startup)
