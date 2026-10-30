# Chatbot BPS Sulawesi Utara

Chatbot WhatsApp untuk konsultasi statistik dan pengaduan layanan BPS Provinsi
Sulawesi Utara. Aplikasi menggabungkan klasifikasi kebutuhan menggunakan Google
Gemini, pencarian sumber resmi BPS, serta dashboard operator untuk penanganan
pengaduan.

## Fitur

- **Konsultasi statistik** — pencarian Berita Resmi Statistik dan tabel BPS,
  dilengkapi sumber serta tanggal jika tersedia.
- **AI dan fallback aturan** — klasifikasi kebutuhan melalui Gemini dengan
  failover API key/model serta mode tanpa AI.
- **Dua provider WhatsApp** — Meta Cloud API dengan tombol interaktif dan Fonnte
  dengan pilihan berbasis teks.
- **Pengaduan dan operator** — alih kelola pada Senin–Jumat, 08.00–15.30 WITA,
  dashboard percakapan, balasan manual, dan penutupan sesi.
- **Keamanan** — verifikasi HMAC webhook Meta, autentikasi operator, CSRF,
  validasi input, rate limiting, dan deduplikasi pesan masuk.
- **Persistensi** — sesi dan arsip percakapan di SQLite, timeout bot lima menit,
  serta cache BPS dengan TTL default 24 jam.

## Teknologi

| Komponen | Teknologi |
| --- | --- |
| Backend | Python, Flask, Waitress |
| Klasifikasi AI | Google Gemini API |
| WhatsApp | Meta WhatsApp Cloud API / Fonnte |
| Sumber statistik | BPS Web API dan katalog BPS Sulawesi Utara |
| Penyimpanan | SQLite dengan WAL |
| Dashboard | HTML, Bootstrap 5, JavaScript |

## Prasyarat

- Python **3.10+** dan pip.
- Akun serta credential provider WhatsApp untuk menjalankan server webhook.
- API key Gemini untuk mode AI dan BPS Web API untuk retrieval data; keduanya
  opsional jika hanya memakai fallback aturan dan navigasi katalog.
- Endpoint HTTPS yang dapat dijangkau provider untuk menerima webhook nyata.

## Instalasi

```bash
git clone https://github.com/gleey/chatbot-bps-sulut.git
cd chatbot-bps-sulut
python -m venv .venv
```

Aktifkan virtual environment:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Pasang dependency dan siapkan konfigurasi:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Pada PowerShell, gunakan `Copy-Item .env.example .env`. Jika `.env` sudah ada,
perbarui isinya tanpa menimpa konfigurasi lama.

## Konfigurasi

Format `.env` lama tetap didukung. Contoh ringkas tersedia dalam
[.env.example](.env.example); parameter tambahan di bawah bersifat opsional kecuali
dibutuhkan oleh fitur yang digunakan.

| Variabel | Keterangan |
| --- | --- |
| `WHATSAPP_PROVIDER` | `meta` atau `fonnte` |
| `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID` | Credential pengiriman Meta |
| `META_VERIFY_TOKEN` | Token challenge webhook Meta |
| `META_APP_SECRET` | Diperlukan untuk mengaktifkan verifikasi signature dan menerima pesan Meta |
| `META_API_VERSION` | Opsional; default `v23.0` |
| `FONNTE_TOKEN`, `FONNTE_WEBHOOK_SECRET` | Token pengiriman dan secret autentikasi webhook Fonnte |
| `GEMINI_API_KEYS` | API key Gemini, dipisah koma; alternatif satu key: `GEMINI_API_KEY` |
| `GEMINI_MODEL`, `GEMINI_MODEL_FALLBACKS` | Model utama dan model cadangan |
| `BPS_API_KEY` | API key BPS untuk mengambil rilis dan tabel |
| `OPERATOR_USERNAME`, `OPERATOR_PASSWORD_HASH` | Identitas login dan hash password operator |
| `FLASK_SECRET_KEY` | Secret penandatanganan session operator |
| `DATABASE_PATH` | Lokasi file SQLite; default `chatbot.db` |
| `SESSION_TIMEOUT`, `BPS_CACHE_TTL` | Timeout bot dan TTL cache dalam detik; default `300` dan `86400` |
| `APP_ENV`, `COOKIE_SECURE` | Development HTTP lokal: `development` / `false`; production HTTPS: `production` / `true` |
| `HOST`, `PORT` | Alamat server; default `127.0.0.1:5000` |

