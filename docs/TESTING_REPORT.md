# Laporan Pengujian

## Baseline dan hasil akhir

| Tahap | Perintah | Hasil |
| --- | --- | --- |
| Baseline sebelum perubahan | `python -m unittest discover -s tests -v` | 65 tes; 61 lulus, 1 failure, 3 errors; 2,533 detik |
| Validasi akhir | `python -m unittest discover -s tests -v` | 136 tes; 136 lulus, 0 failure, 0 error, 0 skip; 2,962 detik |
| Pemeriksaan warning | `python -Wd -m unittest discover -s tests -v` | 136 lulus; 3,023 detik; satu DeprecationWarning dari SDK Google |

Bukti suite akhir: [test-results.txt](test-results.txt). Waktu total suite bukan
waktu balasan chatbot. Baseline membocorkan URL berkredensial melalui exception
kode lama, sehingga keluaran mentahnya tidak dimasukkan ke repository. Hanya
hasil ringkas dan masalah penentu yang didokumentasikan.

Baseline memakai SDK terpasang yang berbeda dari requirements lama. Tiga errors
berasal dari konstruktor `ClientError` yang tidak cocok. Satu failure dipengaruhi
panggilan Gemini nyata dan state offline global. Tes kini menggunakan credential
sintetis, database sementara, mock API, dan blokir koneksi socket. `.env` tidak
dibaca saat TESTING=1. Tidak ada API key nyata yang diperlukan.

## Cakupan dan bukti utama

| Area | Bukti |
| --- | --- |
| Meta HMAC | Raw body persis diterima; signature hilang/palsu, payload berubah, secret kosong dan header non-ASCII ditolak |
| Webhook | GET challenge, seluruh changes/messages, status-only diabaikan, JSON/form Fonnte, payload buruk/terlalu besar, kapasitas inbox dan rate limit |
| Operator | Login/password, perubahan identitas, kedaluwarsa 30 menit, logout, semua route tanpa autentikasi, CSRF palsu, cookie Secure/HttpOnly/SameSite |
| Input/XSS | Nomor berbahaya, tipe/panjang pesan, DOM textContent, tidak ada onclick dinamis, CSP nonce; bukan uji browser interaktif |
| Pengiriman | Timeout/JSON invalid ditolak; Meta memerlukan ID pesan; Fonnte memerlukan status=true; pesan panjang dipecah dan kegagalan tidak dianggap sukses |
| FSM | Semua step, menu, konsultasi, Ya/Tidak/Selesai, luar jam kerja, operator diam, timeout serta invalid step |
| Roundtrip | Payload bertanda tangan melalui inbox ke FSM, konsultasi dan pengaduan, dashboard, balasan dan arsip penutupan |
| Persistensi | Database legacy, backup sebelum migrasi, restart, reset tanpa kehilangan pesan, arsip pengaduan, purge hanya arsip eligible |
| Konkurensi | 20 get/create pada nomor sama, 20 pesan operator bersamaan, 20 delivery ID sama hanya diterima sekali |
| Crash/retry | Event queued bertahan, processing terputus menjadi failed, pengiriman ambigu tidak diulang, batch ditolak secara atomik saat throttle |
| BPS | Cache TTL/hit, kegagalan tidak dicache, respons salah bentuk, validasi domain/HTTPS, filter periode, katalog diberi label, Server Action opsional |
| Gemini | 429/404/503, timeout/batas percobaan, cooldown, koneksi gagal, JSON buruk, batas konteks dan penolakan angka/URL model pada jawaban |
| Startup/health | Env opsional kosong, konfigurasi provider/database/numerik salah, production tanpa keamanan ditolak, factory idempoten, database health gagal |

Nama tes lengkap dan status masing-masing tersedia dalam log suite. Tidak ada
klaim coverage baris atau persentase karena alat coverage tidak dijalankan.

## Pengukuran performa lokal

Sumber data: [performance_results.json](performance_results.json).
Waktu pengukuran UTC: `2026-10-30T02:16:34.809194+00:00`.
Lingkungan: Python 3.14.8, Linux,
SQLite WAL pada direktori sementara, Flask test client tanpa server TCP.
Versi paket: Flask 3.1.3, google-genai 2.16.0, requests 2.33.1, Waitress 3.0.2.
Sistem melaporkan 20 CPU; ini bukan bukti alokasi resource khusus benchmark.

