import os
from dotenv import load_dotenv

load_dotenv()

# Google Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL")

# Multi-key rotation — pisahkan dengan koma di .env
# Jika GEMINI_API_KEYS tidak di-set, fallback ke GEMINI_API_KEY tunggal
_raw_keys = os.getenv("GEMINI_API_KEYS", GEMINI_API_KEY)
GEMINI_API_KEYS = [k.strip() for k in _raw_keys.split(",") if k.strip()]

# Multi-model fallback — dicoba berurutan saat model sebelumnya gagal (429/404)
_raw_fallbacks = os.getenv("GEMINI_MODEL_FALLBACKS")
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
    # 519: Kependudukan dan Migrasi
    "kependudukan dan migrasi": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "kependudukan": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "penduduk": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "migrasi": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "perceraian": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "nikah": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "cerai": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "laju pertumbuhan penduduk": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "kepadatan penduduk": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "rasio jenis kelamin": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "beban ketergantungan": "https://sulut.bps.go.id/id/statistics-table?subject=519",

    # 520: Tenaga Kerja
    "tenaga kerja": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "pengangguran": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "tpt": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "tpak": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "angkatan kerja": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "pekerja": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "jam kerja": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "pencari kerja": "https://sulut.bps.go.id/id/statistics-table?subject=520",

    # 521: Pendidikan
    "pendidikan": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "sekolah": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "beasiswa": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "apk": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "apm": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "perguruan tinggi": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "literasi": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "madrasah": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "melek aksara": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "pustakawan": "https://sulut.bps.go.id/id/statistics-table?subject=521",

    # 522: Kesehatan
    "kesehatan": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "jaminan kesehatan": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "merokok": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "penyakit": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "rumah sakit": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "puskesmas": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "posyandu": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "tenaga kesehatan": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "kb": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "imunisasi": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "asi": "https://sulut.bps.go.id/id/statistics-table?subject=522",

    # 523: Konsumsi dan Pendapatan
    "konsumsi dan pendapatan": "https://sulut.bps.go.id/id/statistics-table?subject=523",
    "konsumsi": "https://sulut.bps.go.id/id/statistics-table?subject=523",
    "pendapatan": "https://sulut.bps.go.id/id/statistics-table?subject=523",
    "pengeluaran per kapita": "https://sulut.bps.go.id/id/statistics-table?subject=523",
    "perkapita": "https://sulut.bps.go.id/id/statistics-table?subject=523",
    "komoditas makanan": "https://sulut.bps.go.id/id/statistics-table?subject=523",

    # 524: Perlindungan Sosial
    "perlindungan sosial": "https://sulut.bps.go.id/id/statistics-table?subject=524",
    "bansos": "https://sulut.bps.go.id/id/statistics-table?subject=524",
    "bantuan sosial": "https://sulut.bps.go.id/id/statistics-table?subject=524",
    "kpm": "https://sulut.bps.go.id/id/statistics-table?subject=524",
    "pkh": "https://sulut.bps.go.id/id/statistics-table?subject=524",
    "kks": "https://sulut.bps.go.id/id/statistics-table?subject=524",

    # 525: Pemukiman dan Perumahan
    "pemukiman dan perumahan": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "perumahan": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "pemukiman": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "air minum": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "sanitasi": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "penerangan": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "kloset": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "ipal": "https://sulut.bps.go.id/id/statistics-table?subject=525",

    # 526: Hukum dan Kriminal
    "hukum dan kriminal": "https://sulut.bps.go.id/id/statistics-table?subject=526",
    "kriminal": "https://sulut.bps.go.id/id/statistics-table?subject=526",
    "kejahatan": "https://sulut.bps.go.id/id/statistics-table?subject=526",
    "pencurian": "https://sulut.bps.go.id/id/statistics-table?subject=526",
    "penganiayaan": "https://sulut.bps.go.id/id/statistics-table?subject=526",

    # 527: Budaya
    "budaya": "https://sulut.bps.go.id/id/statistics-table?subject=527",
    "haji": "https://sulut.bps.go.id/id/statistics-table?subject=527",
    "jemaah haji": "https://sulut.bps.go.id/id/statistics-table?subject=527",
    "warisan budaya": "https://sulut.bps.go.id/id/statistics-table?subject=527",

    # 528: Aktivitas Politik dan Komunitas
    "aktivitas politik dan komunitas": "https://sulut.bps.go.id/id/statistics-table?subject=528",
    "politik": "https://sulut.bps.go.id/id/statistics-table?subject=528",
    "demokrasi": "https://sulut.bps.go.id/id/statistics-table?subject=528",
    "idi": "https://sulut.bps.go.id/id/statistics-table?subject=528",
    "indeks demokrasi": "https://sulut.bps.go.id/id/statistics-table?subject=528",
    "dprd": "https://sulut.bps.go.id/id/statistics-table?subject=528",

    # 529: Penggunaan Waktu
    "penggunaan waktu": "https://sulut.bps.go.id/id/statistics-table?subject=529",

    # 530: Makroekonomi & PDRB
    "statistik makroekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=530",
    "pdrb": "https://sulut.bps.go.id/id/statistics-table?subject=530",

    # 531: Neraca Ekonomi
    "neraca ekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=531",
    "pertumbuhan ekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=531",
    "ekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=531",

    # 532 & 533: Bisnis & Sektoral
    "statistik bisnis": "https://sulut.bps.go.id/id/statistics-table?subject=532",
    "statistik sektoral": "https://sulut.bps.go.id/id/statistics-table?subject=533",
    "panjang jalan": "https://sulut.bps.go.id/id/statistics-table?subject=533",

    # 534: Keuangan Pemerintah
    "keuangan pemerintah, fiskal dan statistik sektor publik": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "keuangan pemerintah": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "pegawai negeri": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "pns": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "asn": "https://sulut.bps.go.id/id/statistics-table?subject=534",

    # 535: Perdagangan Internasional
    "perdagangan internasional dan neraca pembayaran": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "perdagangan internasional": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "ekspor": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "impor": "https://sulut.bps.go.id/id/statistics-table?subject=535",

    # 536: Harga-Harga & Inflasi
    "harga-harga": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "harga": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "inflasi": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "ihk": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "ntp": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "nilai tukar petani": "https://sulut.bps.go.id/id/statistics-table?subject=536",

    # 537: Biaya Tenaga Kerja
    "biaya tenaga kerja": "https://sulut.bps.go.id/id/statistics-table?subject=537",
    "upah": "https://sulut.bps.go.id/id/statistics-table?subject=537",
    "gaji": "https://sulut.bps.go.id/id/statistics-table?subject=537",

    # 538: Ilmu Pengetahuan & Teknologi
    "ilmu pengetahuan, teknologi dan inovasi": "https://sulut.bps.go.id/id/statistics-table?subject=538",
    "teknologi": "https://sulut.bps.go.id/id/statistics-table?subject=538",

    # 557: Pertanian, Kehutanan, Perikanan
    "pertanian kehutanan perikanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "pertanian": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "perikanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "kehutanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "petani": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "padi": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "beras": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "jagung": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "daging": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "telur": "https://sulut.bps.go.id/id/statistics-table?subject=557",

    # 558: Energi
    "energi": "https://sulut.bps.go.id/id/statistics-table?subject=558",
    "listrik": "https://sulut.bps.go.id/id/statistics-table?subject=558",
    "pln": "https://sulut.bps.go.id/id/statistics-table?subject=558",

    # 559: Pertambangan, Manufaktur, Konstruksi
    "pertambangan, manufaktur, konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "pertambangan": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "manufaktur": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "industri": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "ikk": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "indeks kemahalan konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",

    # 560: Transportasi
    "transportasi": "https://sulut.bps.go.id/id/statistics-table?subject=560",
    "penerbangan": "https://sulut.bps.go.id/id/statistics-table?subject=560",
    "kapal laut": "https://sulut.bps.go.id/id/statistics-table?subject=560",
    "bandara": "https://sulut.bps.go.id/id/statistics-table?subject=560",
    "pelabuhan": "https://sulut.bps.go.id/id/statistics-table?subject=560",

    # 561: Pariwisata
    "pariwisata": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "wisata": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "wisman": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "hotel": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "tpk": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "lama menginap": "https://sulut.bps.go.id/id/statistics-table?subject=561",

    # 562: Perbankan, Asuransi dan Finansial
    "perbankan, asuransi dan finansial": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "perbankan": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "finansial": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "bank": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "koperasi": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "umkm": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "kredit": "https://sulut.bps.go.id/id/statistics-table?subject=562",

    # 539: Lingkungan
    "lingkungan": "https://sulut.bps.go.id/id/statistics-table?subject=539",
    "bencana alam": "https://sulut.bps.go.id/id/statistics-table?subject=539",
    "bmkg": "https://sulut.bps.go.id/id/statistics-table?subject=539",
    "suhu udara": "https://sulut.bps.go.id/id/statistics-table?subject=539",

    # 540: Statistik Regional
    "statistik regional dan statistik area kecil": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "statistik regional": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "kecamatan": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "desa": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "kelurahan": "https://sulut.bps.go.id/id/statistics-table?subject=540",

    # 541 & 542: Multi-Domain & Buku Tahunan
    "statistik dan indikator multi-domain": "https://sulut.bps.go.id/id/statistics-table?subject=541",
    "buku tahunan dan ringkasan sejenis": "https://sulut.bps.go.id/id/statistics-table?subject=542",

    # 563: Kemiskinan & Sosial
    "kondisi tempat tinggal, kemiskinan, dan permasalahan sosial lintas sektor": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "kemiskinan": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "miskin": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "garis kemiskinan": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "gini ratio": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "ipm": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "indeks pembangunan manusia": "https://sulut.bps.go.id/id/statistics-table?subject=563",

    # 564: Gender
    "gender dan kelompok populasi khusus": "https://sulut.bps.go.id/id/statistics-table?subject=564",
    "gender": "https://sulut.bps.go.id/id/statistics-table?subject=564",
    "perempuan": "https://sulut.bps.go.id/id/statistics-table?subject=564",
    "ipg": "https://sulut.bps.go.id/id/statistics-table?subject=564",
    "idg": "https://sulut.bps.go.id/id/statistics-table?subject=564",

    # 565: Masyarakat Informasi
    "masyarakat informasi": "https://sulut.bps.go.id/id/statistics-table?subject=565",
    "internet": "https://sulut.bps.go.id/id/statistics-table?subject=565",
    "komputer": "https://sulut.bps.go.id/id/statistics-table?subject=565",

    # 566-569: Globalisasi, MDGs, SDGs, Kewiraswastaan
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
