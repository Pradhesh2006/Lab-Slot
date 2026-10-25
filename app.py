"""LabSlot - Research Equipment Assistant (Flask web app)."""

import os
import re
import secrets
import socket
import sys
from functools import wraps
from urllib.parse import urlparse

if sys.version_info < (3, 9):
    sys.exit("LabSlot needs Python 3.9 or newer (you have %s)." % sys.version.split()[0])

try:
    from dotenv import load_dotenv
    from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
    from werkzeug.security import check_password_hash, generate_password_hash

    import database
    from rag import get_engine
    from tools import EQUIPMENT, TRAINING_MODULES, check_equipment_session
except ModuleNotFoundError as exc:
    sys.exit(
        f"LabSlot cannot start: missing Python package '{exc.name}'.\n"
        "Activate your virtual environment and run:  pip install -r requirements.txt\n"
        "(or just run setup_and_run.bat on Windows / ./setup_and_run.sh on macOS/Linux)."
    )

load_dotenv()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_QUESTION_LENGTH = 500

database.init_db()


# ------------------------------------------------------------------ helpers
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def verify_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
        if not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "Invalid or missing CSRF token. Reload the page and try again.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def safe_next(target):
    """Allow only same-site relative redirects."""
    if target and target.startswith("/") and not target.startswith("//") and not urlparse(target).netloc:
        return target
    return url_for("index")


# ------------------------------------------------------------------- auth
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))
    form = {"username": "", "email": ""}
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        form = {"username": username, "email": email}

        errors = []
        if not USERNAME_RE.match(username):
            errors.append("Username must be 3-32 characters: letters, numbers or underscores.")
        if not EMAIL_RE.match(email) or len(email) > 254:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            user_id = database.add_user(username, generate_password_hash(password), email)
            if user_id is None:
                errors.append("That username is already taken.")
            else:
                flash("Account created. Sign in to open LabSlot.", "success")
                return redirect(url_for("login"))
        for message in errors:
            flash(message, "error")
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.get_user(username) if username else None
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(safe_next(request.args.get("next")))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out of LabSlot.", "success")
    return redirect(url_for("login"))


# -------------------------------------------------------------- dashboard
@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        equipment=EQUIPMENT,
        training_modules=TRAINING_MODULES,
        username=session.get("username"),
    )


@app.route("/api/check", methods=["POST"])
@login_required
def api_check():
    payload = request.get_json(silent=True) or {}
    duration = payload.get("duration_minutes")
    if isinstance(duration, str) and duration.strip().isdigit():
        duration = int(duration.strip())
    try:
        result = check_equipment_session(
            payload.get("equipment_code", ""),
            payload.get("start_time", ""),
            duration,
            payload.get("completed_training") or [],
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    result["equipment_code"] = str(payload.get("equipment_code", "")).strip().upper()
    return jsonify(result)


@app.route("/api/ask", methods=["POST"])
@login_required
def api_ask():
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"error": "Enter a question first."}), 400
    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({"error": f"Questions are limited to {MAX_QUESTION_LENGTH} characters."}), 400
    try:
        result = get_engine().answer(question)
    except Exception as exc:
        app.logger.exception("LabSlot RAG failure")
        return jsonify({"error": f"LabSlot could not answer right now: {type(exc).__name__}"}), 500
    return jsonify(
        {
            "answer": result["answer"],
            "mode": result["mode"],
            "citations": [
                {"source": c["source"], "chunk": c["chunk"], "score": c["score"]}
                for c in result["citations"]
            ],
        }
    )


def pick_port(preferred):
    """Use the preferred port, or the next free one (macOS often occupies 5000 for AirPlay)."""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


if __name__ == "__main__":
    port = pick_port(int(os.environ.get("PORT", "5000")))
    print("LabSlot - Research Equipment Assistant")
    print(f"  Database : {database.get_db_path()}")
    print(f"  Gemini   : {'configured' if os.environ.get('GEMINI_API_KEY') else 'no API key - offline extractive answers'}")
    print(f"  Open     : http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
