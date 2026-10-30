# Rencana Utama Revisi Laporan Magang

## Tujuan dan status

**Status: rencana siap digunakan; revisi DOCX belum dikerjakan.**

Dokumen ini menjadi titik awal dan checklist utama untuk menyelaraskan laporan
magang dengan implementasi chatbot BPS Sulawesi Utara. Revisi harus membedakan
fitur yang tersedia, fitur yang diuji menggunakan mock, dan integrasi nyata yang
masih membutuhkan bukti.

- Dokumen sumber: `/home/gley/Gley/Magang BPS/Laporan Magang Gley.docx`.
- Usulan hasil: `Laporan Magang Gley - Revisi.docx`, disimpan sebagai salinan
  terpisah setelah pekerjaan revisi dokumen diminta.
- Baseline implementasi: commit `32db572`, yang memuat hasil audit dan perbaikan.
- Bukti tersimpan: 136 tes lulus, enam skenario benchmark dengan masing-masing
  50 sampel. Seluruh integrasi eksternal pada tes tersebut menggunakan mock.
- Pemetaan subbab/paragraf terperinci: [REPORT_ALIGNMENT.md](REPORT_ALIGNMENT.md).
  Nomor paragraf mengacu pada `word/document.xml`, bukan halaman Word.

Pembuatan rencana ini tidak mengubah DOCX asli, tidak menjalankan pengujian live,
dan tidak menyatakan seluruh kebutuhan produksi sudah terpenuhi.

## Aturan pelaksanaan

1. Kerjakan salinan laporan. Pertahankan identitas penulis, struktur kampus,
   sitasi, tabel, gambar, dan penomoran yang masih relevan.
2. Jadikan kode pada commit yang dicatat sebagai sumber klaim implementasi.
   Cocokkan setiap klaim teknis dengan fungsi, tes, atau artefak hasil pengukuran.
3. Tulis hasil mock sebagai hasil mock. Pisahkan dari pengujian akun Gemini,
   BPS, Meta/Fonnte, dan pengiriman WhatsApp sebenarnya.
4. Gunakan hasil yang tersimpan untuk angka pengujian. Jika tes diulang setelah
   kode berubah, catat commit, perintah, lingkungan, waktu, dan hasil baru.
5. Nyatakan fitur yang belum tersedia sebagai batas atau pengembangan berikutnya.
   Jangan menambah fitur aplikasi hanya untuk membenarkan kalimat laporan lama.
6. Gunakan data sintetis pada lampiran dan screenshot. Rahasiakan nomor nyata,
   pengaduan, password, token, API key, cookie session, dan secret webhook.
7. Kutip sumber resmi untuk teori dan kontrak API. Tinjau ulang lifecycle model
   saat revisi; pemeriksaan dokumentasi bukan bukti akses akun live.

## Tahap 1 — Tetapkan snapshot dan siapkan salinan

- [ ] Catat commit implementasi yang akan dijelaskan pada laporan final.
- [ ] Simpan salinan DOCX sumber dan buat dokumen revisi dengan nama berbeda.
- [ ] Inventarisasi judul subbab, tabel, caption, gambar, serta daftar isi.
- [ ] Tandai setiap klaim PostgreSQL, Tailwind, asynchronous I/O, real-time,
      high availability, tiga detik, KeyPoolManager, login, dan HMAC.
- [ ] Cocokkan matriks dalam `REPORT_ALIGNMENT.md` dengan dokumen yang akan diedit.

**Selesai jika:** sumber tetap utuh, salinan tersedia, dan seluruh lokasi klaim
yang bertentangan sudah tercatat. Nomor halaman diperbarui setelah layout final.

## Tahap 2 — Perbaiki klaim prioritas tertinggi

