import json
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from config import GEMINI_API_KEY, MODEL_NAME, SYSTEM_PROMPT

_offline_mode = False


def set_offline_mode(value):
    """Set mode offline (True = skip API, pakai fallback)."""
    global _offline_mode
    _offline_mode = value


def is_offline_mode():
    """Cek apakah sedang dalam mode offline."""
    return _offline_mode


def _get_client():
    """Inisialisasi Gemini client."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY belum di-set! "
            "Jalankan: export GEMINI_API_KEY='your-api-key' "
            "atau set di file config.py"
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def test_api_connection():
    """Test koneksi ke Gemini API.
    
    Returns:
        (bool, str): (berhasil, pesan_error)
    """
    if not GEMINI_API_KEY:
        return False, "GEMINI_API_KEY belum di-set."

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents="test",
            config=types.GenerateContentConfig(
                system_instruction="Balas dengan satu kata: OK",
                temperature=0,
            ),
        )
        return True, ""
    except genai_errors.ClientError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def analisis_pesan(history, pesan_baru, info_terkumpul=None):
    """Kirim pesan ke Gemini dan dapatkan analisis structured.
    
    Jika mode offline aktif, langsung gunakan fallback tanpa coba API.
    
    Args:
        history: List conversation history (format Gemini Content)
        pesan_baru: Pesan terbaru dari user
        info_terkumpul: Dict info yang sudah terkumpul (nama, instansi, tujuan)
        
    Returns:
        Dict dengan keys: intent, nama, instansi, tujuan, balasan
    """

    if _offline_mode:
        return _fallback_offline(pesan_baru)

    client = _get_client()

    context_prefix = ""
    if info_terkumpul:
        collected = []
        if info_terkumpul.get("nama"):
            collected.append(f"nama={info_terkumpul['nama']}")
        if info_terkumpul.get("instansi"):
            collected.append(f"instansi={info_terkumpul['instansi']}")
        if info_terkumpul.get("tujuan"):
            collected.append(f"tujuan={info_terkumpul['tujuan']}")
        if collected:
            context_prefix = f"[INFO TERKUMPUL: {', '.join(collected)}]\n"

    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=msg["parts"][0]["text"])],
            )
        )

    pesan_lengkap = context_prefix + pesan_baru
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=pesan_lengkap)],
        )
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
            ),
        )

    except genai_errors.ClientError as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            print("Quota API habis. Menggunakan mode offline untuk pesan ini.")
        else:
            print(f"Error API: {error_msg}")
        return _fallback_offline(pesan_baru)

    except Exception as e:
        print(f"Error tidak terduga: {e}")
        return _fallback_offline(pesan_baru)

    try:
        response_text = response.text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        hasil = json.loads(response_text)
    except json.JSONDecodeError:
        hasil = {
            "intent": "lainnya",
            "nama": "",
            "instansi": "",
            "tujuan": "",
            "balasan": response.text.strip(),
        }

    default_fields = {
        "intent": "lainnya",
        "nama": "",
        "instansi": "",
        "tujuan": "",
        "balasan": "Maaf, saya tidak mengerti. Bisa diulangi?",
    }
    for key, default_val in default_fields.items():
        if key not in hasil:
            hasil[key] = default_val

    return hasil


def _fallback_offline(pesan):
    """Fallback sederhana saat API tidak bisa diakses.
    
    Menggunakan keyword matching dasar (mirip rule-based lama)
    supaya chatbot tetap bisa berfungsi minimal.
    """
    pesan_lower = pesan.lower()
    kata_kata = set(pesan_lower.split())

    intent = "lainnya"
    nama = ""
    instansi = ""
    tujuan = ""
    balasan = ""

    kata_sapa = {"halo", "hai", "hi", "selamat", "permisi", "assalamualaikum"}
    introduction = {"nama", "saya", "berasal", "dari", "asal", "instansi"}

    if kata_kata & {"data", "statistik", "cari", "butuh", "ingin", "mau", "perlu"}:
        intent = "cari_data"
        tujuan = pesan_lower
        for stop in ["saya", "mau", "ingin", "cari", "butuh", "data", "tentang",
                      "mengenai", "soal", "terkait", "perlu", "tolong", "bisa"]:
            tujuan = tujuan.replace(stop, "")
        tujuan = " ".join(tujuan.split())
        balasan = f"Baik, saya carikan data terkait *{tujuan}* untuk Anda."

    elif (kata_kata & kata_sapa) and (kata_kata & introduction):
        intent = "perkenalan"
        balasan = (
            "Halo! Saya asisten virtual BPS Sulawesi Utara. 👋\n"
            "Ada data atau informasi apa yang sedang Anda butuhkan?\n\n"
        )

    elif kata_kata & kata_sapa:
        intent = "greeting"
        balasan = (
            "Halo! Selamat datang di layanan BPS Sulawesi Utara. 👋\n"
            "Perkenalkan, saya asisten virtual BPS Sulut.\n"
            "Boleh saya tahu nama dan asal instansi Bapak/Ibu?"
        )

    elif kata_kata & {"ya", "makasih", "puas", "sudah", "oke", "thanks", "thx"} or "terima kasih" in pesan_lower:
        intent = "puas"
        balasan = "Terima kasih! Senang bisa membantu. 😊"

    elif kata_kata & {"tidak", "belum", "kurang", "salah", "operator", "bukan"}:
        intent = "tidak_puas"
        balasan = (
            "Mohon maaf atas ketidaknyamanannya. "
            "Saya akan menghubungkan Anda dengan operator kami. "
            "Mohon ditunggu ya 🙏"
        )

    else:
        balasan = (
            "Halo! Saya asisten virtual BPS Sulawesi Utara. 👋\n"
            "Ada data atau informasi apa yang sedang Anda butuhkan?\n\n"
        )

    return {
        "intent": intent,
        "nama": nama,
        "instansi": instansi,
        "tujuan": tujuan,
        "balasan": balasan,
    }

