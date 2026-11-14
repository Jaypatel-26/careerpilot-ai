# More real job sources — setup and deployment

This update keeps the Phase 5 job features and earlier phases. It adds three Greenhouse company boards to the existing GitLab and Figma defaults and an optional Adzuna India integration. The default search displays both providers in the **same opportunity list**. Source-specific views are available from the dropdown. The original demonstration jobs remain separate and labeled.

## Before deploying

- Back up the Neon production branch first, and make sure you can restore it. The additive migration `e914a0b7f2d3` creates `job_source_cache`; it follows Phase 5 migration `d6a3b8f710e2`. It does not intentionally replace existing tables.
- The default Greenhouse boards are `gitlab,figma,stripe,coinbase,airbnb`. If `GREENHOUSE_BOARD_TOKENS` already exists on Render, **that value overrides the new defaults**. Update the existing value if you want all five; it accepts at most five unique verified tokens. Greenhouse listings and external destinations can change or close.
- Adzuna is optional. Before enabling it, register with [Adzuna's developer portal](https://developer.adzuna.com/overview), and check its current [terms and licence requirements](https://developer.adzuna.com/docs/terms_of_service). The terms describe a limited evaluation tier and require a licence for certain uses, including commercial, revenue- or lead-generating products, and after applicable trial periods. Confirm the appropriate permission and that the integration meets all current attribution and data-use requirements with Adzuna. This document is not legal advice.
- Do not put credentials, database URLs, JWT keys, or Gemini keys in GitHub or share them in chat. Never use a `VITE_` variable for Adzuna credentials.

## Upload this complete project on a Mac

1. Unzip the delivered ZIP. Open its `careerpilot-neon-render` folder. The project root contains `package.json`, `src`, `backend`, and `render.yaml` side by side.
2. Open your existing GitHub repository in a browser, at its **root**, on your intended branch. Choose **Add file → Upload files**. Drag the **contents** of `careerpilot-neon-render` into the upload area, not the enclosing folder itself; otherwise GitHub can create a nested project. If the browser has trouble uploading a folder, upload its contents in smaller batches, preserving all folder paths. Allow GitHub to replace files with the same paths and commit all updates.
3. Check on GitHub that `src/features/jobs/Jobs.tsx` and `backend/migrations/versions/e914a0b7f2d3_job_source_cache.py` appear at those exact root-relative paths, alongside `package.json`. Do not upload `node_modules`, `.venv`, real `.env` files, or local databases.
4. GitHub may not pick up hidden files when selecting in Finder; `.env.example` and `.gitignore` are examples, not secret settings. Show hidden files with Command-Shift-period if you need them. Existing repository settings/hidden files should remain in place.

## Render backend and frontend

1. Open the existing **backend** web service on Render. Under **Environment**, keep the existing `DATABASE_URL`, `MIGRATION_DATABASE_URL` if used, `JWT_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, Gemini settings and all other working values unchanged. Set `GREENHOUSE_BOARD_TOKENS` to `gitlab,figma,stripe,coinbase,airbnb` if it is currently set to the old two boards. If this variable is not set at all, the five-board default is used.
2. To enable Adzuna, after confirming your permission/licence, add `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` to the **backend** Render environment with your own registered credentials. Leave them absent or blank to keep Adzuna disabled; Greenhouse still works. Never add the values to the frontend, repository or screenshots.
3. Deploy the updated commit to the backend. Confirm root directory is `backend`, build command is `pip install -r requirements.txt`, and start command is:

   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

   The migration runs before the API starts. Check deploy logs for a successful start without copying secrets. If the migration fails, stop and investigate before using the new frontend; do not delete existing tables to force it. If using `MIGRATION_DATABASE_URL`, it must point to the same intended Neon branch/database and have migration permissions.
4. Deploy the frontend from the same commit. Its existing public build-time `VITE_API_BASE_URL` must remain the backend API URL ending in `/api/v1`. The backend CORS setting must still include the exact frontend origin without a trailing slash. These are separate services; both must be updated.
5. Log in, open **Find real jobs**, and search broadly. With Adzuna configured, choose **Both sources** to see the two providers in the same list. If Adzuna is not configured or fails, a warning appears while available Greenhouse results remain. Search for `India`, or select Adzuna India; click a job and use its external application link. Apply on the destination website yourself. To test AI match, first save a resume analysis, open a job and generate a match; treat the score as guidance only. Verify provider and Gemini behavior in your own deployment.

## How it works and limits

- Greenhouse fetches public employer boards, not the entire internet. Adzuna uses its India search API; neither includes verified Unstop coverage. The app does not invent listings or links. URLs are allowed only when HTTPS and pass basic safety checks; some provider results with missing, HTTP-only, or unsafe links will show **Apply link not available**. Listings may be duplicates across sources, stale, expired, or no longer accepting applications. Confirm details on the destination.
- A combined page requests a page of up to 20 from each source (up to 40 cards), with independent provider pagination. The larger provider count determines whether a next page exists; it is not a deduplicated combined total. Search result counts from Adzuna are before local filters. Company, skill, workplace and experience filters apply **only to each returned Adzuna page**, so an empty page does not mean no later matches. Skills are text mentions; workplace and experience are inferred and may miss jobs. The UI limits browsing to a bounded offset.
- Adzuna descriptions are excerpts, so detail and Gemini matching may miss requirements. Sending the selected job, saved resume report and optional verified resume text to Gemini is necessary to generate a match. Matches are estimates, not hiring guarantees. Live Adzuna calls and Gemini job matching were not verified during this update because credentials were unavailable; mocked tests do not verify an external service or licensing.
- Adzuna search data has a short in-process response cache and database snapshots for detail pages. Snapshots expire after 30 minutes and are deleted during later searches, not by a continuously running cleanup job. A saved job or AI match retains its snapshot until removed; search again to refresh an expired detail. Users can remove their own saved jobs and matches. Adzuna attribution links appear with its listings, including saved jobs and matches.
- The Adzuna per-user request limit is process-local, not a distributed production rate limiter. The application is still a prototype; production use needs security, abuse controls and privacy review. Failed providers are reported rather than fabricated.

## If Adzuna permission ends or data must be removed

1. Stop access to Adzuna and remove **both** Adzuna credentials from the backend Render environment. Restart/redeploy all workers to clear their in-memory caches. This immediately disables Adzuna searches and hides its saved/match snapshots from normal reads, but **does not erase the database**.
2. Obtain a verified database backup first. The next command is irreversible and deletes **all users'** Adzuna cached snapshots, saved jobs and Adzuna match reports, including generated match content. Coordinate notices, retention and backup removal with your obligations and Adzuna. Ensure no Adzuna-enabled old worker can repopulate data. Verify any exports, logs, replicas and backups separately; this script only affects the connected database.
3. Run from the deployed backend environment with its existing `DATABASE_URL` and installed requirements, for example in an authorized Render Shell (availability depends on plan). From the `backend` directory, first run `python -m scripts.purge_adzuna` to see the no-change warning, then, only when ready, run `python -m scripts.purge_adzuna --confirm-delete-all-adzuna`. The database user must have permission to delete all matching rows, including through any RLS policies. Verify the printed counts and absence of Adzuna data. If Render Shell is unavailable, use a trusted local backend environment securely configured to access the correct Neon database; do not paste its URL into a public terminal log or GitHub. A database administrator can help verify the target and permissions.
4. The script does not clean old backups or records saved outside this application's three tables. Handle those according to your licence, privacy obligations, and backup policy. Do not turn the provider back on without valid permission.

## Test notes

This update passed 38 backend tests, frontend typecheck/build, and mocked browser tests covering combined results, attribution, job detail, saved jobs and earlier Greenhouse matching. These tests use fictional providers and mock AI. A SQLite dry-run/confirmed purge was tested; verify PostgreSQL permissions and migration in your own environment. The Vite build reports a large JavaScript chunk warning; it is not a build failure.

See `PHASE5.md`, `PHASE4.md`, `PHASE3.md` and `PHASE2.md` for earlier features and deployment context. Where older Phase 5 documentation describes only two boards or only Greenhouse, this document describes the current behavior.
