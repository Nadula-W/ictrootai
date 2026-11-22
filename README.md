# ICTRoot AI
| Role | Email |
|---|---|
| Student | `student@ictroot.local` |
| Teacher | `teacher@ictroot.local` |
| Admin | `admin@ictroot.local` |

Demo passwords are private. Use the password saved during seeding, or reset the development demo accounts with `python -m app.reset_demo_password`. Never publish live passwords in this file.

A Sri Lankan A/L ICT learning and assessment application with a Next.js frontend, FastAPI backend, **Supabase PostgreSQL application database**, and local Ollama AI. The application has no SQLite storage fallback.

**The 2017 source catalogue has been checked:** 14 units, 82 competency levels and 368 explicit learning outcomes, including nine IoT outcomes omitted by the old extraction. All original candidate IDs are preserved. Source verification is separate from question coverage: the existing bank has seven demonstration questions, and a later examination year's applicability is not yet officially confirmed. See [the curriculum audit](curriculum/README.md) and [implementation status](IMPLEMENTATION_STATUS.md).

![Student workspace](docs/student-dashboard.png)

## Start the application

Use two **Command Prompt** terminals after the database setup below.

Backend:

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```cmd
cd /d E:\ictrootai\frontend
npm run dev
```

Open **http://localhost:3000**. API documentation is at **http://127.0.0.1:8000/docs**. Keep both terminals open; Ctrl+C stops each service. Ollama uses **http://127.0.0.1:11434**.

## First-time setup

Install Node.js 24 LTS, Python 3.13 and Ollama for Windows. Commands below use Command Prompt and a project-local virtual environment.

```cmd
cd /d E:\ictrootai\backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
if not exist .env copy .env.example .env
```

Edit **backend/.env** using your separate ICTRoot Supabase project's connection settings. **backend/.env.example** is the canonical backend template; the former root template and separate PostgreSQL template are redundant.

