"""
BPS Web API client dengan cache SQLite 24 jam dan background pre-warming.
Mengambil data resmi BPS Sulut (pressrelease, statictable, subject).
Endpoint: https://webapi.bps.go.id/v1/api
"""
import hashlib
import json
import logging
import re
import threading
import time
from urllib.parse import urlencode
import requests

from db import get_conn, init_db
from config import BPS_API_KEY, BPS_API_BASE, BPS_CACHE_TTL

logger = logging.getLogger(__name__)
TIMEOUT = 8  # detik (WA-friendly timeout)
DOMAIN_SULUT = "7100"

# Mapping kata kunci -> (type_filter: 'sub' atau 'subcsa', id_bps: int)
# Hasil analisis endpoint BPS Sulut (Domain 7100)
KEYWORD_SUBJECT_MAP = {
    # Inflasi & Harga (sub 3 / subcsa 536)
    "inflasi": ("sub", 3),
    "harga": ("sub", 3),
    "ihk": ("sub", 3),

    # Tenaga Kerja & Pengangguran (sub 6 / subcsa 520)
    "tenaga kerja": ("subcsa", 520),
    "pengangguran": ("subcsa", 520),
    "tpt": ("subcsa", 520),
    "pekerja": ("subcsa", 520),
    "angkatan kerja": ("subcsa", 520),

    # Neraca Ekonomi & PDRB (subcsa 531 / 530)
    "pdrb": ("subcsa", 531),
    "pertumbuhan ekonomi": ("subcsa", 531),
    "ekonomi": ("subcsa", 531),
    "neraca ekonomi": ("subcsa", 531),

    # Ekspor-Impor & Perdagangan (sub 8 / subcsa 535)
    "ekspor": ("sub", 8),
    "impor": ("sub", 8),
    "perdagangan": ("subcsa", 535),
    "neraca perdagangan": ("subcsa", 535),

    # Kependudukan & Migrasi (sub 12 / subcsa 519)
    "penduduk": ("subcsa", 519),
    "kependudukan": ("subcsa", 519),
    "migrasi": ("subcsa", 519),
    "sensus penduduk": ("subcsa", 519),

    # Kemiskinan & Ketimpangan (sub 23 / subcsa 563)
    "kemiskinan": ("sub", 23),
    "miskin": ("sub", 23),
    "gini ratio": ("subcsa", 563),

    # IPM & Pembangunan Manusia (sub 26)
    "ipm": ("sub", 26),
    "indeks pembangunan manusia": ("sub", 26),

    # Pariwisata & Transportasi (sub 16 / subcsa 561 / 560)
    "pariwisata": ("subcsa", 561),
    "wisata": ("subcsa", 561),
    "wisman": ("subcsa", 561),
    "hotel": ("subcsa", 561),
    "tpk": ("subcsa", 561),
    "transportasi": ("subcsa", 560),
    "penerbangan": ("subcsa", 560),

    # Pertanian & Nilai Tukar Petani (subcsa 557)
    "pertanian": ("subcsa", 557),
    "petani": ("subcsa", 557),
    "ntp": ("subcsa", 557),
    "perikanan": ("subcsa", 557),
    "kehutanan": ("subcsa", 557),

    # Energi & Pertambangan (subcsa 558 / 559)
    "energi": ("subcsa", 558),
    "listrik": ("subcsa", 558),
    "pertambangan": ("subcsa", 559),
    "manufaktur": ("subcsa", 559),
    "konstruksi": ("subcsa", 559),

    # Gender & Sosial (subcsa 564 / 521)
    "gender": ("subcsa", 564),
    "pendidikan": ("subcsa", 521),
    "kesehatan": ("subcsa", 522),
}


def _cache_get(cache_key: str):
    """Ambil response dari cache SQLite jika belum expired."""
    init_db()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT response, ts FROM bps_cache WHERE cache_key=?",
            (cache_key,)
        ).fetchone()
        if row and (time.time() - row["ts"]) < BPS_CACHE_TTL:
            return json.loads(row["response"])
    except Exception as e:
        logger.warning("BPS cache read error: %s", e)
    finally:
        conn.close()
    return None


def _cache_set(cache_key: str, response: dict):
    """Simpan response ke cache SQLite."""
    init_db()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO bps_cache (cache_key, response, ts) VALUES (?, ?, ?)",
            (cache_key, json.dumps(response), time.time())
        )
        conn.commit()
    except Exception as e:
        logger.warning("BPS cache write error: %s", e)
    finally:
        conn.close()


def _request_bps(endpoint_path: str):
    """HTTP GET ke Web API BPS dengan caching 24 jam."""
    if not BPS_API_KEY:
        logger.warning("BPS_API_KEY belum di-set")
        return None

    # URL format: {base}/{path}/key/{key}/
    url = f"{BPS_API_BASE}/{endpoint_path}/key/{BPS_API_KEY}/"
    cache_key = hashlib.sha256(url.encode()).hexdigest()

    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("BPS API cache HIT: %s", endpoint_path)
        return cached

    try:
        logger.info("BPS API HTTP request: %s", endpoint_path)
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "OK":
            _cache_set(cache_key, data)
            return data
        else:
            logger.warning("BPS API response status not OK: %s", data.get("status"))
            return None
    except (requests.RequestException, ValueError) as e:
        logger.error("BPS API request failed: %s", e)
        return None


