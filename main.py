"""
Chatbot BPS Sulut — Main module.
State machine via dispatch table + fuzzy matching kategori BPS.
Gemini memberikan ringkasan jawaban + link sumber otomatis.
"""
import difflib
import logging
from datetime import datetime, timezone, timedelta

from llm_engine import analisis_pesan, test_api_connection, set_offline_mode, is_offline_mode
from session_manager import SessionManager
from config import BPS_CATEGORIES
from bps_api import cari_data_bps, cari_tabel_terbaru_bps, normalisasi_pencarian, ringkas_tabel_bps

logger = logging.getLogger(__name__)

session_mgr = SessionManager()

# Lookup table case-insensitive (dibuat sekali)
_CATEGORIES_LOWER = {k.lower(): v for k, v in BPS_CATEGORIES.items()}

# WITA = UTC+8
WITA = timezone(timedelta(hours=8))


def is_jam_kerja():
    """Cek apakah saat ini jam kerja BPS Sulut (Senin–Jumat, 08.00–15.30 WITA)."""
    now = datetime.now(WITA)
    # 0 = Senin, 4 = Jumat, 5 = Sabtu, 6 = Minggu
    if now.weekday() > 4:
        return False
    # Jam 08.00 (8*60 = 480 menit) s/d 15.30 (15*60+30 = 930 menit)
    m = now.hour * 60 + now.minute
    return 480 <= m <= 930


# ============================================================
# Fuzzy matching kategori → link BPS
# ============================================================
def cari_link_otomatis(teks_tujuan):
    """Cari link BPS paling sesuai dengan tujuan user.

    1. Exact/substring match
    2. Fuzzy match per kata
    3. Fallback homepage
    """
    teks_bersih = normalisasi_pencarian(teks_tujuan)
    if not teks_bersih:
        return None, "https://sulut.bps.go.id"

    daftar_kategori = list(_CATEGORIES_LOWER.keys())

    # 1. Exact/substring
    matches = [k for k in daftar_kategori if f" {normalisasi_pencarian(k)} " in f" {teks_bersih} "]
    if matches:
        best = max(matches, key=len)
        return best, _CATEGORIES_LOWER[best]

    # 2. Fuzzy match
    kata_pengguna = teks_bersih.split()
    best_score = 0
    best_kategori = None
    best_link = None

    for kategori in daftar_kategori:
        kata_kategori = normalisasi_pencarian(kategori).split()
        score = 0
        for kata_user in kata_pengguna:
            if len(kata_user) > 2:
                for kata_kat in kata_kategori:
                    if kata_user == kata_kat:
                        score += 2
                    elif len(kata_user) > 3:
                        if difflib.get_close_matches(kata_user, [kata_kat], n=1, cutoff=0.88):
                            score += 1
        if score > best_score:
            best_score = score
            best_kategori = kategori
            best_link = _CATEGORIES_LOWER[kategori]

    if best_link and best_score >= 1:
        return best_kategori, best_link

    return None, "https://sulut.bps.go.id"


# ============================================================
# State handlers — satu fungsi per step
# ============================================================
def _step_awal(phone, msg, session):
    session_mgr.add_to_history(phone, "user", msg)
    session_mgr.set_step(phone, "pilih_layanan")
    balasan = (
        "Halo! Selamat datang di layanan BPS Sulawesi Utara.\n"
        "Silakan pilih layanan yang Anda butuhkan:"
    )
    buttons = [
        {"id": "btn_pengaduan", "title": "Pengaduan"},
        {"id": "btn_konsultasi", "title": "Konsultasi"},
    ]
    session_mgr.add_to_history(phone, "model", balasan)
    return _reply(phone, balasan, buttons)


