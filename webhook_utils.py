"""
Webhook utilities — validasi input, rate limiting.
"""
import time
import logging
import re
import threading

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
RATE_LIMIT_SECONDS = 2

_last_msg_ts = {}  # phone → timestamp
_rate_lock = threading.Lock()
_phone_locks = [threading.RLock() for _ in range(64)]
# ponytail: multi-worker → Redis token bucket


def validate_message(text):
    """Validasi dan sanitasi pesan masuk.
    Returns: (clean_text, error_message)
    """
    if not text or not isinstance(text, str):
        return None, "Pesan kosong atau bukan teks."

    text = text.strip()
    if not text:
        return None, "Pesan kosong."

    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]
        logger.warning("Pesan dipotong ke %d karakter", MAX_MESSAGE_LENGTH)

    return text, None


def check_rate_limit(phone):
    """Cek apakah user mengirim terlalu cepat.
    Returns: True jika boleh lewat, False jika rate limited.
    """
    with _rate_lock:
        now = time.time()
        for key in [key for key, ts in _last_msg_ts.items() if now - ts >= RATE_LIMIT_SECONDS]:
            del _last_msg_ts[key]
        last = _last_msg_ts.get(phone, 0)
        if now - last < RATE_LIMIT_SECONDS:
            return False
        _last_msg_ts[phone] = now
        return True


def valid_phone(phone):
    return isinstance(phone, str) and re.fullmatch(r"[0-9]{8,15}", phone) is not None


def phone_lock(phone):
    """Bounded lock set for one-process threaded deployments."""
    return _phone_locks[hash(phone) % len(_phone_locks)]
