"""
Delvrixo Studios — Full Site + Admin Panel (single Flask app)
Pure Python (Flask) backend. Admin frontend is plain HTML/CSS/JS.
Content is stored in data/content.json — no external DB required.

Run:
    pip install -r requirements.txt
    python app.py

Then:
    Public site  ->  http://127.0.0.1:5000/
    Admin panel  ->  http://127.0.0.1:5000/admin   (default login below)
"""

import json
import os
import uuid
from functools import wraps
from pathlib import Path

from flask import (
    Flask, jsonify, request, session, redirect, url_for,
    render_template, send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "content.json"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET_KEY", "delvrixo-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

# ── Admin credentials (change these, or set env vars ADMIN_USER / ADMIN_PASS_HASH) ──
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS_HASH = os.environ.get(
    "ADMIN_PASS_HASH",
    generate_password_hash("delvrixo2025"),
)


# ───────────────────────── Data helpers ─────────────────────────
def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return normalize_data(json.load(f))


def save_data(data):
    data = normalize_data(data)
    tmp_path = DATA_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp_path.replace(DATA_FILE)


def normalize_proof_images(testimonial):
    proof_images = testimonial.get("proof_images")
    if isinstance(proof_images, list):
        cleaned = [str(url).strip() for url in proof_images if str(url).strip()]
    elif proof_images:
        cleaned = [str(proof_images).strip()]
    else:
        legacy = str(testimonial.get("proof_image", "")).strip()
        cleaned = [legacy] if legacy else []

    testimonial["proof_images"] = cleaned
    testimonial["proof_image"] = cleaned[0] if cleaned else ""
    return testimonial


def normalize_data(data):
    if isinstance(data, dict) and isinstance(data.get("testimonials"), list):
        data["testimonials"] = [normalize_proof_images(dict(t)) for t in data["testimonials"]]
    return data


def parse_proof_images(body):
    proof_images = body.get("proof_images")
    if isinstance(proof_images, list):
        return [str(url).strip() for url in proof_images if str(url).strip()]

    legacy = str(body.get("proof_image", "")).strip()
    return [legacy] if legacy else []


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/admin"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_error):
    message = f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), 413
    return message, 413


# ───────────────────────── Public site ─────────────────────────
@app.route("/")
def public_site():
    """Serves the main Delvrixo Studios website to regular visitors."""
    return send_from_directory(BASE_DIR, "index.html")


# ───────────────────────── Auth routes ─────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("logged_in"):
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    payload = request.get_json(silent=True) or request.form
    username = payload.get("username", "")
    password = payload.get("password", "")

    if username == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, password):
        session["logged_in"] = True
        session["username"] = username
        return jsonify({"ok": True, "redirect": url_for("dashboard")})

    return jsonify({"ok": False, "error": "Invalid username or password"}), 401


@app.route("/admin/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("login")})


# ───────────────────────── Admin panel pages ─────────────────────────
@app.route("/admin")
@app.route("/admin/")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"))


@app.route("/api/admin/upload", methods=["POST"])
@login_required
def admin_upload_image():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXT))}"}), 400

    safe_name = f"{uuid.uuid4().hex}.{ext}"
    f.save(UPLOAD_DIR / secure_filename(safe_name))
    return jsonify({"ok": True, "url": f"/static/uploads/{safe_name}"})


# ───────────────────────── Admin API (requires login) ─────────────────────────
@app.route("/api/admin/content", methods=["GET"])
@login_required
def admin_get_content():
    return jsonify(load_data())


@app.route("/api/admin/hero", methods=["PUT"])
@login_required
def admin_update_hero():
    data = load_data()
    body = request.get_json(force=True) or {}
    data["hero"].update({k: v for k, v in body.items() if k in data["hero"]})
    save_data(data)
    return jsonify({"ok": True, "hero": data["hero"]})


@app.route("/api/admin/pricing", methods=["PUT"])
@login_required
def admin_update_pricing():
    data = load_data()
    body = request.get_json(force=True) or {}
    for key, values in body.items():
        if key in data["pricing"]:
            data["pricing"][key].update(values)
    save_data(data)
    return jsonify({"ok": True, "pricing": data["pricing"]})


@app.route("/api/admin/testimonials", methods=["GET"])
@login_required
def admin_list_testimonials():
    data = load_data()
    return jsonify(data["testimonials"])


@app.route("/api/admin/testimonials", methods=["POST"])
@login_required
def admin_create_testimonial():
    data = load_data()
    body = request.get_json(force=True) or {}

    new_id = data.get("next_testimonial_id", len(data["testimonials"]) + 1)
    testimonial = {
        "id": new_id,
        "name": body.get("name", "").strip(),
        "role": body.get("role", "").strip(),
        "company": body.get("company", "").strip(),
        "text": body.get("text", "").strip(),
        "rating": max(1, min(5, int(body.get("rating", 5) or 5))),
        "location": body.get("location", "intl"),
        "published": bool(body.get("published", True)),
        "avatar_url": body.get("avatar_url", "").strip(),
        "proof_images": parse_proof_images(body),
    }

    if not testimonial["name"] or not testimonial["text"]:
        return jsonify({"error": "Name and testimonial text are required"}), 400

    data["testimonials"].append(testimonial)
    data["next_testimonial_id"] = new_id + 1
    save_data(data)
    return jsonify({"ok": True, "testimonial": testimonial}), 201


@app.route("/api/admin/testimonials/<int:tid>", methods=["PUT"])
@login_required
def admin_update_testimonial(tid):
    data = load_data()
    body = request.get_json(force=True) or {}

    for t in data["testimonials"]:
        if t["id"] == tid:
            for field in ("name", "role", "company", "text", "location", "avatar_url"):
                if field in body:
                    t[field] = str(body[field]).strip()
            if "proof_images" in body or "proof_image" in body:
                t["proof_images"] = parse_proof_images(body)
            if "rating" in body:
                t["rating"] = max(1, min(5, int(body["rating"] or 5)))
            if "published" in body:
                t["published"] = bool(body["published"])
            normalize_proof_images(t)
            save_data(data)
            return jsonify({"ok": True, "testimonial": t})

    return jsonify({"error": "Testimonial not found"}), 404


@app.route("/api/admin/testimonials/<int:tid>", methods=["DELETE"])
@login_required
def admin_delete_testimonial(tid):
    data = load_data()
    before = len(data["testimonials"])
    data["testimonials"] = [t for t in data["testimonials"] if t["id"] != tid]

    if len(data["testimonials"]) == before:
        return jsonify({"error": "Testimonial not found"}), 404

    save_data(data)
    return jsonify({"ok": True})


# ───────────────────────── Public API (read-only, used by the live site) ─────────────────────────
@app.route("/api/testimonials", methods=["GET"])
def public_testimonials():
    data = load_data()
    published = [t for t in data["testimonials"] if t.get("published", True)]
    return jsonify(published)


@app.route("/api/content", methods=["GET"])
def public_content():
    data = load_data()
    return jsonify({"hero": data["hero"], "pricing": data["pricing"]})


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
    )
