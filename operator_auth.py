"""Password login, signed operator sessions, CSRF and bounded login throttling."""
import hmac
import secrets
import threading
import time
from datetime import timedelta

from flask import request, session, jsonify, redirect, url_for, render_template, g
from werkzeug.security import check_password_hash

from config import (OPERATOR_USERNAME, OPERATOR_PASSWORD_HASH, FLASK_SECRET_KEY, COOKIE_SECURE)

LOGIN_TTL = 1800
_attempts = {}
_attempt_lock = threading.Lock()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def _csrf_valid():
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    expected = session.get("csrf", "")
    return bool(expected and supplied) and hmac.compare_digest(expected.encode(), supplied.encode())


def _allow_login():
    now = time.monotonic()
    key = request.remote_addr or "unknown"
    with _attempt_lock:
        for ip in list(_attempts):
            _attempts[ip] = [ts for ts in _attempts[ip] if now - ts < 300]
            if not _attempts[ip]:
                del _attempts[ip]
        attempts = _attempts.setdefault(key, [])
        if len(attempts) >= 5:
            return False
        attempts.append(now)
        return True


def install_auth(app):
    app.config.update(
        SECRET_KEY=FLASK_SECRET_KEY or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=COOKIE_SECURE,
        SESSION_COOKIE_SAMESITE="Strict", PERMANENT_SESSION_LIFETIME=timedelta(seconds=LOGIN_TTL),
        MAX_CONTENT_LENGTH=256 * 1024,
    )
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def prepare_nonce():
        g.csp_nonce = secrets.token_urlsafe(24)

    @app.context_processor
    def template_nonce():
        return {"csp_nonce": g.csp_nonce}

    @app.before_request
    def protect_operator():
        protected = (request.path.startswith("/operator") or request.path.startswith("/api/operator")
                     or request.path == "/stats")
        if not protected:
            return None
        if not (OPERATOR_USERNAME and OPERATOR_PASSWORD_HASH and FLASK_SECRET_KEY):
            return jsonify(status="error", message="Konfigurasi login operator belum lengkap"), 503
        if request.endpoint == "operator_login":
            return None
        authenticated = (session.get("operator") == OPERATOR_USERNAME
                         and time.time() - session.get("login_at", 0) < LOGIN_TTL)
        if not authenticated:
            session.clear()
            if request.path == "/operator" and request.method == "GET":
                return redirect(url_for("operator_login"))
            return jsonify(status="error", message="Login diperlukan"), 401
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not _csrf_valid():
            return jsonify(status="error", message="CSRF token tidak valid"), 403

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.path.startswith(("/operator", "/api/operator")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = (
                f"default-src 'self'; script-src 'self' 'nonce-{g.csp_nonce}'; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; "
                "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        return response

    @app.route("/operator/login", methods=["GET", "POST"])
    def operator_login():
        error = None
        if request.method == "POST":
            if not _csrf_valid():
                return jsonify(status="error", message="CSRF token tidak valid"), 403
            if not _allow_login():
                return jsonify(status="error", message="Terlalu banyak percobaan login"), 429
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            valid = len(password) <= 1024 and check_password_hash(OPERATOR_PASSWORD_HASH, password)
            if hmac.compare_digest(username.encode(), OPERATOR_USERNAME.encode()) and valid:
                session.clear()
                session.permanent = True
                session.update(operator=OPERATOR_USERNAME, login_at=time.time())
                csrf_token()
                return redirect(url_for("operator_dashboard"))
            error = "Nama pengguna atau kata sandi tidak valid."
        return render_template("operator_login.html", error=error), 401 if error else 200

    @app.post("/operator/logout")
    def operator_logout():
        session.clear()
        return redirect(url_for("operator_login"))
