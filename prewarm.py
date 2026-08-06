"""
Standalone script untuk pre-warming BPS API cache.
Bisa dijalankan manual: python prewarm.py
Atau via cron job: 0 */6 * * * /path/to/.venv/bin/python /path/to/prewarm.py
"""
import sys
import logging
from logging_setup import setup_logging
from bps_api import prewarm_cache

if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== Menjalankan Prewarm BPS API Cache ===")
    prewarm_cache()
    logger.info("=== Selesai ===")
