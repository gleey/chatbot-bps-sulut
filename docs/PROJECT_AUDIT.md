# Audit Project Chatbot BPS Sulawesi Utara

Audit dimulai pada 30 Oktober 2026. Sumber implementasi: remote lokal
`https://github.com/gleey/chatbot-bps.git`, `origin/main` commit `7ec2038`.
URL `chatbot-bps-sulut` diverifikasi melalui GitHub pada audit ini: commit terbarunya
juga `7ec203845fe21ad66af0e2fa719772ee52096985`. Remote lama dan URL permintaan
mengacu pada snapshot kode yang sama. Tidak ada perubahan remote atau publikasi.
Perbaikan dikerjakan pada branch
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

Laporan asli diberikan kemudian di
`/home/gley/Gley/Magang BPS/Laporan Magang Gley.docx` dan dibaca tanpa diubah.
Pemetaan menggunakan nomor subbab serta paragraf `word/document.xml`; nomor
halaman hasil layout Word tidak diverifikasi. Tidak ada deployment maupun
pengiriman WhatsApp nyata.

## Status fitur setelah perbaikan

“Implemented & Verified” di bawah berarti dibuktikan oleh tes otomatis lokal
dengan mock API, bukan sertifikasi integrasi akun provider produksi.

| Fitur | Status awal | Status akhir | Bukti implementasi dan pengujian |
| --- | --- | --- | --- |
| Penerimaan/pengiriman WhatsApp | Needs Improvement | Implemented & Verified (mock); live unverified | `wa_webhook.webhook`, `_dispatch_reply`, `ProviderTests`, `test_full_webhook_consultation_and_complaint_roundtrip` |
| Menu Konsultasi/Pengaduan | Implemented & Verified | Implemented & Verified | `main._step_awal/_step_pilih_layanan`, `TestStateMachine` |
| Gemini dan konteks | Implemented but Unverified | Implemented & Verified (mock); akun live unverified | `llm_engine.analisis_pesan`, `EngineTests`, konteks maksimal 30 pesan |
| Retrieval statistik resmi | Needs Improvement | Implemented & Verified (fixture); live unverified | `bps_api.cari_data_bps`, `RetrievalTests`, teks berasal dari abstrak BRS |
| Tautan tabel individual | Partially Implemented | Partially Implemented | `cari_tabel_terbaru_bps`, URL unduhan resmi jika tersedia; katalog diberi label; bukan penelusuran semua halaman |
| Rotasi key/model | Broken (tes integrasi) | Implemented & Verified | `_call_gemini`, `TestRotatorIntegration`, `EngineTests`; failover berurutan, bukan pool terdistribusi |
| Fallback aturan | Needs Improvement | Implemented & Verified | `is_offline_mode`, `_fallback_offline`, `TestStateMachine`; offline berarti tanpa Gemini, BPS masih bisa membutuhkan internet |
| FSM enam step | Needs Improvement | Implemented & Verified | `main.STATES/handle_incoming_message`, tes selesai, puas, tidak puas, jam kerja, timeout |
| Persistensi/timeout/reset | Broken (retensi) | Implemented & Verified | `SessionManager.reset/cleanup_expired/get_archives`, `PersistenceTests`; arsip terpisah dari history aktif |
| Jam kerja WITA | Implemented & Verified | Implemented & Verified | `is_jam_kerja`, tes batas 07:59, 08:00, 15:30, 15:31 dan Sabtu; hari libur nasional belum dimodelkan |
| Alih kelola operator | Needs Improvement | Implemented & Verified | `set_step('operator')`, `mark_complaint`, tes bot diam dan timeout operator dikecualikan |
| Dashboard/balasan manual | Broken (kontrol akses) | Implemented & Verified (HTTP/mock) | `operator_auth.install_auth`, API operator, tes login/otorisasi/CSRF/kegagalan send; browser visual belum diuji |
| Cache BPS dan prewarm | Needs Improvement | Implemented & Verified | `_cache_get/_cache_set/_request_bps`, `TestBpsApi`, `RetrievalTests`; TTL default 86400 detik |
| Validasi/rate limit | Needs Improvement | Implemented & Verified | `valid_phone/validate_message`, `message_queue.enqueue`, tes 429, batch atomik, kapasitas inbox |
| Error handling/logging | Needs Improvement | Implemented & Verified untuk jalur tercakup | Exception eksternal dilog sebagai nama kelas/status; tanpa isi pesan/URL berkredensial; tes kegagalan provider dan database |
| Deployment/health | Partially Implemented | Implemented & Verified untuk factory dan health; deployment live unverified | `create_app/start_background_workers/run_server/health`, `test_wsgi_factory_initializes_workers_once`, README |
| Signature HMAC Meta | Missing | Implemented & Verified | `webhook`, tes signature valid, hilang, berubah, secret kosong dan raw body |
| Login operator | Missing | Implemented & Verified | `operator_auth`, sesi 30 menit, password hash, logout dan cookie aman |
| Deduplikasi/pemulihan webhook | Missing | Implemented & Verified dengan batas crash terdokumentasi | `message_queue`, ID persisten, tes konkurensi, queued restart, crash ambigu tidak diulang otomatis |

