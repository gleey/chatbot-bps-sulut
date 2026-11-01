"""
BPS Web API client dengan cache SQLite 24 jam dan background pre-warming.
Mengambil data resmi BPS Sulut (pressrelease, tablestatistic, statictable, subject).
Endpoint: https://webapi.bps.go.id/v1/api
"""
import hashlib
import difflib
import json
import logging
import math
import re
import threading
import time
from html import unescape
from html.parser import HTMLParser
from itertools import islice, product
from urllib.parse import urlencode, urlsplit, parse_qs, quote
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

    # Statistik Makroekonomi (530)
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


def normalisasi_pencarian(text):
    """Match common indicator abbreviations against official BPS titles."""
    aliases = {
        "pdrb": "produk domestik regional bruto", "ipm": "indeks pembangunan manusia",
        "tpt": "tingkat pengangguran terbuka", "tpak": "tingkat partisipasi angkatan kerja",
        "apk": "angka partisipasi kasar", "apm": "angka partisipasi murni",
        "bansos": "bantuan sosial", "kb": "keluarga berencana",
        "pns": "pegawai negeri sipil", "asn": "aparatur sipil negara",
        "ikk": "indeks kemahalan konstruksi", "wisman": "wisatawan mancanegara",
        "tpk": "tingkat penghunian kamar", "ihk": "indeks harga konsumen",
        "ntp": "nilai tukar petani", "ipg": "indeks pembangunan gender",
        "idg": "indeks pemberdayaan gender", "idi": "indeks demokrasi indonesia",
        "kpm": "keluarga penerima manfaat", "pkh": "program keluarga harapan",
        "kks": "kartu keluarga sejahtera", "asi": "air susu ibu",
        "perkapita": "per kapita", "pemukiman": "permukiman",
        "petani": "pertanian", "suhu udara": "suhu", "wisata": "pariwisata",
    }
    text = " ".join(re.findall(r"\w+", text.casefold()))
    for alias, replacement in aliases.items():
        text = re.sub(r"\b" + re.escape(alias) + r"\b", replacement, text)
    return text


def _search_words(keyword):
    ignored = {"saya", "mau", "ingin", "cari", "butuh", "data", "statistik", "tentang", "mengenai",
               "berapa", "berapakah", "tolong", "bisa", "tampilkan", "jumlah", "di", "dan", "yang",
               "sulut", "sulawesi", "utara", "bps", "tahun", "terbaru", "untuk", "pada", "adalah",
               "terkait", "informasi", "mencari", "minta", "seputar", "lihat", "dong", "ya"}
    return [word for word in normalisasi_pencarian(keyword).split() if word not in ignored and len(word) > 2]


def _matches(keyword, text):
    words = _search_words(keyword)
    titles = set(normalisasi_pencarian(text).split())
    return bool(words) and all(word in titles or (len(word) > 4 and
        difflib.get_close_matches(word, titles, n=1, cutoff=0.88)) for word in words)