| Prioritas | Bagian laporan | Perubahan wajib | Bukti utama |
| --- | --- | --- | --- |
| P0 | Diagram operator, p581; pembahasan database terkait | Ganti PostgreSQL sebagai implementasi saat ini menjadi SQLite dengan WAL. Tempatkan PostgreSQL/Redis sebagai opsi skala berikutnya | `db.py`, `session_manager.py` |
| P0 | Tabel 4.2, frontend | Ganti Tailwind dengan HTML, Bootstrap 5, dan JavaScript | `templates/operator.html`, `operator_login.html` |
| P0 | 3.3.1; Tabel 4.2; arsitektur | Ganti klaim asynchronous I/O dengan WSGI dan HTTP sinkron, inbox SQLite, serta satu background worker | `wa_webhook.py`, `message_queue.py` |
| P0 | 4.3.2; 4.7; kesimpulan | Tulis tiga detik sebagai target yang belum dibuktikan end-to-end. Pisahkan waktu ACK, pemrosesan, antrean, dan pengiriman provider | `TESTING_REPORT.md`, `performance_results.json` |
| P0 | Seluruh pembahasan keamanan | Sebut HMAC sebagai autentikasi dan integritas pesan berbasis MAC. Batasi klaim HMAC pada provider Meta; Fonnte menggunakan mekanisme auth terpisah | `wa_webhook.webhook`, `operator_auth.py` |
| P0 | 3.5; 4.3.1; 4.5.3; 5.1 | Nyatakan Gemini mengklasifikasi kebutuhan; backend memformat cuplikan BRS resmi. Hilangkan klaim bahwa seluruh JSON BPS disintesis kembali oleh Gemini | `main.py`, `llm_engine.py`, `bps_api.py` |
| P0 | 4.7; Tabel 4.3 | Ganti pernyataan lulus umum dengan nama skenario, metode, hasil nyata, dan batas pembuktiannya | `test-results.txt`, `tests/` |

**Selesai jika:** seluruh klaim P0 pada teks, tabel, gambar, abstrak, dan kesimpulan
konsisten. Satu klaim yang sudah diperbaiki di BAB IV tidak boleh tetap salah
pada diagram atau BAB V.

## Tahap 3 — Revisi BAB III: dasar teori yang sesuai sistem

| Bagian | Isi revisi | Kriteria selesai |
| --- | --- | --- |
| 3.2.2 Gemini dan rotasi key | Jelaskan failover key/model berurutan, cooldown, batas percobaan, timeout, dan fallback aturan. Gunakan nama `_KeyRotator` dan `_ModelRotator` untuk kelas implementasi | Tidak menyebut pool terdistribusi atau menjamin ketersediaan tanpa batas |
| 3.3.1 Python dan backend | Jelaskan Flask/Waitress WSGI, request sinkron, pemisahan ACK dan worker, serta lock per nomor pada satu proses | Tidak menyamakan background thread dengan asynchronous I/O |
| 3.3.2 Webhook | Jelaskan raw body, App Secret, HMAC SHA-256, compare_digest, penolakan signature invalid, retry, serta deduplikasi | Bedakan verify token GET, signature POST Meta, dan auth masuk Fonnte |
| 3.4.1 FSM | Bedakan tiga kelompok konseptual dari enam step kode | Setiap kelompok memiliki pemetaan implementasi yang jelas |
| 3.4.2 Session Manager | Jelaskan sesi aktif, history, conversation_id, arsip, restart, timeout, dan retensi | Reset tidak lagi digambarkan sebagai penghapusan permanen history |
| 3.5 BPS API | Jelaskan retrieval resmi, cache default 24 jam, validasi hasil/tautan, dan fallback katalog | Tidak menyebut setiap jawaban sebagai data live atau terbaru secara global |

Pertahankan dasar teori BPS/PST dan NLP yang masih relevan. Periksa kesesuaian
sitasi saat kalimat teorinya berubah. Verifikasi bibliografi belum termasuk bukti
audit kode yang tersedia.

**Selesai jika:** setiap subbab membedakan konsep umum dari teknik yang benar-benar
digunakan aplikasi dan tetap memiliki sumber teori yang sesuai.

## Tahap 4 — Revisi BAB IV: implementasi dan diagram

### 4.3 Kebutuhan dan pemilihan teknologi

