"""
Delvrixo Studios — Full Site + Admin Panel (single Flask app)
Data lives in Firebase Realtime Database (no local files, so it survives
Render free-tier restarts). Admin login uses Firebase Authentication
(email/password) behind the scenes — the login screen still just asks for
a plain username + password so nothing changes for you.

Run:
    pip install -r requirements.txt
    python app.py

Then:
    Public site  ->  http://127.0.0.1:5000/
    Admin panel  ->  http://127.0.0.1:5000/admin   (see README for the one-time
                       Firebase setup: create the RTDB + the admin auth user)
"""

import base64
import os
from functools import wraps
from pathlib import Path

import pyrebase
from flask import (
    Flask, jsonify, request, session, redirect, url_for,
    render_template, send_from_directory,
)
from werkzeug.exceptions import RequestEntityTooLarge

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET_KEY", "delvrixo-dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

# ───────────────────────── Firebase setup ─────────────────────────
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyClHoL6BPdnibnwvO5vpiwyrNy3KCSoYaE",
    "authDomain": "delvrixo-studios.firebaseapp.com",
    "databaseURL": "https://delvrixo-studios-default-rtdb.firebaseio.com",
    "projectId": "delvrixo-studios",
    "storageBucket": "delvrixo-studios.firebasestorage.app",
    "messagingSenderId": "755041568240",
    "appId": "1:755041568240:web:d3acb3487d8cf2e8d78935",
    "measurementId": "G-DW4V1DSLY1",
}

firebase = pyrebase.initialize_app(FIREBASE_CONFIG)
fb_db = firebase.database()
fb_auth = firebase.auth()

# The login screen still asks for a plain "username" (not an email), but Firebase
# Authentication needs a real email/password account under the hood. This fixed
# username maps to a fixed email in your Firebase project — see README for the
# one-time step of creating that user in Firebase Console → Authentication.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_FIREBASE_EMAIL = os.environ.get("ADMIN_FIREBASE_EMAIL", "admin@delvrixo-studios.firebaseapp.com")

DEFAULT_CONTENT = {
    "hero": {
        "meta_pill": "GLOBAL · 2025",
        "meta_text": "Premium Offshore Product Studio",
        "title_line1": "DIGITAL",
        "title_line2": "PRODUCT",
        "title_line3": "STUDIO",
        "ceo_image": "",
    },
    "pricing": {
        "web_basic":     {"label": "BASIC LAUNCH",    "usd": 1000,  "inr": 15000},
        "web_standard":  {"label": "STANDARD LAUNCH", "usd": 2000,  "inr": 25000},
        "web_pro":       {"label": "PRO LAUNCH",      "usd": 4000,  "inr": 45000},
        "mvp_micro":     {"label": "MICRO MVP",       "usd": 3500,  "inr": 45000},
        "mvp_core":      {"label": "CORE MVP",        "usd": 8500,  "inr": 90000},
        "mvp_full":      {"label": "FULL MVP",        "usd": 15000, "inr": 150000},
        "scale_starter": {"label": "STARTER ENGINE",  "usd": 1000,  "inr": 10000},
        "scale_growth":  {"label": "GROWTH ENGINE",   "usd": 2000,  "inr": 20000},
        "scale_pro":     {"label": "PRO ENGINE",      "usd": 4000,  "inr": 35000},
    },
    "testimonials": {},
    "next_testimonial_id": 1,
}


# ───────────────────────── Data helpers (Firebase Realtime Database) ─────────────────────────
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


def parse_proof_images(body):
    proof_images = body.get("proof_images")
    if isinstance(proof_images, list):
        return [str(url).strip() for url in proof_images if str(url).strip()]

    legacy = str(body.get("proof_image", "")).strip()
    return [legacy] if legacy else []


def _testimonials_val_to_list(raw):
    """RTDB stores objects as {id: {...}} — convert to the list shape every
    route in this file already expects (unchanged from the old JSON-file version)."""
    if not raw:
        return []
    items = raw.values() if isinstance(raw, dict) else raw
    cleaned = [normalize_proof_images(dict(t)) for t in items if t]
    return sorted(cleaned, key=lambda t: t.get("id", 0))


def load_data():
    """Fetch the whole /content node from Firebase. Seeds sensible defaults
    the very first time it's called (i.e. on a brand-new Firebase project)."""
    val = fb_db.child("content").get().val()
    if not val:
        fb_db.child("content").set(DEFAULT_CONTENT)
        val = DEFAULT_CONTENT

    return {
        "hero": {**DEFAULT_CONTENT["hero"], **(val.get("hero") or {})},
        "pricing": val.get("pricing") or DEFAULT_CONTENT["pricing"],
        "testimonials": _testimonials_val_to_list(val.get("testimonials")),
        "next_testimonial_id": val.get("next_testimonial_id", 1),
    }


def save_data(data):
    """Write the whole /content node back to Firebase in one call — same
    call shape every route below already used with the old JSON file."""
    testimonials_dict = {
        str(t["id"]): normalize_proof_images(dict(t)) for t in data["testimonials"]
    }
    fb_db.child("content").set({
        "hero": data["hero"],
        "pricing": data["pricing"],
        "testimonials": testimonials_dict,
        "next_testimonial_id": data.get("next_testimonial_id", 1),
    })


def image_to_data_uri(file_storage):
    """Read an uploaded image straight into memory and return it as an
    embeddable base64 data: URI — no filesystem writes at all, so this
    works fine on ephemeral hosts (Render free tier) and needs nothing
    beyond the Realtime Database (no Firebase Storage / billing required)."""
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_EXT:
        return None
    mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
    raw_bytes = file_storage.read()
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


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


# ───────────────────────── Auth routes (Firebase Authentication) ─────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("logged_in"):
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    payload = request.get_json(silent=True) or request.form
    username = (payload.get("username", "") or "").strip()
    password = payload.get("password", "") or ""

    if username != ADMIN_USERNAME:
        return jsonify({"ok": False, "error": "Invalid username or password"}), 401

    try:
        fb_auth.sign_in_with_email_and_password(ADMIN_FIREBASE_EMAIL, password)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid username or password"}), 401

    session["logged_in"] = True
    session["username"] = username
    return jsonify({"ok": True, "redirect": url_for("dashboard")})


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

    data_uri = image_to_data_uri(f)
    if not data_uri:
        return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXT))}"}), 400

    return jsonify({"ok": True, "url": data_uri})


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