def cari_data_bps(keyword: str):
    """
    Entry point utama: Cari data aktual BPS berdasarkan kata kunci.

    1. Cocokkan keyword ke sub/subcsa BPS
    2. Panggil BPS API dengan direct endpoint filter (misal: /subcsa/520/page/1)
    3. Cari rilis terdahulu melalui filter keyword jika halaman awal tidak cocok
    4. Ekstrak BRS yang cocok + abstraksi naratif berisi angka resmi

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
    # Subject filters on the legacy route are ignored; search older matching releases explicitly.
    if not any(_matches(keyword_clean, f"{item['title']} {item.get('subcsa') or ''}") for item in press_releases):
        query = " ".join(_search_words(keyword_clean))
        if query:
            press_releases = _items(_request_bps(
                f"list/model/pressrelease/domain/{DOMAIN_SULUT}", keyword=query))
    if not isinstance(press_releases, list) or not press_releases:
        return None

    # Filter BRS paling relevan dari list — skor setiap BRS
    kata_kunci = _search_words(keyword_clean)
    best_brs = None
    best_score = 0

    for brs in press_releases:
        title = brs.get("title", "").lower()
        subcat = str(brs.get("subcsa") or "").lower()
        haystack = normalisasi_pencarian(f"{title} {subcat}")
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


def _csa_table_url(item, year=None):
    """Use the same source/id/title route as the official BPS table catalog."""
    source = str(item.get("tablesource", ""))
    value = item.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ""
    identifier = str(value)
    if source not in {"1", "2", "3"} or not re.fullmatch(r"[A-Za-z0-9_+=-]{1,256}", identifier):
        return ""
    slug = re.sub(r"[^a-zA-Z0-9]", "-", item["title"].lower().replace("%", "-persen"))
    url = f"https://sulut.bps.go.id/id/statistics-table/{source}/{quote(identifier, safe='=')}/{slug}.html"
    period = year or item.get("latest_period")
    if source == "3" and re.fullmatch(r"[0-9]{4}", str(period)):
        url += "?" + urlencode({"year": period})
    return url


def _summary_number(value):
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return ""
        return format(value, ",").translate(str.maketrans({",": ".", ".": ","}))
    if isinstance(value, str) and re.fullmatch(r"[-+]?\d+(?:[.,]\d+)*(?:\s*(?:\*{1,3}|[erabc]))?", value.strip()):
        return value.strip()
    return ""


def _summary_label(value):
    return _clean_html(unescape(value)) if isinstance(value, str) else ""


def _summary_row_order(rows):
    """Prefer explicit province/total rows, preserving the actual subgroup label."""
    def priority(pair):
        index, row = pair
        label = normalisasi_pencarian(str(row.get("label_raw") or row.get("label") or ""))
        aggregate = label in {"sulawesi utara", "provinsi sulawesi utara", "jumlah", "total"}
        combined = "laki laki perempuan" in label
        return (0 if aggregate else 1 if combined else 2, -index if aggregate or combined else index)
    return [row for _, row in sorted(enumerate(rows), key=priority)]


def _summary_yearbook(detail, table, year):
    columns, rows = detail.get("kolom"), detail.get("data")
    period = detail.get("tahun_data")
    if not isinstance(columns, dict) or not isinstance(rows, list) or not str(period).isdigit():
        return []
    if year and str(period) != str(year):
        return []
    facts = []
    for row in _summary_row_order([row for row in rows if isinstance(row, dict)]):
        label = _summary_label(row.get("label_raw") or row.get("label"))
        label = re.sub(r"(?i)(laki[–-]laki)\s*\+\s*(perempuan)", r"\1 dan \2", label)
        values = row.get("variables")
        if not label or not isinstance(values, dict):
            continue
        for key, column in columns.items():
            cell = values.get(key)
            if not isinstance(column, dict) or not isinstance(cell, dict):
                continue
            value = _summary_number(cell.get("value"))
            indicator = _summary_label(column.get("nama_variabel"))
            if not value or not indicator:
                continue
            code = cell.get("value_code")
            if isinstance(code, str) and code in {"NA", "...", "–"}:
                continue
            if isinstance(code, str) and code and not value.endswith(code):
                notes = detail.get("keterangan_data")
                note = notes.get(code, code) if isinstance(notes, dict) else code
                value += f" ({_summary_label(note)})"
            unit = _summary_label(row.get("satuan") or column.get("satuan"))
            if not unit and "persentase" in indicator.casefold():
                unit = "persen"
            facts.append(f"Pada tahun {period}, {indicator} untuk kelompok {label} tercatat sebesar {value}{' ' + unit if unit else ''}.")
            if len(facts) == 2:
                return facts
    return facts


def _summary_dynamic(detail, table, year):
    axes = [detail.get(name) for name in ("tahun", "turtahun", "vervar", "var", "turvar")]
    content = detail.get("datacontent")
    if not isinstance(content, dict) or not all(isinstance(axis, list) and axis and all(
            isinstance(item, dict) and isinstance(item.get("val"), (str, int)) and
            isinstance(item.get("label"), str) for item in axis) for axis in axes):
        return []
    years, periods, verticals, variables, horizontals = axes
    years = sorted((item for item in years if item["label"].isdigit() and
                    (not year or item["label"] == str(year))), key=lambda item: int(item["label"]), reverse=True)
    periods = sorted(periods, key=lambda item: int(item["val"]) if str(item["val"]).isdigit() else -1, reverse=True)
    verticals = _summary_row_order(verticals)
    months = ("januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus",
              "september", "oktober", "november", "desember", "tahunan")
    if all(item["label"].casefold() in months for item in verticals):
        verticals = sorted(verticals, key=lambda item: months.index(item["label"].casefold()), reverse=True)
    horizontals = _summary_row_order(horizontals)
    facts = []
    # shortcut: inspect at most 100,000 dimension combinations; use an indexed decoder for larger tables.
    for annual, period, vertical, variable, horizontal in islice(product(
            years, periods, verticals, variables, horizontals), 100000):
        key = "".join(str(item["val"]) for item in (vertical, variable, horizontal, annual, period))
        value = _summary_number(content.get(key))
        if not value:
            continue
        period_label = _summary_label(period["label"])
        if period_label.casefold() in {"tahun", "tidak ada", ""}:
            period_label = ""
        group = _summary_label(vertical["label"])
        if not period_label and group.casefold() in months:
            period_label = group if group.casefold() != "tahunan" else ""
            group = ""
        when = f"{period_label} {annual['label']}" if period_label else f"tahun {annual['label']}"
        subject = _summary_label(variable["label"])
        if group.casefold() in {"sulawesi utara", "provinsi sulawesi utara"} and group.casefold() in subject.casefold():
            group = ""
        if group.casefold() not in {"tidak ada", ""}:
            subject += f" untuk {group}"
        category = _summary_label(horizontal["label"])
        if category.casefold() not in {"tidak ada", "tidak ada satuan", ""}:
            subject += f" ({category})"
        unit = _summary_label(variable.get("unit"))
        if unit.casefold() == "tidak ada satuan":
            unit = ""
        facts.append(f"Pada {when}, {subject} tercatat sebesar {value}{' ' + unit if unit else ''}.")
        if len(facts) == 2:
            return facts
    return facts


class _SummaryTableParser(HTMLParser):
    """Read simple static tables; leave merged layouts to the linked original."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None
        self.merged = False
        self.row_merged = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
            self.row_merged = False
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []
            self.merged = self.merged or any(key == "rowspan" and value != "1" for key, value in attrs)
            self.row_merged = self.row_merged or any(key == "colspan" and value != "1" for key, value in attrs)
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row_merged:
                self.merged = self.merged or len(self.row) > 1
            else:
                self.rows.append(self.row)
            self.row = None


