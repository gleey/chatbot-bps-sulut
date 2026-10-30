# Chatbot BPS Sulawesi Utara

Prototipe layanan konsultasi statistik dan pengaduan WhatsApp untuk BPS Sulawesi
Utara. Backend menggunakan Python, Flask, Waitress, Gemini, dan SQLite. Dashboard
operator menggunakan HTML, Bootstrap, dan JavaScript.

## Perilaku yang tersedia

- Menu Konsultasi dan Pengaduan; tombol native pada Meta, pilihan teks pada Fonnte.
- Gemini mengklasifikasi kebutuhan data. Angka jawaban berasal dari cuplikan rilis
  resmi BPS yang diperoleh aplikasi; angka dan URL hasil model tidak ditampilkan.
- Pencarian BRS/tabel pada halaman API yang dikembalikan, dengan cache default
  **24 jam**. Hasil bukan jaminan data terbaru di seluruh katalog BPS.
- URL unduhan/halaman yang dikembalikan API harus memakai HTTPS dan domain BPS.
  Jika URL individual tidak tersedia, tautan ditandai sebagai **katalog subjek**.
- Fallback aturan tanpa Gemini; tanpa internet, navigasi katalog tetap tersedia,
  tetapi retrieval angka BPS dapat gagal. “Offline” berarti tanpa Gemini.
- Failover key/model berurutan, cooldown default 300 detik, maksimal empat
  percobaan dan anggaran request Gemini delapan detik. Ini bukan pool terdistribusi.
- Pengaduan dialihkan pada Senin–Jumat, 08.00–15.30 WITA. Hari libur nasional
  belum dimodelkan. Di luar jam kerja, bot memberikan kontak resmi.
- Login operator dengan password hash, session 30 menit, CSRF, cookie HttpOnly,
  SameSite=Strict, dan Secure untuk HTTPS. Tidak ada akun/password bawaan.
- Reset/timeout bot lima menit **mengarsipkan** percakapan. Sesi operator aktif
  tidak ditutup oleh timeout biasa. Pengguna tetap bisa mengetik `Selesai`.
- Inbox SQLite menyimpan pesan sebelum ACK webhook. Deduplikasi memakai ID Meta
  atau `inboxid` Fonnte; satu worker memproses antrean secara berurutan.
- Kegagalan kirim tidak dilaporkan sebagai sukses. HTTP sukses dari provider
  menunjukkan permintaan diterima, bukan bukti pesan dibaca/delivered.

Flask/Waitress dan HTTP ke API eksternal bersifat **sinkron**, dengan background
thread. Sistem tidak menggunakan asynchronous I/O. Target tiga detik end-to-end
belum dibuktikan pada jaringan/provider nyata.

## Instalasi

Python **3.10+** diperlukan oleh dependency yang dipin. Audit dijalankan pada
Python 3.14.8. Paket dan hasil tes tercatat di [laporan pengujian](docs/TESTING_REPORT.md).

```bash
git clone https://github.com/gleey/chatbot-bps-sulut.git
cd chatbot-bps-sulut
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Bekerjalah pada branch terpisah. Jangan melacak `.env`, database, backup, atau log
operasional dalam Git.

## Konfigurasi

Isi `.env` sesuai provider yang digunakan. File contoh memuat seluruh opsi.

| Variabel | Kebutuhan |
| --- | --- |
| `WHATSAPP_PROVIDER` | `meta` atau `fonnte` |
| `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN`, `META_APP_SECRET`, `META_API_VERSION` | Wajib ketika server menggunakan Meta |
| `FONNTE_TOKEN`, `FONNTE_WEBHOOK_SECRET` | Token keluar dan secret Authorization masuk pada Fonnte; secret kosong memakai token lama untuk kompatibilitas |
| `OPERATOR_USERNAME`, `OPERATOR_PASSWORD_HASH`, `FLASK_SECRET_KEY` | Wajib untuk membuka dashboard; tanpa ketiganya akses operator ditolak |
| `GEMINI_API_KEYS` | Opsional, dipisah koma; fallback `GEMINI_API_KEY` tunggal |
| `GEMINI_MODEL`, `GEMINI_MODEL_FALLBACKS` | Model utama dan fallback; contoh `gemini-3.6-flash` dan `gemini-3.5-flash-lite` |
| `GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_ATTEMPTS` | Default 8 detik / 4 percobaan; SDK retry internal dinonaktifkan |
| `ROTATOR_COOLDOWN_SECONDS` | Default 300; offline akibat kegagalan dicoba kembali setelah cooldown |
| `BPS_API_KEY`, `BPS_CACHE_TTL` | Key opsional untuk retrieval; TTL default 86400 detik |
| `BPS_SERVER_ACTION_ID` | Opsional; kosong menonaktifkan fallback website yang rapuh |
| `DATABASE_PATH`, `SESSION_TIMEOUT` | File SQLite persisten dan timeout bot, default `chatbot.db` / 300 detik |
| `APP_ENV`, `COOKIE_SECURE` | Development HTTP lokal: `development` / `false`; production HTTPS: `production` / `true` |
| `HOST`, `PORT`, `LOG_LEVEL` | Default `127.0.0.1`, `5000`, `INFO` |

Buat secret session dan hash password secara lokal:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
python -c 'from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass("Password operator: ")))'
```

