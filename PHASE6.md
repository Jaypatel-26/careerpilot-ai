# CareerPilot AI — Phase 6: Career Roadmap and Skill Gap Analysis

This update builds on the rollback-compatible Phase 5 project. The existing demo and account pages, authentication, interviews, voice, resume analysis and job matching remain in place; it does not add Supabase or reinstate Adzuna. Phase 6 adds an account-owned **AI career roadmap** in the existing sidebar, with Career Roadmap, Skill Gap, Learning Progress and AI Mentor pages.

## Before deploying

1. Back up the Neon production database/branch and verify how to restore it. This release adds `career_plans` using migration `f63a029e481b` after compatibility migration `e914a0b7f2d3`; no existing data needs to be deleted. The latter migration is deliberately retained so that both databases which saw the Adzuna-era release and older Phase 5 databases have a continuous migration history. It may create an **unused** `job_source_cache` table on older databases; Phase 6 does not use Adzuna.
2. You need an existing working Gemini key and model on the backend. The same `GEMINI_API_KEY`, `GEMINI_MODEL` and timeout settings used by previous phases are reused. No new AI key is required. **Real Gemini roadmap and mentor requests have not been tested for this release**, because a real key was not available during implementation. Structured output, duration, quota, model compatibility and quality must be verified in your own deployment; a mocked test is not proof of live success.
3. Keep `DATABASE_URL`, optional `MIGRATION_DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ALLOWED_ORIGINS` and existing settings. Do not share or commit keys, database URLs, passwords or screenshots of their values. The migration URL, if configured, must point to the same Neon database and branch as the app and have permission to migrate.

## Mac / GitHub browser upload

1. Unzip the complete Phase 6 ZIP. Open the `careerpilot-neon-render` folder. Its **contents** include `package.json`, `src`, `backend`, and `render.yaml` at the same level.
2. In the existing GitHub repository, open the repository **root** and intended branch. Click **Add file → Upload files** and drag the **contents** of `careerpilot-neon-render`, not the outer folder, into the upload area. Commit the changes. If folders fail to upload, use smaller batches while preserving the paths. GitHub web upload overwrites matching files but does not automatically delete extra files already in the repository.
3. Verify these exact paths exist on GitHub: `backend/migrations/versions/e914a0b7f2d3_job_source_cache.py`, `backend/migrations/versions/f63a029e481b_career_roadmap.py`, `backend/app/api/career.py`, and `src/features/career/Career.tsx`. Check that `package.json` is at the root. Do not upload `node_modules`, `.venv`, local databases, or real `.env` files. Show hidden files in Finder with Command-Shift-period if necessary; `.env.example` is not a secret.

## Render deployment

1. Deploy the new commit to the **existing backend** service. Its root directory should be `backend`, build command `pip install -r requirements.txt`, and start command:

   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

   The migration runs before the app starts. In Render logs confirm a successful startup and that the deploy is using the new commit. If migration fails, stop and investigate. **Do not delete tables, downgrade, edit `alembic_version`, or use `stamp`** as a shortcut. Migrating requires the appropriate Neon privileges. The new table has PostgreSQL row-level security enabled without a public policy, like prior tables; the backend database role needs the required access (the table owner normally bypasses RLS). The application enforces user ownership on every request; RLS is not a replacement for application authorization.
2. Deploy the **frontend** from the same commit. Preserve its existing `VITE_API_BASE_URL` (the public backend URL ending in `/api/v1`) and backend `CORS_ALLOWED_ORIGINS`. PUT was added to allowed CORS methods for saving goals.
3. Log in, select **AI career roadmap**, set and save a goal, and generate a plan. Open Skill Gap, Learning Progress and AI Mentor. Test task completion and refresh, then test a second account cannot see the first account's plan. Also verify an existing interview, resume report and job match. If Gemini fails, check server logs and quota/settings without sharing any secrets. Do not interpret mocked test results as a live Gemini verification.

## Use and limitations

