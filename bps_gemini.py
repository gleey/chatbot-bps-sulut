import json
import os
import difflib
# pip install google-genai
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# 1. KONFIGURASI DAN DATA MASTER
# ---------------------------------------------------------------------------

# Ganti dengan API Key Anda atau pastikan environment variable GEMINI_API_KEY sudah diset
API_KEY = os.environ.get("GEMINI_API_KEY") 

BPS_CATEGORIES = {
    "kependudukan dan migrasi": "https://sulut.bps.go.id/id/statistics-table?subject=519",
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
    "perdagangan internasional dan neraca pembayaran": "https://sulut.bps.go.id/id/statistics-table?subject=535",
    "harga-harga": "https://sulut.bps.go.id/id/statistics-table?subject=536",
    "biaya tenaga kerja": "https://sulut.bps.go.id/id/statistics-table?subject=537",
    "ilmu pengetahuan, teknologi dan inovasi": "https://sulut.bps.go.id/id/statistics-table?subject=538",
    "pertanian kehutanan perikanan": "https://sulut.bps.go.id/id/statistics-table?subject=557",
    "energi": "https://sulut.bps.go.id/id/statistics-table?subject=558",
    "pertambangan, manufaktur, konstruksi": "https://sulut.bps.go.id/id/statistics-table?subject=559",
    "transportasi": "https://sulut.bps.go.id/id/statistics-table?subject=560",
    "pariwisata": "https://sulut.bps.go.id/id/statistics-table?subject=561",
    "perbankan, asuransi dan finansial": "https://sulut.bps.go.id/id/statistics-table?subject=562",
    "lingkungan":  "https://sulut.bps.go.id/id/statistics-table?subject=539",
    "statistik regional dan statistik area kecil": "https://sulut.bps.go.id/id/statistics-table?subject=540",
    "statistik dan indikator multi-domain": "https://sulut.bps.go.id/id/statistics-table?subject=541",
    "buku tahunan dan ringkasan sejenis": "https://sulut.bps.go.id/id/statistics-table?subject=542",
    "kondisi tempat tinggal, kemiskinan, dan permasalahan sosial lintas sektor": "https://sulut.bps.go.id/id/statistics-table?subject=563",
    "gender dan kelompok populasi khusus": "https://sulut.bps.go.id/id/statistics-table?subject=564",
    "masyarakat informasi": "https://sulut.bps.go.id/id/statistics-table?subject=565",
    "globalisasi": "https://sulut.bps.go.id/id/statistics-table?subject=566",
    "indikator millenium development goals (mdgs)": "https://sulut.bps.go.id/id/statistics-table?subject=567",
    "perkembangan berkelanjutan": "https://sulut.bps.go.id/id/statistics-table?subject=568",
    "kewiraswastaan": "https://sulut.bps.go.id/id/statistics-table?subject=569",
}

user_sessions = {}

# ---------------------------------------------------------------------------
# 2. SETUP GEMINI API
# ---------------------------------------------------------------------------

client = genai.Client(api_key=API_KEY) if API_KEY else None

def get_system_instruction():
    """
    Ini adalah inti dari bagaimana kita mengatur perilaku Gemini.
    Kita berikan aturan ketat (System Instructions) agar dia tidak halu.
    """
    daftar_kategori = "\n- ".join(BPS_CATEGORIES.keys())
    
    instruction = f"""
    Kamu adalah asisten virtual resmi untuk Badan Pusat Statistik (BPS) Provinsi Sulawesi Utara.
    Tugas utamamu HANYA DUA:
    1. Menyapa pengguna dengan ramah, menanyakan nama, dan asal instansi mereka.
    2. Menanyakan data apa yang mereka cari, lalu mengkategorikannya ke dalam salah satu kategori resmi BPS.
    
    ATURAN KETAT (PENTING!):
    - Kamu TIDAK BOLEH menjawab pertanyaan di luar konteks statistik, data, atau layanan BPS.
    - Jika ada yang bertanya di luar itu (misal: resep masakan, politik, cuaca, dll), tolak dengan sopan dan katakan bahwa kamu hanya melayani informasi BPS Sulut.
    - Kamu TIDAK BOLEH memberikan angka statistik atau data spesifik secara langsung (misal: "jumlah penduduk Manado adalah 400.000"). Ini untuk menghindari halusinasi data.
    - Kamu hanya bertugas mengekstrak informasi ke dalam format JSON.
    
    DAFTAR KATEGORI RESMI BPS:
    - {daftar_kategori}
    
    Tugasmu adalah membaca pesan dari pengguna, dan mengekstrak informasi berikut:
    - intent: "tanya_data" (jika membahas data/BPS/statistik/penelitian/kategori di atas), "umum" (jika sapaan biasa), atau "luar_konteks" (jika menanyakan hal di luar BPS).
    - nama: Nama pengguna jika disebutkan (jika tidak ada, kosongkan "").
    - instansi: Asal instansi/universitas/perusahaan jika disebutkan (jika tidak ada, kosongkan "").
    - kategori_ditemukan: Jika pengguna menyebutkan topik data, pilih SATU nama kategori yang PALING COCOK dari 'DAFTAR KATEGORI RESMI BPS' di atas. Jika tidak ada yang cocok sama sekali, kosongkan "".
    - balasan_ramah: Kalimat balasan sapaan atau tolakan yang sopan (gunakan ini jika intent 'umum' atau 'luar_konteks').
    - kepuasan: "puas" (jika bilang ya/terima kasih), "tidak_puas" (jika bilang tidak/kurang/salah/operator), atau "netral" (jika selain itu).
    
    KEMBALIKAN HANYA FORMAT JSON MURNI (tanpa markdown).
    """
    return instruction

