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
from urllib.parse import urlencode, urlsplit
import requests

from db import get_conn, init_db
from config import BPS_API_KEY, BPS_API_BASE, BPS_CACHE_TTL, BPS_SERVER_ACTION_ID

logger = logging.getLogger(__name__)
TIMEOUT = 8  # detik (WA-friendly timeout)
DOMAIN_SULUT = "7100"

# Mapping kata kunci -> (type_filter: 'sub' atau 'subcsa', id_bps: int)
# Hasil analisis endpoint BPS Sulut (Domain 7100)
KEYWORD_SUBJECT_MAP = {
    # Kependudukan dan Migrasi (519)
    "penduduk": ("subcsa", 519),
    "kependudukan": ("subcsa", 519),
    "migrasi": ("subcsa", 519),
    "sensus penduduk": ("subcsa", 519),
    "perceraian": ("subcsa", 519),
    "nikah": ("subcsa", 519),
    "cerai": ("subcsa", 519),
    "laju pertumbuhan penduduk": ("subcsa", 519),
    "kepadatan penduduk": ("subcsa", 519),
    "rasio jenis kelamin": ("subcsa", 519),
    "beban ketergantungan": ("subcsa", 519),

    # Tenaga Kerja (520)
    "tenaga kerja": ("subcsa", 520),
    "pengangguran": ("subcsa", 520),
    "tpt": ("subcsa", 520),
    "tpak": ("subcsa", 520),
    "pekerja": ("subcsa", 520),
    "angkatan kerja": ("subcsa", 520),
    "jam kerja": ("subcsa", 520),
    "pencari kerja": ("subcsa", 520),

    # Pendidikan (521)
    "pendidikan": ("subcsa", 521),
    "sekolah": ("subcsa", 521),
    "beasiswa": ("subcsa", 521),
    "apk": ("subcsa", 521),
    "apm": ("subcsa", 521),
    "perguruan tinggi": ("subcsa", 521),
    "literasi": ("subcsa", 521),
    "madrasah": ("subcsa", 521),
    "melek aksara": ("subcsa", 521),
    "pustakawan": ("subcsa", 521),

    # Kesehatan (522)
    "kesehatan": ("subcsa", 522),
    "jaminan kesehatan": ("subcsa", 522),
    "merokok": ("subcsa", 522),
    "penyakit": ("subcsa", 522),
    "rumah sakit": ("subcsa", 522),
    "puskesmas": ("subcsa", 522),
    "posyandu": ("subcsa", 522),
    "tenaga kesehatan": ("subcsa", 522),
    "kb": ("subcsa", 522),
    "imunisasi": ("subcsa", 522),
    "asi": ("subcsa", 522),

    # Konsumsi dan Pendapatan (523)
    "konsumsi dan pendapatan": ("subcsa", 523),
    "konsumsi": ("subcsa", 523),
    "pendapatan": ("subcsa", 523),
    "pengeluaran per kapita": ("subcsa", 523),
    "perkapita": ("subcsa", 523),

    # Perlindungan Sosial (524)
    "perlindungan sosial": ("subcsa", 524),
    "bansos": ("subcsa", 524),
    "bantuan sosial": ("subcsa", 524),
    "kpm": ("subcsa", 524),
    "pkh": ("subcsa", 524),
    "kks": ("subcsa", 524),

    # Pemukiman dan Perumahan (525)
    "pemukiman dan perumahan": ("subcsa", 525),
    "perumahan": ("subcsa", 525),
    "pemukiman": ("subcsa", 525),
    "air minum": ("subcsa", 525),
    "sanitasi": ("subcsa", 525),
    "penerangan": ("subcsa", 525),
    "kloset": ("subcsa", 525),
    "ipal": ("subcsa", 525),

    # Hukum dan Kriminal (526)
    "hukum dan kriminal": ("subcsa", 526),
    "kriminal": ("subcsa", 526),
    "kejahatan": ("subcsa", 526),
    "pencurian": ("subcsa", 526),
    "penganiayaan": ("subcsa", 526),

    # Budaya (527)
    "budaya": ("subcsa", 527),
    "haji": ("subcsa", 527),
    "jemaah haji": ("subcsa", 527),
    "warisan budaya": ("subcsa", 527),

    # Aktivitas Politik dan Komunitas (528)
    "aktivitas politik dan komunitas": ("subcsa", 528),
    "politik": ("subcsa", 528),
    "demokrasi": ("subcsa", 528),
    "idi": ("subcsa", 528),
    "indeks demokrasi": ("subcsa", 528),
    "dprd": ("subcsa", 528),

    # Penggunaan Waktu (529)
    "penggunaan waktu": ("subcsa", 529),

    # Makroekonomi & PDRB (530)
    "statistik makroekonomi": ("subcsa", 530),

    # Neraca Ekonomi & PDRB (531)
    "pdrb": ("subcsa", 531),
    "pertumbuhan ekonomi": ("subcsa", 531),
    "ekonomi": ("subcsa", 531),
    "neraca ekonomi": ("subcsa", 531),

    # Statistik Bisnis & Sektoral (532, 533)
    "statistik bisnis": ("subcsa", 532),
    "statistik sektoral": ("subcsa", 533),
    "panjang jalan": ("subcsa", 533),

    # Keuangan Pemerintah (534)
    "keuangan pemerintah": ("subcsa", 534),
    "pegawai negeri": ("subcsa", 534),
    "pns": ("subcsa", 534),
    "asn": ("subcsa", 534),

    # Perdagangan Internasional (535)
    "perdagangan": ("subcsa", 535),
    "perdagangan internasional": ("subcsa", 535),
    "ekspor": ("subcsa", 535),
    "impor": ("subcsa", 535),
    "neraca perdagangan": ("subcsa", 535),

    # Harga-Harga & Inflasi (536)
    "inflasi": ("subcsa", 536),
    "harga": ("subcsa", 536),
    "ihk": ("subcsa", 536),
    "ntp": ("subcsa", 536),
    "nilai tukar petani": ("subcsa", 536),

    # Biaya Tenaga Kerja (537)
    "biaya tenaga kerja": ("subcsa", 537),
    "upah": ("subcsa", 537),
    "gaji": ("subcsa", 537),

    # Teknologi (538)
    "teknologi": ("subcsa", 538),

    # Pertanian, Kehutanan, Perikanan (557)
    "pertanian": ("subcsa", 557),
    "petani": ("subcsa", 557),
    "padi": ("subcsa", 557),
    "beras": ("subcsa", 557),
    "jagung": ("subcsa", 557),
    "perikanan": ("subcsa", 557),
    "kehutanan": ("subcsa", 557),
    "daging": ("subcsa", 557),
    "telur": ("subcsa", 557),

    # Energi (558)
    "energi": ("subcsa", 558),
    "listrik": ("subcsa", 558),
    "pln": ("subcsa", 558),

    # Pertambangan, Manufaktur, Konstruksi (559)
    "pertambangan": ("subcsa", 559),
    "manufaktur": ("subcsa", 559),
    "konstruksi": ("subcsa", 559),
    "industri": ("subcsa", 559),
    "ikk": ("subcsa", 559),
    "indeks kemahalan konstruksi": ("subcsa", 559),

    # Transportasi (560)
    "transportasi": ("subcsa", 560),
    "penerbangan": ("subcsa", 560),
    "kapal laut": ("subcsa", 560),
    "bandara": ("subcsa", 560),
    "pelabuhan": ("subcsa", 560),

    # Pariwisata (561)
    "pariwisata": ("subcsa", 561),
    "wisata": ("subcsa", 561),
    "wisman": ("subcsa", 561),
    "hotel": ("subcsa", 561),
    "tpk": ("subcsa", 561),
    "lama menginap": ("subcsa", 561),

    # Perbankan & Finansial (562)
    "perbankan": ("subcsa", 562),
    "finansial": ("subcsa", 562),
    "bank": ("subcsa", 562),
    "koperasi": ("subcsa", 562),
    "umkm": ("subcsa", 562),
    "kredit": ("subcsa", 562),

    # Lingkungan (539)
    "lingkungan": ("subcsa", 539),
    "bencana alam": ("subcsa", 539),
    "bmkg": ("subcsa", 539),
    "suhu udara": ("subcsa", 539),

    # Statistik Regional (540)
    "statistik regional": ("subcsa", 540),
    "kecamatan": ("subcsa", 540),
    "desa": ("subcsa", 540),
    "kelurahan": ("subcsa", 540),

    # Multi-Domain (541, 542)
    "statistik dan indikator multi-domain": ("subcsa", 541),
    "buku tahunan": ("subcsa", 542),

    # Kemiskinan & Sosial (563)
    "kemiskinan": ("subcsa", 563),
    "miskin": ("subcsa", 563),
    "gini ratio": ("subcsa", 563),
    "ipm": ("subcsa", 563),
    "indeks pembangunan manusia": ("subcsa", 563),

    # Gender (564)
    "gender": ("subcsa", 564),
    "perempuan": ("subcsa", 564),
    "ipg": ("subcsa", 564),
    "idg": ("subcsa", 564),

    # Masyarakat Informasi (565)
    "masyarakat informasi": ("subcsa", 565),
    "internet": ("subcsa", 565),
    "komputer": ("subcsa", 565),

    # Globalisasi, MDGs, SDGs (566-569)
    "globalisasi": ("subcsa", 566),
    "mdgs": ("subcsa", 567),
    "sdgs": ("subcsa", 568),
    "kewiraswastaan": ("subcsa", 569),
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


def _request_bps(endpoint_path: str, **params):
    """HTTP GET ke Web API BPS dengan caching 24 jam."""
    if not BPS_API_KEY:
        logger.warning("BPS_API_KEY belum di-set")
        return None

    # URL format: {base}/{path}/key/{key}/
    url = f"{BPS_API_BASE}/{endpoint_path}/key/{BPS_API_KEY}/"
    query = urlencode(params)
    if query:
        url += "?" + query
    cache_key = hashlib.sha256((endpoint_path + "?" + query).encode()).hexdigest()

    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("BPS API cache HIT: %s", endpoint_path)
        return cached

    try:
        logger.info("BPS API HTTP request: %s", endpoint_path)
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and data.get("status") == "OK":
            _cache_set(cache_key, data)
            return data
        else:
            logger.warning("BPS API response tidak valid")
            return None
    except (requests.RequestException, ValueError) as e:
        logger.warning("BPS API request gagal (%s)", type(e).__name__)
        return None


def _clean_html(html_text: str) -> str:
    """Hapus tag HTML dan unescape entity dari abstract BRS."""
    if not isinstance(html_text, str):
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


def _official_url(value):
    if not isinstance(value, str) or not value or (BPS_API_KEY and BPS_API_KEY in value):
        return ""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (parsed.scheme == "https" and (host == "bps.go.id" or host.endswith(".bps.go.id"))
                and not parsed.username and not parsed.password and parsed.port in (None, 443)):
            return value
    except ValueError:
        pass
    return ""


def _items(data):
    if not isinstance(data, dict):
        return []
    values = data.get("data")
    if not isinstance(values, list) or len(values) < 2 or not isinstance(values[1], list):
        return []
    return [item for item in values[1] if isinstance(item, dict) and isinstance(item.get("title"), str)]


def _matches(keyword, text):
    ignored = {"saya", "mau", "ingin", "cari", "butuh", "data", "statistik", "tentang", "mengenai",
               "berapa", "berapakah", "tolong", "bisa", "tampilkan", "jumlah", "di", "dan", "yang",
               "sulut", "sulawesi", "utara", "bps", "tahun", "terbaru", "untuk", "pada", "adalah"}
    words = [word for word in re.findall(r"\w+", keyword.lower()) if word not in ignored and len(word) > 2]
    text = text.lower()
    return bool(words) and all(word in text for word in words)


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

    for k, filter_info in sorted(KEYWORD_SUBJECT_MAP.items(), key=lambda pair: len(pair[0]), reverse=True):
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

    press_releases = _items(data)
    if not isinstance(press_releases, list) or not press_releases:
        return None

    # Filter BRS paling relevan dari list — skor setiap BRS
    kata_kunci = [k for k in keyword_clean.split() if len(k) > 2]
    best_brs = None
    best_score = 0

    for brs in press_releases:
        title = brs.get("title", "").lower()
        subcat = str(brs.get("subcsa") or "").lower()
        haystack = f"{title} {subcat}"
        if not _matches(keyword_clean, haystack):
            continue

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
        "link_pdf": _official_url(best_brs.get("pdf", "")),
    }


