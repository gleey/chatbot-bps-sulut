import difflib
from llm_engine import analisis_pesan, test_api_connection, set_offline_mode, is_offline_mode
from session_manager import SessionManager

# ============================================================
# HARDCODED: Kategori data BPS Sulut → Link website
# ============================================================
BPS_CATEGORIES = {
    "kependudukan dan migrasi": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "kependudukan": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "tenaga kerja": "https://sulut.bps.go.id/id/statistics-table?subject=520",
    "pendidikan": "https://sulut.bps.go.id/id/statistics-table?subject=521",
    "kesehatan": "https://sulut.bps.go.id/id/statistics-table?subject=522",
    "konsumsi dan pendapatan": "https://sulut.bps.go.id/id/statistics-table?subject=523",
    "perlindungan sosial": "https://sulut.bps.go.id/id/statistics-table?subject=524",
    "pemukiman dan perumahan": "https://sulut.bps.go.id/id/statistics-table?subject=525",
    "hukum dan kriminal": "https://sulut.bps.go.id/id/statistics-table?subject=526",
    "budaya": "https://sulut.bps.go.id/id/statistics-table?subject=527",
    "aktivitas politik dan komunitas": "https://sulut.bps.go.id/id/statistics-table?subject=528",
    "penggunaan waktu": "https://sulut.bps.go.id/id/statistics-table?subject=529",
    "statistik makroekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=530",
    "neraca ekonomi": "https://sulut.bps.go.id/id/statistics-table?subject=531",
    "statistik bisnis": "https://sulut.bps.go.id/id/statistics-table?subject=532",
    "statistik sektoral": "https://sulut.bps.go.id/id/statistics-table?subject=533",
    "keuangan pemerintah, fiskal dan statistik sektor publik": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "keuangan pemerintah": "https://sulut.bps.go.id/id/statistics-table?subject=534",
    "perdagangan internasional dan neraca pembayaran": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "perdagangan internasional": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "harga-harga": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "harga": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "biaya tenaga kerja": "https://sulut.bps.go.id/id/statistics-table?subject=537",
    "ilmu pengetahuan, teknologi dan inovasi": "https://sulut.bps.go.id/id/statistics-table?subject=538",
    "teknologi": "https://sulut.bps.go.id/id/statistics-table?subject=538",
    "pertanian kehutanan perikanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "pertanian": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "perikanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "kehutanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "energi": "https://sulut.bps.go.id/id/statistics-table?subject=558",
    "pertambangan, manufaktur, konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "pertambangan": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "manufaktur": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "transportasi": "https://sulut.bps.go.id/id/statistics-table?subject=560",
    "pariwisata": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "wisata": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "perbankan, asuransi dan finansial": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "perbankan": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "finansial": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "lingkungan": "https://sulut.bps.go.id/id/statistics-table?subject=539",
    "statistik regional dan statistik area kecil": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "statistik regional": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "statistik dan indikator multi-domain": "https://sulut.bps.go.id/id/statistics-table?subject=541",
    "buku tahunan dan ringkasan sejenis": "https://sulut.bps.go.id/id/statistics-table?subject=542",
    "kondisi tempat tinggal, kemiskinan, dan permasalahan sosial lintas sektor": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "gender dan kelompok populasi khusus": "https://sulut.bps.go.id/id/statistics-table?subject=564",
    "masyarakat informasi": "https://sulut.bps.go.id/id/statistics-table?subject=565",
    "globalisasi": "https://sulut.bps.go.id/id/statistics-table?subject=566",
    "indikator millenium development goals (mdgs)": "https://sulut.bps.go.id/id/statistics-table?subject=567",
    "mdgs": "https://sulut.bps.go.id/id/statistics-table?subject=567",
    "perkembangan berkelanjutan": "https://sulut.bps.go.id/id/statistics-table?subject=568",
    "sdgs": "https://sulut.bps.go.id/id/statistics-table?subject=568",
    "kewiraswastaan": "https://sulut.bps.go.id/id/statistics-table?subject=569",
    "inflasi": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "ekspor": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "impor": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "pdrb": "https://sulut.bps.go.id/id/statistics-table?subject=530",
    "penduduk": "https://sulut.bps.go.id/id/statistics-table?subject=519",
    "migrasi": "https://sulut.bps.go.id/id/statistics-table?subject=519",
}

