# Phase 4 — account-backed AI resume analysis

## What is new

The original `/resume` remains a local-only demonstration. The separate `/account/resume` page requires sign-in and lets users upload a PDF or DOCX (or paste text), edit extracted text, optionally paste a job description, generate and save a report, open/delete saved reports, and download a plain-text report. It uses the existing Neon account database, JWT authentication and server-side Gemini configuration. No Supabase is used.

The server sends the edited resume and optional job description to Gemini in one request. Reports cover estimated overall/ATS scores, strengths, gaps, grammar, projects, experience, education/skills, formatting, action verbs, measurable-achievement ideas, and bullet rewrites. Job comparison includes estimated match, evidenced/missing skills and keywords, uncovered requirements, targeted suggestions and project ideas. Unverified suggestions are not facts. The model is instructed not to invent details, but AI is fallible; users must review all output. The server suppresses rewrites whose quoted “before” text is not found in the supplied resume, but this cannot guarantee the suggested rewrite is truthful.

Uploads are limited to 5 MiB, PDFs to 12 pages, resume text to 20,000 characters, job descriptions to 12,000 characters. Extraction runs in a separate short-lived process with timeout and, on Linux, CPU and memory limits. The upload handler checks filename extension and signature and DOCX ZIP structure, not the browser-supplied MIME alone. The server temporarily buffers uploads (the web framework may spool them to temporary disk); it does not intentionally keep the original file or extracted text as account records. Gemini output can quote resume text and is retained in the saved report until deletion. Provider retention follows Google's terms and configuration. Don't use sensitive documents without considering privacy. Text from complex layouts, headers, footers, text boxes and images may be lost or reordered; users should review it. OCR is not implemented; scanned/image-only PDFs are unsupported.

## Deploy safely on existing Render + Neon

1. **Back up Neon first** (a branch/restore point or another tested backup). The migration adds a table and does not deliberately touch earlier interview data; backups are still essential. Never paste secrets into GitHub or share them in screenshots.
2. Download and unzip the complete Phase 4 ZIP. In your GitHub repository, open the existing `careerpilot-neon-render` folder and upload the **contents** of the ZIP's `careerpilot-neon-render` folder into that same location, preserving directories and replacing matching files. Do not upload an extra nested `careerpilot-neon-render` folder. Keep your existing local copy and personal files until the new deployment is verified. GitHub's browser may require uploading files inside individual subfolders; ensure new files are present. Commit the change.
3. In the existing Render **backend** web service, retain current root directory, environment variables (including Gemini key/model, database URLs, JWT secret, and CORS origins), and start command. Ensure the build command installs `backend/requirements.txt`; three new production packages are needed. The existing start command is:

   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

   Here the service root is the existing `careerpilot-neon-render/backend` directory. If the repository root is configured differently, use the actual existing backend root setting instead of nesting directories. Deploy the new commit. Alembic applies additive revision `c4d7e3f912a0` after `b7c8d9e402f1` on startup. Check the deployment logs for successful migration/start and `/api/v1/health/database` for connection health. Do not run downgrade casually: it deletes saved resume reports.
4. Deploy the existing frontend static site from the same commit. Keep its current project root (`careerpilot-neon-render`), `npm ci && npm run build`, publish directory `dist`, backend API URL setting, and SPA rewrite `/*` to `/index.html`. Backend should be live before using the new page.
5. Sign in, open **AI resume analysis**, upload a non-sensitive text-based PDF or DOCX, review/edit the text, add an optional job description and analyze. Verify a saved report opens after refresh and can be downloaded/deleted. Test an earlier text and voice interview. Test with a second account that reports cannot be opened or deleted across users. If AI is unavailable, check Render logs and configuration without exposing secrets; model/schema/provider behavior and quota are external dependencies.

### Database role and RLS

`resume_reports` enables PostgreSQL row-level security without adding public policies, consistent with the existing server-owned tables. Account isolation is enforced by backend queries filtered by the authenticated `user_id`; the backend database role must be the table owner or otherwise have appropriate RLS bypass and table privileges. PostgreSQL table owners normally bypass RLS; a separate migration role can leave the application role unable to access the table, and `FORCE ROW LEVEL SECURITY` changes behavior. Do not grant public policies or disable RLS to work around a deployment error. Confirm the actual Neon migration/app role setup and grants with your database administrator. The migration test used one owner role; a granted non-owner role saw zero rows. This is not a replacement for production role verification.

## Changed/new files

- `backend/requirements.txt`, `backend/requirements-test.txt`
- `backend/app/models/resume.py`, `backend/app/models/__init__.py`
- `backend/migrations/versions/c4d7e3f912a0_resume_reports.py`
- `backend/app/schemas/resume.py`, `backend/app/services/gemini.py`
- `backend/app/services/resume_extract.py`, `backend/app/services/resume_extract_worker.py`, `backend/app/api/resumes.py`, `backend/app/main.py`
- `src/features/resume/ResumeAnalyzer.tsx`, `src/main.tsx`, `src/style.css`
- `backend/tests/test_resume.py`, `backend/tests/support/mockserver.py`, `tests/e2e/phase4-resume.cjs`, `tests/fixtures/sample-resume.docx`
- `package.json`, `package-lock.json` (Playwright test dependency), `PHASE4.md`

## Tests and limitations

At delivery: frontend TypeScript/Vite production build passed (existing large-chunk warning); 28 backend pytest tests passed (existing Starlette/httpx deprecation warning). Real generated PDF/DOCX extraction, malformed/oversized/scanned files, mocked Gemini with/without JD, idempotent retry, ownership, provider quota and deletion were covered. Chromium browser tests covered the new page with mock AI and DOCX extraction, and earlier demo/text/voice flows with mock AI and simulated browser speech. A disposable PostgreSQL 17 upgrade from Phase 3 preserved a voice transcript and interview report, created a report, and verified RLS for a non-owner. SQLite migration upgrade/downgrade is in the test suite.

**No real Gemini request, Neon production migration, live deployment, real microphone, or actual ATS screening was tested for Phase 4.** Verify these after deployment. ATS/job scores are estimates only and do not guarantee ATS or hiring outcomes. Output can omit details, hallucinate, or be affected by prompt injection despite instructions. Scrutinize every recommendation and only include true claims and verified numbers. Rate limits are per process, not shared across workers; use a shared rate limiter and edge request-size controls for production scale. Uploads require Content-Length and large requests are rejected before parsing; reverse proxies should enforce size and request-duration limits too. The first 100 newest reports are shown; the API supports limit/offset pagination. Analysis retry deduplication is per request ID and retained while the page stays open; refreshing after an ambiguous failure can result in another charge/report. A provider error after generation or database failure can also cost a call without saving a report.

For local tests: `cd backend && pip install -r requirements-test.txt && pytest -q`; frontend: `npm ci && npm run build`. Browser tests additionally require `npx playwright install chromium`, a disposable migrated SQLite database and `tests.support.mockserver` running locally; the mock server must never be deployed as production. Avoid pointing tests at a real database.