## Perubahan yang diselesaikan

A01–A09 dan A12–A17 diperbaiki melalui kontrol akses, signature, inbox persisten,
arsip, timeout, validasi respons provider, pembatasan percobaan API, dan tes
terisolasi. A10 diselesaikan dengan satu definisi fungsi pencarian tabel.
A11 dimitigasi dengan API resmi sebagai jalur utama; Server Action opsional dan
URL tidak dibangun dari slug dugaan. A18 diselesaikan dalam README dan
`REPORT_ALIGNMENT.md`. Nomor baris dapat berubah; nama fungsi dan nama tes di
atas menjadi referensi stabil. Snapshot sebelum perbaikan tetap tersedia pada
commit awal audit dan `origin/main` yang disebutkan di atas.

## Keterbatasan dan urutan tindak lanjut

1. **Sebelum demo WhatsApp:** isi secret/provider, uji dengan akun dan nomor uji
   yang diizinkan, buktikan akses model serta BPS dengan akun sebenarnya. Tidak
   ada pengiriman nyata selama audit ini.
2. **Fonnte:** kontrak dokumentasi masuk menyertakan `inboxid`, tetapi dukungan
   header Authorization masuk tidak dibuktikan. Gunakan relay tepercaya yang
   memverifikasi sumber sebelum menambahkan header. Jangan menonaktifkan auth.
3. **Crash/pengiriman ambigu:** event `processing` menjadi `failed` saat restart.
   Periksa transcript dan riwayat provider sebelum mengulang. Tidak ada klaim
   exactly-once pada batas transaksi database dan pengiriman eksternal.
4. **Retensi:** tidak ada penghapusan arsip otomatis sebelum kebijakan BPS
   ditetapkan. `purge_archives(days)` tersedia untuk pemeliharaan eksplisit;
   backup juga memerlukan kebijakan retensi dan pembatasan akses.
5. **Skala:** satu worker inbox memproses berurutan. Panggilan eksternal yang
   lambat dapat menambah antrean. Terapkan metrik waktu antre dan benchmark live
   sebelum meningkatkan jumlah worker/proses. SQLite tidak perlu diganti untuk
   demonstrasi, tetapi deployment multi-proses membutuhkan lock terdistribusi.
6. **Data:** pencarian hanya memeriksa halaman API yang dikembalikan; tidak
   menjamin data/tabel terbaru secara global. Pencarian publikasi, jawaban umum
   berbasis pengetahuan LLM, serta sintesis bebas tidak dianggap tervalidasi.
   Jawaban angka memakai cuplikan sumber resmi; Gemini berperan sebagai
   pengklasifikasi agar angka dan URL hasil model tidak dipercaya sebagai fakta.
7. **Performa:** target tiga detik end-to-end belum terbukti. Pengukuran lokal
   memakai mock tanpa latensi eksternal; detail di `TESTING_REPORT.md`.
8. **Log historis:** kode lama dapat mencetak URL API beserta key. Tinjau akses
   log lama dan rotasi credential yang pernah tercetak. `.env` tidak dilacak Git;
   tidak ada secret asli yang ditambahkan dalam perubahan audit.

## Sumber resmi yang diperiksa

- [Repository yang diminta, commit 7ec2038](https://github.com/gleey/chatbot-bps-sulut/commit/7ec203845fe21ad66af0e2fa719772ee52096985).
- [Meta: validasi signature dan retry webhook](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/).
- [Meta: versi Graph API](https://developers.facebook.com/docs/graph-api/changelog/).
- [Google: katalog model](https://ai.google.dev/gemini-api/docs/models).
- [Google: Gemini 3.5 Flash yang deprecated](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).
- [Google: SDK Python](https://googleapis.github.io/python-genai/).
- [BPS: dokumentasi API resmi](https://webapi.bps.go.id/documentation/).
- [Fonnte: payload webhook masuk](https://docs.fonnte.com/webhook-reply-message/).

Verifikasi dokumentasi tidak membuktikan akses akun atau hasil jaringan live.
Model contoh diperbarui ke `gemini-3.6-flash` dengan fallback
`gemini-3.5-flash-lite`, yang tercantum pada katalog resmi saat audit.
