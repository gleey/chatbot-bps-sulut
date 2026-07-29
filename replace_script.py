import sys

target_file = '/home/lerch/Documents/project/magang/chatbot/main.py'

with open(target_file, 'r') as f:
    content = f.read()

start_marker = "def handle_incoming_message(phone_number, message_text):"
end_marker = "def send_message(phone_number, text):"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found!")
    sys.exit(1)

new_function = '''def handle_incoming_message(phone_number, message_text):
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
            "Halo! Selamat datang di layanan BPS Sulawesi Utara.\\n"
            "Silakan sebutkan nama dan asal instansi Anda."
        )
        session_mgr.add_to_history(phone_number, "model", balasan)
        return send_message(phone_number, balasan)

    elif step == "tanya_nama_instansi":
        # Simpan input user ke history sebagai penanda perkenalan
        session_mgr.update_info(phone_number, nama=message_text)
        session_mgr.add_to_history(phone_number, "user", message_text)
        
        session_mgr.set_step(phone_number, "pilih_layanan")
        balasan = "Terima kasih! Silakan pilih layanan (ketik angkanya atau namanya):\\n1. Pengaduan\\n2. Konsultasi"
        session_mgr.add_to_history(phone_number, "model", balasan)
        return send_message(phone_number, balasan)

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
            balasan = "Pilihan tidak valid. Silakan pilih layanan:\\n1. Pengaduan\\n2. Konsultasi"
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
                f"Berikut adalah link website BPS Sulut terkait data yang Anda minta:\\n"
                f"🔗 {link_bps}\\n\\n"
                f"Apakah Anda puas dengan hasil yang dikirimkan? (Ya/Tidak)"
            )
            session_mgr.set_step(phone_number, "tanya_kepuasan")
            session_mgr.add_to_history(phone_number, "model", balasan)
            return send_message(phone_number, balasan)
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
                f"Berikut adalah link website BPS Sulut terkait data yang Anda minta:\\n"
                f"🔗 {link_bps}\\n\\n"
                f"Apakah Anda puas dengan hasil yang dikirimkan? (Ya/Tidak)"
            )
            session_mgr.set_step(phone_number, "tanya_kepuasan")
            session_mgr.add_to_history(phone_number, "model", balasan)
            return send_message(phone_number, balasan)

    elif step == "tanya_kepuasan":
        session_mgr.add_to_history(phone_number, "user", message_text)
        if "tidak" in pesan_lower:
            balasan = "Mohon maaf atas ketidaknyamanannya. Menghubungkan Anda dengan operator kami... 🙏"
            session_mgr.reset(phone_number)
            return send_message(phone_number, balasan)
        elif "ya" in pesan_lower:
            session_mgr.set_step(phone_number, "tanya_masih_bertanya")
            balasan = "Apakah masih ada yang ingin ditanyakan? (Ya/Tidak)"
            session_mgr.add_to_history(phone_number, "model", balasan)
            return send_message(phone_number, balasan)
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


'''

new_content = content[:start_idx] + new_function + content[end_idx:]

with open(target_file, 'w') as f:
    f.write(new_content)

print("Replacement successful.")
