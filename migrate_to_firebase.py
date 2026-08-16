"""
Delvrixo Studios — one-time Firebase migration script.

Copies your existing local data/content.json into Firebase Realtime
Database, and embeds any images currently sitting in static/uploads/
(testimonial photos, proof screenshots, the CEO photo) as base64 data
URIs so they come along too instead of pointing at files that won't
exist anymore once you're running off Firebase.

Run this ONCE, from the project folder (same folder as app.py), after
you've done the two Firebase Console steps from the README (created the
Realtime Database and the admin auth user) — but it's also safe to
re-run any time; it just overwrites whatever's currently in Firebase's
/content node with what's in your local content.json.

Usage:
    python migrate_to_firebase.py
    python migrate_to_firebase.py path/to/content.json

It will ask for your admin password (the one you set for
admin@delvrixo-studios.firebaseapp.com in Firebase Console) before
writing, since the database only accepts writes from a signed-in admin.
"""

import base64
import getpass
import json
import sys
from pathlib import Path

from app import (
    fb_db,
    fb_auth,
    ADMIN_FIREBASE_EMAIL,
    DEFAULT_CONTENT,
    ALLOWED_EXT,
    normalize_proof_images,
)

BASE_DIR = Path(__file__).resolve().parent


def file_to_data_uri(path: Path):
    if not path.exists():
        return None
    ext = path.suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXT:
        return None
    mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def resolve_image(value):
    """Turn a local /static/uploads/... reference into an embedded base64
    data URI so it survives the move off local disk. Data URIs and
    external (http) URLs are left untouched."""
    value = (value or "").strip()
    if not value or value.startswith("data:") or value.startswith("http"):
        return value
    if value.startswith("/static/uploads/"):
        local_path = BASE_DIR / value.lstrip("/")
        data_uri = file_to_data_uri(local_path)
        if data_uri:
            print(f"    embedded {value}")
            return data_uri
        print(f"    \u26a0 could not find {local_path} on disk — leaving reference as-is")
    return value


def build_payload(raw):
    hero = {**DEFAULT_CONTENT["hero"], **raw.get("hero", {})}
    hero["ceo_image"] = resolve_image(hero.get("ceo_image", ""))

    pricing = raw.get("pricing") or DEFAULT_CONTENT["pricing"]

    testimonials = {}
    for t in raw.get("testimonials", []):
        t = dict(t)
        t["avatar_url"] = resolve_image(t.get("avatar_url", ""))

        proof_images = t.get("proof_images")
        if not isinstance(proof_images, list):
            legacy = t.get("proof_image", "")
            proof_images = [legacy] if legacy else []
        t["proof_images"] = [resolve_image(p) for p in proof_images if p]

        normalize_proof_images(t)
        testimonials[str(t["id"])] = t

    return {
        "hero": hero,
        "pricing": pricing,
        "testimonials": testimonials,
        "next_testimonial_id": raw.get("next_testimonial_id", len(testimonials) + 1),
    }


def main():
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data" / "content.json"
    if not json_path.exists():
        print(f"Could not find {json_path}")
        sys.exit(1)

    print(f"Reading {json_path} ...")
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    print("Resolving images referenced in hero + testimonials...")
    payload = build_payload(raw)

    print(f"\nFound {len(payload['testimonials'])} testimonial(s), plus hero + pricing.")
    print("Signing in to Firebase as admin...")
    password = getpass.getpass(f"Password for {ADMIN_FIREBASE_EMAIL}: ")

    try:
        user = fb_auth.sign_in_with_email_and_password(ADMIN_FIREBASE_EMAIL, password)
    except Exception as e:
        print(f"\n\u274c Could not sign in: {e}")
        print("Make sure you've created this exact user in Firebase Console \u2192 Authentication \u2192 Users")
        print(f"(email: {ADMIN_FIREBASE_EMAIL}) with the Email/Password provider enabled.")
        sys.exit(1)

    print("Writing to Firebase Realtime Database at /content ...")
    fb_db.child("content").set(payload, user["idToken"])

    print("\n\u2705 Migration complete.")
    print("Your live site will pick this up on its next /api/content and")
    print("/api/testimonials request — usually within a few seconds if it's")
    print("already running the Firebase-backed app.py.")


if __name__ == "__main__":
    main()
