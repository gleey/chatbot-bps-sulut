# Penyelarasan Laporan Magang dengan Implementasi

Dokumen sumber: `/home/gley/Gley/Magang BPS/Laporan Magang Gley.docx`.
Dokumen dibaca tanpa dimodifikasi. Referensi paragraf di bawah mengacu pada urutan
`w:p` dalam `word/document.xml`, termasuk paragraf kosong dan tabel. Nomor halaman
Word tidak dijadikan bukti karena pagination bergantung pada renderer.

## Matriks revisi

| Bagian laporan / paragraf | Penilaian | Revisi dan bukti implementasi |
| --- | --- | --- |
| 3.2.2, p370; 4.5.2, p622 | Perlu revisi | Ganti “KeyPoolManager terdistribusi” dengan failover key/model berurutan dalam satu proses, cooldown 300 detik, empat percobaan dan anggaran delapan detik. Kelas aktual `_KeyRotator`, `_ModelRotator`; `EngineTests` dan `TestRotatorIntegration` |
| 3.3.1, p373–375 | Klaim harus diganti | Python + Flask/Waitress WSGI sinkron, requests dan SDK sinkron; penerimaan disimpan ke inbox SQLite lalu diproses satu background worker. Tidak ada asyncio/non-blocking I/O; `wa_webhook`, `message_queue` |
| 3.3.2, p378; 4.3.2, p440; 4.5.1, p619 | Kini didukung untuk Meta | HMAC SHA-256 raw body diverifikasi sebelum parsing; signature hilang/palsu ditolak 403. Istilah yang benar **autentikasi/integritas berbasis MAC**, bukan enkripsi atau tanda tangan asimetris. Fonnte memakai shared-secret Authorization, bukan HMAC Meta |
| 3.4.2, p385–386 | Perlu diperjelas | State/history disimpan langsung di SQLite. Reset membuat pemisahan konteks aktif dan arsip, bukan menghapus history. Timeout bot 300 detik; operator dikecualikan; `SessionManager`, `PersistenceTests` |
| 3.5, p390; 4.3.1, p432; 4.5.3, p626 | Perlu dipersempit | Retrieval BRS/statictable dengan cache TTL 24 jam. Gemini mengklasifikasi, backend memformat abstrak resmi; tidak ada sintesis kembali seluruh JSON oleh Gemini. Pencarian publikasi lengkap belum ada |
| Tabel 4.2, p449–451; 4.5.1, p619 | Perlu revisi | Python minimal 3.10 sesuai dependency; audit teruji pada 3.14.8. Hapus alasan performa async yang tidak sesuai |
| Tabel 4.2, p469 | Salah teknologi | Ganti Tailwind CSS dengan **Bootstrap 5 + HTML + JavaScript**; `templates/operator.html`, `operator_login.html` |
| 4.3.2, p439 | Butuh bukti tambahan | Tiga detik adalah target, bukan hasil. Ukur dari penerimaan webhook hingga permintaan balasan diterima provider, termasuk antrean. Lampirkan benchmark lokal hanya sebagai overhead aplikasi, terpisah dari pengujian live |
| 4.4.2, p481; Gambar 4.2 | Perlu diperbarui | Tambahkan inbox persisten, worker tunggal, SQLite, arsip, cache 24 jam, auth/CSRF dashboard. Web Chat Client untuk pengguna belum tersedia; dashboard operator bukan web chat publik |
| 4.4.3, p486–491; Gambar 4.3 | Sesuai secara konseptual | Pertahankan tiga kelompok konsep, tampilkan pemetaan enam step implementasi di bawah |
| Diagram memulai percakapan, p507, p557 | Kini didukung, urutan perlu diperbarui | HMAC sebelum parsing; pesan disimpan sebelum ACK; pemrosesan FSM/pengiriman terjadi pada worker. `test_duplicate_delivery_runs_fsm_once` dan tes roundtrip |
| Diagram konsultasi, p560; menilai jawaban p567 | Perlu diperbarui | Tombol kepuasan dikirim setelah hasil pencarian; klarifikasi yang belum menemukan kategori tetap dalam konsultasi. Rotasi berlaku terbatas, tidak menjamin semua kegagalan terselesaikan |
| Diagram login/memantau, p531 | Kini didukung | Login wajib sebelum mengakses dashboard dan data pengaduan. Session, server-side authorization, dan CSRF dibuktikan oleh `WebIntegration` |
| Diagram operator melihat pengaduan, p581 | Tidak sesuai | Ganti PostgreSQL menjadi SQLite. Hapus tombol **Takeover Session** yang tidak ada: alih kelola otomatis saat FSM memasuki `operator`. Jangan menyatakan dashboard mengambil seluruh riwayat tanpa batas; UI menampilkan maksimal 200 pesan aktif |
| 4.5.2, p622; 5.1, p730 | Model perlu diperbarui | Model contoh menjadi `gemini-3.6-flash`, fallback `gemini-3.5-flash-lite`. `gemini-3.5-flash` lama deprecated menurut dokumentasi resmi; akses akun live belum diuji |
| 4.5.4, p630–632; Gambar 4.29–4.30 | Sesuai dengan batas | Dashboard polling lima detik. Indikator koneksi berubah setelah respons sukses/gagal; bukan WebSocket. Tambahkan screenshot login dan kegagalan pengiriman dari lingkungan demo berizin |
| 4.7; Tabel 4.3, p687–724 | Perlu bukti terukur | Ganti “Sesuai Spesifikasi/Lulus” umum dengan nama tes, perintah, jumlah, fixture, status, dan log. Klaim pemahaman NLP serta retrieval/provider live tetap unverified sampai diuji nyata |
| 5.1, p730–732 | Klaim harus dipersempit | Nyatakan hasil prototipe dan tes mock; jangan menyimpulkan high availability, akurasi NLP, seluruh kebutuhan terpenuhi, atau SLA produksi dari unit test |
| 5.2, p736 | Sesuai sebagai saran | SQLite sudah menyimpan data secara persisten. PostgreSQL/Redis adalah pilihan untuk skala dan koordinasi, bukan syarat agar riwayat bertahan setelah restart |

