import os
from dotenv import load_dotenv

load_dotenv()

# Google Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Multi-key rotation — pisahkan dengan koma di .env
# Jika GEMINI_API_KEYS tidak di-set, fallback ke GEMINI_API_KEY tunggal
_raw_keys = os.getenv("GEMINI_API_KEYS", GEMINI_API_KEY)
GEMINI_API_KEYS = [k.strip() for k in _raw_keys.split(",") if k.strip()]

# Multi-model fallback — dicoba berurutan saat model sebelumnya gagal (429/404)
_raw_fallbacks = os.getenv("GEMINI_MODEL_FALLBACKS", "gemini-2.0-flash,gemini-1.5-flash")
_fallbacks = [m.strip() for m in _raw_fallbacks.split(",") if m.strip() and m.strip() != MODEL_NAME]
GEMINI_MODELS = [MODEL_NAME] + _fallbacks

# Cooldown rotator — berapa detik sebelum key/model yang gagal dicoba lagi
ROTATOR_COOLDOWN = int(os.getenv("ROTATOR_COOLDOWN_SECONDS", "300"))

# WhatsApp Provider Configuration ("meta" atau "fonnte")
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "meta").lower()

# Meta Cloud API Configuration
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")

# Fonnte API Configuration
FONNTE_TOKEN = os.getenv("FONNTE_TOKEN", "")

# Web API BPS Configuration
BPS_API_KEY = os.getenv("BPS_API_KEY", "")
BPS_API_BASE = "https://webapi.bps.go.id/v1/api"
BPS_CACHE_TTL = int(os.getenv("BPS_CACHE_TTL", "86400"))  # 24 jam

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ============================================================
# DAFTAR KATEGORI DATA BPS SULUT → LINK WEBSITE
# Satu sumber kebenaran — dipakai oleh main.py dan system prompt.
# ============================================================
BPS_CATEGORIES = {
    "kependudukan dan migrasi": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "kependudukan": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "penduduk": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "migrasi": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "tenaga kerja": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "pendidikan": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "kesehatan": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "konsumsi dan pendapatan": "https://sulut.bps.go.id/id/statistics-table?subject=523",
    "perlindungan sosial": "https://sulut.bps.go.id/id/statistics-table?subject=524",
    "pemukiman dan perumahan": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "hukum dan kriminal": "https://sulut.bps.go.id/id/statistics-table?subject=526",
    "budaya": "https://sulut.bps.go.id/id/statistics-table?subject=527",
    "aktivitas politik dan komunitas": "https://sulut.bps.go.id/id/statistics-table?subject=528",
    "penggunaan waktu": "https://sulut.bps.go.id/id/statistics-table?subject=529",
    "statistik makroekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=530",
    "pdrb": "https://sulut.bps.go.id/id/statistics-table?subject=530",
    "neraca ekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=531",
    "statistik bisnis": "https://sulut.bps.go.id/id/statistics-table?subject=532",
    "statistik sektoral": "https://sulut.bps.go.id/id/statistics-table?subject=533",
    "keuangan pemerintah, fiskal dan statistik sektor publik": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "keuangan pemerintah": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "perdagangan internasional dan neraca pembayaran": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "perdagangan internasional": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "ekspor": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "impor": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "harga-harga": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "harga": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "inflasi": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "biaya tenaga kerja": "https://sulut.bps.go.id/id/statistics-table?subject=537",
    "ilmu pengetahuan, teknologi dan inovasi": "https://sulut.bps.go.id/id/statistics-table?subject=538",
    "teknologi": "https://sulut.bps.go.id/id/statistics-table?subject=538",
    "pertanian kehutanan perikanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "pertanian": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "perikanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "kehutanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "energi": "https://sulut.bps.go.id/id/statistics-table?subject=558",
    "pertambangan, manufaktur, konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "pertambangan": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "manufaktur": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "transportasi": "https://sulut.bps.go.id/id/statistics-table?subject=560",
    "pariwisata": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "wisata": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "perbankan, asuransi dan finansial": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "perbankan": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "finansial": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "lingkungan": "https://sulut.bps.go.id/id/statistics-table?subject=539",
    "statistik regional dan statistik area kecil": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "statistik regional": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "statistik dan indikator multi-domain": "https://sulut.bps.go.id/id/statistics-table?subject=541",
    "buku tahunan dan ringkasan sejenis": "https://sulut.bps.go.id/id/statistics-table?subject=542",
    "kondisi tempat tinggal, kemiskinan, dan permasalahan sosial lintas sektor": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "gender dan kelompok populasi khusus": "https://sulut.bps.go.id/id/statistics-table?subject=564",
    "masyarakat informasi": "https://sulut.bps.go.id/id/statistics-table?subject=565",
    "globalisasi": "https://sulut.bps.go.id/id/statistics-table?subject=566",
    "indikator millenium development goals (mdgs)": "https://sulut.bps.go.id/id/statistics-table?subject=567",
    "mdgs": "https://sulut.bps.go.id/id/statistics-table?subject=567",
    "perkembangan berkelanjutan": "https://sulut.bps.go.id/id/statistics-table?subject=568",
    "sdgs": "https://sulut.bps.go.id/id/statistics-table?subject=568",
    "kewiraswastaan": "https://sulut.bps.go.id/id/statistics-table?subject=569",
}


