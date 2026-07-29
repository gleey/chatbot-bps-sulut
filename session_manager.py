import time

SESSION_TIMEOUT = 1800 # reset session in 30 minutes

class SessionManager:
    """Mengelola session percakapan per user (berdasarkan nomor telepon)."""

    def __init__(self):
        self.sessions = {}

    def is_expired(self, phone_number):
        session = self.get_or_create(phone_number)

        return (
            time.time() - session["last_active"]
            > SESSION_TIMEOUT
        )

    def touch(self, phone_number):
        session = self.get_or_create(phone_number)
        session["last_active"] = time.time()

    def active_bot(self, phone_number):
        session = self.get_or_create(phone_number)
        session["step"] = "awal"

        return session

    def get_or_create(self, phone_number):
        """Ambil session yang ada atau buat baru."""
        if phone_number not in self.sessions:
            self.sessions[phone_number] = {
                "nama": "",
                "instansi": "",
                "tujuan": "",
                "step": "awal",
                "history": [],  # conversation history untuk Gemini
                "last_active": time.time(),
            }
        return self.sessions[phone_number]

    def update_info(self, phone_number, nama=None, instansi=None, tujuan=None):
        """Update informasi user di session (hanya jika ada nilai baru)."""
        session = self.get_or_create(phone_number)
        if nama:
            session["nama"] = nama
        if instansi:
            session["instansi"] = instansi
        if tujuan:
            session["tujuan"] = tujuan

    def set_step(self, phone_number, step):
        """Update step/state dari session."""
        session = self.get_or_create(phone_number)
        session["step"] = step

    def add_to_history(self, phone_number, role, text):
        """Tambahkan pesan ke conversation history.
        
        Args:
            phone_number: Nomor telepon user
            role: 'user' atau 'model'
            text: Isi pesan
        """
        session = self.get_or_create(phone_number)
        session["history"].append({
            "role": role,
            "parts": [{"text": text}],
        })

    def get_history(self, phone_number):
        """Ambil conversation history untuk dikirim ke Gemini."""
        session = self.get_or_create(phone_number)
        return session["history"]

    def reset(self, phone_number):
        """Reset session user (setelah selesai atau mau mulai ulang)."""
        if phone_number in self.sessions:
            del self.sessions[phone_number]

    def get_info_summary(self, phone_number):
        """Dapatkan ringkasan info user yang sudah terkumpul."""
        session = self.get_or_create(phone_number)
        parts = []
        if session["nama"]:
            parts.append(f"Nama: {session['nama']}")
        if session["instansi"]:
            parts.append(f"Instansi: {session['instansi']}")
        if session["tujuan"]:
            parts.append(f"Tujuan: {session['tujuan']}")
        return " | ".join(parts) if parts else "Belum ada info"