session_mgr = SessionManager()


# ============================================================
# HARDCODED: Fuzzy matching kategori → link BPS
# ============================================================
def cari_link_otomatis(teks_tujuan):
    """Cari link BPS yang paling sesuai dengan tujuan user.
    
    Pendekatan:
    1. Exact match (substring)
    2. Fuzzy match per kata
    3. Fallback ke homepage BPS Sulut
    """
    teks_bersih = teks_tujuan.lower().strip()

    if not teks_bersih:
        return "https://sulut.bps.go.id"

    kategori_lower_map = {}
    for kunci, nilai in BPS_CATEGORIES.items():
        kategori_lower_map[kunci.lower()] = nilai

    daftar_kategori = list(kategori_lower_map.keys())

    matches = []
    for kategori in daftar_kategori:
        if kategori in teks_bersih or teks_bersih in kategori:
            matches.append(kategori)
    if matches:
        best = max(matches, key=len)
        return kategori_lower_map[best]

    kata_pengguna = teks_bersih.split()
    best_score = 0
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
                        kecocokan = difflib.get_close_matches(
                            kata_user, [kata_kat], n=1, cutoff=0.75
                        )
                        if kecocokan:
                            score += 1

        if score > best_score:
            best_score = score
            best_link = kategori_lower_map[kategori]

    if best_link and best_score >= 1:
        return best_link

    return "https://sulut.bps.go.id"


