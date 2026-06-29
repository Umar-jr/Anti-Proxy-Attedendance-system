# Deploying the QR Attendance System

This is a single full-stack Flask app: it serves the HTML pages **and** the
JSON/SSE APIs from one process. You deploy **one service** — there is no
separate frontend to host.

What changed to make it production-ready:

- `DATABASE_URL` is used when set (Postgres in production), SQLite locally.
- CSRF protection is on for every form and the attendance API.
- `SECRET_KEY` and debug mode are read from the environment (debug off by default).
- Runs under `gunicorn` (threaded worker) instead of the Flask dev server.
- `ProxyFix` makes QR scan URLs come out as `https://...` behind the host proxy.

---

## Recommended: Render (free, easiest)

Render natively runs persistent full-stack apps, gives free automatic HTTPS
(required for GPS), and needs no credit card. The included `render.yaml`
provisions the web service **and** a free Postgres database for you.

**Steps**

1. Push this project to a GitHub repo.
2. Go to <https://render.com> → **New** → **Blueprint** → connect the repo.
   Render reads `render.yaml`, creates the web service + Postgres, and wires
   `DATABASE_URL` and a generated `SECRET_KEY` automatically.
3. Wait for the first deploy, then copy your service URL
   (e.g. `https://qr-attendance.onrender.com`).
4. In the service's **Environment** tab, set **`BASE_URL`** to that exact URL,
   then **Manual Deploy → Deploy latest commit** (or just save — it redeploys).
   This makes the QR codes point at the right host.
5. Open the URL and log in with the seeded admin:
   `admin@uni.edu` / `Admin123!` — then change that password.

**Know this about the free tier**

- The service **sleeps after ~15 min idle**; the next request takes ~30–60s to
  wake. Fine for a demo; upgrade to Starter (~$7/mo) to keep it always-on.
- The **free Postgres database expires ~30 days** after creation. Recreate it
  before a demo if it lapses, or move to a paid database to keep data.
- Don't rely on the local filesystem on the free tier — that's exactly why we
  use Postgres, not SQLite, in production.

---

## Alternative: Fly.io (Docker — closest to Nigeria, best for DevOps practice)

Uses the included `Dockerfile` and `fly.toml`. The `jnb` (Johannesburg) region
is the nearest to Nigeria, and persistent volumes are available.

1. Install the CLI and sign in: `fly auth signup` (or `fly auth login`).
2. From the project folder: `fly launch --no-deploy` (accept the `fly.toml`;
   pick a unique app name).
3. Add a database: `fly postgres create`, then `fly postgres attach <db-name>`
   — this sets `DATABASE_URL` on the app automatically.
4. Set the remaining secrets:
   ```bash
   fly secrets set SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
   fly secrets set BASE_URL="https://<your-app>.fly.dev"
   ```
5. Deploy: `fly deploy`. Open it: `fly open`.

> The same `Dockerfile` also deploys on Railway, or on Render via "Docker"
> instead of the Blueprint, if you prefer one platform over another.

**Avoid Vercel and Netlify** for this app — they're built for static/serverless
frontends and won't run the persistent live-update (SSE) stream.

---

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # optional; SQLite is used if DATABASE_URL is unset
python run.py                   # http://127.0.0.1:5001
```

Set `FLASK_DEBUG=1` in `.env` for the auto-reloading debug server while developing.
To test scanning on a real phone, expose your local server over HTTPS with a
tunnel (e.g. `ngrok http 5001`) and set `BASE_URL` to the tunnel URL — handy for
demos, but a tunnel is not a permanent host.

---

## Production checklist

- [ ] `SECRET_KEY` set to a strong random value (Render's blueprint does this).
- [ ] `BASE_URL` set to your real HTTPS URL.
- [ ] `DATABASE_URL` points at Postgres (not SQLite).
- [ ] Debug is **off** (it is, unless `FLASK_DEBUG=1`).
- [ ] Default admin password changed after first login.
