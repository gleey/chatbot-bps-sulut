# Chatbot BPS Sulawesi Utara

Chatbot layanan Badan Pusat Statistik (BPS) Provinsi Sulawesi Utara. Melayani pengaduan dan konsultasi, membantu pengguna menemukan data statistik di website resmi BPS Sulut dengan dukungan Gemini AI, integrasi live Web API & Server Action BPS Sulut, serta Dashboard Operator untuk penanganan pengaduan.

## Fitur Utama

- **Hybrid AI + Rule-Based**: Gemini API untuk pemahaman natural + fuzzy matching sebagai fallback offline
- **Dashboard Operator (Web UI)**: Antarmuka berbasis web (`/operator`) untuk petugas BPS membalas pesan pengaduan pengguna secara real-time
- **Pengaturan Jam Kerja Operator (08.00–15.30 WITA)**: Pengaduan/respon tidak puas pada jam kerja langsung diteruskan ke operator. Di luar jam kerja, sistem otomatis menginformasikan jam operasional dan kontak resmi BPS
- **Auto-Closing & Timeout (5 Menit)**: Daemon thread otomatis mendeteksi inaktivitas 5 menit (`SESSION_TIMEOUT=300`), mengirim pesan penutup otomatis, dan mereset sesi
- **Pencarian Link Tabel Statistik Individual**: Integrasi Server Action BPS Sulut untuk menyajikan 2 link URL tabel statistik individual terbaru yang paling relevan dengan kata kunci pengguna
- **Pemetaan Kata Kunci 28 Subjek BPS**: Cakupan kata kunci komprehensif untuk 28 subjek resmi BPS Sulut (kependudukan, inflasi, pertambahan penduduk, perceraian, kemiskinan/PKH, air minum, pertanian, pariwisata, dll)
- **Key & Model Rotator**: Otomatisasi rotasi multiple API Key Gemini dengan cooldown & fallback model saat 429/404
- **BPS Web API & Cache SQLite**: Integrasi API BPS dengan pencarian data real-time, pembersihan HTML, dan caching SQLite 24 jam
- **Background Pre-Warming**: Pre-warming cache otomatis untuk menjamin waktu respons cepat (< 100ms)
- **WhatsApp Integration**: Mendukung Meta Cloud API dan Fonnte sebagai provider
- **WSGI Server Ready**: Menggunakan Waitress (WSGI server produksi) untuk stabilitas tinggi tanpa warning development server
- **Session Persistence**: SQLite — sesi percakapan & riwayat bertahan saat server restart
- **Interactive Buttons**: Tombol interaktif di WhatsApp untuk navigasi layanan
- **Rate Limiting & Validasi**: Proteksi input dan throttle per user
- **Logging Terstruktur**: Rotating file log + stdout

## Struktur Proyek

```
chatbot-bps/
├── main.py              # State machine + fuzzy matching + simulasi terminal
├── llm_engine.py        # Gemini API wrapper + Key/Model Rotator + offline fallback
├── bps_api.py           # Web API client & Server Action BPS + SQLite 24h cache & HTML cleaner
├── session_manager.py   # Session manager (SQLite-backed) dengan auto-timeout
├── db.py                # SQLite database setup (sessions, messages, bps_cache)
├── config.py            # Konfigurasi + system prompt + daftar kategori & kata kunci BPS
├── wa_webhook.py        # Flask webhook server (Meta + Fonnte + Dashboard Operator)
├── webhook_utils.py     # Validasi input & rate limiting
├── prewarm.py           # Script manual/cron pre-warming cache BPS
├── logging_setup.py     # Setup logging terstruktur
├── templates/
│   └── operator.html    # Web UI Dashboard Operator Pengaduan
├── requirements.txt
├── .env.example         # Template konfigurasi
├── tests/
│   ├── test_session_manager.py
│   ├── test_cari_link.py
│   ├── test_state_machine.py
│   ├── test_bps_api.py
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

| Variable | Wajib? | Keterangan |
| --- | --- | --- |
| `GEMINI_API_KEY` | Ya (untuk mode AI) | Google Gemini API key (bisa multiple dipisah koma) |
| `WHATSAPP_PROVIDER` | Tidak | `meta` (default) atau `fonnte` |
| `META_ACCESS_TOKEN` | Untuk WA Meta | Meta Cloud API token |
| `META_PHONE_NUMBER_ID` | Untuk WA Meta | Phone Number ID dari Meta |
| `META_VERIFY_TOKEN` | Untuk WA Meta | Token verifikasi webhook |
| `FONNTE_TOKEN` | Untuk WA Fonnte | Token API Fonnte |
| `GEMINI_MODEL` | Ya | Default: `gemini-3.5-flash` |
| `SESSION_TIMEOUT` | Tidak | Timeout inaktivitas sesi dalam detik. Default: `300` (5 menit) |
| `GEMINI_MODEL_FALLBACKS` | Tidak | Model cadangan jika utama 429/404, dipisah koma |

## Menjalankan

### 1. Webhook WhatsApp & Dashboard Operator

```bash
python wa_webhook.py
```

*Server otomatis berjalan menggunakan **Waitress** (WSGI Server produksi) pada Port 5000.*

Endpoint Web & API:

- `GET /operator` — **Web UI Dashboard Chat Operator**
- `GET /api/operator/sessions` — API daftar sesi pengaduan aktif
- `POST /api/operator/send` — API kirim balasan operator ke WhatsApp
- `POST /api/operator/close` — API selesaikan sesi operator & aktifkan bot kembali
- `POST /webhook` — menerima pesan WhatsApp dari Meta/Fonnte
- `GET /webhook` — verifikasi webhook Meta
- `GET /health` — health check (`{"status": "ok", "mode": "ai/offline"}`)
- `GET /stats` — statistik session aktif

### 2. Simulasi Terminal

```bash
python main.py
```

Perintah khusus:
- `keluar` — hentikan simulasi
- `reset` — mulai percakapan baru
- `info` — tampilkan info session
- `online` — coba koneksi API lagi

## Testing

```bash
python -m unittest discover tests -v
```

## Alur Percakapan & Jam Kerja

```
[User kirim pesan] → [Step: awal]
     ↓
[Pilih layanan] ──→ Pengaduan ──→ [Cek Jam Kerja: Senin–Jumat 08.00–15.30 WITA]
                 │                   ├─ Jam Kerja: Ke Operator (Web UI /operator)
                 │                   └─ Luar Jam Kerja: Info Maaf + Kontak BPS Sulut
                 │
                 └── Konsultasi ─→ [Step: gemini_tanya_data / rule_based_tanya_data]
                                          ↓
                              [Cari data] ─→ [Ringkasan Jawaban + Data BPS + 2 Link Tabel Individual]
                                          ↓
                              [Puas?] ──→ Ya ──→ Lanjut cari data / Ketik "Selesai"
                                      └─→ Tidak ─→ [Cek Jam Kerja]
                                                    ├─ Jam Kerja: Ke Operator
                                                    └─ Luar Jam Kerja: Info Maaf + Kontak BPS
```
