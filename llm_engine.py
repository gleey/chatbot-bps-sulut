"""
LLM engine — Gemini API wrapper + offline fallback.
Mendukung rotasi API Key dan Model secara otomatis saat terjadi 429/404.
"""
import json
import logging
import time
import threading
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from config import (
    GEMINI_API_KEYS, GEMINI_MODELS, MODEL_NAME,
    SYSTEM_PROMPT, ROTATOR_COOLDOWN, GEMINI_TIMEOUT_SECONDS, GEMINI_MAX_ATTEMPTS,
)

logger = logging.getLogger(__name__)

_offline_mode = False
_offline_since = 0


def set_offline_mode(value):
    global _offline_mode, _offline_since
    _offline_mode = value
    _offline_since = time.monotonic()


def is_offline_mode():
    if _offline_mode and GEMINI_API_KEYS and time.monotonic() - _offline_since >= ROTATOR_COOLDOWN:
        set_offline_mode(False)
    return _offline_mode or not GEMINI_API_KEYS


# ============================================================
# Key & Model Rotator
# ============================================================
class _KeyRotator:
    """Ordered API key failover dengan cooldown otomatis."""

    def __init__(self, keys, cooldown=300):
        self.keys = keys if keys else []
        self.failed = {}  # index -> timestamp gagal
        self.cooldown = cooldown
        self._lock = threading.RLock()

    def _reset_expired(self):
        now = time.time()
        expired = [i for i, ts in self.failed.items() if now - ts > self.cooldown]
        for i in expired:
            del self.failed[i]

    def get_available_keys(self):
        """Return list (index, key) yang belum gagal atau sudah melewati cooldown."""
        with self._lock:
            self._reset_expired()
            return [(i, k) for i, k in enumerate(self.keys) if i not in self.failed]

    def mark_failed(self, index):
        with self._lock:
            self.failed[index] = time.time()
            logger.warning("Rotator: key #%d ditandai gagal (%d/%d aktif)",
                           index + 1, len(self.keys) - len(self.failed), len(self.keys))

    def has_available(self):
        return bool(self.get_available_keys())


class _ModelRotator:
    """Fallback model rotator — pindah model saat 404 atau semua key habis."""

    def __init__(self, models, cooldown=300):
        self.models = models if models else []
        self.failed = {}  # index -> timestamp gagal
        self.cooldown = cooldown
        self._lock = threading.RLock()

    def _reset_expired(self):
        now = time.time()
        expired = [i for i, ts in self.failed.items() if now - ts > self.cooldown]
        for i in expired:
            del self.failed[i]

    def get_available_models(self):
        with self._lock:
            self._reset_expired()
            return [(i, m) for i, m in enumerate(self.models) if i not in self.failed]

    def mark_failed(self, index):
        with self._lock:
            self.failed[index] = time.time()
            logger.warning("Rotator: model '%s' ditandai gagal", self.models[index])

    def has_available(self):
        return bool(self.get_available_models())


# Singleton instances
_key_rotator = _KeyRotator(GEMINI_API_KEYS, ROTATOR_COOLDOWN)
_model_rotator = _ModelRotator(GEMINI_MODELS, ROTATOR_COOLDOWN)


def get_rotator_status():
    """Status rotator untuk debugging/monitoring."""
    avail_keys = _key_rotator.get_available_keys()
    avail_models = _model_rotator.get_available_models()
    return {
        "keys_total": len(_key_rotator.keys),
        "keys_available": len(avail_keys),
        "models_total": len(_model_rotator.models),
        "models_available": len(avail_models),
        "active_models": [m for _, m in avail_models],
    }


