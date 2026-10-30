# Changelog Audit — 30 Oktober 2026

## Keamanan dan akses

- Verifikasi Meta HMAC SHA-256 pada raw request body; token/secret kosong ditolak.
- Pisahkan autentikasi masuk Fonnte dari signature Meta dan dukung JSON/form.
- Tambahkan login operator berbasis password hash/session, CSRF, logout, cookie
  aman, throttling login, CSP nonce, dan no-store untuk data operator.
- Lindungi seluruh rute operator dan `/stats`; hapus default API key development.
- Validasi nomor, panjang pesan, respons provider, dan batas request/batch.
- Render nomor/pesan menggunakan DOM textContent; perbaiki indikator polling.
- Hilangkan URL exception berkredensial, isi pesan, dan nomor dari log aplikasi;
  batasi log debug pustaka HTTP.

## Persistensi dan keandalan

- Migrasi aditif SQLite v2 dengan backup sebelum perubahan skema lama.
- Pisahkan sesi aktif dan arsip melalui conversation_id; reset tidak menghapus
  pesan. Tandai jenis pengaduan dan alasan penutupan.
- Kecualikan sesi operator dari timeout bot lima menit; serialisasi per nomor.
- Sediakan purge arsip eksplisit tanpa menghapus percakapan aktif.
- Ganti thread per pesan dengan inbox SQLite berkapasitas terbatas dan satu worker.
- Deduplikasi event persisten, proses seluruh batch, ACK setelah commit.
- Simpan status pengiriman gagal/ambigu; tidak mengulang otomatis setelah crash.
- Pengiriman operator yang gagal tidak dicatat sebagai sukses atau menutup sesi.
- Sediakan WSGI factory dengan startup worker idempoten; health memeriksa database.

## FSM, BPS, dan Gemini

- Deterministikkan pilihan menu serta Selesai pada semua state.
- Gunakan jalur yang sama untuk pencarian hasil klasifikasi Gemini dan aturan.
- Ambil angka dari hasil retrieval resmi; jangan menampilkan angka/URL dari model.
- Prioritaskan BPS Web API, validasi hasil, labeli katalog, dan tampilkan tanggal.
- Hapus definisi pencarian tabel yang tertimpa; buat Server Action opsional dan
  hindari membangun URL dari slug dugaan.
- Batasi percobaan, timeout, dan konteks Gemini; validasi JSON; lindungi rotator
  dengan lock dan pertahankan cooldown.
- Perbarui contoh model berdasarkan katalog resmi dan dependency ke versi teruji.

## Pengujian dan dokumentasi

- Isolasi tes dari .env, API nyata, dan path /tmp/opencode; blokir socket jaringan.
- Perbaiki konstruksi ClientError sesuai SDK dan hilangkan ketergantungan urutan.
- Tambahkan integrasi HTTP, keamanan, retensi/migrasi, crash, dan konkurensi.
- Ukur enam skenario lokal, masing-masing 50 sampel; simpan data mentah dan p95.
- Sinkronkan README, audit, pemetaan laporan DOCX, dan panduan demo.
- Tidak ada deployment, push, pengiriman WhatsApp nyata, atau perubahan DOCX asli.
