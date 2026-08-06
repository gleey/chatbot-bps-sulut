"""
Chatbot BPS Sulut — Main module.
State machine via dispatch table + fuzzy matching kategori BPS.
Gemini memberikan ringkasan jawaban + link sumber otomatis.
"""
import difflib
import logging
from llm_engine import analisis_pesan, test_api_connection, set_offline_mode, is_offline_mode
from session_manager import SessionManager
from config import BPS_CATEGORIES
from bps_api import cari_data_bps

logger = logging.getLogger(__name__)

session_mgr = SessionManager()

# Lookup table case-insensitive (dibuat sekali)
_CATEGORIES_LOWER = {k.lower(): v for k, v in BPS_CATEGORIES.items()}


# ============================================================
# Fuzzy matching kategori → link BPS
# ============================================================
def cari_link_otomatis(teks_tujuan):
    """Cari link BPS paling sesuai dengan tujuan user.

    1. Exact/substring match
    2. Fuzzy match per kata
    3. Fallback homepage
    """
    teks_bersih = teks_tujuan.lower().strip()
    if not teks_bersih:
        return None, "https://sulut.bps.go.id"

    daftar_kategori = list(_CATEGORIES_LOWER.keys())

    # 1. Exact/substring
    matches = [k for k in daftar_kategori if k in teks_bersih or teks_bersih in k]
    if matches:
        best = max(matches, key=len)
        return best, _CATEGORIES_LOWER[best]

    # 2. Fuzzy match
    kata_pengguna = teks_bersih.split()
    best_score = 0
    best_kategori = None
    best_link = None

    for kategori in daftar_kategori:
        kata_kategori = kategori.split()
        score = 0
        for kata_user in kata_pengguna:
            if len(kata_user) > 2:
                for kata_kat in kata_kategori:
                    if kata_user == kata_kat:
                        score += 2
                    elif len(kata_user) > 3:
                        if difflib.get_close_matches(kata_user, [kata_kat], n=1, cutoff=0.75):
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

    if "pengaduan" in pesan_lower or pesan_lower == "1":
        balasan = "Anda memilih Pengaduan. Menghubungkan ke operator kami... Mohon ditunggu ya."
        session_mgr.add_to_history(phone, "model", balasan)
        session_mgr.reset(phone)
        return _reply(phone, balasan)

    if "konsultasi" in pesan_lower or pesan_lower == "2":
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


def _step_gemini_tanya_data(phone, msg, session):
    # Simpan pesan user ke history DULU, lalu kirim history ke Gemini
    # (analisis_pesan tidak menambah pesan baru lagi — fix #8 double message)
    session_mgr.add_to_history(phone, "user", msg)
    history = session_mgr.get_history(phone)
    session = session_mgr.get_or_create(phone)
    info_terkumpul = {
        "tujuan": session["tujuan"],
    }

    analisis = analisis_pesan(history, info_terkumpul)
    intent = analisis.get("intent", "lainnya")

    session_mgr.update_info(
        phone,
        tujuan=analisis.get("tujuan"),
    )

    if intent == "cari_data":
        kategori_gemini = analisis.get("kategori_cocok", "")
        tujuan_text = kategori_gemini or analisis.get("tujuan", "") or msg

        link_bps = None
        if kategori_gemini:
            if kategori_gemini.lower() in _CATEGORIES_LOWER:
                link_bps = _CATEGORIES_LOWER[kategori_gemini.lower()]
            else:
                _, link_bps = cari_link_otomatis(kategori_gemini)
                if link_bps == "https://sulut.bps.go.id":
                    link_bps = None

        ringkasan = analisis.get("balasan", "")
        balasan = ringkasan

        # HANYA lampirkan data BPS API dan link jika kategori data spesifik (link_bps) ditemukan/cocok
        if link_bps:
            bps_data = cari_data_bps(tujuan_text)
            if bps_data and bps_data.get("found"):
                balasan += f"\n\n📌 *Data Resmi Terbaru ({bps_data['title']})*:\n{bps_data['naratif']}"

            balasan += f"\n\n🔗 Tabel Data Statistik Website BPS:\n{link_bps}"

        balasan += "\n\nApakah Anda puas dengan informasi ini?"

        buttons = [
            {"id": "btn_ya", "title": "Ya"},
            {"id": "btn_tidak", "title": "Tidak"},
        ]
        session_mgr.set_step(phone, "tanya_kepuasan")
        session_mgr.add_to_history(phone, "model", balasan)
        return _reply(phone, balasan, buttons)

    # Intent bukan cari_data — balasan natural dari Gemini
    balasan = analisis.get("balasan", "Ada yang bisa saya bantu?")
    session_mgr.add_to_history(phone, "model", balasan)
    return _reply(phone, balasan)