def cari_tabel_terbaru_bps(keyword: str, subject_url: str = None, limit: int = 2):
    """Search official API first; return download URLs or clearly labelled catalog links.

    Only the returned page is ranked. This is not a guarantee of the newest table
    across the complete BPS catalog. Website Server Action is an optional fallback.
    """
    kw_clean = keyword.lower().strip()
    if not kw_clean:
        return []
    limit = max(1, min(limit, 10))
    catalog = _official_url(subject_url) or "https://sulut.bps.go.id/id/statistics-table"
    cache_key = hashlib.sha256(f"tables_v2_{catalog}_{kw_clean}_{limit}".encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = _request_bps(f"list/model/statictable/domain/{DOMAIN_SULUT}/page/1", keyword=kw_clean)
    results = []
    for item in _items(data):
        if not _matches(kw_clean, f"{item['title']} {item.get('subj', '')}"):
            continue
        download = _official_url(item.get("excel"))
        url = download or _official_url(item.get("url"))
        results.append({**item, "url": url or catalog,
                        "date": str(item.get("updt_date") or "")[:10],
                        "source_type": "unduhan resmi" if download else ("halaman resmi" if url else "katalog subjek")})
    results.sort(key=lambda item: item["date"], reverse=True)
    if results:
        _cache_set(cache_key, results[:limit])
        return results[:limit]

    # Coba panggil Next.js Server Action BPS Sulut
    # shortcut: Website action IDs change; enable only after checking the current site contract.
    if not BPS_SERVER_ACTION_ID:
        return []
    try:
        payload = {"locale": "id", "page": 1, "perpage": 10, "keyword": kw_clean,
                   "sortBy": "date", "sortOrder": "desc"}
        resp = requests.post("https://sulut.bps.go.id/id/statistics-table",
                             headers={"Next-Action": BPS_SERVER_ACTION_ID,
                                      "Content-Type": "text/plain;charset=UTF-8", "Accept": "text/x-component"},
                             data=json.dumps([payload]), timeout=TIMEOUT)
        resp.raise_for_status()
        for line in resp.text.splitlines():
            if not line.startswith("1:"):
                continue
            envelope = json.loads(line[2:])
            for item in _items(envelope.get("response", {}) if isinstance(envelope, dict) else {}):
                # Do not construct a URL from a guessed slug or table ID.
                url = _official_url(item.get("url"))
                if url and _matches(kw_clean, item["title"]):
                    results.append({"title": item["title"], "url": url,
                                    "date": str(item.get("last_update") or "")[:10],
                                    "source_type": "halaman resmi dari website"})
    except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
        logger.warning("BPS Server Action gagal (%s)", type(error).__name__)
    if results:
        _cache_set(cache_key, results[:limit])
    return results[:limit]


def prewarm_cache():
    """
    Background job: Pre-fetch BRS terbaru + BRS kategori utama Sulut ke SQLite cache.
    Tujuan: Mengurangi permintaan eksternal; waktu respons harus diukur pada lingkungan target.
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
                logger.error("Prewarm worker gagal (%s)", type(e).__name__)
            time.sleep(interval_hours * 3600)

    t = threading.Thread(target=_loop, daemon=True, name="BPSPrewarmThread")
    t.start()
    return t