def _clean_html(html_text: str) -> str:
    """Hapus tag HTML dan unescape entity dari abstract BRS."""
    if not html_text:
        return ""

    # 1. Unescape entity dulu (&lt;ul&gt; -> <ul>)
    text = html_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')

    # 2. Replace <li> dengan bullet point
    text = re.sub(r'<li>', '• ', text, flags=re.IGNORECASE)

    # 3. Strip semua tag HTML lain (<i>, </i>, <ul>, </ul>, dll)
    text = re.sub(r'<[^>]+>', ' ', text)

    # 4. Normalisasi spasi dan baris
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_lines = []
    for line in lines:
        cleaned = ' '.join(line.split())
        if cleaned:
            cleaned_lines.append(cleaned)

    return '\n'.join(cleaned_lines)


def cari_data_bps(keyword: str):
    """
    Entry point utama: Cari data aktual BPS berdasarkan kata kunci.

    1. Cocokkan keyword ke sub/subcsa BPS
    2. Panggil BPS API dengan direct endpoint filter (misal: /subcsa/520/page/1)
    3. Ekstrak BRS yang cocok + abstraksi naratif berisi angka resmi

    Returns:
        dict: {"found": True, "title": ..., "naratif": ..., "tanggal": ..., "link_pdf": ...}
        atau None jika data tidak ditemukan
    """
    if not BPS_API_KEY:
        return None

    keyword_clean = keyword.lower().strip()
    match_filter = None

    for k, filter_info in KEYWORD_SUBJECT_MAP.items():
        if k in keyword_clean:
            match_filter = filter_info
            break

    # Jika keyword match dengan filter spesifik, panggil direct endpoint
    if match_filter:
        filter_type, filter_id = match_filter
        endpoint = f"list/model/pressrelease/domain/{DOMAIN_SULUT}/{filter_type}/{filter_id}/page/1"
        data = _request_bps(endpoint)
    else:
        # Fallback ke general pressrelease page 1
        endpoint = f"list/model/pressrelease/domain/{DOMAIN_SULUT}/page/1"
        data = _request_bps(endpoint)

    if not data or "data" not in data or len(data["data"]) < 2:
        return None

    press_releases = data["data"][1]
    if not isinstance(press_releases, list) or not press_releases:
        return None

    # Filter BRS paling relevan dari list — skor setiap BRS
    kata_kunci = [k for k in keyword_clean.split() if len(k) > 2]
    best_brs = None
    best_score = 0

    for brs in press_releases:
        title = brs.get("title", "").lower()
        subcat = (brs.get("subcsa") or "").lower()
        haystack = f"{title} {subcat}"

        score = 0
        # Exact keyword match
        if keyword_clean in haystack:
            score += 10
        # Per-kata match
        for kata in kata_kunci:
            if kata in haystack:
                score += 3

        if score > best_score:
            best_score = score
            best_brs = brs

    # Tidak ada match via skor — return None.
    # BPS API saat ini mengembalikan data identik untuk semua endpoint
    # (filter subcsa/sub tidak efektif), jadi fallback ke BRS[0] akan
    # menampilkan data yang tidak relevan.
    if not best_brs:
        return None

    # Format naratif
    abstract_clean = _clean_html(best_brs.get("abstract", ""))
    bullets = [b for b in abstract_clean.split('\n') if b.startswith('•')]
    if len(bullets) > 3:
        abstract_clean = '\n'.join(bullets[:3])

    return {
        "found": True,
        "title": best_brs.get("title", ""),
        "naratif": abstract_clean,
        "tanggal": best_brs.get("rl_date", ""),
        "link_pdf": best_brs.get("pdf", ""),
    }


def prewarm_cache():
    """
    Background job: Pre-fetch BRS terbaru + BRS kategori utama Sulut ke SQLite cache.
    Tujuan: Menjamin respons sub-100ms saat user bertanya di WA/Terminal.
    """
    if not BPS_API_KEY:
        logger.info("Prewarm skipped: BPS_API_KEY belum diset")
        return

    logger.info("Memulai pre-warming BPS API cache (Sulut 7100)...")
    endpoints = [
        f"list/model/pressrelease/domain/{DOMAIN_SULUT}/page/1",
        f"list/model/pressrelease/domain/{DOMAIN_SULUT}/subcsa/520/page/1",  # Tenaga kerja
        f"list/model/pressrelease/domain/{DOMAIN_SULUT}/subcsa/531/page/1",  # Ekonomi PDRB
        f"list/model/pressrelease/domain/{DOMAIN_SULUT}/sub/3/page/1",       # Inflasi
        f"list/model/pressrelease/domain/{DOMAIN_SULUT}/sub/23/page/1",      # Kemiskinan
        f"list/model/pressrelease/domain/{DOMAIN_SULUT}/subcsa/561/page/1",  # Pariwisata
        f"list/model/pressrelease/domain/{DOMAIN_SULUT}/sub/8/page/1",       # Ekspor-Impor
    ]

    fetched = 0
    for ep in endpoints:
        res = _request_bps(ep)
        if res:
            fetched += 1

    logger.info("Pre-warming selesai: %d/%d endpoint ter-cache", fetched, len(endpoints))


def start_prewarm_thread(interval_hours=6):
    """Jalankan prewarm_cache() di daemon thread terpisah (setiap N jam)."""
    def _loop():
        while True:
            try:
                prewarm_cache()
            except Exception as e:
                logger.error("Error dalam prewarm thread: %s", e)
            time.sleep(interval_hours * 3600)

    t = threading.Thread(target=_loop, daemon=True, name="BPSPrewarmThread")
    t.start()
    return t