# Schema JSON untuk memaksa Gemini merespons dalam format terstruktur (Structured Output)
response_schema = {
    "type": "OBJECT",
    "properties": {
        "intent": {"type": "STRING", "description": "umum, tanya_data, atau luar_konteks"},
        "nama": {"type": "STRING"},
        "instansi": {"type": "STRING"},
        "kategori_ditemukan": {"type": "STRING"},
        "balasan_ramah": {"type": "STRING"},
        "kepuasan": {"type": "STRING", "description": "puas, tidak_puas, atau netral"}
    },
    "required": ["intent", "nama", "instansi", "kategori_ditemukan", "balasan_ramah", "kepuasan"]
}

def proses_dengan_gemini(teks_pengguna):
    """Fungsi untuk mengirim teks ke Gemini dan mendapatkan balasan JSON."""
    if not client:
        # Fallback jika API Key belum dipasang saat simulasi
        print("[SISTEM] API Key Gemini tidak ditemukan. Menggunakan fallback deteksi manual.")
        return fallback_proses_llm(teks_pengguna)
        
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=teks_pengguna,
            config=types.GenerateContentConfig(
                system_instruction=get_system_instruction(),
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.0 # Temperature 0 agar jawabannya pasti dan tidak terlalu kreatif
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERROR GEMINI]: {e}")
        return fallback_proses_llm(teks_pengguna)

def fallback_proses_llm(teks_pengguna):
    teks_kecil = teks_pengguna.lower()
    
    kata_kunci_dasar = ["data", "statistik", "bps", "penelitian", "jumlah", "angka", "tabel", "informasi", "tanya"]
    intent = "umum"
    
    if any(kata in teks_kecil for kata in kata_kunci_dasar):
        intent = "tanya_data"
        
    tujuan_ekstrak = ""
    daftar_kategori = list(BPS_CATEGORIES.keys())
    
    for kategori in daftar_kategori:
        if kategori.lower() in teks_kecil:
            tujuan_ekstrak = kategori
            intent = "tanya_data"
            break
            
    if not tujuan_ekstrak:
        kata_pengguna = teks_kecil.split()
        for kategori in daftar_kategori:
            kata_kunci_kategori = kategori.lower().split()
            for kata_user in kata_pengguna:
                if len(kata_user) > 3:
                    kecocokan = difflib.get_close_matches(kata_user, kata_kunci_kategori, n=1, cutoff=0.75)
                    if kecocokan:
                        tujuan_ekstrak = kategori
                        intent = "tanya_data"
                        break
            if tujuan_ekstrak:
                break
                
    status_kepuasan = "netral"
    if any(kata in teks_kecil for kata in ["ya", "terimakasih", "sudah", "puas", "makasih", "ok"]):
        status_kepuasan = "puas"
    elif any(kata in teks_kecil for kata in ["tidak", "belum", "kurang", "salah", "operator", "bukan"]):
        status_kepuasan = "tidak_puas"
        
    return {
        "intent": intent,
        "nama": "Keefa Lasut" if "keefa" in teks_kecil else "",
        "instansi": "Universitas Sam Ratulangi" if "ratulangi" in teks_kecil or "unsrat" in teks_kecil else "",
        "kategori_ditemukan": tujuan_ekstrak,
        "balasan_ramah": "Halo! Saya adalah asisten virtual BPS Sulut. Ada yang bisa saya bantu?",
        "kepuasan": status_kepuasan
    }