# ============================================================
# Gemini API call dengan rotasi otomatis
# ============================================================
def _call_gemini(contents, system_instruction, temperature=0.7):
    """Coba semua kombinasi (model, key) sampai sukses atau habis.

    Returns: response object dari Gemini
    Raises: RuntimeError jika semua kombinasi gagal
    """
    last_error = "Tidak ada API key atau model yang tersedia."
    deadline = time.monotonic() + GEMINI_TIMEOUT_SECONDS
    attempts = 0
    for model_idx, model_name in _model_rotator.get_available_models():
        for key_idx, api_key in _key_rotator.get_available_keys():
            remaining = deadline - time.monotonic()
            if attempts >= GEMINI_MAX_ATTEMPTS or remaining <= 0:
                raise RuntimeError("Batas percobaan atau waktu layanan Gemini tercapai")
            attempts += 1
            client = None
            try:
                client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
                    timeout=max(1, int(remaining * 1000)),
                    retry_options=types.HttpRetryOptions(attempts=1)))
                response = client.models.generate_content(
                    model=model_name, contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature, response_mime_type="application/json", max_output_tokens=1024))
                # Berhasil — log jika bukan model/key utama
                if model_idx > 0 or key_idx > 0:
                    logger.info("Rotator: berhasil dengan model='%s', key #%d", model_name, key_idx + 1)
                return response
            except genai_errors.APIError as error:
                code = error.code
                last_error = f"Gemini HTTP {code}"
                if code in (404, 503):
                    _model_rotator.mark_failed(model_idx)
                    break  # pindah model, key di-reset
                if code in (429, 401, 403):
                    _key_rotator.mark_failed(key_idx)
                    continue  # coba key berikutnya, model sama
                # Error lain (400 bad request, 403 forbidden, dll)
                raise RuntimeError(last_error) from None
            except Exception as error:
                logger.warning("Koneksi Gemini gagal (%s)", type(error).__name__)
                raise RuntimeError("Koneksi Gemini tidak tersedia") from None
            finally:
                if client is not None:
                    try:
                        client.close()
                    except Exception as error:
                        logger.warning("Penutupan koneksi Gemini gagal (%s)", type(error).__name__)
        # Semua key habis untuk model ini — tandai model gagal juga
        if not _key_rotator.has_available():
            # Reset key untuk model berikutnya
            # Quota cooldown must survive subsequent requests; do not clear failed keys here.
            break
    raise RuntimeError(last_error)


# ============================================================
# Public API
# ============================================================
def test_api_connection():
    """Test koneksi ke Gemini API dengan rotasi.
    Returns: (berhasil: bool, pesan_error: str)
    """
    if not GEMINI_API_KEYS:
        return False, "GEMINI_API_KEYS belum di-set."

    try:
        _call_gemini(
            contents="test",
            system_instruction="Balas dengan satu kata: OK",
            temperature=0,
        )
        return True, ""
    except RuntimeError as e:
        return False, str(e)


def analisis_pesan(history, info_terkumpul=None):
    """Kirim pesan ke Gemini, dapatkan analisis structured + ringkasan jawaban."""
    # Ambil pesan user terakhir untuk fallback
    pesan_baru = ""
    for msg in reversed(history):
        if msg["role"] == "user":
            pesan_baru = msg["parts"][0]["text"]
            break

    if is_offline_mode():
        return _fallback_offline(pesan_baru)

    # Sertakan info yang sudah terkumpul agar Gemini punya konteks
    context_prefix = ""
    if info_terkumpul:
        collected = []
        if info_terkumpul.get("tujuan"):
            collected.append(f"tujuan={info_terkumpul['tujuan']}")
        if collected:
            context_prefix = f"[INFO TERKUMPUL: {', '.join(collected)}]\n"

    contents = []
    history = [msg for msg in history if msg["role"] in {"user", "model"}][-30:]
    for i, msg in enumerate(history):
        text = msg["parts"][0]["text"]
        if i == len(history) - 1 and msg["role"] == "user":
            text = context_prefix + text

        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=text)],
            )
        )

    try:
        response = _call_gemini(contents, SYSTEM_PROMPT, temperature=0.7)
    except RuntimeError as e:
        logger.warning("Semua key & model habis: %s. Beralih ke mode offline.", e)
        set_offline_mode(True)
        return _fallback_offline(pesan_baru)

    try:
        response_text = (response.text or "").strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        hasil = json.loads(response_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _fallback_offline(pesan_baru)
    if not isinstance(hasil, dict) or any(not isinstance(value, str) for value in hasil.values()):
        return _fallback_offline(pesan_baru)
    if hasil.get("intent") not in {"greeting", "cari_data", "puas", "tidak_puas", "lainnya"}:
        return _fallback_offline(pesan_baru)

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


# ============================================================
# Fallback offline
# ============================================================
def _fallback_offline(pesan):
    """Fallback keyword matching saat API tidak tersedia."""
    pesan_lower = pesan.lower()
    kata_kata = set(pesan_lower.split())

    intent = "lainnya"
    tujuan = ""
    balasan = ""

    kata_sapa = {"halo", "hai", "hi", "selamat", "permisi", "assalamualaikum"}

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