- One active plan per account. Select role, current skill/experience levels, 0.5–8 daily hours, 1–8 weeks and learning style; add current skills and optionally select your own saved resume analysis and job match. Paste reviewed resume text optionally for better evidence. Earlier resume analysis stores generated analysis, not the original resume; strengths and quoted examples from that report are fallible and not proof of skills. The selected match is AI-generated and may contain errors. An absent skill is **not evidenced**, not proof it is absent. Estimated proficiency, priority, time and resources are suggestions, not guaranteed accuracy, mastery, job placement or selection.
- Each week requests seven daily tasks, with exercise, revision, project and interview practice when feasible. The AI output must have the correct weeks/days and valid skill references or the server rejects it without replacing the existing plan. Actual output and estimated times may be unrealistic or miss details. The one-to-eight-week limit bounds output and cost; choose shorter plans if generation fails or times out. No claim is made that the AI response will always be valid.
- Mark tasks complete or incomplete on Learning Progress. Daily count is based on currently completed tasks' most recent completion date in UTC; unchecking removes that completion from the count. It is not a full historical activity log. Weekly counts are based on the AI-assigned week, not calendar dates. The “skills with tasks completed” count means all assigned tasks for a skill were checked; it does **not** certify mastery. Skills with no assigned task remain counted as remaining. The next recommendation is the first unchecked task in plan order.
- Saving a changed goal keeps the previous roadmap and marks it out of date. Regenerating requires confirmation and **replaces the previous plan and its task progress** only after a successful AI response. No previous versions or mentor conversation history are saved. Each account's data is restricted via the existing JWT and owner-scoped database queries. The implementation stores a goal and generated plan, including task statuses and completion timestamps, in Neon; users should avoid entering sensitive data not needed for career planning.
- Original verified resume text is sent to Gemini when supplied, but is not stored as a separate record; generated roadmap text may contain personal details. Goal/current skills, selected report evidence and selected job-match data are sent to Gemini for generation. Mentor requests send the question, goal, plan summary, skills and weekly task details. Mentor questions and replies are not saved by this application. Provider retention policies, logs, database backups and exports are separate considerations. A hash of generation input is stored for retry deduplication.
- Tasks only link to a small **curated registry**; model-generated URLs are never published as resource links. Most are official docs or free sources; some sites have paid material. At implementation-time 13 of 14 links responded HTTP 200; LeetCode returned 403 to the checker and is marked unverified in the UI. Links and availability can change, and the AI can choose an irrelevant resource or none; check independently. AI mentor text is plain text and may still be inaccurate.
- AI calls reuse the existing process-local per-user AI rate limit. It is not a distributed production rate limiter. Existing token storage, authentication, backup, security, accessibility and privacy limitations in previous phase documentation still apply. Review before production use. Do not run test-only `tests/support/career_mockserver.py` in production.

## Verification performed

- 39 backend tests passed, including all existing tests and new goal, plan, progress, regeneration, mentor, error and account-isolation cases. AI was mocked.
- React/TypeScript production build passed. Vite reported a large bundle warning.
- Playwright tests passed for Phase 2 demo/interview, Phase 3 voice fallback, Phase 4 resume, Phase 5 jobs and Phase 6 career flow with mock AI. A 390 px mobile goal-page overflow check passed. These do not prove every browser or every earlier feature.
- A disposable PostgreSQL database was upgraded from `d6a3b8f710e2` through `e914a0b7f2d3` to `f63a029e481b`; a pre-existing user remained, RLS was enabled, and account isolation plus mocked plan/progress operations passed. SQLite migration and tests passed too. Your Neon privileges and deployment have not been independently verified.

## Main changed files

- `backend/app/models/career.py` and `backend/app/models/__init__.py` — account plan model.
- `backend/migrations/versions/f63a029e481b_career_roadmap.py` — additive migration.
- `backend/app/schemas/career.py`, `backend/app/services/career.py`, `backend/app/api/career.py` — validation, curated resources, Gemini prompts and protected endpoints.
- `backend/app/main.py` — router, no-store response and PUT CORS method.
- `src/features/career/Career.tsx`, `src/main.tsx`, `src/style.css` — four account pages, navigation and styles.
- `backend/tests/test_career.py`, `backend/tests/support/career_mockserver.py`, `tests/e2e/phase6-career.cjs` — automated checks; mock server is test-only.
- `PHASE6.md` — these instructions. Earlier phase docs remain in the project.
