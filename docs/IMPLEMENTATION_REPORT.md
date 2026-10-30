# Laporan Implementasi

Perubahan dikerjakan pada `audit/security-reliability`, berangkat dari commit
`7ec2038`. Tidak ada penggantian framework/database, dependency baru di luar
paket stack yang sudah ada, deployment, push, atau pengiriman WhatsApp nyata.
Versi dependency lama diperbarui agar sesuai kontrak SDK yang diuji.

| File | Perubahan dan alasan |
| --- | --- |
| `config.py` | Env kosong aman, validasi startup, pilihan provider, batas retry/timeout, secret auth dan prompt klasifikasi; mencegah crash dan jawaban angka tanpa sumber |
| `.env.example` | App Secret Meta, login operator, cookie, path DB, TTL, model/version terverifikasi dan batas request; seluruh secret kosong |
| `.gitignore` | Abaikan varian .env, DB, WAL/SHM/journal dan backup migrasi agar data pribadi tidak ikut commit |
| `requirements.txt` | Pin SDK Google, requests dan dotenv ke versi yang benar-benar dipakai dalam validasi |
| `db.py` | WAL, busy timeout, izin file, migrasi aditif v2 dan backup online; pertahankan data lama |
| `session_manager.py` | Conversation ID, history aktif terpisah, arsip/purge eksplisit, jenis pengaduan, timeout non-operator dan batas history |
| `webhook_utils.py` | Validasi nomor, lock per nomor dengan ukuran tetap, rate limiter thread-safe |
| `message_queue.py` (baru) | Inbox persisten dan terbatas, batch atomik, deduplikasi, worker tunggal dan status gagal/ambigu; menggantikan thread per pesan |
| `operator_auth.py` (baru) | Password hash, session, TTL, throttling login, CSRF, cookie, CSP nonce dan guard untuk semua rute operator |
| `wa_webhook.py` | Signature raw body, parsing seluruh batch, auth provider terpisah, respons send tervalidasi, API operator aman, penutupan hanya setelah send diterima, WSGI factory dan DB health |
| `templates/operator.html` | Token CSRF, logout, DOM textContent, status polling dan batas pesan; pertahankan struktur Bootstrap |
| `templates/operator_login.html` (baru) | Form login sederhana dengan CSRF dan input berlabel; tanpa credential pada frontend |
| `logging_setup.py` | Batasi debug pustaka HTTP yang dapat mencetak URL key |
| `main.py` | Pilihan menu deterministik, Selesai global, serialisasi FSM, jawaban angka/URL dari retrieval dan label sumber/tanggal yang jelas |
| `llm_engine.py` | Lock rotator, timeout/retry terbatas, cooldown, penutupan client dan validasi JSON; pemulihan offline tanpa loop tanpa batas |
| `bps_api.py` | Satu fungsi pencarian tabel, API resmi dahulu, shape/keyword/URL validation, cache, Server Action opsional, tanpa slug dugaan atau log URL credential |
| Enam file tes lama | Isolasi env/path, mock API dan konstruktor ClientError sesuai SDK; tambah regresi FSM |
| `tests/support.py` (baru) | Credential sintetis, temporary directory portable dan blok socket untuk seluruh suite |
| `tests/test_config.py` (baru) | Env kosong/salah dan production guard |
| `tests/test_security_integration.py` (baru) | Flask HTTP, signature, auth/CSRF/XSS, provider failure dan roundtrip |
| `tests/test_persistence_reliability.py` (baru) | Migrasi/backup, retensi, restart, race, deduplikasi dan crash |
| `tests/test_retrieval_engine.py` (baru) | BPS/Gemini failure, cache, grounding dan output validation |
| `tests/benchmark.py` (baru) | Enam skenario terukur dengan assert dan sampel mentah, tanpa API nyata |
| `README.md` | Instalasi, URL repo, konfigurasi development/production, deployment satu proses, endpoint, retensi dan batas klaim |
| `docs/PROJECT_AUDIT.md` | Baseline, risiko, matriks status fitur, sumber resmi dan tindak lanjut |
| `docs/REPORT_ALIGNMENT.md` | Revisi per subbab/paragraf DOCX dan teks usulan BAB III–V |
| `docs/TESTING_REPORT.md`, `test-results.txt`, `performance_results.json` | Bukti tes, warning, metode benchmark dan keterbatasan |
| `docs/CHANGELOG.md`, `docs/DEMO_GUIDE.md`, dokumen ini | Ringkasan perubahan, cara demonstrasi dan alasan teknis |

## Perubahan kompatibilitas yang disengaja

- POST Meta tanpa signature sekarang ditolak. Setup memerlukan Meta App Secret.
- Endpoint lama `/operator/selesai` tetap tersedia, tetapi mewajibkan login dan
  CSRF; default development API key dihapus karena tidak aman.
- Fonnte memerlukan ID pesan stabil (`inboxid`, atau `id`) dan header auth masuk;
  kompatibilitas header token lama dipertahankan jika secret khusus kosong.
- Reset mengosongkan history aktif, tetapi menyimpan history lama dalam arsip.
- Keluaran statistik memakai retrieval resmi, tidak mempercayai angka/URL model.
  Jawaban bebas untuk pertanyaan umum tanpa sumber belum menjadi fitur terverifikasi.
- URL tabel tanpa bukti individual ditandai katalog; tidak diklaim sebagai link
  individual terbaru. Server Action harus diaktifkan eksplisit setelah verifikasi.
- Launcher WSGI perlu memakai `create_app` agar background worker berjalan.

Hasil akhir: **136 tes lulus**. Validasi dan risiko yang belum terselesaikan
tercantum dalam `TESTING_REPORT.md` dan `PROJECT_AUDIT.md`.