# ---------------------------------------------------------------------------
# 3. ROUTER & CONTROLLER CHATBOT (Bagian Rule-Based)
# ---------------------------------------------------------------------------

def handle_incoming_message(phone_number, message_text):
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {"nama": "", "instansi": "", "kategori": "", "step": "awal"}
        
    session = user_sessions[phone_number]
    
    if session["step"] == "operator":
        return None # Chatbot diam, manusia ambil alih
        
    # --- PROSES KE GEMINI ---
    analisis = proses_dengan_gemini(message_text)
    
    # Update data sesi dari hasil ekstraksi Gemini
    if analisis["nama"]: session["nama"] = analisis["nama"]
    if analisis["instansi"]: session["instansi"] = analisis["instansi"]
    if analisis["kategori_ditemukan"]: session["kategori"] = analisis["kategori_ditemukan"]
    
    # 1. Cek apakah ini di luar konteks
    if analisis["intent"] == "luar_konteks":
        return send_message(phone_number, analisis["balasan_ramah"])
        
    # 2. Cek apakah sedang dalam tahap evaluasi kepuasan
    if session["step"] == "tanya_kepuasan":
        if analisis["kepuasan"] == "puas":
            del user_sessions[phone_number]
            return send_message(phone_number, "Terima kasih! Senang bisa membantu. Semoga harinya menyenangkan!")
        elif analisis["kepuasan"] == "tidak_puas":
            session["step"] = "operator"
            return send_message(phone_number, "Mohon maaf jika datanya belum sesuai. Mohon ditunggu, Anda akan segera dihubungkan dengan tim kami.")
        else:
            return send_message(phone_number, "Mohon informasikan, apakah link data yang diberikan sebelumnya sudah sesuai? (Ketik YA atau TIDAK)")
            
    # 3. Cek Intent Utama: Jika minta data, jalankan aturan BPS
    if analisis["intent"] == "tanya_data" or session["kategori"]:
        if not session["kategori"]:
            return send_message(phone_number, "Baik, terkait hal tersebut, bisa sebutkan lebih spesifik data atau topik apa yang Anda cari?")
            
        link_bps = BPS_CATEGORIES.get(session["kategori"].lower(), "https://sulut.bps.go.id")
        
        teks_balasan = f"Untuk data statistik terkait '{session['kategori']}', Anda dapat merujuk ke tabel resmi berikut:\n{link_bps}\n\nApakah informasi ini sudah membantu? (Ketik YA atau TIDAK)"
        
        if session["nama"]:
            teks_balasan = f"Baik Kak {session['nama']}, untuk tabel data statistik '{session['kategori']}' silakan cek di link berikut:\n{link_bps}\n\nApakah informasi ini sudah membantu? (Ketik YA atau TIDAK)"
            
        session["step"] = "tanya_kepuasan"
        return send_message(phone_number, teks_balasan)

    # 4. Fallback jika intent umum (sekadar sapaan)
    else:
        # Jika belum ada nama, Gemini biasanya disuruh membalas dengan menanyakan nama (lewat balasan_ramah)
        return send_message(phone_number, analisis["balasan_ramah"])

def send_message(phone_number, text):
    return {"to": phone_number, "message": text}

# ---------------------------------------------------------------------------
# 4. SIMULATOR TERMINAL
# ---------------------------------------------------------------------------

def simulasi_chat():
    nomor_hp = "08123456789"
    print("--- Memulai Simulasi Chatbot BPS (Powered by Gemini) ---")
    if not API_KEY:
        print("[PERINGATAN] GEMINI_API_KEY tidak ditemukan. Menggunakan fallback deteksi manual.")
    print("Ketik 'keluar' untuk menghentikan simulasi.\n")

    while True:
        pesan_masuk = input("Anda: ")
        
        if pesan_masuk.lower() == 'keluar':
            print("Simulasi dihentikan.")
            break
            
        balasan = handle_incoming_message(nomor_hp, pesan_masuk)
        
        if balasan is None:
            print("Chatbot: [Sistem membisukan bot, pesan diteruskan ke Operator Manusia]")
        else:
            print(f"Chatbot: {balasan['message']}\n")

if __name__ == "__main__":
    simulasi_chat()