Simpan hasil sebagai `FLASK_SECRET_KEY` dan `OPERATOR_PASSWORD_HASH`. Jangan
menuliskan password plaintext atau secret provider pada JavaScript. Pertahankan
secret session yang sama saat restart; menggantinya membatalkan semua login.

Model contoh diperiksa terhadap [katalog Google](https://ai.google.dev/gemini-api/docs/models)
pada 30 Oktober 2026. `gemini-3.5-flash` lama sudah ditandai deprecated dalam
[dokumentasi Google](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).
Akses akun, kuota, dan ketersediaan model tetap perlu diuji dengan akun target.
Graph API versi contoh `v23.0` tercantum pada
[jadwal versi Meta](https://developers.facebook.com/docs/graph-api/changelog/).
Jangan menyalin model/version lama tanpa meninjau lifecycle.

## Menjalankan

```bash
python wa_webhook.py
```

Waitress berjalan dengan satu proses dan empat request thread. Startup memvalidasi
konfigurasi provider, lalu memulai inbox worker, prewarm, dan pemeriksa timeout.
Alternatif WSGI dengan factory yang memulai worker:

```bash
waitress-serve --host=127.0.0.1 --port=5000 --call wa_webhook:create_app
```

Jangan menjalankan beberapa proses/instance pada database yang sama. Lock FSM
berlaku hanya dalam proses. Impor `wa_webhook:app` saja tidak memulai worker;
periksa `worker_running` pada `/health` jika memakai launcher lain.

Buka `http://127.0.0.1:5000/operator`; halaman mengarahkan ke login. Dashboard
melakukan polling setiap lima detik, bukan WebSocket. HTTP development memerlukan
`COOKIE_SECURE=false`; browser tidak mengirim cookie Secure melalui HTTP biasa.

Simulasi terminal tanpa provider WhatsApp:

```bash
python main.py
```

Jika Gemini tidak tersedia, pilih mode offline. Perintah terminal: `reset`,
`info`, `online`, dan `keluar`. `Selesai` mengakhiri sesi pengguna.

## Webhook dan endpoint

| Endpoint | Perilaku dan akses |
| --- | --- |
| `GET /webhook` | Challenge Meta dengan verify token nonkosong |
| `POST /webhook` | Meta: `X-Hub-Signature-256` wajib sesuai raw body dan App Secret. Fonnte: `Authorization` wajib sesuai secret masuk |
| `GET/POST /operator/login` | Login; POST memerlukan CSRF dari form; maksimal lima percobaan per IP per lima menit |
| `POST /operator/logout` | Session operator dan CSRF wajib |
| `GET /operator` | Dashboard setelah login |
| `GET /api/operator/sessions` | Daftar sesi operator, maksimal 200 pesan terakhir per sesi |
| `POST /api/operator/send` | Login + CSRF; nomor 8–15 digit, pesan 1–4096 karakter, sesi harus berstatus operator |
| `POST /api/operator/close` | Login + CSRF; menutup setelah provider menerima pesan penutup; pesan masuk pending menyebabkan HTTP 409 |
| `POST /operator/selesai` | Alias close dengan autentikasi session dan CSRF yang sama; key development lama tidak berlaku |
| `GET /health` | Koneksi database, mode Gemini, status worker; tidak melakukan panggilan provider |
| `GET /stats` | Statistik sesi; login operator wajib |

CSRF API dikirim dalam `X-CSRF-Token` menggunakan token session dari HTML.
Webhook dibatasi 256 KiB, maksimal 100 pesan per batch, dan 1000 event pending.
Pesan teks melebihi 4096 karakter dipotong. Deduplikasi diperiksa sebelum throttle
per nomor dua detik. HTTP 429/503 tidak menerima batch; provider dapat mencoba
kembali. Status notification Meta tidak diperlakukan sebagai pesan pengguna.

**Fonnte:** [payload resmi](https://docs.fonnte.com/webhook-reply-message/)
menyertakan `inboxid`. Dokumentasi yang dibaca belum membuktikan header auth masuk
langsung. Jika akun tidak dapat mengirim header, gunakan relay terkontrol yang
memverifikasi sumber terlebih dahulu dan menambahkan Authorization. Jangan
membuka endpoint Fonnte tanpa autentikasi. Dukungan live perlu divalidasi.

## Persistensi, migrasi, dan pemulihan

- `sessions`: status aktif; `messages`: pesan bertaut ke `conversation_id`;
  `conversations`: identitas percakapan, jenis konsultasi/pengaduan, dan penutupan.
- Reset membersihkan konteks aktif dan mempertahankan transcript arsip. Gemini
  menerima maksimal 30 pesan konteks; SessionManager mengambil 100 pesan aktif.
- Migrasi v2 menambah tabel/kolom tanpa menghapus data lama. Database lama mendapat
  backup SQLite online `*.pre-v2-*.bak` sebelum migrasi. File baru dibatasi mode
  `0600`; lakukan startup dengan user layanan yang memiliki direktori database.
- Tidak ada purge arsip otomatis. Kebijakan retensi harus ditetapkan BPS.
  `SessionManager.purge_archives(retention_days)` hanya untuk pemeliharaan
  eksplisit setelah backup; menghapus arsip tertutup yang melewati batas, pesan
  arsip, dan event inbox selesai/gagal yang lebih lama. Sesi aktif tidak dihapus.
- Deduplikasi event `done` dipertahankan tujuh hari. Event gagal disimpan untuk
  pemeriksaan. Inbox dan backup juga memuat data pribadi; batasi aksesnya.
- Event `queued` bertahan setelah restart. Event `processing` yang terputus menjadi
  `failed/interrupted_unknown`. Tidak ada retry otomatis untuk pengiriman ambigu;
  cocokkan transcript dan provider sebelum tindakan manual. Ini bukan jaminan
  exactly-once di antara SQLite dan provider eksternal.

Backup database menggunakan SQLite backup API saat aplikasi berjalan, atau
hentikan layanan sebelum menyalin file beserta WAL yang masih aktif. Jangan
menyalin hanya file `.db` yang sedang ditulis. Untuk rollback skema, hentikan
layanan dan pulihkan backup yang kompatibel; kode lama dapat menghapus arsip.

## Production

Gunakan HTTPS melalui reverse proxy, `APP_ENV=production`, `COOKIE_SECURE=true`,
secret session acak minimal 32 karakter, password hash, dan credential provider
lengkap. Batasi akses langsung port Waitress dan akses direktori `.env`, log,
database, serta backup. Sesuaikan retensi dan pemantauan event gagal sebelum
pemakaian operasional. Reverse proxy tidak otomatis dipercaya untuk identitas IP.

SQLite WAL mencukupi demonstrasi satu proses. Multi-proses/host memerlukan
koordinasi antrean dan lock terdistribusi; evaluasi PostgreSQL/Redis setelah
pengukuran beban. Startup/tes tidak membuktikan high availability produksi.

## Tes dan bukti audit

```bash
python -m unittest discover -s tests -v
python -Wd -m unittest discover -s tests -v
python -m tests.benchmark > docs/performance_results.json
```

Tes menggunakan credential sintetis, direktori sementara lintas platform, Flask
test client, dan mock API. Koneksi socket jaringan diblokir. Benchmark mengukur
pemrosesan lokal dan ACK; API dimock tanpa latensi buatan. Tidak ada pengiriman
WhatsApp nyata. Hasil benchmark tidak membuktikan SLA tiga detik.

- [Audit dan status fitur](docs/PROJECT_AUDIT.md)
- [File perubahan dan alasan teknis](docs/IMPLEMENTATION_REPORT.md)
- [Penyesuaian laporan magang](docs/REPORT_ALIGNMENT.md)
- [Hasil pengujian dan performa](docs/TESTING_REPORT.md)
- [Changelog](docs/CHANGELOG.md)
- [Panduan demonstrasi](docs/DEMO_GUIDE.md)
