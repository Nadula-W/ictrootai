
# ICTRoot AI

A locally runnable Sri Lankan A/L ICT learning and assessment application built with Next.js, FastAPI, SQLAlchemy and Ollama. It includes complete local student/teacher assessment workflows and an administrator workspace. **This is a working research foundation with partial curriculum verification, not a fully populated or production-certified complete-syllabus product.** See [implementation status](IMPLEMENTATION_STATUS.md) for exact limits.

![Student workspace](docs/student-dashboard.png)

## What works

- Registration, password login, HttpOnly session cookies, database-backed student/teacher/admin roles, session revocation and logout.
- Classes, enrolment by class code, approved-question bank, manual JSON drafts, approval/rejection with review reasons, mixed-outcome assessment creation and class assignment.
- Timed attempts, server-side answer persistence, resume after interruption, locked submission, deterministic feedback, results, revision history and outcome performance.
- MCQ option-ID marking, integer base conversion, bounded Boolean truth-table equivalence, approved output comparison and read-only SQL result comparison in disposable SQLite.
- Structured/short answers with approved rubrics remain pending until teacher marking. Teacher overrides store a reason and audit record. Scores are normalized 0–1 per question.
- Official PDF import candidates for all 14 syllabus areas; outcome editing/import; resource PDF/TXT/JSON ingestion, chunk review and indexing; honest coverage reporting.
- Real Ollama model discovery/configuration, local `/api/chat` JSON-schema validation, local `/api/embed` integration and cosine vector retrieval restricted to reviewed resources for the chosen outcome. Generated questions remain drafts.
- Sinhala preference, reviewed-translation workflow and explicit English fallback. English originals and answer IDs stay intact.
- Administrator user-role management, actual AI status, health checks, private generation-status logs and teacher CSV exports.

## Windows setup from a clean computer

Install Node.js 24 LTS, Python 3.13 (with Python available on PATH), and Ollama for Windows. Git is optional. Open PowerShell in the project directory; the commands below assume `E:\ictrootai`.

```powershell
cd E:\ictrootai
# Only if PowerShell blocks local scripts; applies to this terminal only:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup-backend.ps1
.\scripts\setup-frontend.ps1
```

Backend setup creates `backend/.venv`, installs pinned dependencies, copies `.env.example` if needed, extracts the included syllabus, migrates SQLite, and seeds original demonstration questions. **Save the randomly generated password printed by the seed command.** The three local accounts are:

| Role | Email |
| --- | --- |
| Student | `student@ictroot.local` |
| Teacher | `teacher@ictroot.local` |
| Administrator | `admin@ictroot.local` |

Seeding is idempotent and refuses non-development environments. These accounts use ordinary password authentication; there is no bypass login endpoint. If the database was already seeded and you need a password:

```powershell
cd E:\ictrootai\backend
.\.venv\Scripts\python.exe -m app.reset_demo_password
```

Start the services in **two terminals**:

```powershell
# Terminal 1
cd E:\ictrootai
.\scripts\start-backend.ps1
```

```powershell
# Terminal 2
cd E:\ictrootai
.\scripts\start-frontend.ps1
```

Open **http://localhost:3000**. Backend API documentation: **http://127.0.0.1:8000/docs**. Ollama: **http://127.0.0.1:11434**. Ctrl+C stops each terminal's service. `scripts/start-dev.ps1` is an optional combined launcher; two terminals make stopping both services simpler.

For a production frontend build served locally:

```powershell
cd E:\ictrootai\frontend
npm run build
npm start
```

## Try the complete local workflow

1. Sign in as the student. Open Assessments and start **Number systems · First steps**. Select an answer, reload, resume, and submit. View feedback, progress and revision history.
2. Sign in as the teacher. Create a class and copy its code. Create an assessment, select approved questions and publish it to the class. A student can join using that code.
3. Open Question bank, create a manual draft, inspect the key/explanation, enter a review reason and approve it. Only approved questions can be assigned.
4. For short/structured questions, include a `rubric` array in the draft; students receive pending marks until a teacher reviews the submission. Each teacher mark is 0–1 with a required reason.
5. Sign in as administrator. Open Curriculum, expand a unit, edit an outcome JSON record, compare it with the cited PDF page and verify it only after review. Upload authorised notes in Administration, review each chunk, and index it after installing an embedding model.
6. For Sinhala, teachers open a question's translation editor, translate display fields while preserving identifiers/symbols, save the unreviewed draft, then approve the saved translation with a reason. Until approved, Sinhala-preferring students see an English fallback notice.