def _summary_static(detail, table, year):
    html = detail.get("table")
    if not isinstance(html, str):
        return []
    parser = _SummaryTableParser()
    parser.feed(html)
    # shortcut: merged static-table headers are not inferred; add span-aware parsing when needed.
    if parser.merged:
        return []
    headers, facts = [], []
    for row in parser.rows:
        if len(row) < 2 or not row[0]:
            continue
        if not headers:
            if all(re.fullmatch(r"(?:19|20)\d{2}", value) for value in row[1:]):
                headers = row
            continue
        if len(row) != len(headers):
            continue
        for index in reversed(range(1, len(row))):
            if not re.fullmatch(r"(?:19|20)\d{2}", headers[index]) or (year and headers[index] != str(year)):
                continue
            value = _summary_number(row[index])
            if value:
                facts.append(f"Pada tahun {headers[index]}, {row[0]} tercatat sebesar {value}.")
                break
        if len(facts) == 2:
            break
    return facts


def ringkas_tabel_bps(table, keyword=""):
    """Read up to two official cells with labels; never generate missing figures."""
    if not isinstance(table, dict) or not isinstance(table.get("title"), str) or not _csa_table_url(table):
        return ""
    requested = re.findall(r"\b(?:19|20)\d{2}\b", keyword)
    year = max(requested) if requested else None
    params = {"year": year or table["latest_period"]} if year or table.get("latest_period") else {}
    data = _request_bps(f"view/domain/{DOMAIN_SULUT}/model/tablestatistic/id/{quote(str(table['id']), safe='')}/lang/ind", **params)
    if not isinstance(data, dict):
        return ""
    if str(table["tablesource"]) == "2":
        detail = data
    else:
        detail = data.get("data")
        if isinstance(detail, list):
            detail = detail[1] if len(detail) > 1 else None
    if not isinstance(detail, dict):
        return ""
    parser = {"1": _summary_static, "2": _summary_dynamic, "3": _summary_yearbook}[str(table["tablesource"])]
    return "\n".join("• " + fact for fact in parser(detail, table, year))


