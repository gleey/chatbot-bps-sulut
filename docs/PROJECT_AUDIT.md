# Audit Project Chatbot BPS Sulawesi Utara

Audit dimulai pada 30 Oktober 2026. Sumber implementasi: remote lokal
`https://github.com/gleey/chatbot-bps.git`, `origin/main` commit `7ec2038`.
URL `chatbot-bps-sulut` dalam permintaan berbeda dari remote lokal; tidak ada
perubahan remote atau publikasi. Perbaikan dikerjakan pada branch
`audit/security-reliability`.

## Baseline sebelum perubahan

Perintah: `python -m unittest discover -s tests -v`.
Hasil awal: **65 tes, 61 lulus, 1 failure, 3 errors**, durasi 2,533 detik.
Tiga error berasal dari konstruktor `google.genai.errors.ClientError` yang tidak
sesuai SDK terpasang. Failure: `test_tidak_puas_luar_jam_kerja`, karena tes
membiarkan panggilan Gemini nyata dan bergantung pada hasil serta urutan tes.
Tes juga membaca `.env`, memakai path `/tmp/opencode`, dan mencoba jaringan.
Output baseline tidak disalin mentah karena exception HTTP mengandung URL API
dengan credential. Versi lokal sebelum fetch hanya berbeda dalam batas jam kerja.

## Temuan dan urutan perbaikan

| ID | Risiko | Bukti kode awal dan reproduksi | Tindakan |
| --- | --- | --- | --- |
| A01 | Kritis | `wa_webhook.webhook`: komentar melewati signature; POST Meta palsu diproses | HMAC raw body, compare_digest, gagal tertutup |
| A02 | Kritis | `operator_dashboard`, `api_operator_sessions/send/close`: tanpa autentikasi | Login session, password hash, CSRF, otorisasi semua endpoint |
| A03 | Tinggi | `OPERATOR_API_KEY` memiliki default `dev_operator_key_123`; endpoint lama dapat mereset nomor apa pun | Hapus credential default dan samakan kontrol akses |
| A04 | Tinggi | `SessionManager.reset/cleanup_expired`: DELETE messages dan sessions; timeout mencakup operator | Arsip percakapan, migrasi aditif dengan backup, kecualikan operator |
| A05 | Tinggi | `webhook`: satu daemon thread per pesan, tidak ada ID deduplikasi, hanya messages[0]/changes[0] | Inbox SQLite persisten, worker terbatas, iterasi seluruh batch |
| A06 | Tinggi | `api_operator_send`: menulis history sebelum send; close mengabaikan kegagalan send | Catat hanya pengiriman diterima provider, gagal tidak menutup sesi |
| A07 | Tinggi | `config`: `.split()` pada None; provider bebas; tidak ada validasi startup | Default aman dan pemeriksaan konfigurasi tanpa nilai secret |
| A08 | Tinggi | `main._step_gemini_tanya_data` mempercayai angka/URL hasil model tanpa grounding | Model hanya klasifikasi; jawaban statistik berasal dari retrieval resmi |
| A09 | Tinggi | `bps_api._request_bps` mencetak exception URL termasuk API key; webhook log isi pesan dan nomor | Log metadata aman; tanpa response body atau exception eksternal mentah |
| A10 | Sedang | Dua definisi `cari_tabel_terbaru_bps`; definisi pertama tertimpa | Satu jalur resmi dengan validasi hasil, fallback website terkontrol |
| A11 | Sedang | Next.js action ID hardcoded; URL dibangun dari slug dugaan | Resmi dahulu; action opsional, jangan mengklaim URL dugaan sebagai terverifikasi |
| A12 | Sedang | FSM dan timeout worker dapat mengubah sesi yang sama bersamaan | Serialisasi per nomor dalam satu proses; deployment satu proses |
| A13 | Sedang | Fonnte menganggap semua HTTP 200 sukses; token kosong dapat lolos jika header juga kosong | Validasi status JSON dan autentikasi nonkosong terpisah dari Meta |
| A14 | Sedang | `templates/operator.html`: nomor di interpolasi ke onclick/HTML; refresh tidak menyatakan kegagalan | Gunakan DOM textContent/event listener; indikator status aktual |
| A15 | Sedang | `_call_gemini`: tanpa timeout eksplisit; retry kombinatorial dan mutasi rotator tanpa lock | Deadline, jumlah percobaan terbatas, cooldown aman, output JSON tervalidasi |
| A16 | Sedang | Versi dependency aktual berbeda requirements; README menjanjikan sub-100ms tanpa bukti | Sinkronkan versi teruji; ukur benchmark mock dan jelaskan batasnya |
| A17 | Sedang | Background worker hanya pada `__main__`, bukan saat WSGI import | Entry point eksplisit, startup idempoten, tanpa side effect jaringan saat import |
| A18 | Rendah | README clone URL akun lain; PostgreSQL/Tailwind/async/realtime tak cocok implementasi | Dokumentasi dan matriks penyesuaian laporan |

## Arsitektur dan batas audit

Flask adalah lapisan HTTP; `main.py` menjalankan enam step FSM;
`session_manager.py` menyimpan sesi dan history; `bps_api.py` menangani retrieval
dan cache; `llm_engine.py` menangani Gemini serta fallback. SQLite dengan WAL
masih sesuai untuk prototipe satu proses dengan thread terbatas. Lock dalam
proses tidak cukup untuk beberapa WSGI process atau beberapa host. Migrasi
PostgreSQL/queue terdistribusi merupakan pengembangan setelah pengukuran beban.

Laporan magang asli (PDF/DOCX) tidak tersedia dalam repository. Pemetaan laporan
berdasarkan daftar ketidaksesuaian yang diberikan pengguna; nomor halaman tidak
dapat diverifikasi. Tidak ada deployment maupun pengiriman WhatsApp nyata.

Status fitur akhir, bukti tes, risiko tersisa, dan referensi fungsi ditambahkan
setelah implementasi serta validasi selesai.
