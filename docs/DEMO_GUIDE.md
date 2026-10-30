# Panduan Demonstrasi Seminar

## Bukti lokal tanpa API dan tanpa pesan nyata

Dari root repository, jalankan:

```bash
python -m unittest discover -s tests -v
python -m unittest tests.test_security_integration.WebIntegration.test_full_webhook_consultation_and_complaint_roundtrip -v
python -m tests.benchmark > docs/performance_results.json
```

Tes roundtrip memverifikasi pesan bertanda tangan dari menu, Konsultasi, pencarian
inflasi, Ya, Selesai, percakapan baru, Pengaduan, pesan pengguna, balasan operator,
hingga penutupan arsip. Semua nomor/credential sintetis, API dimock, dan koneksi
jaringan diblokir. Ini adalah bukti perilaku aplikasi, bukan bukti layanan live.

## Menyiapkan aplikasi untuk demonstrasi manual

1. Gunakan virtual environment, install `requirements.txt`, salin `.env.example`.
2. Gunakan database demonstrasi terpisah, misalnya `DATABASE_PATH=demo.db`.
3. Buat `FLASK_SECRET_KEY` dan password hash melalui perintah README. Isi username
   operator. Jangan memakai data pribadi/pengaduan nyata untuk slide seminar.
4. Untuk Meta, isi access token, Phone Number ID, verify token, App Secret dan
   Graph API version. Gemini/BPS key boleh kosong untuk fallback aturan/katalog.
5. Untuk HTTP lokal pilih `APP_ENV=development`, `COOKIE_SECURE=false`.
6. Jalankan `python wa_webhook.py`. Buka `/health`; pastikan database sehat dan
   `worker_running=true`. Buka `/operator` dan login.
7. Untuk webhook provider, siapkan URL HTTPS terkontrol yang meneruskan raw body
   dan header signature utuh. Untuk HTTPS dashboard gunakan cookie Secure.

Konfigurasi placeholder sengaja tidak dapat dipakai mengirim pesan. Aplikasi
memvalidasi provider saat startup. Tidak ada pengiriman nyata yang dilakukan
selama audit; langkah WhatsApp di bawah dijalankan manusia setelah izin tersedia.

## Skenario presentasi

| Skenario | Tindakan | Hasil yang ditunjukkan |
| --- | --- | --- |
| Autentikasi | Buka `/operator` dari browser tanpa login | Form login; API pengaduan tidak dapat dibaca |
| Keamanan webhook | Tampilkan tes signature valid, hilang dan payload berubah | Valid diterima; invalid ditolak 403 |
| WhatsApp/menu | Kirim sapaan dari nomor uji berizin | Tombol Pengaduan/Konsultasi pada Meta; pilihan teks pada Fonnte |
| Konsultasi | Pilih Konsultasi, ketik `inflasi`, lalu `Ya` | Sumber resmi/tanggal jika retrieval tersedia; katalog diberi label jika tidak |
| Akhir konsultasi | Ketik `Selesai` | Sesi aktif kembali awal; arsip tidak hilang |
| Pengaduan jam kerja | Mulai percakapan baru, pilih Pengaduan, kirim keluhan sintetis | Sesi tampil di dashboard; bot tidak membalas pesan berikutnya |
| Operator | Login, pilih nomor, kirim jawaban | Provider menerima permintaan; history operator ditambahkan |
| Tutup | Klik Selesaikan Sesi Operator | Pesan penutup, arsip pengaduan, bot kembali aktif |
| Di luar jam kerja | Tampilkan tes terkontrol untuk waktu di luar jam kerja | Pemberitahuan kontak; tidak membuat sesi operator yang menggantung |
| Kegagalan layanan | Tampilkan tes timeout Gemini/BPS/provider | Fallback aturan, keterangan data tidak tersedia, atau sesi operator tetap aktif |
| Persistensi | Tampilkan tes restart dan migrasi pada database sementara | Pesan tetap tersimpan; backup migrasi dibuat |

Jangan mengganti jam sistem untuk menguji jam kerja. Tes memock waktu WITA secara
terkontrol. Tombol dashboard membutuhkan waktu hingga lima detik untuk refresh.

## Mencatat bukti live

Untuk setiap nomor uji yang telah diizinkan, catat waktu penerimaan webhook,
waktu mulai proses worker, dan waktu request pengiriman diterima provider. Catat
waktu WhatsApp muncul secara terpisah jika mengukur latensi pengguna. Ukur
sejumlah sampel yang dilaporkan, lalu hitung rata-rata, median, p95 dan maksimum.
Pisahkan cache hit/miss, mode Gemini/aturan, panjang antrean, dan kegagalan.

Target tiga detik tidak boleh dinyatakan tercapai berdasarkan benchmark mock.
Kondisi kuota, timeout API delapan detik, dan antrean tunggal dapat membuat target
terlewati. Jika pengiriman ambigu, periksa riwayat provider sebelum mengulang.

## Batas yang harus disebutkan saat seminar

- SQLite satu proses, bukan PostgreSQL; Bootstrap, bukan Tailwind.
- Pemrosesan sinkron dengan background thread, bukan asynchronous I/O.
- Cache 24 jam; hasil hanya dari halaman API yang dicari, bukan seluruh katalog.
- Fonnte memerlukan pembuktian auth masuk/relay; model dan akun API perlu uji live.
- Arsip tersedia di database, belum ada layar pencarian seluruh arsip/pagination.
- Retensi operasional dan hari libur nasional belum ditetapkan dalam aplikasi.
- Hasil audit adalah tes prototipe lokal, bukan jaminan SLA atau high availability.
