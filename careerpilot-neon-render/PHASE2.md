# Phase 2 — Gemini AI text interviews

## What it does

A signed-in user can create an account-owned draft, start Gemini question generation, answer or skip questions, evaluate submitted answers, and generate a saved report and history entry. Existing drafts can be started if they contain at most five questions. All questions, answers, evaluations and reports use the existing database tables; migration `9f0a2c7d842e` adds only nullable setup and report fields. The earlier `6e7c2a9d3011` profile migration is its prerequisite. Account profiles and the local demo remain separate. Demo data stays in the browser.

Questions are generated once and stored. A submitted answer is committed before evaluation; if AI fails, reload and retry evaluation without losing it. A stored evaluation/report is returned on retry. PostgreSQL session row locks serialize these operations across API workers. A timeout or crash after the provider has processed a request but before the database commits can still cause a second paid provider call on retry: exactly-once billing is not guaranteed. The limit is five AI questions per interview; the current in-process throttle allows 30 AI calls per account per hour and resets on restart. It is not a production abuse/billing protection mechanism. Skipped questions count as zero in the total score; a fully skipped interview creates a no-evidence report without calling Gemini.

AI is fallible and can produce incorrect, biased or unsafe content. Do not use scores as hiring decisions. Role, difficulty, experience, skills, question text and submitted answers are sent to Google; do not enter passwords or sensitive personal data. Name, email and account ID are not intentionally included in prompts, but any information typed into role, skills or answers is sent. Review Google's current data-use terms, privacy policies, model availability, quota and pricing for your project. The model is configurable; the default `gemini-3.5-flash-lite` may not be available in every region or project.

## Required backend configuration

- `DATABASE_URL`: existing Neon URL, kept secret.
- `MIGRATION_DATABASE_URL`: optional Neon direct URL for the same database.
- `JWT_SECRET_KEY`: existing stable secret. Do not regenerate it.
- `CORS_ALLOWED_ORIGINS`: exact deployed frontend URL, no trailing slash.
- `GEMINI_API_KEY`: Google AI Studio / Gemini API key, backend ONLY.
- `GEMINI_MODEL`: for example `gemini-3.5-flash-lite`; check access, availability and pricing.
- `GEMINI_TIMEOUT_MS`: optional, defaults to 30000 ms.

Never place API keys or database credentials in `VITE_` variables, Git, screenshots or chat. `VITE_API_BASE_URL` is only the public backend URL.

## Render deployment (existing services)

1. Before deploying, back up Neon / create a recoverable restore point and check that the existing profile migration is already deployed. Do not replace database or JWT secrets. Verify `DATABASE_URL` and optional `MIGRATION_DATABASE_URL` refer to the same database.
2. In Google AI Studio create a Gemini API key for your own project. Check its billing/quota and available models. Do not share the key.
3. In Render, open the existing **backend Web Service** → **Environment**. Add `GEMINI_API_KEY` (paste it privately) and `GEMINI_MODEL` (e.g. `gemini-3.5-flash-lite`). Save; Render may redeploy. Existing frontend environment variables remain unchanged.
4. Upload the updated source into the existing repository's `careerpilot-neon-render` folder. Preserve the directory structure. Ensure all backend and frontend files are included, especially `backend/migrations/versions/9f0a2c7d842e_ai_text_interviews.py`. See the upload package instructions. No `.env`, secrets, `.venv`, `node_modules` or build artifacts should be uploaded.
5. Deploy the backend latest commit first. Its existing start command must remain `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`. In deployment logs confirm migration succeeded and service is Live. Database health only checks SELECT 1; it does not prove migrations ran.
6. Deploy the static frontend latest commit. Existing root, build command, `VITE_API_BASE_URL`, and SPA rewrite should remain unchanged. Confirm both services use the intended commit. A briefly out-of-sync frontend may show errors while deployment is ongoing.
7. Verify the real flow below. Never show secrets, tokens or connection strings in support screenshots.

## Actual Gemini smoke test (uses quota)

1. Log in to the deployed frontend; open **Real interviews** → **New interview**. Enter a role, skills, experience and type. Choose three questions.
2. Create the draft and explicitly click **Start AI interview**. The app sends setup data to Gemini; wait for the first question.
3. Enter a non-sensitive answer; submit and wait for evaluation. Use Next, skip one question, answer the rest. Click **Finish & generate report**.
4. Check the report, refresh it, sign out/in and check history and the saved report. Also open `/interviews/new` and check the separate demo still works.
5. If the app reports quota/configuration failure, check the backend deployment logs without exposing keys, model availability and project quota. If evaluation fails, the saved answer can be retried. Do not keep retrying a quota error rapidly.

Automated tests mock the Gemini service and do not make real Gemini requests. Without a real configured key and actual request, successful provider connectivity, availability and output cannot be claimed.

## Development, API and tests

Install `backend/requirements.txt`, configure backend environment, run `alembic upgrade head` then `uvicorn app.main:app`. Run `npm ci && npm run dev` for the frontend. Never put a real key in a tracked file.

Endpoints (all require bearer auth and ownership): existing `POST/GET /api/v1/interviews` and `GET/DELETE /api/v1/interviews/{id}`; `POST /{id}/start`, `GET /{id}/current`, `POST /{id}/questions/{question_id}/answer`, `POST /{id}/questions/{question_id}/evaluate`, `POST /{id}/questions/{question_id}/skip`, `POST /{id}/complete`, `GET /{id}/report`. All latter paths are under `/api/v1/interviews`. Retries with the same stored answer are idempotent; a different answer after saving is rejected. Existing list endpoint is the real history.

```bash
npm ci && npm run build
cd backend
pip install -r requirements.txt
python -m pytest -q
alembic upgrade head
```

The automated unit tests use SQLite and mocked AI; PostgreSQL and browser checks are separate integration checks. The browser flow in `tests/e2e/phase2-browser.cjs` requires a fresh local test database, Playwright Chromium, Vite, and the local-only `backend/tests/support/mockserver.py` on port 8000. The mock server must **never** be deployed in production; it does not call Gemini. For example, from `backend` after migrating a fresh test database, run `PYTHONPATH=tests/support:. DATABASE_URL=<local-test-url> JWT_SECRET_KEY=<test-only-secret> uvicorn mockserver:app --port 8000`. Start Vite separately. Install Playwright locally without saving it (`npm install --no-save playwright && npx playwright install chromium`), then run `node tests/e2e/phase2-browser.cjs`. Use fresh test accounts/database on each run. AI rate limiting is in-process only; JWT tokens remain accessible to JavaScript. Use distributed rate limits, budget controls, monitoring, backups, hardened auth and security review before real public use. Free hosting may sleep and incur cold-start delays or changing usage limits. Phase 2 originally did not include voice or resume analysis. Voice is added in Phase 3; see PHASE3.md. Resume analysis remains unimplemented.
