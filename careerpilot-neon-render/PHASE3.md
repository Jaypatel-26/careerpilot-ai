# CareerPilot Phase 3 — Voice interviews

## What changes

Voice interviews are a separate option under Real interviews; text interviews and the local demo remain separate and unchanged. The same authenticated Phase 2 question, transcript evaluation, report and history APIs are reused. An interview has a `mode` of `text` or `voice`. Browser SpeechSynthesis reads each voice question; Replay is available if autoplay is blocked. Browser SpeechRecognition converts speech to an editable transcript. On submit only the transcript is saved, then sent to Gemini for evaluation. Input may also be typed when recognition is unavailable. The browser may send audio to its own speech service; CareerPilot does not collect or store a raw audio file. Do not speak sensitive information; Gemini also receives the transcript.

The new Alembic migration `b7c8d9e402f1` adds `interview_sessions.mode` with default `text`; existing interview sessions, answers and reports remain intact. Existing answer `input_mode` distinguishes speech-derived (`voice`) and typed (`text`) answers, but this is client-reported metadata, not proof of audio origin. Recognition output can be edited before submit. AI evaluation and communication feedback judge the transcript, not pronunciation, tone, accent or audio quality.

Questions, submitted answers, evaluation and reports survive refresh. **Unsubmitted transcripts are held only in the current page and are lost on reload or navigation.** On a failed evaluation, the submitted transcript stays saved; retry evaluation. End interview asks for confirmation and marks a voice interview abandoned; saved data stays in history but the interview cannot be resumed and no final report is created. For a report, finish or skip each question and select Finish & generate report. Navigating back without ending leaves it resumable.

## Browser compatibility and privacy

Use HTTPS and grant microphone permission when clicking Speak answer. Support for Web Speech Recognition is browser/OS/service dependent and may need an internet connection. Desktop Chrome is a practical first choice, but support and accuracy are not guaranteed; Firefox and other unsupported browsers can type a response. A denied permission should be changed using browser site settings. Recording ends before transcript editing/submission and is aborted when leaving/changing questions. Automatic speech may be blocked by browser autoplay policy; use Repeat question. Voice output and available voices depend on device settings. Some browsers send audio to a third-party recognition service (such as their browser vendor); consult its policy before using sensitive data.

## Existing Render deployment

No new environment variables or voice vendor keys are required. Keep the existing `DATABASE_URL`, optional `MIGRATION_DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, `GEMINI_API_KEY` and `GEMINI_MODEL`. The user's working Gemini model is `gemini-3.5-flash-lite`; do not reset secrets, recreate the database, or change URLs. Model availability/quota and pricing can change.

1. Back up the Neon database / create a recoverable restore point before applying migrations.
2. Upload the updated source to the existing repository, preserving `careerpilot-neon-render/`. The full source ZIP includes that single folder and no `.env`/credentials or installed dependencies. In GitHub browser upload from repository root, the paths must begin `careerpilot-neon-render/`. Do not place the folder inside another copy of itself. Upload replaces matching files but will not delete unrelated extra files.
3. Existing backend root `careerpilot-neon-render/backend`, build `pip install -r requirements.txt`, and start `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` remain unchanged. The migration runs before the app starts. Confirm latest backend deployment is Live and the migration ran; the health database endpoint checks connectivity only, not migration level.
4. Existing static frontend root `careerpilot-neon-render`, build `npm ci && npm run build`, publish `dist`, API base URL and SPA rewrite remain unchanged. Wait until frontend is Live on the intended commit. Backend and frontend may deploy simultaneously when uploading the complete folder; avoid testing until both finish.
5. On HTTPS, sign in → Real interviews → New voice interview → set role/type/difficulty/experience → create draft → Start voice interview. Click Speak answer, allow mic, speak, stop, edit transcript, submit, continue, and generate a report. Test Repeat question and try refresh/resume. Verify text interview and local demo remain functional. A real Gemini request uses the project's quota and may have billing implications.

Automated tests mock Gemini and browser speech; they do not validate a real user's microphone, device-specific permission prompt, browser vendor's transcription service, or actual Google API request. Do not claim a live deployment before deploying, or real voice recognition without a real browser/microphone test. Never share keys, tokens or screenshots of environment variable values.

## Tests

```
npm ci && npm run build
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

SQLite automated tests cover ownership, legacy data migration and mocked Gemini. `tests/e2e/phase3-voice.cjs` uses a locally mocked SpeechRecognition and SpeechSynthesis; `tests/e2e/phase2-browser.cjs` tests text and demo. To rerun use a fresh local test database, migrate it, start `backend/tests/support/mockserver.py` (test-only, never deploy) at port 8000, start Vite at port 5173, install Playwright locally without saving and run the scripts. See PHASE2.md for test-server setup. PostgreSQL migration preservation should also be tested against a disposable database before production.