Isi credential provider seperti pada `.env` lama. Versi API, lokasi database,
timeout, dan opsi internal memiliki default sehingga tidak perlu ditambahkan
hanya untuk memulai server lokal. Nilai `.env` yang sudah ada tetap digunakan.

Khusus Meta, App Secret tidak dapat diturunkan dari access token atau verify token.
Tambahkan `META_APP_SECRET` dari dashboard Meta untuk menerima pesan bertanda
tangan. Jika belum diisi, server development tetap berjalan dengan peringatan;
POST webhook mengembalikan HTTP 503 dan tidak memproses pesan. Production tetap
mewajibkan secret tersebut.

Login dashboard adalah fitur terpisah yang memerlukan username, password hash,
dan secret session; tidak ada akun bawaan. Pengaturan ini tidak menghalangi
startup server development. Cookie lokal memakai HTTP secara default; cookie
production memakai Secure secara default.

Buat secret session dan hash password secara lokal:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
python -c 'from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass("Password operator: ")))'
```

Simpan hasilnya sebagai `FLASK_SECRET_KEY` dan `OPERATOR_PASSWORD_HASH`. Jangan
memasukkan credential ke kode, screenshot, atau commit.

## Menjalankan aplikasi

### Webhook WhatsApp dan dashboard

```bash
python wa_webhook.py
```

Server menggunakan Waitress. Buka `http://127.0.0.1:5000/operator` untuk login
operator dan `http://127.0.0.1:5000/health` untuk memeriksa database serta status
worker. Pastikan `worker_running` bernilai `true`.

Alternatif menjalankan melalui WSGI factory:

```bash
waitress-serve --host=127.0.0.1 --port=5000 --call wa_webhook:create_app
```

Gunakan **satu proses aplikasi** untuk database yang sama. Factory `create_app`
memulai worker inbox, prewarm cache, dan pemeriksa timeout. Mengimpor `app` saja
tidak memulai worker tersebut.

### Simulasi terminal

```bash
python main.py
```

Simulasi ini tidak memerlukan provider WhatsApp. Jika Gemini tidak tersedia,
pilih mode offline pada menu terminal.

| Perintah | Fungsi |
| --- | --- |
| `reset` | Memulai sesi baru dan mempertahankan arsip lama |
| `info` | Menampilkan informasi sesi |
| `online` | Mencoba kembali koneksi Gemini |
| `Selesai` | Mengakhiri percakapan |
| `keluar` | Menutup simulasi |

## Alur penggunaan

1. Pengguna mengirim sapaan melalui WhatsApp.
2. Bot menampilkan pilihan **Konsultasi** dan **Pengaduan**.
3. Konsultasi mengarahkan pengguna ke rilis atau tabel resmi BPS, kemudian meminta
   penilaian **Ya/Tidak** saat hasil pencarian tersedia.
4. Pengaduan atau jawaban **Tidak** dialihkan ke operator pada jam layanan.
   Di luar jam layanan, bot memberikan informasi kontak BPS.
5. Operator membalas melalui dashboard dan menutup sesi setelah selesai.
   Pengguna juga dapat mengetik **Selesai**.

Dashboard memperbarui daftar percakapan melalui polling setiap lima detik.
Sesi operator aktif dikecualikan dari timeout bot biasa.

## Endpoint utama