def _csa_tables(keyword, subject):
    endpoint = f"list/model/tablestatistic/domain/{DOMAIN_SULUT}"
    params = {"page": 1, "perpage": 100}
    if subject:
        params["subject"] = subject
    data = _request_bps(endpoint, **params)
    rows = _items(data)
    values = data.get("data", []) if isinstance(data, dict) else []
    paging = values[0] if isinstance(values, list) and values and isinstance(values[0], dict) else {}
    try:
        pages = min(max(int(paging.get("pages", 1)), 1), 10 if subject else 20)
    except (TypeError, ValueError):
        pages = 1
    # shortcut: inspect 1,000 tables per subject or 2,000 across subjects; add indexed search above these limits.
    for page in range(2, pages + 1):
        rows.extend(_items(_request_bps(endpoint, **{**params, "page": page})))

    years = re.findall(r"\b(?:19|20)[0-9]{2}\b", keyword)
    topic = re.sub(r"\b(?:19|20)[0-9]{2}\b", "", keyword)
    results = {}
    for item in rows:
        if subject and item.get("id_subject") is not None and str(item["id_subject"]) != str(subject):
            continue
        if not _matches(topic, f"{item['title']} {item.get('subject', '')}"):
            continue
        if years:
            try:
                oldest, latest = int(item["oldest_period"]), int(item["latest_period"])
            except (KeyError, TypeError, ValueError):
                if not _matches(keyword, item["title"]):
                    continue
            else:
                if not all(oldest <= int(year) <= latest for year in years):
                    continue
        url = _csa_table_url(item, years[0] if len(years) == 1 else None)
        if not url:
            continue
        results[url] = {**item, "title": _clean_html(item["title"]), "url": url,
                        "date": str(item.get("last_update") or "")[:10], "source_type": "tabel resmi"}
    ordered = sorted(results.values(), key=lambda item: item["title"].casefold())
    ordered.sort(key=lambda item: str(item.get("last_update") or ""), reverse=True)
    return ordered


def cari_tabel_terbaru_bps(keyword: str, subject_url: str = None, limit: int = 2):
    """Return matching tables in update-date descending, title ascending order.

    The CSA endpoint includes static, dynamic and yearbook tables. Legacy static
    tables and the optional website Server Action remain fallback sources.
    """
    kw_clean = keyword.lower().strip()
    if not kw_clean:
        return []
    limit = max(1, min(limit, 10))
    catalog = _official_url(subject_url) or "https://sulut.bps.go.id/id/statistics-table"
    subject = parse_qs(urlsplit(catalog).query).get("subject", [None])[0]
    if not subject or not subject.isdigit():
        subject = next((str(value[1]) for term, value in sorted(KEYWORD_SUBJECT_MAP.items(),
                        key=lambda pair: len(pair[0]), reverse=True)
                        if f" {normalisasi_pencarian(term)} " in f" {normalisasi_pencarian(kw_clean)} "), None)
    cache_key = hashlib.sha256(f"tables_v3_{catalog}_{kw_clean}_{limit}".encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results = _csa_tables(kw_clean, subject)
    if not results and subject:
        results = _csa_tables(kw_clean, None)
    if results:
        _cache_set(cache_key, results[:limit])
        return results[:limit]

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
