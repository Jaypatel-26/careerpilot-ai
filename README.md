# CareerPilot AI — Phase 3: Voice and text interviews

React + TypeScript + Tailwind frontend, FastAPI backend, and PostgreSQL. The original design, pages, mock data, and browser-only demo interview remain in place. The separate `/real-interviews` area provides account-backed Gemini AI text and browser-assisted voice interviews. See [Phase 3 deployment and testing](PHASE3.md) before deployment.

## What works and what does not

- Email/password signup and login, Argon2id password hashing, short-lived JWT access tokens, current-user endpoint, and logout with server-side token revocation.
- Account-owned interview drafts, AI-generated questions, text answers, evaluations, and reports.
- PostgreSQL migrations and a Neon-compatible connection setup; Render deployment configuration.
- Existing local text demo at `/interviews/new`, with sample questions and local history, remains separate from real account data.
- Resume analysis, email verification, password recovery, account deletion, and refresh tokens are not implemented. Forgot-password pages explicitly say recovery is unavailable; do not rely on accounts to recover important data.
- The dashboard and sample scores remain demo content. The demo profile is browser-local; the separate account profile is backed by the database. Local demo data is not uploaded.

This is a portfolio/prototype foundation, **not a production-ready authentication service**. Before opening it to real users, add a persistent distributed login rate limiter, email verification, secure email-based password recovery, account deletion, security reviews, monitoring, backups and recovery, and abuse protection. Do not use it for sensitive information yet.

## 1. Prepare Neon

1. Create a free Neon account and PostgreSQL project; choose a nearby region.
2. Open **Connect** in the Neon dashboard. Copy the connection string for your database. It should include `sslmode=require`. Do not share or commit the URL; it contains database credentials.
3. For the application, use the pooled connection URL if desired. For migrations, copy the direct/unpooled URL to the same branch and database. The app accepts `postgresql://` and converts it to the SQLAlchemy `postgresql+psycopg://` form. Keep URL parameters supplied by Neon, including TLS settings. If your password is embedded manually, URL-encode special characters.
4. Neon may scale idle compute to zero. The first connection after inactivity can take longer. Set a reasonable `connect_timeout` URL parameter if needed.

For local-only development you can instead run `docker compose up -d db` from the project root; the provided database uses **development-only** credentials and a Docker volume. Docker isn't needed if you use Neon.

## 2. Configure and run the backend locally

Requirements: Python 3.10+ and pip. From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Edit `backend/.env`:

- `DATABASE_URL`: Neon pooled URL, or a local PostgreSQL URL.
- `MIGRATION_DATABASE_URL`: Neon direct URL for the **same** branch/database; leave blank for local PostgreSQL or to use `DATABASE_URL`.
- `JWT_SECRET_KEY`: paste the freshly generated high-entropy secret, at least 32 bytes. Keep it stable between deploys and never share it or put it in frontend variables. Changing it logs out all users.
- `JWT_ISSUER` and `JWT_AUDIENCE`: use the provided defaults unless you have a reason to change them.
- `ACCESS_TOKEN_MINUTES`: defaults to 30. There is no refresh-token flow; users sign in again after expiry.
- `CORS_ALLOWED_ORIGINS`: comma-separated **exact** frontend origins without a trailing slash, e.g. `http://localhost:5173,https://your-site.example`.
- `GEMINI_API_KEY`: server-only Gemini API key. `GEMINI_MODEL` defaults to `gemini-3.5-flash-lite`; access and pricing depend on your Google project. `GEMINI_TIMEOUT_MS` defaults to 30000.

Run from the `backend` directory so `.env` is found:

```bash
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/docs` for interactive API documentation. The connection uses a small pool and `pool_pre_ping` for idle disconnections. This does not eliminate every cold-start or transient network failure.

## 3. Run the frontend locally

From the repository root in a separate terminal:

```bash
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`. The default `VITE_API_BASE_URL=/api/v1` uses the Vite dev proxy to `http://127.0.0.1:8000` on the server side. You can set `API_PROXY_TARGET` in Vite's environment when starting it if your local backend differs. Browser code does not call the developer's localhost directly. The demo continues working without a backend.

## 4. Test the database connection

```bash
curl http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/health/database
cd backend
alembic current
alembic heads
```

The first URL checks that the API is alive. The database endpoint returns `{"status":"ok","database":"connected"}` when `SELECT 1` works; `503` means the database is unconfigured or unreachable. It does **not** confirm migrations; compare `current` with `heads` separately. Never expose the connection URL in a screenshot or support request.

## 5. Test signup, login, logout, and isolation

1. Start the frontend and backend, configure `JWT_SECRET_KEY`, and apply migrations.
2. Visit `/signup`, enter a name, a valid email address, and a password of 10–128 characters. Signup signs you in and opens `/real-interviews`.
3. Select **New interview**, create a draft, and click **Start AI interview**. Gemini needs to be configured first. Questions are generated only when you start.
4. Sign out from the real draft list. The backend revokes the current JWT session; the same token cannot be used again. Log in at `/login` and confirm your draft is still present.
5. Sign out and sign up as a second user. The first user's draft should not appear. A direct read or delete of its URL/ID returns `404`.
6. Visit `/interviews/new` to verify the independent local demo still works. It remains local to that browser.