# ============================================================
# HYBRID: Handle pesan masuk (LLM + Hardcoded)
# ============================================================
def handle_incoming_message(phone_number, message_text):
    """Proses pesan masuk dari user berdasarkan State Machine."""
    session = session_mgr.get_or_create(phone_number)

    if session_mgr.is_expired(phone_number):
        session_mgr.reset(phone_number)
        session = session_mgr.get_or_create(phone_number)

    session_mgr.touch(phone_number)
    step = session["step"]
    pesan_lower = message_text.strip().lower()

    if step == "awal":
        session_mgr.set_step(phone_number, "tanya_nama_instansi")
        balasan = (
            "Halo! Selamat datang di layanan BPS Sulawesi Utara.\n"
            "Silakan sebutkan nama dan asal instansi Anda."
        )
        session_mgr.add_to_history(phone_number, "model", balasan)
        return send_message(phone_number, balasan)

    elif step == "tanya_nama_instansi":
        # Simpan input user ke history sebagai penanda perkenalan
        session_mgr.update_info(phone_number, nama=message_text)
        session_mgr.add_to_history(phone_number, "user", message_text)
        
        session_mgr.set_step(phone_number, "pilih_layanan")
        balasan = "Terima kasih! Silakan pilih layanan:"
        buttons = [
            {"id": "btn_pengaduan", "title": "Pengaduan"},
            {"id": "btn_konsultasi", "title": "Konsultasi"}
        ]
        session_mgr.add_to_history(phone_number, "model", balasan)
        return send_message(phone_number, balasan, buttons)

    elif step == "pilih_layanan":
        session_mgr.add_to_history(phone_number, "user", message_text)
        
        if "pengaduan" in pesan_lower or "1" in pesan_lower:
            balasan = "Anda memilih Pengaduan. Menghubungkan ke operator kami... Mohon ditunggu ya 🙏"
            session_mgr.reset(phone_number)
            return send_message(phone_number, balasan)
        elif "konsultasi" in pesan_lower or "2" in pesan_lower:
            if is_offline_mode():
                session_mgr.set_step(phone_number, "rule_based_tanya_data")
                balasan = "Anda memilih Konsultasi (Mode Rule-Based). Data apa yang ingin Anda cari?"
                session_mgr.add_to_history(phone_number, "model", balasan)
                return send_message(phone_number, balasan)
            else:
                session_mgr.set_step(phone_number, "gemini_tanya_data")
                balasan = "Anda memilih Konsultasi. Silakan ketik pertanyaan atau data yang Anda cari."
                session_mgr.add_to_history(phone_number, "model", balasan)
                return send_message(phone_number, balasan)
        else:
            balasan = "Pilihan tidak valid. Silakan pilih layanan:\n1. Pengaduan\n2. Konsultasi"
            return send_message(phone_number, balasan)

    elif step == "gemini_tanya_data":
        session_mgr.add_to_history(phone_number, "user", message_text)
        history = session_mgr.get_history(phone_number)
        info_terkumpul = {
            "nama": session["nama"],
            "instansi": session["instansi"],
            "tujuan": session["tujuan"],
        }
        
        analisis = analisis_pesan(history, message_text, info_terkumpul)
        intent = analisis.get("intent", "lainnya")
        
        session_mgr.update_info(
            phone_number,
            nama=analisis.get("nama"),
            instansi=analisis.get("instansi"),
            tujuan=analisis.get("tujuan"),
        )
        
        if intent == "cari_data":
            tujuan = session["tujuan"] if session["tujuan"] else analisis.get("tujuan", message_text)
            link_bps = cari_link_otomatis(tujuan)
            
            balasan = (
                f"Berikut adalah link website BPS Sulut terkait data yang Anda minta:\n"
                f"🔗 {link_bps}\n\n"
                f"Apakah Anda puas dengan hasil yang dikirimkan?"
            )
            buttons = [
                {"id": "btn_ya", "title": "Ya"},
                {"id": "btn_tidak", "title": "Tidak"}
            ]
            session_mgr.set_step(phone_number, "tanya_kepuasan")
            session_mgr.add_to_history(phone_number, "model", balasan)
            return send_message(phone_number, balasan, buttons)
        else:
            balasan = analisis.get("balasan", "Saya membalas percakapan Anda secara natural.")
            session_mgr.add_to_history(phone_number, "model", balasan)
            session_mgr.reset(phone_number)
            return send_message(phone_number, balasan)

    elif step == "rule_based_tanya_data":
        session_mgr.add_to_history(phone_number, "user", message_text)
        link_bps = cari_link_otomatis(message_text)
        
        # Validasi sederhana: Jika fallback tanpa keyword BPS di pesan
        if link_bps == "https://sulut.bps.go.id" and not any(k in pesan_lower for k in ["bps", "sulut"]):
            balasan = "Error: Data tidak ditemukan."
            session_mgr.reset(phone_number)
            return send_message(phone_number, balasan)
        else:
            balasan = (
                f"Berikut adalah link website BPS Sulut terkait data yang Anda minta:\n"
                f"🔗 {link_bps}\n\n"
                f"Apakah Anda puas dengan hasil yang dikirimkan?"
            )
            buttons = [
                {"id": "btn_ya", "title": "Ya"},
                {"id": "btn_tidak", "title": "Tidak"}
            ]
            session_mgr.set_step(phone_number, "tanya_kepuasan")
            session_mgr.add_to_history(phone_number, "model", balasan)
            return send_message(phone_number, balasan, buttons)

    elif step == "tanya_kepuasan":
        session_mgr.add_to_history(phone_number, "user", message_text)
        if "tidak" in pesan_lower:
            balasan = "Mohon maaf atas ketidaknyamanannya. Menghubungkan Anda dengan operator kami... 🙏"
            session_mgr.reset(phone_number)
            return send_message(phone_number, balasan)
        elif "ya" in pesan_lower:
            session_mgr.set_step(phone_number, "tanya_masih_bertanya")
            balasan = "Apakah masih ada yang ingin ditanyakan?"
            buttons = [
                {"id": "btn_ya", "title": "Ya"},
                {"id": "btn_tidak", "title": "Tidak"}
            ]
            session_mgr.add_to_history(phone_number, "model", balasan)
            return send_message(phone_number, balasan, buttons)
        else:
            balasan = "Silakan jawab dengan Ya atau Tidak. Apakah Anda puas dengan hasil yang dikirimkan?"
            return send_message(phone_number, balasan)

    elif step == "tanya_masih_bertanya":
        session_mgr.add_to_history(phone_number, "user", message_text)
        if "tidak" in pesan_lower:
            balasan = "Terima kasih telah menggunakan layanan chatbot BPS SULUT! 😊"
            session_mgr.reset(phone_number)
            return send_message(phone_number, balasan)
        elif "ya" in pesan_lower:
            if is_offline_mode():
                session_mgr.set_step(phone_number, "rule_based_tanya_data")
                balasan = "Data apa lagi yang ingin Anda cari?"
                session_mgr.add_to_history(phone_number, "model", balasan)
                return send_message(phone_number, balasan)
            else:
                session_mgr.set_step(phone_number, "gemini_tanya_data")
                balasan = "Silakan ketik pertanyaan atau data yang Anda cari selanjutnya."
                session_mgr.add_to_history(phone_number, "model", balasan)
                return send_message(phone_number, balasan)
        else:
            balasan = "Silakan jawab dengan Ya atau Tidak. Apakah masih ada yang ingin ditanyakan?"
            return send_message(phone_number, balasan)

    else:
        session_mgr.reset(phone_number)
        balasan = "Maaf, terjadi kesalahan sesi. Silakan mulai ulang percakapan (ketik 'reset')."
        return send_message(phone_number, balasan)


