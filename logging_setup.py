"""
Logging setup — rotating file + stdout.
Panggil setup_logging() sekali saat startup.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from config import LOG_LEVEL

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "chatbot.log")

_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"


def setup_logging():
    root = logging.getLogger()
    # HTTP debug logs may include credentials embedded in BPS request URLs.
    for name in ("urllib3", "httpx", "httpcore", "google.genai", "requests"):
        logging.getLogger(name).setLevel(logging.WARNING)
    
    # Guard against duplicate handlers on reload
    if root.handlers:
        return
        
    os.makedirs(LOG_DIR, exist_ok=True)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(ch)

    # File handler — 5 MB x 3 rotasi
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(fh)
