# Chatbot BPS Sulawesi Utara

Chatbot layanan Badan Pusat Statistik (BPS) Provinsi Sulawesi Utara. Melayani pengaduan dan konsultasi, membantu pengguna menemukan data statistik di website resmi BPS Sulut dengan dukungan Gemini AI dan fallback rule-based.

## Fitur Utama

- **Hybrid AI + Rule-Based**: Gemini API untuk pemahaman natural + fuzzy matching sebagai fallback offline
- **Key & Model Rotator**: Otomatisasi rotasi multiple API Key Gemini dengan cooldown & fallback model
- **BPS Web API & Cache SQLite**: Integrasi API BPS dengan pencarian data real-time, pembersihan HTML, dan caching SQLite 24 jam
- **Background Pre-Warming**: Pre-warming cache otomatis/cron untuk menjamin waktu respons cepat (< 100ms)
- **Ringkasan Jawaban**: AI memberikan penjelasan singkat tentang data yang tersedia sebelum mengarahkan ke link sumber
- **WhatsApp Integration**: Mendukung Meta Cloud API dan Fonnte sebagai provider
- **WSGI Server Ready**: Menggunakan Waitress (WSGI server produksi) untuk stabilitas tinggi tanpa warning development server
- **Session Persistence**: SQLite — sesi percakapan & riwayat bertahan saat server restart (timeout otomatis via `SESSION_TIMEOUT`)
- **Interactive Buttons**: Tombol interaktif di WhatsApp untuk navigasi layanan
- **Rate Limiting & Validasi**: Proteksi input dan throttle per user
- **Logging Terstruktur**: Rotating file log + stdout

## Struktur Proyek

```
chatbot-bps/
├── main.py              # State machine + fuzzy matching + simulasi terminal
├── llm_engine.py        # Gemini API wrapper + Key/Model Rotator + offline fallback
├── bps_api.py           # Web API client BPS + SQLite 24h cache & HTML cleaner
├── session_manager.py   # Session manager (SQLite-backed)
├── db.py                # SQLite database setup (sessions, messages, bps_cache)
├── config.py            # Konfigurasi + system prompt + daftar kategori BPS
├── wa_webhook.py        # Flask webhook server (Meta + Fonnte)
├── webhook_utils.py     # Validasi input & rate limiting
├── prewarm.py           # Script manual/cron pre-warming cache BPS
├── logging_setup.py     # Setup logging terstruktur
├── requirements.txt
├── .env.example         # Template konfigurasi
├── tests/
│   ├── test_session_manager.py
│   ├── test_cari_link.py
│   ├── test_state_machine.py
│   └── test_webhook_utils.py
└── logs/                # Auto-generated, gitignored
```

## Persyaratan

- Python 3.8+
- Kunci API Google Gemini (opsional — bisa jalan tanpa AI via mode offline)

## Instalasi

```bash
git clone https://github.com/marchelrn/chatbot-bps.git
cd chatbot-bps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Konfigurasi

Salin `.env.example` ke `.env` dan isi dengan token Anda:

```bash
cp .env.example .env
```

**PENTING:** Token di `.env.example` adalah **placeholder**. Ganti semua value dengan token asli Anda.

| Variable | Wajib? | Keterangan |
|---|---|---|
| `GEMINI_API_KEY` | Ya (untuk mode AI) | Google Gemini API key (bisa multiple dipisah koma) |
| `WHATSAPP_PROVIDER` | Tidak | `meta` (default) atau `fonnte` |
| `META_ACCESS_TOKEN` | Untuk WA Meta | Meta Cloud API token |
| `META_PHONE_NUMBER_ID` | Untuk WA Meta | Phone Number ID dari Meta |
| `META_VERIFY_TOKEN` | Untuk WA Meta | Token verifikasi webhook |
| `FONNTE_TOKEN` | Untuk WA Fonnte | Token API Fonnte |
| `GEMINI_MODEL` | Tidak | Default: `gemini-2.0-flash` |
| `SESSION_TIMEOUT` | Tidak | Timeout sesi percakapan dalam detik. Default: `1800` (30 menit) |
| `GEMINI_MODEL_FALLBACKS` | Tidak | Model cadangan jika utama 429/404, dipisah koma (mis. `gemini-flash-lite-latest,gemini-2.0-flash`) |
| `LOG_LEVEL` | Tidak | Default: `INFO` |

## Menjalankan

### Simulasi Terminal

```bash
python main.py
```

Perintah khusus:
- `keluar` — hentikan simulasi
- `reset` — mulai percakapan baru
- `info` — tampilkan info session
- `online` — coba koneksi API lagi

### Background Pre-warming Cache BPS (Opsional)

Untuk menjamin waktu respons < 100ms saat user bertanya data BPS, Anda bisa menjalankan pre-warming cache secara manual atau via cron job:

```bash
# Jalankan sekali secara manual
python prewarm.py

# Contoh setup Cron Job (tiap 6 jam):
# 0 */6 * * * /path/to/.venv/bin/python /path/to/prewarm.py
```

### Webhook WhatsApp

```bash
python wa_webhook.py
```

*Server otomatis berjalan menggunakan **Waitress** (WSGI Server produksi).*

Endpoint:
- `POST /webhook` — menerima pesan WhatsApp
- `GET /webhook` — verifikasi webhook Meta
- `POST /operator/selesai` — akhiri sesi operator, aktifkan bot kembali
- `GET /health` — health check (`{"status": "ok", "mode": "ai/offline"}`)
- `GET /stats` — statistik session aktif

## Testing

```bash
python -m unittest discover tests -v
```

## Alur Percakapan

```
[User kirim pesan] → [Step: awal]
     ↓
[Pilih layanan] → Pengaduan → ke operator
                → Konsultasi → [Step: gemini_tanya_data / rule_based_tanya_data]
     ↓
[Cari data] → [Ringkasan jawaban + link BPS]
     ↓
[Puas?] → Ya → kembali cari data → Tidak → selesai
     ↓
Tidak → ke operator
```