| Metode | Endpoint | Fungsi |
| --- | --- | --- |
| GET | `/webhook` | Verifikasi challenge Meta |
| POST | `/webhook` | Menerima pesan provider yang telah diautentikasi |
| GET, POST | `/operator/login` | Login operator |
| POST | `/operator/logout` | Logout operator |
| GET | `/operator` | Dashboard operator |
| GET | `/api/operator/sessions` | Daftar percakapan operator |
| POST | `/api/operator/send` | Mengirim balasan operator |
| POST | `/api/operator/close` | Menutup dan mengarsipkan sesi |
| GET | `/health` | Health check database dan status worker |
| GET | `/stats` | Statistik sesi untuk operator yang sudah login |

API operator memerlukan session login. Request perubahan data juga memerlukan
CSRF token. Webhook Meta memerlukan `X-Hub-Signature-256`; Fonnte memerlukan
`Authorization` dan ID pesan stabil berupa `inboxid` atau `id`. Jika provider
Fonnte tidak dapat menyertakan header autentikasi masuk, gunakan relay tepercaya
yang memverifikasi sumber sebelum meneruskan pesan.

## Struktur proyek

```text
chatbot-bps-sulut/
├── main.py                   # FSM dan simulasi terminal
├── wa_webhook.py             # Webhook, pengiriman, dan API operator
├── message_queue.py          # Inbox persisten dan worker pesan
├── operator_auth.py          # Login, session, dan CSRF
├── llm_engine.py             # Gemini dan fallback aturan
├── bps_api.py                # Retrieval dan cache BPS
├── session_manager.py        # Sesi aktif dan arsip percakapan
├── db.py                     # Skema dan migrasi SQLite
├── config.py                 # Konfigurasi dan kategori data
├── webhook_utils.py          # Validasi dan rate limiting
├── logging_setup.py          # Logging aplikasi
├── prewarm.py                # Prewarm cache manual
├── templates/                # Dashboard dan halaman login
├── tests/                    # Unit test, integrasi, dan benchmark
├── .env.example
├── requirements.txt
└── LICENSE
```

## Pengujian

```bash
python -m unittest discover -s tests -v
```

Tes memakai database sementara, credential sintetis, Flask test client, dan mock
API eksternal. Koneksi jaringan diblokir sehingga tes tidak memerlukan API key
asli atau mengirim pesan WhatsApp.

Benchmark pemrosesan lokal:

```bash
python -m tests.benchmark
```

Benchmark menggunakan mock API dan tidak membuktikan waktu respons WhatsApp
end-to-end. Uji integrasi dengan akun provider dilakukan terpisah.

## Deployment dan batasan

- Gunakan HTTPS, `APP_ENV=production`, `COOKIE_SECURE=true`, secret session acak
  minimal 32 karakter, dan credential provider yang lengkap untuk production.
- Backend memakai I/O sinkron dengan background thread. Lock sesi berlaku dalam
  satu proses; deployment multi-proses memerlukan koordinasi tambahan.
- Angka jawaban berasal dari hasil retrieval resmi. Cache default 24 jam dan
  pencarian terbatas pada halaman API yang diperoleh; hasil tidak menjamin data
  terbaru dari seluruh katalog. Tautan katalog diberi label jika URL individual
  tidak tersedia.
- Mode offline berarti tanpa Gemini. Retrieval angka BPS tetap memerlukan
  koneksi internet dan API key.
- Reset mengarsipkan percakapan. Database lama mendapat backup sebelum migrasi;
  tetapkan kebijakan retensi dan backup untuk database, inbox, serta arsip.
- Event dengan pengiriman gagal atau ambigu membutuhkan pemeriksaan sebelum
  diulang. Respons sukses provider menunjukkan permintaan diterima, bukan bukti
  pesan telah dibaca atau diterima pengguna.
- Hari libur nasional belum dimodelkan. Target respons tiga detik dan integrasi
  provider live tetap membutuhkan pengukuran pada lingkungan tujuan.

## Kontribusi

Buat branch kerja, lakukan perubahan sesuai cakupan, lalu jalankan tes sebelum
membuka pull request. Sertakan ringkasan perubahan dan hasil verifikasi. Laporkan
bug atau usulan melalui [GitHub Issues](https://github.com/gleey/chatbot-bps-sulut/issues).

## Lisensi

Proyek ini menggunakan [MIT License](LICENSE).