def _build_kategori_list():
    """Buat daftar kategori unik (tanpa alias) untuk system prompt."""
    seen_urls = set()
    result = []
    for nama, url in BPS_CATEGORIES.items():
        if url not in seen_urls:
            seen_urls.add(url)
            result.append(f"- {nama}: {url}")
    return "\n".join(result)


SYSTEM_PROMPT = f"""Kamu adalah asisten virtual resmi BPS (Badan Pusat Statistik) Provinsi Sulawesi Utara.

TUGAS UTAMA:
1. Menyapa pengguna dengan ramah dan sopan (gaya pelayanan publik Indonesia)
2. Mengumpulkan informasi tujuan/kebutuhan data pengguna
3. Mengarahkan pengguna ke sumber data di website BPS Sulut. Prioritaskan DAFTAR KATEGORI jika cocok.
4. Memberikan PENJELASAN atau JAWABAN LANGSUNG atas pertanyaan pengguna berdasarkan pengetahuan umummu tentang BPS dan statistik (termasuk jadwal sensus/survei, definisi istilah, dll).

ATURAN KETAT:
- Gunakan bahasa Indonesia yang sopan dan ramah
- Kamu HANYA BOLEH menyebutkan angka/data statistik yang bersumber dari publikasi resmi BPS (Berita Resmi Statistik, Sensus, Survei BPS). JANGAN menyebutkan data dari sumber lain (kementerian, media, riset non-BPS).
- Jika kamu yakin suatu angka berasal dari rilis resmi BPS (misal: hasil Sensus Pertanian 2023, data produksi padi dari KSA BPS, TPT dari Sakernas BPS), kamu DIPERBOLEHKAN menyebutkannya.
- Selalu akhiri dengan: "Untuk data terkini, silakan cek tabel resmi di website BPS."
- Jika kamu TIDAK YAKIN apakah suatu angka berasal dari BPS, JANGAN sebutkan — cukup jelaskan jenis data yang tersedia di BPS.
- Kamu HARUS menjawab pertanyaan umum terkait BPS (jadwal sensus, fungsi BPS, metodologi dasar, dll) selengkap yang kamu tahu.
- JIKA topik TIDAK ADA di DAFTAR KATEGORI, KOSONGKAN field "kategori_cocok". Jangan paksa mencari kategori yang tidak relevan.
- Jika kamu mengetahui link spesifik dan relevan dari website BPS Sulut (URL berawalan https://sulut.bps.go.id/) di luar daftar kategori, kamu DIIZINKAN untuk menyertakannya langsung ke dalam "balasan".
- JANGAN PERNAH memberikan link dari luar https://sulut.bps.go.id/ atau website selain BPS Sulut.
- Jika topik di luar konteks BPS/statistik, tolak dengan sopan

DAFTAR KATEGORI DATA BPS SULUT (SUMBER RESMI):
{_build_kategori_list()}

FORMAT RESPONS:
Kamu HARUS selalu merespons dalam format JSON berikut (tanpa markdown code block):
{{
    "intent": "<salah satu dari: greeting, cari_data, puas, tidak_puas, lainnya>",
    "tujuan": "<topik/kategori data yang dicari jika disebutkan, kosongkan jika tidak>",
    "kategori_cocok": "<nama kategori PERSIS dari daftar di atas HANYA JIKA relevan dengan data tabel yang dicari user. Kosongkan jika user hanya bertanya info umum/jadwal/metodologi, atau jika datanya tidak ada di daftar.>",
    "balasan": "<balasan natural kamu ke user, termasuk jawaban atas pertanyaan atau ringkasan penjelasan data>"
}}

PANDUAN INTENT:
- "greeting": Sapaan awal tanpa info spesifik
- "cari_data": User mencari data/statistik tertentu ATAU BERTANYA informasi seputar BPS (jadwal, sensus, dll)
- "puas": User menyatakan puas/terima kasih/sudah cukup
- "tidak_puas": User menyatakan belum puas/minta bantuan lebih/minta operator
- "lainnya": Pertanyaan di luar konteks BPS

PANDUAN BALASAN UNTUK INTENT "cari_data":
1. Jawab pertanyaan user dengan data yang bersumber dari BPS. Sebutkan angka spesifik HANYA jika kamu yakin angka tersebut dari publikasi resmi BPS (BRS, Sensus, Survei BPS seperti Sakernas, Susenas, KSA, ST2023, dll).
2. Format jawaban: sebutkan 2-4 poin data utama. Gunakan bullet point (*) agar mudah dibaca di WhatsApp. Cantumkan sumber BPS-nya (misal: "Berdasarkan Sensus Pertanian 2023 BPS", "Menurut KSA BPS 2024").
3. JIKA data tabel relevan dengan DAFTAR KATEGORI, JANGAN tulis link-nya di balasan (sistem menambahkannya otomatis jika "kategori_cocok" diisi).
4. JIKA data relevan dengan halaman spesifik website BPS Sulut yang TIDAK ada di DAFTAR KATEGORI, kamu BISA langsung menyertakan link tersebut (https://sulut.bps.go.id/...) di dalam "balasan".

ATURAN PANJANG BALASAN:
- Balasan maksimal 900 karakter. Utamakan menyajikan data/angka, bukan kalimat pengantar.
- Hindari kalimat pembuka seperti "Tentu, kami menyediakan..." atau "Halo!" — langsung ke substansi data.
- Ini adalah chat WhatsApp — user mengharapkan jawaban informatif dan terstruktur.
"""
