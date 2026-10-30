"""
Session manager berbasis SQLite.
ponytail: multi-worker → ganti ke Redis + distributed lock.
"""
import os
import time
from db import get_conn, init_db
from config import SESSION_TIMEOUT
from webhook_utils import phone_lock



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
            "conversation_id": row["conversation_id"],
            "tujuan": row["tujuan"],
            "step": row["step"],
            "last_active": row["last_active"],
        }
        msgs = conn.execute(
            "SELECT role, text FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 100",
            (row["conversation_id"],),
        ).fetchall()
        d["history"] = [{"role": m["role"], "parts": [{"text": m["text"]}]} for m in reversed(msgs)]
        return d

    # -- public API --

    def get_or_create(self, phone_number):
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM sessions WHERE phone=?", (phone_number,)).fetchone()
            if row is None:
                now = time.time()
                conn.execute(
                    "INSERT INTO sessions (phone, last_active) VALUES (?, ?)",
                    (phone_number, now),
                )
                row = conn.execute("SELECT * FROM sessions WHERE phone=?", (phone_number,)).fetchone()
            if row["conversation_id"] is None:
                cursor = conn.execute(
                    "INSERT INTO conversations(phone, started_at) VALUES (?, ?)",
                    (phone_number, time.time()))
                conn.execute("UPDATE sessions SET conversation_id=?, last_active=? WHERE phone=?",
                             (cursor.lastrowid, time.time(), phone_number))
                row = conn.execute("SELECT * FROM sessions WHERE phone=?", (phone_number,)).fetchone()
            conn.commit()
            return self._get_session_dict(row, conn)
        finally:
            conn.close()

    def is_expired(self, phone_number):
        session = self.get_or_create(phone_number)
        return session["step"] != "operator" and time.time() - session["last_active"] > SESSION_TIMEOUT

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
            if tujuan is not None:
                conn.execute("UPDATE sessions SET tujuan=? WHERE phone=?", (tujuan, phone_number))
            conn.commit()
        finally:
            conn.close()

    def set_step(self, phone_number, step):
        self.get_or_create(phone_number)
        conn = get_conn()
        try:
            conn.execute("UPDATE sessions SET step=? WHERE phone=?", (step, phone_number))
            if step == "operator":
                conn.execute("UPDATE conversations SET kind='pengaduan' WHERE id="
                             "(SELECT conversation_id FROM sessions WHERE phone=?)", (phone_number,))
            conn.commit()
        finally:
            conn.close()

    def add_to_history(self, phone_number, role, text):
        session = self.get_or_create(phone_number)
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO messages (phone, role, text, ts, conversation_id) VALUES (?, ?, ?, ?, ?)",
                (phone_number, role, text, time.time(), session["conversation_id"]),
            )
            conn.commit()
        finally:
            conn.close()

    def get_history(self, phone_number):
        session = self.get_or_create(phone_number)
        return session["history"]

    def reset(self, phone_number, reason="reset"):
        """Close active conversation without deleting its messages or complaint archive."""
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE conversations SET closed_at=?, close_reason=? WHERE closed_at IS NULL "
                "AND id=(SELECT conversation_id FROM sessions WHERE phone=?)",
                (time.time(), reason, phone_number))
            conn.execute("UPDATE sessions SET tujuan='', step='awal', last_active=0, conversation_id=NULL WHERE phone=?",
                         (phone_number,))
            conn.commit()
        finally:
            conn.close()

    def active_bot(self, phone_number):
        """Start a new active session; keep previous messages in its closed archive."""
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
                "SELECT COUNT(*) as c FROM sessions WHERE conversation_id IS NOT NULL "
                "AND (last_active > ? OR step='operator')", (cutoff,)
            ).fetchone()
            return row["c"]
        finally:
            conn.close()

    def get_operator_sessions(self):
        """Ambil semua sesi aktif yang berstatus 'operator' beserta riwayat obrolannya."""
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT phone, last_active, tujuan, conversation_id FROM sessions WHERE step='operator' ORDER BY last_active DESC"
            ).fetchall()
            results = []
            for r in rows:
                phone = r["phone"]
                msgs = conn.execute(
                    "SELECT role, text, ts FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 200",
                    (r["conversation_id"],),
                ).fetchall()
                results.append({
                    "phone": phone,
                    "tujuan": r["tujuan"],
                    "last_active": r["last_active"],
                    "messages": [{"role": m["role"], "text": m["text"], "ts": m["ts"]} for m in reversed(msgs)],
                })
            return results
        finally:
            conn.close()

    def is_operator(self, phone_number):
        conn = get_conn()
        try:
            row = conn.execute("SELECT step FROM sessions WHERE phone=?", (phone_number,)).fetchone()
            return row is not None and row["step"] == "operator"
        finally:
            conn.close()

    def mark_complaint(self, phone_number):
        conn = get_conn()
        try:
            conn.execute("UPDATE conversations SET kind='pengaduan' WHERE id="
                         "(SELECT conversation_id FROM sessions WHERE phone=?)", (phone_number,))
            conn.commit()
        finally:
            conn.close()

    def get_expired_sessions(self):
        """Ambil daftar nomor telepon yang sesinya sudah kedaluwarsa (> 5 menit) dan belum di-reset."""
        conn = get_conn()
        try:
            cutoff = time.time() - SESSION_TIMEOUT
            rows = conn.execute(
                "SELECT phone FROM sessions WHERE last_active <= ? AND conversation_id IS NOT NULL AND step != 'operator'", (cutoff,)
            ).fetchall()
            return [r["phone"] for r in rows]
        finally:
            conn.close()

    def cleanup_expired(self):
        """Archive expired bot conversations; operator sessions require explicit closure."""
        for phone in self.get_expired_sessions():
            with phone_lock(phone):
                if phone in self.get_expired_sessions():
                    self.reset(phone, reason="timeout")

    def get_archives(self, phone_number):
        """Return closed conversations; intentionally not exposed through a public API."""
        conn = get_conn()
        try:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM conversations WHERE phone=? AND closed_at IS NOT NULL ORDER BY id",
                (phone_number,))]
        finally:
            conn.close()

    def purge_archives(self, retention_days):
        """Explicit maintenance only; never removes active conversations. Back up before use."""
        if not isinstance(retention_days, int) or retention_days <= 0:
            raise ValueError("retention_days harus positif dan disetujui pengelola data")
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cutoff = time.time() - retention_days * 86400
            # Hapus pesan dari sesi yang expired
            conn.execute("DELETE FROM messages WHERE conversation_id IN "
                         "(SELECT id FROM conversations WHERE closed_at < ?)", (cutoff,))
            # Hapus sesi yang expired
            result = conn.execute("DELETE FROM conversations WHERE closed_at < ?", (cutoff,))
            removed = result.rowcount
            conn.execute("DELETE FROM webhook_inbox WHERE created_at < ? AND status IN ('done', 'failed')", (cutoff,))
            conn.execute("DELETE FROM sessions WHERE conversation_id IS NULL AND NOT EXISTS "
                         "(SELECT 1 FROM conversations WHERE phone=sessions.phone)")
            conn.commit()
            return removed
        finally:
            conn.close()