- [ ] Jelaskan bahwa otomasi konsultasi dapat berjalan di luar jam kerja,
      sedangkan alih kelola operator mengikuti jadwal layanan.
- [ ] Ubah Python 3.8+ menjadi minimal 3.10 sesuai dependency. Nyatakan versi
      lingkungan yang benar-benar dipakai untuk hasil pengujian.
- [ ] Perbaiki Tabel 4.2: SQLite, Bootstrap, WSGI sinkron, Gemini sebagai
      pengklasifikasi, dan API BPS dengan cache.
- [ ] Pertahankan tiga detik sebagai target; jangan memberi status tercapai
      tanpa pengukuran jaringan dan provider nyata.
- [ ] Batasi cakupan pencarian saat ini pada BRS dan tabel dari halaman hasil
      API. Pencarian seluruh publikasi/katalog belum tersedia.

### 4.4 Arsitektur, FSM, activity diagram, dan sequence diagram

Perbarui Gambar 4.2, Gambar 4.3, serta seluruh diagram yang menunjukkan alur berikut:

| Alur | Urutan yang harus digambarkan |
| --- | --- |
| Pesan masuk Meta | Terima raw body; verifikasi HMAC; validasi payload; deduplikasi dan commit inbox; ACK; worker menjalankan FSM; kirim melalui provider |
| Konsultasi | Ambil sesi; klasifikasi Gemini atau aturan; retrieval/cache BPS; format sumber resmi; tampilkan hasil atau klarifikasi; kepuasan bila hasil tersedia |
| Ketidakpuasan/pengaduan | Periksa jam kerja WITA; ubah step menjadi operator pada jam layanan; di luar jam kerja kirim kontak dan tutup percakapan aktif ke arsip |
| Login dan membaca pengaduan | Login; validasi session server; ambil daftar sesi operator; polling dashboard lima detik |
| Balasan operator | Validasi session, CSRF, nomor, pesan, dan status operator; kirim; catat history hanya setelah provider menerima permintaan |
| Penutupan operator | Validasi auth/CSRF; tolak saat pesan masuk masih pending; kirim penutup; arsipkan jika send diterima; aktifkan kembali bot |
| Timeout/reset | Bot idle 300 detik diarsipkan; operator tidak ditutup oleh timeout biasa; pengguna tetap dapat mengetik Selesai |
| Kegagalan/crash | Terapkan fallback atau simpan event failed/unknown; jangan menggambarkan retry pengiriman ambigu sebagai exactly-once |

Gunakan pemetaan FSM berikut secara konsisten:

| Konsep laporan | Step implementasi |
| --- | --- |
| STATE_INITIAL | `awal`, `pilih_layanan` |
| STATE_KONSULTASI | `gemini_tanya_data`, `rule_based_tanya_data`, `tanya_kepuasan` |
| STATE_PENGADUAN | `operator` |

- [ ] Hapus tombol Takeover Session dari diagram jika menggambarkan UI saat ini:
      alih kelola terjadi otomatis ketika FSM memasuki step operator.
- [ ] Bedakan dashboard petugas dari Web Chat Client publik yang belum tersedia.
- [ ] Tampilkan alternatif signature gagal, API gagal, luar jam kerja, dan send
      gagal pada diagram yang relevan.
- [ ] Samakan nama komponen, endpoint, state, caption, dan uraian naratif.

### 4.5 Implementasi dan 4.6 antarmuka

- [ ] Jelaskan fungsi aktual pada `wa_webhook.py`, `operator_auth.py`,
      `message_queue.py`, `session_manager.py`, `llm_engine.py`, dan `bps_api.py`.
- [ ] Jelaskan pemisahan tabel sessions, messages, conversations, webhook_inbox,
      dan bps_cache; sertakan migrasi aditif serta backup sebelum perubahan skema.
- [ ] Jelaskan default: timeout bot 300 detik, login 1800 detik, TTL BPS 86400
      detik, empat percobaan Gemini dengan anggaran request delapan detik.
      Nyatakan nilai tersebut dapat dikonfigurasi; bukan hasil pengukuran SLA.