def _step_rule_based_tanya_data(phone, msg, session):
    session_mgr.add_to_history(phone, "user", msg)
    pesan_lower = msg.strip().lower()
    kategori_nama, link_bps = cari_link_otomatis(msg)
    
    if link_bps == "https://sulut.bps.go.id":
        link_bps = None

    if not link_bps and not any(k in pesan_lower for k in ["bps", "sulut"]):
        balasan = (
            "Maaf, saya tidak menemukan kategori data yang sesuai.\n"
            "Silakan coba dengan kata kunci lain, misal: kependudukan, inflasi, pertanian, pariwisata."
        )
        session_mgr.add_to_history(phone, "model", balasan)
        return _reply(phone, balasan)

    balasan = f"Berikut adalah data BPS Sulut terkait *{msg}*:\n"
    if link_bps:
        bps_data = cari_data_bps(msg)
        if bps_data and bps_data.get("found"):
            balasan += f"\n📌 *{bps_data['title']}*:\n{bps_data['naratif']}\n"
        balasan += f"\n🔗 Link Tabel BPS: {link_bps}\n\n"
    else:
        balasan += f"\n🔗 Website BPS Sulut: https://sulut.bps.go.id\n\n"
        
    balasan += "Apakah Anda puas dengan hasil yang dikirimkan?"
    buttons = [
        {"id": "btn_ya", "title": "Ya"},
        {"id": "btn_tidak", "title": "Tidak"},
    ]
    session_mgr.set_step(phone, "tanya_kepuasan")
    session_mgr.add_to_history(phone, "model", balasan)
    return _reply(phone, balasan, buttons)


def _step_kepuasan(phone, msg, session):
    session_mgr.add_to_history(phone, "user", msg)
    pesan_clean = msg.strip().lower()

    # Match exact untuk hindari false positive (#16)
    if pesan_clean in ("tidak", "no", "tdk", "blm", "belum"):
        if is_offline_mode():
            session_mgr.set_step(phone, "rule_based_tanya_data")
            balasan = "Mohon maaf jika jawaban belum memuaskan. Data apa lagi yang ingin Anda cari?"
        else:
            session_mgr.set_step(phone, "gemini_tanya_data")
            balasan = "Mohon maaf jika jawaban belum memuaskan. Silakan ketik pertanyaan atau data yang Anda cari selanjutnya."
        session_mgr.add_to_history(phone, "model", balasan)
        return _reply(phone, balasan)

    if pesan_clean in ("ya", "yes", "iya", "yaa", "oke", "ok"):
        if is_offline_mode():
            session_mgr.set_step(phone, "rule_based_tanya_data")
            balasan = "Terima kasih! Data apa lagi yang ingin Anda cari?"
        else:
            session_mgr.set_step(phone, "gemini_tanya_data")
            balasan = "Silakan ketik pertanyaan atau data yang Anda cari selanjutnya."
        session_mgr.add_to_history(phone, "model", balasan)
        return _reply(phone, balasan)

    balasan = "Silakan jawab dengan Ya atau Tidak. Apakah Anda puas dengan informasi ini?"
    return _reply(phone, balasan)


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
}


def handle_incoming_message(phone_number, message_text):
    """Proses pesan masuk — dispatch ke handler berdasarkan step."""
    # Bersihkan sesi kedaluwarsa secara berkala/saat ada pesan masuk.
    session_mgr.cleanup_expired()
    
    session = session_mgr.get_or_create(phone_number)

    if session_mgr.is_expired(phone_number):
        session_mgr.reset(phone_number)
        session = session_mgr.get_or_create(phone_number)

    session_mgr.touch(phone_number)
    step = session["step"]

    handler = STATES.get(step)
    if handler is None:
        logger.warning("Step tidak dikenal: %s, reset session %s", step, phone_number)
        session_mgr.reset(phone_number)
        return _reply(phone_number, "Maaf, terjadi kesalahan sesi. Silakan mulai ulang percakapan.")

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