The browser test suite creates classes/assessments and submits demo work. Run it against a disposable demo database when preserving local practice history matters.

## Ollama and local RAG

Inspection on 2026-11-14 found `qwen3:4b-instruct` installed (approximately 2.5 GB on disk). A real structured `/api/chat` smoke test succeeded. The machine reports 15.5 GiB RAM, with about 4.8 GiB available during testing. Use the existing 4B quantized model; close heavy applications if inference exhausts memory. No instruction model was downloaded by this project.

```powershell
cd E:\ictrootai
.\scripts\check-ollama.ps1
.\backend\.venv\Scripts\python.exe .\scripts\ollama-smoke.py
```

If Ollama is not running, open its Windows app or run `ollama serve`. If the instruction model is absent, install it explicitly:

```powershell
ollama pull qwen3:4b-instruct
```

**No embedding model was installed at inspection time.** To enable semantic retrieval, explicitly install the configured lightweight local embedding model after checking disk space:

```powershell
ollama pull embeddinggemma
```

Then use Administration → Learning resources → review a chunk → Create local embedding. Generation requires a verified outcome and relevant reviewed/indexed material. Select that outcome in Question bank and generate an AI draft. Review its sources, answer and explanation before approval. Upload JSON resources as `{"text":"Your authorised educational passage"}`. PDF extraction does not perform OCR.

Vectors are stored as JSON alongside source chunks and searched by bounded cosine similarity over the selected outcome. This is a small-corpus local vector index, not FAISS; it avoids a Windows native FAISS dependency. Changing `EMBEDDING_MODEL` requires reindexing. Model identity is stored with embeddings.

The configured Ollama URL must resolve to a loopback hostname. Cloud-tagged/remote models are excluded. No student details or answers are sent to AI. Reviewed passages are treated as quoted data; generated output is schema-validated and never written as approved content. Prompt injection cannot be eliminated by prompting alone, so human approval remains required.

With Ollama offline or embeddings missing, existing approved questions, manual drafts and deterministic grading continue to work. Generation returns a clear failure rather than unsupported questions.

## Curriculum provenance and coverage