def _step_pilih_layanan(phone, msg, session):
    session_mgr.add_to_history(phone, "user", msg)
    pesan_lower = msg.strip().lower()

    if pesan_lower in {"pengaduan", "1", "btn_pengaduan"}:
        session_mgr.mark_complaint(phone)
        if is_jam_kerja():
            balasan = "Anda memilih Pengaduan. Menghubungkan Anda dengan operator petugas BPS... Mohon ditunggu ya."
            session_mgr.add_to_history(phone, "model", balasan)
            session_mgr.set_step(phone, "operator")
            return _reply(phone, balasan)
        else:
            balasan = (
                "Mohon maaf, Anda menghubungi kami di luar jam kerja layanan (Jam Kerja: Senin–Jumat, 08.00–15.30 WITA) sehingga operator tidak aktif.\n\n"
                "Silakan hubungi BPS Sulawesi Utara pada jam kerja atau melalui kontak resmi berikut:\n"
                "📞 Telepon: (0431) 847044\n"
                "📧 Email: bps7100@bps.go.id\n"
                "📠 Faks: (0431) 842206\n"
                "📍 Alamat: Jl. 17 Agustus, Manado, Sulawesi Utara 95119\n"
                "📷 Instagram: @bpsprovsulut"
            )
            session_mgr.add_to_history(phone, "model", balasan)
            session_mgr.reset(phone)
            return _reply(phone, balasan)

    if pesan_lower in {"konsultasi", "2", "btn_konsultasi"}:
        if is_offline_mode():
            session_mgr.set_step(phone, "rule_based_tanya_data")
            balasan = "Anda memilih Konsultasi (Mode Offline). Data apa yang ingin Anda cari?"
        else:
            session_mgr.set_step(phone, "gemini_tanya_data")
            balasan = "Anda memilih Konsultasi. Silakan ketik pertanyaan atau data yang Anda cari."
        session_mgr.add_to_history(phone, "model", balasan)
        return _reply(phone, balasan)

    balasan = "Pilihan tidak valid. Silakan pilih layanan:\n1. Pengaduan\n2. Konsultasi"
    return _reply(phone, balasan)


def _handle_selesai(phone, msg):
    """Cek apakah user ketik 'selesai' untuk mengakhiri sesi. Return balasan atau None."""
    if msg.strip().lower() in ("selesai", "done", "exit"):
        session_mgr.add_to_history(phone, "user", msg)
        balasan = "Terima kasih telah menggunakan layanan BPS Sulawesi Utara. Sampai jumpa!"
        session_mgr.add_to_history(phone, "model", balasan)
        session_mgr.reset(phone)
        return _reply(phone, balasan)
    return None


def _step_gemini_tanya_data(phone, msg, session):
    selesai = _handle_selesai(phone, msg)
    if selesai:
        return selesai
    history = session_mgr.get_history(phone) + [{"role": "user", "parts": [{"text": msg}]}]
    analisis = analisis_pesan(history, {"tujuan": session["tujuan"]})
    if analisis.get("intent") == "tidak_puas":
        return _step_kepuasan(phone, "Tidak", session)
    kategori, _ = cari_link_otomatis(msg)
    if analisis.get("intent") == "cari_data" or kategori or is_offline_mode():
        # Simpan pesan user ke history DULU, lalu kirim history ke Gemini
        # (analisis_pesan tidak menambah pesan baru lagi — fix #8 double message)
        # Retrieval formats the answer; generated figures and URLs are never displayed.
        return _step_rule_based_tanya_data(phone, msg, session)
    session_mgr.add_to_history(phone, "user", msg)
    balasan = "Silakan sebutkan topik data statistik BPS yang Anda perlukan, misalnya inflasi atau kependudukan."
    session_mgr.add_to_history(phone, "model", balasan)
    return _reply(phone, balasan)


def _step_rule_based_tanya_data(phone, msg, session):
    # Cek apakah user ingin mengakhiri sesi
    selesai = _handle_selesai(phone, msg)
    if selesai:
        return selesai

    session_mgr.add_to_history(phone, "user", msg)
    kategori_nama, link_bps = cari_link_otomatis(msg)

    if link_bps == "https://sulut.bps.go.id":
        link_bps = None

    session_mgr.update_info(phone, tujuan=msg)
    topik = f" tentang *{kategori_nama}*" if kategori_nama else " yang Anda cari"
    balasan = f"Halo! Berikut informasi{topik} di Sulawesi Utara dari BPS.\n"
    bps_data = cari_data_bps(msg)
    if bps_data and bps_data.get("found"):
        balasan += f"\n📌 *{bps_data['title']}* ({bps_data['tanggal']}):\n{bps_data['naratif'][:1600]}\n"

    tabel_terbaru = cari_tabel_terbaru_bps(msg, subject_url=link_bps, limit=2)
    if tabel_terbaru:
        balasan += "\nBeberapa data yang tersedia:\n"
        for t in tabel_terbaru:
            ringkasan = ringkas_tabel_bps(t, msg)
            if ringkasan:
                balasan += f"{ringkasan}\n"
            else:
                balasan += f"• *{t['title']}*\nAngka rincinya belum bisa ditampilkan di sini. Silakan buka tautannya di bawah.\n"
        balasan += "\nUntuk melihat data lebih lengkap, silakan buka tabel BPS berikut.\n\n📊 *Tabel Data Statistik BPS Sulut*:"
        for idx, t in enumerate(tabel_terbaru, 1):
            tgl = f" (diperbarui {t['date']})" if t.get("date") else ""
            balasan += f"\n{idx}. *{t['title']}*{tgl}"
            balasan += f"\n🔗 {t['url']}\n"
        balasan += "\n"
    else:
        balasan += (
            f"\nSaya belum menemukan tabel yang cocok. Anda bisa mencarinya di situs BPS berikut:\n"
            f"🔗 {link_bps or 'https://sulut.bps.go.id/id/statistics-table'}\n\n"
        )

    balasan += "Apakah informasi ini sudah membantu?"
    buttons = [
        {"id": "btn_ya", "title": "Ya"},
        {"id": "btn_tidak", "title": "Tidak"},
    ]
    session_mgr.set_step(phone, "tanya_kepuasan")
    session_mgr.add_to_history(phone, "model", balasan)
    return _reply(phone, balasan, buttons)