def send_message(phone_number, text, buttons=None):
    """Kirim pesan ke user (placeholder — nanti diganti integrasi WA)."""
    res = {"to": phone_number, "message": text}
    if buttons:
        res["buttons"] = buttons
    return res


# ============================================================
# SIMULASI CHAT DI TERMINAL
# ============================================================
def _startup_api_check():
    """Cek koneksi API saat startup. Beri pilihan ke user jika gagal."""
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
            print("\ Mencoba ulang...")
            berhasil, error = test_api_connection()
            if berhasil:
                print(" API terhubung! Menggunakan mode AI.\n")
                set_offline_mode(False) 
                return
            else:
                print(f" Masih gagal: {error[:100]}...\n")
        elif pilihan == "2":
            set_offline_mode(True)
            print(" Mode offline aktif. Chatbot tetap berjalan tanpa AI.\n")
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

        if pesan_masuk.lower() == "keluar":
            print("Simulasi dihentikan. Terima kasih! 👋")
            break

        if pesan_masuk.lower() == "reset":
            session_mgr.reset(nomor_hp)
            print("Session di-reset. Mulai percakapan baru.\n")
            continue

        if pesan_masuk.lower() == "online":
            print("\n Mencoba koneksi ke API...")
            berhasil, error = test_api_connection()
            if berhasil:
                set_offline_mode(False)
                print("API terhubung! Beralih ke mode AI.\n")
            else:
                print(f" API masih tidak tersedia: {error[:80]}...")
                print("   Tetap menggunakan mode offline.\n")
            continue

        if pesan_masuk.lower() == "info":
            session = session_mgr.get_or_create(nomor_hp)
            mode = "OFFLINE" if is_offline_mode() else "AI"
            print(f"Session Info:")
            print(f"   Mode    : {mode}")
            print(f"   Nama    : {session['nama'] or '-'}")
            print(f"   Instansi: {session['instansi'] or '-'}")
            print(f"   Tujuan  : {session['tujuan'] or '-'}")
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