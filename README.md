QR Attendance System (Flask)

Features
- Dynamic QR codes with short expiry
- Student login + device ID check
- Location verification (GPS radius)
- Real-time attendance updates for lecturers (SSE)
- Attendance reports + CSV export
- CSRF protection on all forms and the attendance API

Run (local)
1) python3 -m venv venv
2) source venv/bin/activate            (Windows: venv\Scripts\activate)
3) pip install -r requirements.txt
4) cp .env.example .env                (optional; SQLite used if DATABASE_URL unset)
5) python run.py

Open: http://127.0.0.1:5001
Set FLASK_DEBUG=1 in .env for the auto-reloading debug server.

Default Admin (change the password after first login)
- Email: admin@uni.edu
- Password: Admin123!

Deploying to the internet
- See DEPLOY.md for step-by-step Render (recommended) and Fly.io instructions.
