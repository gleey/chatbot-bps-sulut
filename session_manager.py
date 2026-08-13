"""
Session manager berbasis SQLite.
ponytail: multi-worker → ganti ke Redis + distributed lock.
"""
import os
import time
from db import get_conn, init_db

SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "300"))


class SessionManager:
    """Mengelola session percakapan per user (berdasarkan nomor telepon) di SQLite."""

    def __init__(self):
        init_db()

    # -- helpers --

    def _get_session_dict(self, row, conn):
        """Konversi sqlite3.Row ke dict + ambil history. Pakai koneksi yang sama."""
        if row is None:
            return None
        d = {
            "tujuan": row["tujuan"],
            "step": row["step"],
            "last_active": row["last_active"],
        }
        msgs = conn.execute(
            "SELECT role, text FROM messages WHERE phone=? ORDER BY id",
            (row["phone"],),
        ).fetchall()
        d["history"] = [{"role": m["role"], "parts": [{"text": m["text"]}]} for m in msgs]
        return d

    # -- public API --

    def get_or_create(self, phone_number):
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM sessions WHERE phone=?", (phone_number,)).fetchone()
            if row is None:
                now = time.time()
                conn.execute(
                    "INSERT INTO sessions (phone, last_active) VALUES (?, ?)",
                    (phone_number, now),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM sessions WHERE phone=?", (phone_number,)).fetchone()
            return self._get_session_dict(row, conn)
        finally:
            conn.close()

    def is_expired(self, phone_number):
        session = self.get_or_create(phone_number)
        return time.time() - session["last_active"] > SESSION_TIMEOUT

    def touch(self, phone_number):
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE sessions SET last_active=? WHERE phone=?",
                (time.time(), phone_number),
            )
            conn.commit()
        finally:
            conn.close()

    def update_info(self, phone_number, tujuan=None):
        """Update info user. Pakai `is not None` agar string kosong bisa clear field."""
        self.get_or_create(phone_number)
        conn = get_conn()
        try:
            if tujuan is not None and tujuan:
                conn.execute("UPDATE sessions SET tujuan=? WHERE phone=?", (tujuan, phone_number))
            conn.commit()
        finally:
            conn.close()

    def set_step(self, phone_number, step):
        self.get_or_create(phone_number)
        conn = get_conn()
        try:
            conn.execute("UPDATE sessions SET step=? WHERE phone=?", (step, phone_number))
            conn.commit()
        finally:
            conn.close()

    def add_to_history(self, phone_number, role, text):
        self.get_or_create(phone_number)
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO messages (phone, role, text, ts) VALUES (?, ?, ?, ?)",
                (phone_number, role, text, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_history(self, phone_number):
        session = self.get_or_create(phone_number)
        return session["history"]

    def reset(self, phone_number):
        conn = get_conn()
        try:
            conn.execute("DELETE FROM messages WHERE phone=?", (phone_number,))
            conn.execute("DELETE FROM sessions WHERE phone=?", (phone_number,))
            conn.commit()
        finally:
            conn.close()

    def active_bot(self, phone_number):
        """Reset sesi sepenuhnya (step + history), bukan hanya step."""
        self.reset(phone_number)
        return self.get_or_create(phone_number)

    def get_info_summary(self, phone_number):
        session = self.get_or_create(phone_number)
        parts = []
        if session["tujuan"]:
            parts.append(f"Tujuan: {session['tujuan']}")
        return " | ".join(parts) if parts else "Belum ada info"

    def count_active(self):
        """Jumlah session aktif (belum expired)."""
        conn = get_conn()
        try:
            cutoff = time.time() - SESSION_TIMEOUT
            row = conn.execute(
                "SELECT COUNT(*) as c FROM sessions WHERE last_active > ?", (cutoff,)
            ).fetchone()
            return row["c"]
        finally:
            conn.close()

    def get_operator_sessions(self):
        """Ambil semua sesi aktif yang berstatus 'operator' beserta riwayat obrolannya."""
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT phone, last_active, tujuan FROM sessions WHERE step='operator' ORDER BY last_active DESC"
            ).fetchall()
            results = []
            for r in rows:
                phone = r["phone"]
                msgs = conn.execute(
                    "SELECT role, text, ts FROM messages WHERE phone=? ORDER BY id",
                    (phone,),
                ).fetchall()
                results.append({
                    "phone": phone,
                    "tujuan": r["tujuan"],
                    "last_active": r["last_active"],
                    "messages": [{"role": m["role"], "text": m["text"], "ts": m["ts"]} for m in msgs],
                })
            return results
        finally:
            conn.close()

    def get_expired_sessions(self):
        """Ambil daftar nomor telepon yang sesinya sudah kedaluwarsa (> 5 menit) dan belum di-reset."""
        conn = get_conn()
        try:
            cutoff = time.time() - SESSION_TIMEOUT
            rows = conn.execute(
                "SELECT phone FROM sessions WHERE last_active <= ?", (cutoff,)
            ).fetchall()
            return [r["phone"] for r in rows]
        finally:
            conn.close()

    def cleanup_expired(self):
        """Hapus semua sesi yang sudah melewati batas waktu dari database."""
        conn = get_conn()
        try:
            cutoff = time.time() - SESSION_TIMEOUT
            # Hapus pesan dari sesi yang expired
            conn.execute(
                "DELETE FROM messages WHERE phone IN (SELECT phone FROM sessions WHERE last_active <= ?)",
                (cutoff,)
            )
            # Hapus sesi yang expired
            conn.execute("DELETE FROM sessions WHERE last_active <= ?", (cutoff,))
            conn.commit()
        finally:
            conn.close()
