# Delvrixo Studios — Site + Admin Panel (one Flask app)

Everything runs from a single Python (Flask) app now:

- **Public site** → `http://127.0.0.1:5000/`
- **Admin panel** → `http://127.0.0.1:5000/admin`

No database needed — content is stored in `data/content.json`.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open:
- `http://127.0.0.1:5000/` — this is what your visitors see (the live site).
- `http://127.0.0.1:5000/admin` — this is your private admin panel (login required).

Default login:
- Username: `admin`
- Password: `delvrixo2025`

**Change these before deploying** — either edit the defaults in `app.py`, or
set environment variables:

```bash
export ADMIN_USER="youradminname"
export ADMIN_PASS_HASH=$(python -c "from werkzeug.security import generate_password_hash as g; print(g('yournewpassword'))")
export ADMIN_SECRET_KEY="some-long-random-string"
python app.py
```

## What you can edit from the admin panel

- **Hero & Site Text** — the meta pill label, meta text, and 3-line headline
  on the homepage.
- **Pricing** — USD and INR amounts for every package (websites, MVPs, retainers).
- **Testimonials** — add, edit, publish/unpublish, or delete client reviews.
  Each testimonial has a name, role, company, region (India / Outside India),
  star rating, quote text, an optional client photo, and an optional
  screenshot of your real conversation with them (chat/email proof). On the
  public site, clicking a testimonial card expands it into a detail view
  showing the full text and that screenshot.

## How the site and admin panel connect

`index.html` (the public homepage) fetches published testimonials straight
from this same Flask app:

```
GET /api/testimonials
```

Since everything now runs on one server, no extra config is needed — the
site and admin panel share the same origin (`http://127.0.0.1:5000`). If the
API somehow doesn't respond, the testimonials section quietly falls back to
a small static sample so the page never looks broken.

## File structure

```
project/
├── app.py                  ← Flask app — serves "/" (site) and "/admin" (panel)
├── index.html               ← the public website
├── requirements.txt
├── data/
│   └── content.json         ← all editable content lives here
├── templates/
│   ├── login.html
│   └── dashboard.html
└── static/
    ├── admin.css
    ├── admin.js
    └── uploads/              ← client photos + proof screenshots land here (auto-created)
```

## Notes

- Auth is a single hardcoded admin account with a session cookie — fine for
  one owner/operator. For multiple admins or stronger security, swap in a
  real user table + login system.
- `content.json` is written atomically (temp file + rename) so a crash
  mid-save won't corrupt your data.
- Deploy behind HTTPS in production — the login form sends your password
  in plain JSON over the connection you give it.
- To deploy for real (not just localhost), run this behind a production
  WSGI server (e.g. `gunicorn app:app`).
- On Render, use a persistent disk if you want uploaded images and
  `data/content.json` changes to survive redeploys. Without persistent
  storage, file-based uploads/content reset when the service restarts.