def _step_kepuasan(phone, msg, session):
    # Cek apakah user ingin mengakhiri sesi
    selesai = _handle_selesai(phone, msg)
    if selesai:
        return selesai

    session_mgr.add_to_history(phone, "user", msg)
    pesan_clean = msg.strip().lower()

    # Match exact untuk hindari false positive (#16)
    if pesan_clean in ("tidak", "no", "tdk", "blm", "belum"):
        session_mgr.mark_complaint(phone)
        if is_jam_kerja():
            balasan = "Mohon maaf jika jawaban belum memuaskan. Menghubungkan Anda dengan operator petugas BPS... Mohon ditunggu ya."
            session_mgr.add_to_history(phone, "model", balasan)
            session_mgr.set_step(phone, "operator")
            return _reply(phone, balasan)
        else:
            balasan = (
                "Mohon maaf jika jawaban belum memuaskan. saat ini layanan di luar jam kerja (Jam Kerja: Senin–Jumat, 08.00–15.30 WITA) sehingga operator tidak aktif.\n\n"
                "Anda dapat menghubungi BPS Sulawesi Utara pada jam kerja atau melalui kontak resmi berikut:\n"
                "📞 Telepon: (0431) 847044\n"
                "📧 Email: bps7100@bps.go.id\n"
                "📍 Alamat: Jl. 17 Agustus, Manado, Sulawesi Utara 95119"
            )
            session_mgr.add_to_history(phone, "model", balasan)
            session_mgr.reset(phone)
            return _reply(phone, balasan)

    if pesan_clean in ("ya", "yes", "iya", "yaa", "oke", "ok"):
        if is_offline_mode():
            session_mgr.set_step(phone, "rule_based_tanya_data")
            balasan = "Terima kasih! Data apa lagi yang ingin Anda cari?\n\nJika sudah tidak ada, silakan ketik *Selesai*."
        else:
            session_mgr.set_step(phone, "gemini_tanya_data")
            balasan = "Silakan ketik pertanyaan atau data yang Anda cari selanjutnya.\n\nJika sudah tidak ada, silakan ketik *Selesai*."
        session_mgr.add_to_history(phone, "model", balasan)
        return _reply(phone, balasan)

    balasan = "Silakan jawab dengan Ya atau Tidak. Apakah Anda puas dengan informasi ini?"
    return _reply(phone, balasan)


def _step_operator(phone, msg, session):
    """Handler saat sesi diteruskan ke operator (bot diam/diteruskan)."""
    # Cek apakah user ingin mengakhiri sesi operator
    selesai = _handle_selesai(phone, msg)
    if selesai:
        return selesai
    session_mgr.add_to_history(phone, "user", msg)
    logger.info("Pesan diteruskan ke operator")
    return None


# ============================================================
# Dispatch table — map step name → handler function
# ponytail: kalau state > 10, pakai library `transitions`
# ============================================================
STATES = {
    "awal": _step_awal,
    "pilih_layanan": _step_pilih_layanan,
    "gemini_tanya_data": _step_gemini_tanya_data,
    "rule_based_tanya_data": _step_rule_based_tanya_data,
    "tanya_kepuasan": _step_kepuasan,
    "operator": _step_operator,
}