- [ ] Bedakan angka dari abstrak BRS, teks klarifikasi, URL unduhan/halaman resmi,
      dan tautan katalog subjek. Tampilkan tanggal sumber saat tersedia.
- [ ] Ambil nama model dari konfigurasi snapshot. Nyatakan pemeriksaan katalog
      model sebagai verifikasi dokumentasi, bukan uji akses akun.
- [ ] Perbarui screenshot login, konsultasi, hasil tidak tersedia, pengaduan,
      balasan operator, dan penutupan menggunakan data sintetis.
- [ ] Jelaskan batas history: konteks Gemini maksimal 30 pesan, pengambilan
      history aktif 100 pesan, tampilan operator 200 pesan terakhir per sesi.
- [ ] Tulis bahwa dashboard memakai polling lima detik, bukan WebSocket.

**Selesai jika:** diagram dan penjelasan dapat ditelusuri ke fungsi yang tersedia,
serta screenshot berasal dari alur yang benar-benar dijalankan. Screenshot yang
belum dibuat diberi status menunggu bukti, bukan dianggap selesai.

## Tahap 5 — Susun ulang BAB IV bagian pengujian dan lampiran

### Bukti yang sudah tersedia

| Bukti | Cara menggunakan |
| --- | --- |
| [TESTING_REPORT.md](TESTING_REPORT.md) | Ambil metode, baseline, hasil, warning, dan batas cakupan |
| [test-results.txt](test-results.txt) | Rujuk 136 tes lulus pada snapshot audit; jangan menyebutnya uji live |
| [performance_results.json](performance_results.json) | Ambil 50 sampel per skenario, rata-rata, median, p95, maksimum, serta metadata lingkungan |
| `tests/test_security_integration.py` | Petakan signature, login, otorisasi, CSRF, input, provider mock, dan roundtrip |
| `tests/test_persistence_reliability.py` | Petakan migrasi/backup, reset, restart, retensi, deduplikasi, crash, dan konkurensi |
| `tests/test_retrieval_engine.py` | Petakan validasi BPS, cache, grounding, fallback dan batas request Gemini |

- [ ] Susun ulang Tabel 4.3 dengan kolom skenario, prasyarat/fixture, input,
      hasil yang diharapkan, hasil aktual, metode, status, dan referensi bukti.
- [ ] Nyatakan baseline: 65 tes, 61 lulus, satu failure, tiga errors; hasil audit
      akhir: 136 tes lulus, tanpa failure/error/skip.
- [ ] Pisahkan durasi total suite dari waktu respons chatbot.
- [ ] Sajikan enam skenario benchmark dalam milidetik dengan n=50 per skenario;
      jelaskan p95 nearest-rank dan persiapan yang dikecualikan dari pengukuran.
- [ ] Tulis batas metode: Flask test client, SQLite sementara, API dimock tanpa
      latensi buatan, tanpa jaringan TCP/Waitress dan pengiriman WhatsApp nyata.
- [ ] Catat warning dependency Google pada Python 3.14 tanpa menyebutnya failure
      aplikasi. Jangan mengklaim persentase coverage atau audit CVE yang belum diukur.

### Bukti tambahan yang masih diperlukan

- [ ] Uji berizin dengan nomor WhatsApp uji: penerimaan, menu, konsultasi,
      pengaduan, balasan operator, dan penutupan.
- [ ] Buktikan akses akun/model Gemini, retrieval BPS live, dan mekanisme auth
      incoming Fonnte atau relay yang digunakan.
- [ ] Rekam screenshot/video antarmuka browser aktual dengan data sintetis.
- [ ] Ukur latensi end-to-end termasuk antrean dan request send provider;
      pisahkan cache hit/miss, mode Gemini/aturan, error, dan jumlah sampel.
- [ ] Evaluasi pemahaman NLP dengan korpus pertanyaan berlabel bila hendak
      mencantumkan akurasi pemahaman pengguna.

**Selesai jika:** setiap status lulus memiliki bukti yang sesuai jenis klaimnya.
Pengujian live yang belum dilakukan tetap ditulis belum terverifikasi; target
tiga detik tidak boleh disimpulkan dari benchmark mock.