## Pemetaan FSM

| Konsep laporan | Step kode | Peristiwa |
| --- | --- | --- |
| STATE_INITIAL | `awal`, `pilih_layanan` | Pesan pertama, menu, reset/timeout bot |
| STATE_KONSULTASI | `gemini_tanya_data`, `rule_based_tanya_data`, `tanya_kepuasan` | Klasifikasi, pencarian resmi, kepuasan, lanjut atau selesai |
| STATE_PENGADUAN | `operator` | Bot diam, pesan dicatat untuk operator; tutup eksplisit |

Di luar jam kerja, permintaan pengaduan diarsipkan setelah pemberitahuan kontak;
sesi aktif kembali ke awal. Operator yang sudah menangani sesi tidak dipaksa
berhenti saat jam kerja berakhir atau setelah lima menit. Pengguna dapat menutup
sesi dengan `Selesai`; operator menutup melalui API yang diautentikasi.

## Usulan teks pengganti BAB III

Backend prototipe menggunakan Python dan Flask dengan server WSGI Waitress.
Panggilan ke Gemini dan BPS menggunakan I/O sinkron dengan timeout. Untuk
memisahkan penerimaan webhook dari pemrosesan percakapan, payload yang telah
diautentikasi disimpan ke inbox SQLite dan diproses oleh satu background thread.
Penguncian per nomor menjaga konsistensi transisi FSM dalam deployment satu
proses. Pendekatan ini tidak identik dengan asynchronous I/O dan tidak membuktikan
kapasitas pada deployment multi-proses.

Sesi aktif, pesan, dan arsip percakapan disimpan dalam SQLite dengan WAL. Reset
menutup identitas percakapan lama dan membersihkan konteks aktif tanpa menghapus
arsipnya. Penghapusan arsip dilakukan hanya melalui pemeliharaan eksplisit sesuai
kebijakan retensi yang ditetapkan instansi.

## Usulan teks pengganti BAB IV

Pada provider Meta, aplikasi menghitung HMAC SHA-256 dari raw body memakai App
Secret dan membandingkan signature menggunakan `hmac.compare_digest`. Permintaan
tanpa signature valid ditolak sebelum parsing payload. Dashboard mewajibkan login
petugas, memvalidasi session pada server, serta memerlukan token CSRF untuk
pengiriman dan penutupan sesi. Data tidak disisipkan sebagai HTML mentah pada
antarmuka percakapan.

Gemini digunakan untuk klasifikasi kebutuhan. Untuk mengurangi risiko angka atau
URL yang dibuat model, aplikasi menyusun jawaban statistik dari judul, tanggal,
dan cuplikan rilis resmi yang dikembalikan BPS API. Retrieval menggunakan cache
24 jam; tautan kategori dibedakan dari URL individual. Pencarian terbatas pada
halaman hasil yang diperoleh dan tidak menjamin cakupan seluruh katalog terbaru.

Pengujian otomatis menggunakan Flask test client, database sementara, credential
sintetis, dan mock provider. Pengujian ini memvalidasi kontrak aplikasi, transisi
status, keamanan, dan pemulihan yang tercakup oleh skenario tes. Benchmark lokal
mengukur overhead pemrosesan serta ACK webhook; latensi layanan eksternal dan
pengiriman WhatsApp nyata tidak termasuk.

## Usulan teks pengganti BAB V

Prototipe telah menyediakan autentikasi webhook Meta, akses dashboard terkontrol,
arsip percakapan, deduplikasi pesan, dan fallback layanan yang diuji secara lokal.
Hasil tersebut mendukung demonstrasi alur aplikasi dengan fixture yang terkontrol.
Pengujian live dengan akun provider, evaluasi pemahaman pertanyaan pengguna,
pengukuran waktu balasan end-to-end, dan kebijakan retensi tetap diperlukan
sebelum pemakaian operasional.

Pengembangan selanjutnya mencakup pencarian dengan pagination dan publikasi yang
lebih luas, penanganan kegagalan pengiriman yang dapat direkonsiliasi operator,
serta pengukuran beban pada infrastruktur target. Migrasi database atau antrean
terdistribusi dilakukan apabila kebutuhan multi-proses atau beberapa host telah
terbukti melalui pengukuran.

## Bukti untuk lampiran

- `TESTING_REPORT.md`: baseline, hasil akhir, metode, batas pengujian.
- `test-results.txt`: keluaran suite otomatis dengan credential sintetis.
- `performance_results.json`: 50 sampel tiap skenario dan metadata lingkungan.
- `tests/test_security_integration.py`: signature, login, CSRF, input, provider,
  deduplikasi, dan roundtrip konsultasi/pengaduan.
- `tests/test_persistence_reliability.py`: backup migrasi, restart, retensi, race,
  dan crash ambigu.
- `tests/test_retrieval_engine.py`: grounding, validasi tautan/cache, batas retry,
  cooldown, dan schema respons LLM.
- Screenshot dan video live WhatsApp/dashboard **belum dibuat**. Rekam setelah
  mendapat izin, dengan nomor uji dan data pengaduan sintetis.

Katalog model dan batas versi dapat berubah. Sumber resmi serta waktu audit
tercantum dalam `PROJECT_AUDIT.md`. Referensi ilmiah dan dasar hukum dalam laporan
bukan objek verifikasi bibliografi pada pekerjaan ini.
