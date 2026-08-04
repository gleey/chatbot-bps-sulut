"""
LLM engine — Gemini API wrapper + offline fallback.
Sekarang Gemini memberikan ringkasan jawaban (bukan hanya intent parsing).
"""
import json
import logging
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from config import GEMINI_API_KEY, MODEL_NAME, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_offline_mode = False


def set_offline_mode(value):
    global _offline_mode
    _offline_mode = value


def is_offline_mode():
    return _offline_mode


def _get_client():
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY belum di-set! "
            "Jalankan: export GEMINI_API_KEY='your-api-key' "
            "atau set di file .env"
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def test_api_connection():
    """Test koneksi ke Gemini API.
    Returns: (berhasil: bool, pesan_error: str)
    """
    if not GEMINI_API_KEY:
        return False, "GEMINI_API_KEY belum di-set."
    try:
        client = _get_client()
        client.models.generate_content(
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


def analisis_pesan(history, info_terkumpul=None):
    """Kirim pesan ke Gemini, dapatkan analisis structured + ringkasan jawaban.

    Args:
        history: List conversation history (sudah mengandung pesan user terbaru).
        info_terkumpul: Info dari sesi.
    Returns:
        Dict: intent, nama, instansi, tujuan, kategori_cocok, balasan
    """
    # Ambil pesan user terakhir untuk fallback
    pesan_baru = ""
    for msg in reversed(history):
        if msg["role"] == "user":
            pesan_baru = msg["parts"][0]["text"]
            break

    if _offline_mode:
        return _fallback_offline(pesan_baru)

    client = _get_client()

    # Sertakan info yang sudah terkumpul agar Gemini punya konteks
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
    for i, msg in enumerate(history):
        text = msg["parts"][0]["text"]
        # Sisipkan context di pesan user TERAKHIR (bukan tambah pesan baru)
        if i == len(history) - 1 and msg["role"] == "user":
            text = context_prefix + text
            
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=text)],
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
            logger.warning("Quota API habis. Beralih ke mode offline.")
            set_offline_mode(True)
        else:
            logger.error("Error API: %s", error_msg)
        return _fallback_offline(pesan_baru)
    except Exception as e:
        logger.error("Error tidak terduga: %s", e)
        return _fallback_offline(pesan_baru)

    try:
        # Handle None response.text
        response_text = (response.text or "").strip()
        
        # Strip markdown code fence jika ada
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
            "tujuan": "",
            "kategori_cocok": "",
            "balasan": (response.text or "").strip(),
        }

    # Pastikan semua field ada
    defaults = {
        "intent": "lainnya",
        "tujuan": "",
        "kategori_cocok": "",
        "balasan": "Maaf, saya tidak mengerti. Bisa diulangi?",
    }
    for key, default_val in defaults.items():
        if key not in hasil:
            hasil[key] = default_val

    return hasil


def _fallback_offline(pesan):
    """Fallback keyword matching saat API tidak tersedia."""
    pesan_lower = pesan.lower()
    kata_kata = set(pesan_lower.split())

    intent = "lainnya"
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

    elif kata_kata & kata_sapa:
        intent = "greeting"
        balasan = (
            "Halo! Selamat datang di layanan BPS Sulawesi Utara.\n"
            "Silakan pilih layanan yang Anda butuhkan:\n1. Pengaduan\n2. Konsultasi"
        )

    elif pesan_lower.strip() in ("ya", "makasih", "puas", "sudah", "oke", "thanks", "thx", "terima kasih"):
        # Match exact/standalone untuk menghindari false positive
        intent = "puas"
        balasan = "Terima kasih! Senang bisa membantu."

    elif pesan_lower.strip() in ("tidak", "belum", "kurang", "salah", "operator", "bukan"):
        intent = "tidak_puas"
        balasan = (
            "Mohon maaf atas ketidaknyamanannya. "
            "Saya akan menghubungkan Anda dengan operator kami. "
            "Mohon ditunggu ya."
        )

    else:
        balasan = (
            "Halo! Saya asisten virtual BPS Sulawesi Utara.\n"
            "Ada data atau informasi apa yang sedang Anda butuhkan?"
        )

    return {
        "intent": intent,
        "tujuan": tujuan,
        "kategori_cocok": "",
        "balasan": balasan,
    }