## Tahap 6 — Revisi BAB V dan bagian awal laporan

- [ ] Batasi kesimpulan pada prototipe yang tersedia dan hasil pengujian lokal.
- [ ] Sebutkan keamanan webhook Meta, login/CSRF operator, persistensi arsip,
      deduplikasi, FSM, dan fallback sebagai hasil dengan bukti tes yang sesuai.
- [ ] Ganti klaim high availability, seluruh kebutuhan terpenuhi, akurasi NLP,
      serta SLA produksi dengan pernyataan yang sesuai bukti.
- [ ] Cantumkan batas satu proses/worker, antrean, cakupan katalog, hari libur,
      auth Fonnte live, pengiriman ambigu, dan retensi yang perlu ditetapkan BPS.
- [ ] Tempatkan PostgreSQL/Redis, pencarian publikasi/pagination, rekonsiliasi
      pengiriman, dan analitik sebagai pengembangan berdasarkan kebutuhan nyata.
- [ ] Selaraskan abstrak, ringkasan, tujuan, dan ruang lingkup dengan kesimpulan
      final. Pertahankan rumusan target bila diberi label target yang belum terbukti.

**Selesai jika:** abstrak, kebutuhan, pembahasan, hasil, dan kesimpulan tidak
memberikan tingkat kepastian yang berbeda terhadap fitur yang sama.

## Tahap 7 — Validasi dokumen final

- [ ] Cari ulang istilah bermasalah; pastikan PostgreSQL/Tailwind/async hanya
      tersisa dalam konteks teori, perbandingan, atau pengembangan yang jelas.
- [ ] Periksa seluruh angka, satuan, nama model, endpoint, state, jadwal WITA,
      tabel hasil, serta nama kelas/fungsi terhadap snapshot implementasi.
- [ ] Perbarui daftar isi, daftar gambar, daftar tabel, caption, cross-reference,
      nomor halaman, dan daftar pustaka setelah isi stabil.
- [ ] Buka hasil di Word/LibreOffice; periksa pemotongan tabel, diagram, gambar,
      keterbacaan, dan layout halaman sebelum ekspor PDF.
- [ ] Periksa kembali lampiran dan screenshot agar tidak memuat credential atau
      data pengaduan pribadi.
- [ ] Simpan DOCX hasil revisi dan ringkasan perubahan. Ekspor PDF setelah hasil
      DOCX ditinjau; pertahankan dokumen sumber dan bukti pengujian.

## Definition of Done revisi laporan

Revisi laporan selesai ketika seluruh kondisi berikut terpenuhi:

1. Semua temuan pada matriks penyesuaian sudah diperbaiki atau ditulis sebagai
   batas/bukti yang masih diperlukan pada bagian laporan yang relevan.
2. Seluruh diagram, tabel teknologi, pembahasan implementasi, screenshot yang
   digunakan, dan kesimpulan konsisten dengan snapshot kode yang dicatat.
3. Setiap klaim hasil uji menyebut metode dan memiliki bukti; angka performa
   dapat ditelusuri ke hasil pengukuran dengan satuan dan sampel yang benar.
4. Hasil mock dan integrasi live dibedakan secara eksplisit; tidak ada klaim
   keberhasilan live atau SLA yang belum diukur.
5. Kebijakan retensi yang belum ditetapkan dan fitur yang belum tersedia tetap
   terlihat sebagai keterbatasan, bukan tersamarkan sebagai fitur selesai.
6. Salinan DOCX revisi dapat dibuka, layout dan referensinya sudah diperiksa,
   sumber asli tetap utuh, dan lampiran bebas credential/data pribadi.

Urutan kerja: selesaikan Tahap 1–2 dahulu, lalu BAB III, BAB IV beserta diagram
dan pengujiannya, BAB V/bagian awal, dan terakhir validasi layout. Gunakan
[DEMO_GUIDE.md](DEMO_GUIDE.md) hanya ketika menyiapkan bukti demonstrasi tambahan.