Setiap skenario memakai **50 sampel**, tanpa warm-up khusus. Persiapan/reset
berada di luar interval pengukuran. P95 menggunakan nearest-rank `ceil(0.95*n)`.
Data mentah tiap sampel tersedia dalam JSON. Angka berikut dalam **milidetik**.

| Skenario | n | Rata-rata | Median | P95 | Maksimum |
| --- | --- | --- | --- | --- | --- |
| Menu awal (FSM) | 50 | 1.362 | 1.343 | 1.524 | 1.573 |
| Konsultasi Gemini (SDK dimock) | 50 | 2.195 | 2.137 | 2.442 | 4.071 |
| BPS tanpa cache (HTTP dimock) | 50 | 0.336 | 0.326 | 0.410 | 0.498 |
| BPS cache hit (SQLite) | 50 | 0.133 | 0.123 | 0.193 | 0.241 |
| Alih kelola operator (FSM) | 50 | 1.656 | 1.623 | 1.828 | 1.871 |
| ACK webhook, 8 thread serentak | 50 | 10.107 | 5.541 | 37.152 | 56.007 |

API Gemini/BPS dan pengiriman provider dimock tanpa latensi buatan. Skenario ACK
mengukur validasi signature dan commit inbox pada 50 request dengan delapan
thread. Skenario tersebut tidak mengukur waktu menunggu worker atau pengiriman
WhatsApp. Pengukuran ini bukan load test Waitress di jaringan produksi.

**Evaluasi target tiga detik:** overhead lokal terukur jauh di bawah tiga detik,
namun target end-to-end **belum terbukti**. Timeout Gemini delapan detik, dua
retrieval BPS yang dapat memblokir, antrean worker, dan pengiriman provider
berpotensi melampaui target. Target universal tiga detik tidak dapat dijamin oleh
konfigurasi ini. Pengukuran live harus melaporkan cache hit/miss, panjang antrean,
API latency, kondisi kuota, error, dan batas waktu yang sama.

## Pemeriksaan tambahan

- `compileall`: seluruh modul aplikasi dan tes berhasil dikompilasi.
- `node --check`: script dashboard lolos pemeriksaan sintaks.
- `git diff --check`: tidak ada whitespace error.
- `.env` tidak dilacak dan diabaikan Git; SQLite, sidecar WAL/SHM dan backup migrasi
  diabaikan. Perbandingan nilai secret lokal terhadap file tracked dan kandidat
  baru tidak menemukan kecocokan. Nilai secret tidak dicetak.
- ResourceWarning koneksi SQLite diperbaiki dengan penutupan koneksi eksplisit.
  Satu warning dependency tetap ada: `google/genai/types.py:42` memakai
  `_UnionGenericAlias`, deprecated pada Python 3.14 dan dijadwalkan hilang pada
  Python 3.17. Warning tidak disembunyikan dan tidak mengubah hasil tes saat ini.
- Log `[ERROR] Inbox processing failed (ValueError)` berasal dari tes injeksi
  kegagalan yang disengaja, bukan failure suite.

## Belum dibuktikan dan risiko tersisa

1. Pengiriman Meta/Fonnte nyata, autentikasi langsung incoming Fonnte, akses model
   akun, serta ketersediaan BPS live belum diuji. Tidak ada deployment/push.
2. Tampilan browser, aksesibilitas interaktif, dan pengujian XSS memakai browser
   sungguhan belum dijalankan; bukti saat ini mencakup HTTP, rendering source dan CSP.
3. Instalasi dari virtual environment benar-benar kosong, semua versi Python,
   serta pemindaian CVE dependency otomatis belum dilakukan.
4. Tidak ada SLA tiga detik, sertifikasi keamanan, high availability, atau jaminan
   exactly-once untuk efek eksternal yang dibuktikan oleh tes ini.
5. Ketepatan NLP terhadap korpus pengguna, pagination semua arsip/katalog,
   daftar publikasi, dan uji beban jangka panjang merupakan pengembangan berikutnya.
