# Phase 5 rollback — database migration compatibility fix

This is the original Phase 5 application, without the later Adzuna integration or extra default company boards. The only application-project addition is `backend/migrations/versions/e914a0b7f2d3_job_source_cache.py`, retained exactly as originally shipped. It lets Alembic recognize databases that have already applied the Adzuna-era migration. The application does not use Adzuna. The unused cache table may remain in the database; keeping it avoids deleting any data. If the database is older, upgrading creates that unused table too so the revision has the same meaning across environments.

## Deploy safely

1. Back up the Neon database branch before deploying. Do not delete tables, edit `alembic_version`, run `alembic stamp`, or use `alembic downgrade` to fix this error.
2. On Mac, unzip this project and open the `careerpilot-neon-render` folder. In GitHub open the existing repository root, select **Add file → Upload files**, and drag the folder's **contents**, not the enclosing folder, into the browser. Commit the changes. Browser uploads replace matching files but do not automatically delete old extra files; the old Adzuna adapter, tests or documentation, if left in the repository, are unused by this restored application. Do not upload any real `.env` or secret files.
3. Check that GitHub contains `backend/migrations/versions/e914a0b7f2d3_job_source_cache.py` at that exact path, `backend/app/api/jobs.py`, and `src/features/jobs/Jobs.tsx`; also check `package.json` is at the repository root. The backend service's root directory must be `backend` and it must deploy this new commit, not an earlier commit. GitHub's source/commit ID on Render should match your latest commit.
4. In Render's backend service, retain the existing database, JWT, CORS and Gemini environment settings. If `GREENHOUSE_BOARD_TOKENS` was explicitly set to five boards during the update and you want the original two, change it to `gitlab,figma`. If it is not set, the original app defaults to those two. Remove `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` from backend Render environment if you previously added them; the restored app does not use them.
5. Deploy the new backend commit. Keep the existing startup command:

   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

   Check Render logs for a successful start. Deploy the frontend from the same commit, preserving its existing API base URL and backend CORS configuration. Sign in and check jobs and earlier features.

Retaining the migration does not purge previously acquired Adzuna data. If the provider was actually used and its data must be removed for licensing/privacy reasons, arrange a separate careful, backed-up cleanup of the Adzuna cache, saved jobs, match snapshots, and applicable exports/backups. Do not blindly delete tables or all saved jobs.

## Verification

The original backend test suite passed (34 tests) against the compatibility project. The upgrade was tested with a disposable SQLite database previously migrated to `e914a0b7f2d3`; the restored project recognized the revision and `alembic upgrade head` succeeded. This does not verify your Render/Neon deployment or PostgreSQL permissions. The migration is retained, not rolled back, so future migrations must continue from `e914a0b7f2d3`.
