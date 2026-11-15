# ICTRoot AI contributor instructions

This repository is separate from MathRoot. Work only here. Never copy credentials, modify another project or reuse its Supabase database.

## Architecture

- `frontend/`: Next.js 16 App Router, React 19, TypeScript, Tailwind 4 and Lucide icons. Read frontend/AGENTS.md and installed Next.js documentation before framework changes.
- `backend/app/main.py`: FastAPI endpoints, server authorization and transaction boundaries.
- `models.py`, `database.py`, `schemas.py`: SQLAlchemy schema, bounded PostgreSQL pooling and Pydantic contracts. **Supabase PostgreSQL is the only application database. Do not restore a SQLite storage fallback.**
- `security.py`: scrypt passwords and opaque sessions. Roles come from PostgreSQL, never client input. Supabase storage does not imply Supabase Auth.
- `ai.py`: loopback Ollama, readiness checks, validated drafts and retrieval from reviewed resource embeddings. No student data in AI prompts/logs.
- `verification.py`: deterministic marking; no eval or untrusted Python. SQL-answer marking deliberately uses an isolated in-memory SQLite exercise database with a restricted authorizer and instruction budget. It is never application storage.
- `curriculum/`: official NIE PDF and explicitly unverified extraction. Outcome IDs are application IDs, not NIE-issued IDs.
- `backend/migrations/`: immutable Alembic revisions. Add a new revision; never rewrite an applied one.
- `backend/.env.example`: canonical backend configuration template. Real credentials and migration backups stay ignored.

## Commands (Windows Command Prompt)

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.venv\Scripts\python.exe -m app.check_database
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Separate terminal:

```cmd
cd /d E:\ictrootai\frontend
npm ci
npm run dev
```

Validation:

```cmd
cd /d E:\ictrootai\backend
set TEST_DATABASE_URL=YOUR_SEPARATE_DISPOSABLE_POSTGRESQL_CONNECTION_STRING
.venv\Scripts\python.exe -m pytest -q
set TEST_DATABASE_URL=
cd /d E:\ictrootai\frontend
npm run typecheck
npm run build
npx playwright test generation-readiness.spec.ts
```

Never put actual passwords in tracked files or printed output. Tests require explicit `TEST_DATABASE_URL`; never implicitly reuse `DATABASE_URL` or a SQLite fallback. Generated test schemas must be constrained and cleaned without touching unrelated schemas. Full workflow browser tests require disposable seeded accounts and alter their records.

## Rules

- Verify curriculum wording, competency mapping and source page before marking an outcome verified. Do not claim full syllabus coverage prematurely.
- Student responses before submission must exclude answer keys, explanations, rubrics and distractor misconception labels.
- Assessments use approved immutable questions. Changes require a new draft.
- Enforce class ownership/student membership. Keep save/submit ordering and duplicate-submission protection transactional.
- Descriptive scores remain pending until teacher review. AI confidence is not proof.
- Never execute student SQL/Python against application PostgreSQL. Keep the exercise grader isolated.
- Never use external AI endpoints/cloud-backed Ollama models or download models automatically.
- Preserve English originals and technical identifiers in Sinhala translations. Unreviewed text never appears as reviewed content.
- Keep credentials server-side, TLS enabled, pools bounded and browser roles denied. Do not grant broad Data API privileges to solve a server-connection problem.
- Keep `.env`, databases, backups, sessions, local passwords and dependency directories untracked.
- Preserve legacy records before cleanup. A backup is necessary until PostgreSQL import commits and verification succeeds; never delete the only copy.
- Update IMPLEMENTATION_STATUS.md. Distinguish historical SQLite test runs, current PostgreSQL results, skipped tests and actual remote connection checks.
- Run relevant backend tests, typecheck and build. Report checks actually run. Continue unrelated work when credentials are missing and identify the exact remaining connection requirement.