Authoritative source: [NIE A/L ICT syllabus, effective 2017](https://nie.lk/pdffiles/tg/eALSyl%20ICT.pdf), downloaded to `curriculum/nie-ict-2017.pdf`. The official [Grade 13 teacher guide](https://nie.lk/pdffiles/tg/eGr13TG%20ICT.pdf) also describes the 2017 revision. Search on 2026-11-14 did not locate a newer applicable official syllabus; this does **not** establish examination applicability for every future sitting.

`scripts/extract_curriculum.py` extracts table columns into `curriculum/extracted-review.json`, preserving a source SHA-256, page reference and review status. The current extraction contains **359 unverified outcome candidates** across units 1–13, not a certified official outcome count. Project (unit 14) has competency levels but no bulleted learning-outcome entries in the source table; its outcome inventory is empty rather than invented. PDF column layouts, continuation lines, competencies and subtopic boundaries can produce extraction errors. Verify every candidate against the original before approval. Re-extraction updates the JSON but does not overwrite an already seeded DB; use the administrator import after review.

One number-conversion outcome has been source-checked, with seven original deterministic practice questions. These are **not past-paper questions**. All other outcome candidates require review and question population. The source's summary table has numbering inconsistencies near the final units; internal unit IDs follow the 14-area sequence. Later titles/numbering and all Grade 12/13 unit mappings remain flagged for review. Grade preferences are functional, but unverified curriculum grade mapping is not silently invented.

Coverage reports approved counts, source verification, reviewed material, formats, difficulty, Sinhala availability and review dates per imported outcome. There is no full-syllabus percentage while the denominator is unverified. `CurriculumVersion.verified_complete` is intentionally false and has no casual UI toggle.

## Database and configuration

SQLite is the default: `backend/ictroot.db`. Configuration comes from `backend/.env` when commands run in `backend/`. Frontend uses a same-origin `/api` rewrite to FastAPI; no database credentials or service-role keys belong in frontend configuration.

```powershell
cd E:\ictrootai\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m app.seed
```

For Supabase PostgreSQL, obtain your project's server-side connection string from its Connect dialog. See [Supabase connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres). Use the session pooler or a direct connection that your network supports, and retain `sslmode=require`. Replace `backend/.env` using `.env.postgres.example` and run the migrations. URL-encode the password. **No Supabase credentials were supplied, so remote PostgreSQL migration/queries are untested.**

The PostgreSQL migration enables RLS on all application tables and revokes `anon`/`authenticated` table access. The browser does not use Supabase Data API; authentication and class authorization live in FastAPI, and the backend uses its private DB connection. This is custom application authentication, not Supabase Auth JWT integration. Use a dedicated restricted backend database role, HTTPS, protected backups and deployment-specific origin/proxy configuration before real deployment. The shipped migration assumes Supabase's `anon` and `authenticated` roles exist. No remote database was created or modified.

The backend connection must own the application tables or have explicit server-role RLS policies and grants; an ordinary non-owner role is denied by the shipped default-deny RLS setup. Restrict any app-specific owner role to application objects. Do not solve backend access by granting browser roles broad table privileges.

There are 18 relational tables with foreign keys and unique constraints. Options, rubric criteria, source IDs and vectors are JSON documents attached to questions/resources; they are not separately normalized option/rubric tables. Progress is calculated from persisted finalized answers rather than a duplicate progress table. See [architecture](docs/ARCHITECTURE.md) and [manual question format examples](docs/QUESTION_FORMATS.md).

## Tests and actual results

```powershell
cd E:\ictrootai
.\scripts\test.ps1
# Browser tests require both services running:
cd frontend
npx playwright install chromium --no-shell
$env:ICTROOT_DEMO_PASSWORD = Read-Host 'Password printed during seeding'
npx playwright test
Remove-Item Env:ICTROOT_DEMO_PASSWORD
```

Results recorded on 2026-11-14:

- Backend Pytest: **69 passed**. One upstream Starlette/httpx deprecation warning.
- Frontend TypeScript check: passed.
- Next.js production build: passed.
- Playwright Chromium: **4 passed** (student, teacher, administrator, mobile).
- Fresh SQLite migration upgrade → downgrade → upgrade: passed.
- HTTP frontend and backend/database health checks: passed.
- Real local Ollama schema response: passed (16.7 seconds in the initial smoke run).
- Real embeddings, grounded AI generation and Supabase PostgreSQL: not verified, pending model installation/reviewed indexing or credentials.

## Troubleshooting

- **PowerShell policy:** use the process-scoped command above, or run each script with `powershell -ExecutionPolicy Bypass -File ...`.
- **Windows Store Python temp permission error:** setup redirects TEMP/TMP into the project's `.tmp` directory. Install Python from python.org if Store launcher behavior still prevents venv creation.
- **`spawn EPERM` during build/browser launch:** allow the trusted Node/Chromium subprocess in your execution environment; the production build passed when process creation was permitted.
- **C: disk full during browser installation:** full Chromium is sufficient; `--no-shell` avoids downloading the second headless-shell distribution. Set TEMP/TMP and `PLAYWRIGHT_BROWSERS_PATH` to a disk with space before installation and testing if needed.
- **Login fails:** use the random seed password or run the local password recovery command. Registration always creates a student, never a teacher/admin.
- **Generation unavailable:** verify `/api/tags`, selected local model, embedding installation, source-verified outcome, reviewed chunks and current embeddings. Check administrator generation logs for failure categories. Manual drafting remains available.
- **Port busy:** stop the process you started on that port; do not kill unrelated services.

## Remaining limitations

Full official curriculum verification/population, confirmed grade mappings/exam applicability, reviewed Sinhala content, automated paper blueprints, multipart per-criterion mark totals, richer misconception aggregation, AI provisional descriptive feedback, password reset/email verification, distributed rate limiting, PostgreSQL deployment testing and production operations remain unfinished. There is no arbitrary student Python execution. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for the phase-by-phase record.
