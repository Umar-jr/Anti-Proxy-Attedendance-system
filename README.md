# QR Attendance System

A web app for taking lecture attendance with dynamic QR codes, GPS verification,
and a real-time dashboard for lecturers. Built with Flask.

![CI](https://github.com/<your-username>/qr-attendance-system/actions/workflows/ci.yml/badge.svg)

## Features

- **Dynamic QR codes** that refresh and expire every few seconds (signed, short-lived tokens)
- **GPS check** — a scan is only accepted within a set radius of the lecture hall
- **Lightweight device binding** to flag the same student marking from a new device
- **Real-time attendance** on the lecturer's dashboard via Server-Sent Events
- **CSV export** and admin-wide session reports
- **Three roles** — Admin (users/courses/enrollments), Lecturer (sessions/QR/live view), Student (scan to mark)
- **CSRF protection** on every form and the attendance API

## Tech stack

Flask · Flask-SQLAlchemy · Flask-Login · Flask-WTF · itsdangerous · qrcode ·
gunicorn · SQLite (local) / PostgreSQL (production)

## Quick start (local)

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # optional — SQLite is used if DATABASE_URL is unset
python run.py                     # http://127.0.0.1:5001
```

Default admin (change the password after first login):
`admin@uni.edu` / `Admin123!`

Set `FLASK_DEBUG=1` in `.env` for the auto-reloading debug server.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests also run automatically on every push via GitHub Actions (`.github/workflows/ci.yml`).

## Deployment

This is a single full-stack app — one service, no separate frontend to host.
See **[DEPLOY.md](DEPLOY.md)** for step-by-step instructions. The short version:
push to GitHub, connect the repo to Render as a Blueprint (it reads `render.yaml`
and provisions the app + a Postgres database), then set `BASE_URL` to your live URL.

## Project structure

```
qr_attendance_system/
├── app/
│   ├── __init__.py          # app factory, config, DB + CSRF + ProxyFix setup
│   ├── models.py            # User, Course, Enrollment, LectureSession, Attendance
│   ├── routes.py            # all routes (auth, admin, lecturer, student, APIs)
│   ├── utils.py             # signed QR tokens, haversine distance, SSE pub/sub
│   ├── seed.py              # creates the default admin
│   ├── static/              # css + js (qr refresh, scan, live updates, geolocation)
│   └── templates/           # base + landing/login + admin/lecturer/student pages
├── tests/test_app.py        # CSRF + full attendance-flow tests
├── .github/workflows/ci.yml # GitHub Actions CI
├── render.yaml              # Render Blueprint (web service + Postgres)
├── Dockerfile + fly.toml    # container deploy (Fly.io / Railway / Render-via-Docker)
├── requirements.txt         # app dependencies
├── requirements-dev.txt     # app + test dependencies
├── DEPLOY.md                # deployment guide
└── run.py                   # entry point
```

## Security notes

The anti-proxy measures raise the bar but are not foolproof, by design for a
course project: GPS can be spoofed with mock-location apps, and the device
identifier is a browser-stored token that can be cleared. They are best treated
as deterrents layered on top of physical presence, not hard guarantees.

## License

[MIT](LICENSE)
