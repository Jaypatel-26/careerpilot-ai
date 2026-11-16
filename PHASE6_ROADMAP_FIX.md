# Phase 6 — roadmap generation compatibility update

The reported error `AI provider configuration is unavailable` is returned for several Gemini HTTP errors (400, 401, 403 and 404), so it does not identify one definite cause. In particular, it does not prove that the API key is wrong. This update reduces one possible source of HTTP 400: the career roadmap's large, nested Gemini response schema is simplified before sending it to Gemini. The original Pydantic schema is still used to validate the returned data locally, and all existing weekly/task/skill checks remain in place. An invalid response is rejected rather than saved.

The shared Gemini adapter now logs only a sanitized status number and operation class for provider API errors, for example `Gemini provider response: status=400 operation=RoadmapAI`. It does not intentionally log provider response bodies, prompts, resume text or keys. Existing API messages and other Phase 1–6 functionality are otherwise unchanged. This is a compatibility attempt, not a guarantee or a confirmed diagnosis: real Gemini requests were not available for testing.

## Deploy

1. Back up the Neon database. There is **no new database migration** in this fix; preserve all existing migrations and settings. Do not alter database tables or `alembic_version`.
2. Unzip the complete project ZIP. At the root of your GitHub repository, upload the **contents** of `careerpilot-neon-render` rather than nesting the enclosing folder. Commit changes. At minimum check `backend/app/services/career.py` and `backend/app/services/gemini.py` are updated in GitHub.
3. Redeploy the existing Render **backend** from the new commit. Keep its current `DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, `GEMINI_API_KEY` and `GEMINI_MODEL` settings. No frontend changes are required by this fix.
4. After the backend deploy finishes, log in, open AI Career Roadmap, save a goal and try generation. Start with one or two weeks to reduce output length while diagnosing. The exact same error may still occur for other reasons.
5. If it fails, open the backend's Render Logs around the failed attempt and look for `Gemini provider response`. Share only the status number and operation if seeking help; never share the provider body, API key, database URL, resume, JWT or other secrets. Status 400 can indicate an invalid request or schema; 401/403 can indicate an API key or permission issue; 404 can indicate an unavailable model; 429 is a quota/rate limit. These are possibilities, not proof. Check the configured model and Google AI Studio access privately. A 502 invalid response or timeout may require a separate investigation.

## Verification

41 backend tests pass, including a simulated provider error verifying only safe diagnostic status/operation are logged, and schema-simplification tests confirming local validation remains. Existing backend tests remain green. No real Gemini credentials were available; neither the live provider response nor a successful live roadmap was verified. The previous Phase 6 frontend build and mock browser tests passed; this update changes no frontend code. See `PHASE6.md` for full deployment, security, privacy and feature limitations.