API endpoints are `POST /api/v1/auth/signup`, `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`, and `POST`/`GET`/`DELETE /api/v1/interviews`. Protected endpoints expect `Authorization: Bearer <access_token>`. Never paste real tokens into public issue trackers or logs.

## 6. Deploy the FastAPI backend on Render

1. Push this project to a Git repository, ensuring `.env` files and credentials are not committed.
2. Create a **Web Service** on Render and select the repository. Choose the **Free** instance. Use `backend` as the root directory and Python as the runtime.
3. Build command: `pip install -r requirements.txt`
4. Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables in Render: `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ACCESS_TOKEN_MINUTES`, `CORS_ALLOWED_ORIGINS`, `GEMINI_API_KEY` and `GEMINI_MODEL`. Use the Neon URLs and the deployed frontend's exact HTTPS origin. Generate a high-entropy secret; do not regenerate it on each deploy.
6. Deploy and check `/api/v1/health` and `/api/v1/health/database` on the resulting Render URL. Migrations run on startup; this approach assumes one free instance and isn't a substitute for a coordinated migration release process when scaling.

Alternatively, create a Render Blueprint from the included `render.yaml`; provide the values marked for manual setup. The backend must bind to `0.0.0.0` and Render's `PORT`, as shown.

**Free-tier caveats:** Render free web services spin down after inactivity, so the first request may be slow; free instance hours and included build/bandwidth limits apply. Adding a payment method may allow overage charges. Neon free-plan limits and availability can change. Verify the current plans and configure billing/spend safeguards before deployment. See [Render free services](https://render.com/docs/free), [Render billing FAQ](https://render.com/docs/faq), and [Neon connection documentation](https://neon.com/docs/cli/connection-string).

## 7. Deploy the frontend separately

Use a static host that supports React SPA rewrites. For example, create a separate Render Static Site from the same repository:

- Root directory: repository root.
- Build command: `npm ci && npm run build`.
- Publish directory: `dist`.
- Build-time environment variable: `VITE_API_BASE_URL=https://YOUR-BACKEND.onrender.com/api/v1` (use your actual backend HTTPS URL).
- Configure the host's SPA rewrite `/*` → `/index.html` with rewrite status `200`, so direct visits to `/login` and `/real-interviews` work. The included `public/_redirects` supports hosts that understand that file; on Render configure its rewrite rule in the dashboard.

Set `CORS_ALLOWED_ORIGINS` on the backend to the static site's exact origin and redeploy/restart the backend. Rebuild the frontend whenever a `VITE_` value changes. The API URL is public configuration, not a secret. Never place the database URL, JWT secret or Gemini API key in a `VITE_` variable.

## Existing database migration

The new migration does not delete or automatically claim previously saved interview rows. Earlier rows with old owner IDs remain in the database but are inaccessible to new accounts. PostgreSQL adds the new user foreign key as `NOT VALID` so existing orphan rows don't block deployment; new inserts are still checked. **Do not manually assign rows based only on an unverified email.** Back up existing data and design a verified, administrator-controlled account migration before restoring access. Once orphan rows are safely handled, validate the constraint using `ALTER TABLE interview_sessions VALIDATE CONSTRAINT fk_interview_sessions_user`.

The database tables have PostgreSQL RLS enabled with no direct-client policies. The trusted backend's database role must own the tables or otherwise have appropriate privileges to bypass those policies; the API performs per-user checks. Never expose privileged database credentials in the browser. SQLite migration tests skip the PostgreSQL-specific foreign key/RLS clauses and are not a substitute for PostgreSQL testing.

## Security and tests

- Passwords are stored as Argon2id hashes, not plaintext. JWTs are signed with HS256 and verified for issuer, audience, signature, and expiry; an active database session is checked on every protected request.
- The browser stores the access token in per-tab `sessionStorage` and sends it as a bearer token. It persists across refresh in that tab, but is accessible to JavaScript: an XSS vulnerability could steal it. Use HTTPS and perform an XSS/security review. Logout revokes only the current session; if the server cannot be reached, logout reports an error instead of claiming revocation.
- A basic in-memory, per-process login/signup throttle is included. It resets on restart, isn't shared across instances, and may group users behind a proxy; it is **not** adequate protection for production. Configure a trusted client-IP strategy and distributed/edge throttling before public use.
- `.env` files are Git-ignored. The example files contain no secrets. Database backups, account deletion, and expired-session cleanup beyond login-time cleanup are not provided.

```bash
npm run build
cd backend
python -m pytest -q
```

Tests use SQLite for fast unit/integration checks. Verify actual Neon connectivity and deployed CORS/sign-in behavior with your own accounts and services; no cloud account is provisioned by this project.