The separate [ictroot-ai Supabase project](https://supabase.com/dashboard/project/zbugipqjwamlrgdyycpr) is created, migrated to revision `0002` and populated with the 434 preserved records. The private backend connection is saved and live teacher/student login and database health have passed. Use the startup commands above normally; no repeated connection entry is needed. For a new installation or credential recovery, use `.venv\Scripts\python.exe -m app.configure_database`. See [the connection guide](docs/SUPABASE.md).

This computer currently uses saved `DATABASE_TRANSPORT=supabase_websocket` because raw PostgreSQL negotiation stalls on its network. The same Supabase database is reached over certificate-verified port 443, with PostgreSQL TLS still enabled. No network switch or repeated password entry is needed. New installations default to direct PostgreSQL TCP; see the connection guide for both modes.

```dotenv
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:URL_ENCODED_DATABASE_PASSWORD@POOLER_HOST:5432/postgres?sslmode=require
```

Copy the exact host, port and username from **Supabase Dashboard → your ICTRoot project → Connect → Session pooler**. Session pooling suits a persistent backend on Windows IPv4 networks. Replace the password and percent-encode reserved characters. Keep TLS enabled. See [Supabase's connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

The database password belongs only in the ignored backend environment file. A Supabase API URL or publishable key is not a PostgreSQL connection string. No database password or service-role key belongs in frontend configuration.

Check the connection, then apply migrations:

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m app.check_database
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
```

If PostgreSQL is missing or unavailable, database-dependent requests fail clearly. The app does not create a local database or silently change storage engines. Configure a separate ICTRoot project; the existing MathRoot project must remain untouched. See implementation status for the actual cloud connection state.

Frontend dependencies:

```cmd
cd /d E:\ictrootai\frontend
npm ci
if not exist .env.local copy .env.example .env.local
```

PowerShell setup/start scripts remain optional convenience wrappers. Normal startup uses the commands at the top of this file.

## Preserve existing records when switching databases

**This ICTRoot project's transfer is already complete:** 434 records are in Supabase. The following recovery-import instructions apply only to a different empty destination. Do not re-import or seed the populated project.

Existing accounts, password hashes, classes, resources and assessment records must be preserved before removing the former SQLite application file. A preserved source belongs in the ignored `backups/` directory, named like `sqlite-before-supabase-<timestamp>.db`. Do not commit, publish or share it.

After PostgreSQL migrations succeed, import the preserved source, replacing the filename below with the actual one:

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m app.migrate_legacy_sqlite --source "..\backups\sqlite-before-supabase-TIMESTAMP.db"
```

The importer is a one-time transfer tool, not a runtime database mode. Keep the backup until the import has committed and verification has succeeded. Migrated users retain their passwords. Do not seed a second copy of demo content over migrated records.

For an **empty development database only**, optional original demo content can be added with:

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m app.seed
```

Save the random password printed during seeding. Demonstration accounts are `student@ictroot.local`, `teacher@ictroot.local` and `admin@ictroot.local`. They use ordinary password authentication. Seeding is idempotent and disabled outside development. To reset only those development demo accounts:

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m app.reset_demo_password
```

## Teacher and student workflow

1. A teacher creates a class in **My classes** and shares its joining code. New classes use the grade selected in the teacher's Profile.
2. In **Question bank**, inspect approved questions or create a draft. Review its answer, explanation and sources before approval. The manual editor currently uses JSON; see [question format examples](docs/QUESTION_FORMATS.md).
3. In **Assessments → Create assessment**, choose a class, duration and approved questions, then publish. Questions may come from multiple outcomes.
4. Students join the class, start an assessment, save answers and resume interrupted attempts. Submission locks answers and reveals feedback.
5. Teachers open **Submissions** to inspect work, mark descriptive answers, override scores with a reason and export reports. Each question currently contributes a normalized score from 0 to 1.
6. Administrators manage roles, review syllabus outcomes, upload authorised notes, review resource chunks and configure local AI.

Progress and revision history come from submitted answers. Descriptive marks stay pending until teacher review. Distractor feedback indicates a possible misconception; one wrong answer is insufficient evidence of a persistent weakness.

## Local Ollama AI

The model discovered during original setup was **qwen3:4b-instruct**, which writes drafts. **EmbeddingGemma** supplies embeddings used to find relevant reviewed teaching passages.

Start the Ollama Windows app. Check the local service without downloading models:

```cmd
cd /d E:\ictrootai
backend\.venv\Scripts\python.exe scripts\ollama-smoke.py
```

If required models are absent, install them explicitly:

```cmd
ollama pull qwen3:4b-instruct
ollama pull embeddinggemma
```

Downloads never occur automatically. The 2026-11-15 diagnosis found the instruction model available, the embedding model missing and the reviewed demo note unindexed. See implementation status for later verification.

After installing the embedding model, sign in as administrator, open **Administration → Learning resources**, review the relevant note and click **Create local embedding**. Return to Question bank, select a **Verified:** outcome and click **Refresh AI status**. The UI explains missing prerequisites before enabling generation. Setup-only failures do not consume inference quota; actual generation attempts remain rate-limited.

Vectors are stored with source chunks in PostgreSQL and searched locally by cosine similarity for the selected outcome. Changing models requires reindexing. Only reviewed chunks with current-model vectors are retrieved. Generated questions remain drafts until teacher approval. No student details or answers are sent to AI; cloud-backed Ollama models are excluded.

With Ollama offline, approved questions, manual drafting and deterministic marking work **while PostgreSQL remains available**. Database availability and local AI availability are separate concerns.

## Curriculum and Sinhala content

The source is the [NIE A/L ICT syllabus effective from 2017](https://nie.lk/pdffiles/tg/eALSyl%20ICT.pdf), included in `curriculum/nie-ict-2017.pdf`. A 2026-11-14 search did not locate a newer official replacement; current examination applicability still requires confirmation.

The extraction records source hash, PDF page and review status. Its 359 candidates are not a certified official outcome count. Project lists competency levels but no bulleted outcome-column entries, so its outcome inventory is empty rather than invented. Competency/subtopic boundaries, continuation lines, later-unit numbering and grade mappings require review.

The supplied demo has one source-checked outcome and seven original questions, not past-paper questions. Coverage shows source verification, approved counts, formats, difficulty, Sinhala availability and review dates. No full-syllabus percentage is shown while the official inventory is unverified.

Sinhala display fields have a separate save/review workflow. Preserve English originals, option IDs, code, SQL and symbols. Missing/unreviewed Sinhala text produces a clear English fallback. Navigation is currently English.

## Database security and SQL-answer grading

Persistent application data uses **Supabase PostgreSQL through a private SQLAlchemy/psycopg backend connection**. The browser calls FastAPI through Next.js's same-origin `/api` rewrite. Authentication remains the app's scrypt/password and opaque-session implementation; storage migration does not introduce Supabase Auth JWTs.

Migrations enable RLS and deny direct browser-role access to application tables, sequence values and migration metadata. The backend must own application tables or use explicit server-role grants/policies. Do not grant broad `PUBLIC`, `anon` or `authenticated` access to solve a backend permission issue. Foreign-key/access-path indexes and pool limits are managed by the backend. See [architecture](docs/ARCHITECTURE.md).

The **SQL-answer grader** deliberately retains a fresh **in-memory SQLite** exercise database per comparison. It contains approved fixtures only, never application users or assessment records. Student queries cannot attach files, access PostgreSQL, modify fixtures or call unrestricted functions. This isolated grading tool is needed functionality, not an obsolete application storage fallback. Arbitrary student Python execution remains disabled.

## Testing and actual results

Integration tests require a separate **TEST_DATABASE_URL** pointing to disposable PostgreSQL and use isolated generated schemas. They never automatically reuse `DATABASE_URL` or fall back to SQLite. Missing test configuration causes explicit skips; skipped tests are not successful PostgreSQL verification.

```cmd
cd /d E:\ictrootai\backend
set TEST_DATABASE_URL=YOUR_SEPARATE_DISPOSABLE_POSTGRESQL_CONNECTION_STRING
.venv\Scripts\python.exe -m pytest -q
set TEST_DATABASE_URL=
cd /d E:\ictrootai\frontend
npm run typecheck
npm run build
```

Four generation-readiness browser tests mock APIs without changing demo records:

```cmd
cd /d E:\ictrootai\frontend
npx playwright install chromium --no-shell
npx playwright test generation-readiness.spec.ts
```

The original workflow browser tests require both services and seeded accounts. They create classes/assessments and submit answers, so use a disposable demonstration database. Set `ICTROOT_DEMO_PASSWORD` only for that test process and never commit it.

**Historical results before PostgreSQL-only storage:** 69 backend tests, four workflow browser tests and a SQLite migration smoke test passed on 2026-11-14. On 2026-11-15, 81 backend tests, four mocked readiness browser tests, typecheck and production build passed. These runs do not prove the new PostgreSQL configuration or a remote Supabase connection works. Current migration/test/cloud results are recorded in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

During the PostgreSQL migration, **109 tests passed against an isolated real PostgreSQL server**. Alembic migrations, legacy import, repeated-import refusal and login with the preserved password also passed. Frontend typecheck and build passed. The Supabase schema and transferred counts were checked through the connected management tool. After saving the private connection, live backend-to-Supabase teacher/student login, permissions, question-bank/assessment access, logout and health checks passed. The password-configuration follow-up passed 26 targeted configuration tests.

## Troubleshooting and remaining limits

- **Database unavailable:** configure `backend/.env`, run `app.check_database` and confirm the separate ICTRoot project is active. Copy the exact session-pooler values from its Connect dialog on IPv4 networks.
- **Login fails after migration:** import the preserved records or seed an empty development database. The former local application file is no longer used at runtime.
- **Generation 422/503/429:** an outcome needs source review; setup/inference failed; or repeated actual inference reached its retry delay. The readiness panel explains the next step.
- **Windows temporary-file permissions:** use a writable project-local temporary directory if Python cannot create a virtual environment through system TEMP.
- **Browser/model storage:** use a disk with space. Chromium `--no-shell` avoids downloading a second headless-shell distribution.
- **Port busy:** stop only the service you started on that port.

Full curriculum verification/population, reviewed Sinhala resources, paper blueprints, multipart mark totals, richer misconception analysis, AI provisional feedback, email/account recovery, distributed rate limits and production operations remain unfinished. Keep ICTRoot separate from MathRoot.
