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


def cari_tabel_terbaru_bps(keyword: str, limit: int = 2):
    """
    Cari tabel statistik BPS berdasarkan kata kunci dan kembalikan N tabel terbaru (by updt_date).
    Returns:
        list of dict: [{"title": ..., "updt_date": ..., "excel": ...}]
    """
    if not BPS_API_KEY:
        return []

    keyword_clean = keyword.lower().strip()
    match_filter = KEYWORD_SUBJECT_MAP.get(keyword_clean)
    if not match_filter:
        for k, v in KEYWORD_SUBJECT_MAP.items():
            if k in keyword_clean:
                match_filter = v
                break

    # Panggil statictable list
    if match_filter:
        filter_type, filter_id = match_filter
        endpoint = f"list/model/statictable/domain/{DOMAIN_SULUT}/{filter_type}/{filter_id}/page/1"
    else:
        endpoint = f"list/model/statictable/domain/{DOMAIN_SULUT}/page/1"

    data = _request_bps(endpoint)
    if not data or "data" not in data or len(data["data"]) < 2:
        return []

    tables = data["data"][1]
    if not isinstance(tables, list) or not tables:
        return []

    # Score & filter
    kata_kunci = [k for k in keyword_clean.split() if len(k) > 2]
    matched = []

    for t in tables:
        title = t.get("title", "").lower()
        subj = (t.get("subj") or "").lower()
        haystack = f"{title} {subj}"

        score = 0
        if keyword_clean in haystack:
            score += 10
        for kata in kata_kunci:
            if kata in haystack:
                score += 3

        if score > 0 or not match_filter:
            matched.append((score, t.get("updt_date", ""), t))

    # Urutkan berdasarkan tanggal diperbarui (updt_date desc) lalu skor
    matched.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return [item[2] for item in matched[:limit]]


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


def cari_tabel_terbaru_bps(keyword: str, subject_url: str = None, limit: int = 2):
    """
    Cari hingga `limit` link tabel statistik BPS Sulut terbaru (individual table URLs).
    Menggunakan BPS Sulut website Server Action & caching SQLite 24 jam.
    """
    subject_id = None
    if subject_url and "subject=" in subject_url:
        try:
            subject_id = int(subject_url.split("subject=")[1].split("&")[0])
        except (ValueError, IndexError):
            pass

    kw_clean = keyword.lower().strip()
    cache_key = hashlib.sha256(f"tabel_terbaru_{subject_id}_{kw_clean}".encode()).hexdigest()

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = []

    # Coba panggil Next.js Server Action BPS Sulut
    try:
        action_url = "https://sulut.bps.go.id/id/statistics-table"
        action_id = "4072f1ccc0a450ad525ef0ea7d1d36e0d0e8f00f8d"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "Next-Action": action_id,
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "text/x-component",
        }

        payload = {
            "locale": "id",
            "page": 1,
            "perpage": 10,
            "sortBy": "date",
            "sortOrder": "desc",
        }
        if subject_id:
            payload["subject"] = subject_id

        items = []

        # Cari via kata kunci — hanya tampilkan tabel yang cocok dengan keyword
        if kw_clean:
            kw_payload = dict(payload)
            kw_payload["keyword"] = kw_clean
            try:
                resp = requests.post(action_url, headers=headers, data=json.dumps([kw_payload]), timeout=TIMEOUT)
                if resp.status_code == 200:
                    for line in resp.text.split("\n"):
                        if line.startswith("1:"):
                            data = json.loads(line[2:])
                            if data.get("status") and data.get("response", {}).get("status") == "OK":
                                items = data["response"]["data"][1]
                            break
            except Exception as e:
                logger.warning("BPS Server Action keyword search failed: %s", e)

        for item in items[:limit]:
            title = item.get("title", "")
            slug = title.lower().replace("%", "-persen")
            slug = re.sub(r"[^a-zA-Z0-9]", "-", slug)

            tablesource = str(item.get("tablesource", ""))
            table_id = item.get("id", "")
            latest_period = item.get("latest_period", "")

            table_url = f"https://sulut.bps.go.id/id/statistics-table/{tablesource}/{table_id}/{slug}.html"
            if tablesource == "3" and latest_period:
                table_url += f"?year={latest_period}"

            date_str = item.get("last_update", "")[:10]
            results.append({
                "title": title,
                "url": table_url,
                "date": date_str,
            })

    except Exception as e:
        logger.error("Error fetching live table links from BPS Sulut: %s", e)

    if results:
        _cache_set(cache_key, results)
        return results

    # Fallback ke pencarian BPS Web API jika live website offline
    kata_kunci = [k for k in kw_clean.split() if len(k) > 2]
    matched = []
    data_st = _request_bps(f"list/model/statictable/domain/{DOMAIN_SULUT}/page/1")
    if data_st and "data" in data_st and len(data_st["data"]) > 1:
        tables = data_st["data"][1]
        if isinstance(tables, list):
            for t in tables:
                t_title = t.get("title", "")
                subj = t.get("subj", "")
                haystack = f"{t_title} {subj}".lower()
                if kw_clean in haystack or (kata_kunci and all(k in haystack for k in kata_kunci)):
                    matched.append({
                        "title": t_title,
                        "url": subject_url or "https://sulut.bps.go.id",
                        "date": t.get("updt_date", ""),
                    })

    if matched:
        _cache_set(cache_key, matched[:limit])

    return matched[:limit]


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
