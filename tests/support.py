"""Shared, portable isolation: synthetic credentials, temporary DB, no network."""
import atexit
import os
import tempfile
from unittest.mock import patch

_temporary = tempfile.TemporaryDirectory(prefix="bps-tests-")
atexit.register(_temporary.cleanup)
os.environ.update(
    TESTING="1", APP_ENV="development", COOKIE_SECURE="false",
    DATABASE_PATH=os.path.join(_temporary.name, "chatbot.db"),
    GEMINI_API_KEY="", GEMINI_API_KEYS="test-key-a,test-key-b",
    GEMINI_MODEL="test-model-a", GEMINI_MODEL_FALLBACKS="test-model-b",
    BPS_API_KEY="test-bps-key", WHATSAPP_PROVIDER="meta",
    META_ACCESS_TOKEN="test-meta-token", META_PHONE_NUMBER_ID="123456789",
    META_VERIFY_TOKEN="test-verify-token", META_APP_SECRET="test-meta-secret",
    META_API_VERSION="v23.0", FONNTE_TOKEN="test-fonnte-token",
    FONNTE_WEBHOOK_SECRET="test-fonnte-secret",
    OPERATOR_USERNAME="", OPERATOR_PASSWORD_HASH="",
    FLASK_SECRET_KEY="test-flask-secret-with-at-least-32-characters",
    SESSION_TIMEOUT="300", BPS_CACHE_TTL="86400",
    ROTATOR_COOLDOWN_SECONDS="300", BPS_SERVER_ACTION_ID="",
)
_network = patch("socket.socket.connect", side_effect=AssertionError("Network is disabled in automated tests"))
_network.start()
atexit.register(_network.stop)