def handle_incoming_message(phone_number, message_text):
    """Proses pesan masuk — dispatch ke handler berdasarkan step."""
    from webhook_utils import phone_lock
    with phone_lock(phone_number):
        session = session_mgr.get_or_create(phone_number)

        if session_mgr.is_expired(phone_number):
            session_mgr.reset(phone_number)
            session = session_mgr.get_or_create(phone_number)

        session_mgr.touch(phone_number)
        step = session["step"]

        handler = STATES.get(step)
        if handler is None:
            logger.warning("Step sesi tidak dikenal; reset diperlukan")
            session_mgr.reset(phone_number)
            return _reply(phone_number, "Maaf, terjadi kesalahan sesi. Silakan mulai ulang percakapan.")

        selesai = _handle_selesai(phone_number, message_text)
        if selesai:
            return selesai
        if step in {"gemini_tanya_data", "rule_based_tanya_data"} and message_text.strip().lower() in {"tidak", "operator", "belum"}:
            return _step_kepuasan(phone_number, "Tidak", session)
        return handler(phone_number, message_text, session)


def _reply(phone_number, text, buttons=None):
    """Bangun response dict."""
    res = {"to": phone_number, "message": text}
    if buttons:
        res["buttons"] = buttons
    return res


# ============================================================
# SIMULASI CHAT DI TERMINAL
# ============================================================
def _startup_api_check():
    """Cek koneksi API saat startup."""
    print("Mengecek koneksi ke Gemini API...")
    berhasil, error = test_api_connection()

    if berhasil:
        print("API terhubung! Menggunakan mode AI.\n")
        set_offline_mode(False)
        return

    print(f"API tidak tersedia: {error[:100]}...\n")

    while True:
        print("Pilih mode:")
        print("  [1] Coba lagi (retry)")
        print("  [2] Gunakan mode offline (tanpa AI)")
        print("  [3] Keluar")

        try:
            pilihan = input("Pilihan (1/2/3): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            exit(0)

        if pilihan == "1":
            print("Mencoba ulang...")
            berhasil, error = test_api_connection()
            if berhasil:
                print("API terhubung! Menggunakan mode AI.\n")
                set_offline_mode(False)
                return
            print(f"Masih gagal: {error[:100]}...\n")
        elif pilihan == "2":
            set_offline_mode(True)
            print("Mode offline aktif. Chatbot tetap berjalan tanpa AI.\n")
            return
        elif pilihan == "3":
            print("Keluar.")
            exit(0)
        else:
            print("Pilihan tidak valid.\n")


def simulasi_chat():
    nomor_hp = "08123456789"

    print("=" * 55)
    print("  Chatbot BPS Sulawesi Utara — Simulasi Terminal")
    print("=" * 55)
    print()

    _startup_api_check()

    # Pre-warm BPS API Cache di background
    from bps_api import start_prewarm_thread
    start_prewarm_thread(interval_hours=6)

    mode_label = "OFFLINE" if is_offline_mode() else "AI"
    print("-" * 55)
    print(f"  Mode: {mode_label}")
    print("  Ketik 'keluar' untuk berhenti")
    print("  Ketik 'reset' untuk mulai percakapan baru")
    print("  Ketik 'info' untuk lihat data session")
    print("  Ketik 'online' untuk coba koneksi API lagi")
    print("-" * 55)
    print()

    while True:
        try:
            pesan_masuk = input("Anda: ")
        except (EOFError, KeyboardInterrupt):
            print("\nSimulasi dihentikan.")
            break

        if not pesan_masuk.strip():
            continue

        cmd = pesan_masuk.lower().strip()

        if cmd == "keluar":
            print("Simulasi dihentikan. Terima kasih!")
            break

        if cmd == "reset":
            session_mgr.reset(nomor_hp)
            print("Session di-reset. Mulai percakapan baru.\n")
            continue

        if cmd == "online":
            print("\nMencoba koneksi ke API...")
            berhasil, error = test_api_connection()
            if berhasil:
                set_offline_mode(False)
                print("API terhubung! Beralih ke mode AI.\n")
            else:
                print(f"API masih tidak tersedia: {error[:80]}...")
                print("  Tetap menggunakan mode offline.\n")
            continue

        if cmd == "info":
            session = session_mgr.get_or_create(nomor_hp)
            mode = "OFFLINE" if is_offline_mode() else "AI"
            print(f"Session Info:")
            print(f"   Mode    : {mode}")
            print(f"   Tujuan  : {session.get('tujuan') or '-'}")
            print(f"   Step    : {session['step']}")
            print(f"   History : {len(session['history'])} pesan\n")
            continue

        balasan = handle_incoming_message(nomor_hp, pesan_masuk)

        if balasan is None:
            print("Bot: [Diteruskan ke operator — chatbot tidak merespon lagi]")
            print("Ketik 'reset' untuk memulai percakapan baru.\n")
        else:
            print(f"Bot: {balasan['message']}\n")


if __name__ == "__main__":
    simulasi_chat()
