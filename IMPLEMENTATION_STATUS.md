# Implementation status — updated 2026-11-15

**Current database status:** Application storage is PostgreSQL only. A separate `ictroot-ai` Supabase project (`zbugipqjwamlrgdyycpr`, Mumbai) was created with the user's approval at the quoted $0/month cost. Schema revision `0002` is installed, and all **434 preserved records** have been imported and checked. The private connection string for the running Windows backend has not yet been supplied; database-dependent requests return a clear 503 until that connection is configured and the backend restarted. MathRoot was not changed.

The dated local-demo results below are historical. The PostgreSQL migration details at the end record the current storage implementation and verification.

Working local application delivered in `E:\ictrootai`; MathRoot was not accessed or modified. This status intentionally distinguishes functional workflows from the complete requested production/curriculum scope.

| Phase | Implemented and exercised | Remaining |
| --- | --- | --- |
| 1. Foundation | Next.js/React/TypeScript/Tailwind frontend; FastAPI/Pydantic/SQLAlchemy backend; Supabase PostgreSQL schema and transferred records; bounded pool; pinned dependencies; Windows setup | Private local-backend connection string and production hosting |
| 2. Curriculum | Official 63-page NIE PDF downloaded; hash/page-linked extraction; 14 unit areas; 359 unverified outcome candidates; one reviewed conversion outcome; import/edit UI/API; per-outcome coverage | Full source-wording verification, competency/subtopic cleanup, grade mappings, official exam applicability, reviewed complete inventory |
| 3. Ollama/RAG | Installed model discovery; admin selection/status; real local structured chat succeeded; local embeddings client; resource ingestion/review/indexing; cosine vector retrieval; source attachment | Embedding model not installed, so real embedding/retrieval/generation chain not smoke-tested |
| 4. Question bank | Seven original approved questions; manual drafts; schema validation; local generation API; source-review gating; approve/reject/edit-as-new workflow; offline fallback | Broad reviewed question population and formal quality evaluation |
| 5. Assessment | Teacher classes/enrolment code; mixed-outcome selection; publish/assign; student start, save, resume, navigation, timer, locking; results | Automatic Paper I/II blueprints and bulk mixed-outcome AI generation; deadline currently requires user submission to finalize |
| 6. Adaptive learning | Persistent answers/history; accuracy by outcome; recent-score difficulty recommendation; tentative distractor feedback; same-outcome follow-up when available | Longitudinal misconception evidence aggregation, spaced repetition, student-specific practice assignment engine |
| 7. Structured answers | Rubric-required drafts; pending descriptive marking; teacher review/override with reason/audit; deterministic number/Boolean/output/SQL strategies | Multipart individual criterion scoring and AI provisional feedback; output compares approved expected strings (no executable Python sandbox) |
| 8. Sinhala/admin | Preferences; translation save/review API and editor; explicit fallback; user roles; resource management; health; AI logs; teacher reports/submissions | Actual reviewed Sinhala question population, Sinhala navigation, translation suggestions, detailed class/misconception analytics, student roster detail pages |
| 9. Security/tests/docs | Role/access checks; key filtering; scrypt/session auth; origin protection; atomic save/submit; bounded SQL; local-only AI; tests, setup scripts, README and architecture | Production audit, password recovery/email verification, distributed limits, parser worker isolation, deployment and Supabase verification |

## Actual verification

- **69 backend tests passed** in the final run (12.01 seconds). One upstream Starlette TestClient/httpx deprecation warning. Tests cover authentication, role/session changes, class ownership, enrolment, key leakage, attempts, duplicate submission, timing, progress, curriculum import/schema, question review, teacher review, translations, resources, AI offline/malformed output, local-only models, numbers, Boolean truth tables and SQL restrictions. A focused independent review found incomplete technical-key validation; regression tests now cover malformed Boolean/SQL/number keys, safe legacy deferral, and SQL numeric equivalence with duplicate counts.
- **4 Playwright browser tests passed** in Chromium (8.8 seconds): student autosave/resume/submit/results, teacher class + assessment creation, administrator AI/curriculum view, mobile width.
- Next.js typecheck and optimized production build passed (Next.js 16.4.6 / React 19.3.1). First sandboxed build hit `spawn EPERM`; it passed with trusted process creation allowed.
- Fresh SQLite Alembic upgrade → downgrade → upgrade passed; revision `0001` is a frozen schema snapshot.
- Frontend HTTP 200 and backend/database health `ok` verified.
- Real Ollama `/api/tags` succeeded; `qwen3:4b-instruct` installed. Real `/api/chat` returned schema-valid `{"status":"local-ready"}` in 16.7 seconds. No model was downloaded.
- Host memory read through Windows API: 15.5 GiB RAM / 4.8 GiB available during test. Initial CIM query was denied; Windows API succeeded.
- Full Chromium installed. Optional separate headless-shell download failed with C: `ENOSPC`; browser testing succeeded using full Chromium. No unrelated files were deleted.

## Exact external/content blockers and next actions

Project (unit 14) has competency levels but no bulleted outcome-column entries in the PDF table. The 359 extracted candidates come from units 1–13; Project has no invented outcome rows. Final browser-test records were removed from the demo and the seeded assessment restored for a fresh student attempt. Desktop/mobile screenshots were inspected and mobile horizontal overflow checked false. Preview services were stopped after verification; use the startup scripts to run them again.

1. **Embedding model absent:** free sufficient model-storage space and explicitly run `ollama pull embeddinggemma`. Review and index authorised resource chunks, then run generation and inspect its source-grounded draft. Mock tests do not establish real generation quality.
2. **Verified full curriculum corpus absent:** review each extracted row against `curriculum/nie-ict-2017.pdf`; correct continuation/column errors, competency/subtopic mapping and grade applicability in administrator import. Obtain official confirmation of the currently applicable exam syllabus. Do not mark the full inventory complete merely because 14 units exist.
3. **Local backend connection pending:** The new ICTRoot Supabase project, schema, RLS restrictions and 434 transferred records have been checked through the management connection. Save its private Session pooler connection with `python -m app.configure_database`, run `python -m app.check_database`, and restart the backend. The connection from the local FastAPI process to Supabase remains unverified until then.
4. **Reviewed content/translation staffing:** authorised teachers must populate and review conceptual questions, rubrics, source notes and Sinhala translations. Locally authored demo questions are not official exam materials.

No paid AI, external student-data transmission, deployment, Git commit or remote push occurred.

## Generation troubleshooting update — 2026-11-15

Investigated the reported `422 → 503 → 429` generation errors against the running local services and database. Ollama and `qwen3:4b-instruct` are available. The configured search model `embeddinggemma` is absent; the single reviewed demo note has no stored embedding. The former catch-all `ValueError` log concealed these setup blockers. No models were downloaded and no curriculum review flags were changed.

- Added staff-only per-outcome AI readiness checks, with distinct messages for unverified outcomes, unavailable Ollama, missing local models, unreviewed material and missing/current resource indexes.
- The question bank checks readiness before enabling AI generation and labels outcomes `Verified:` or `Needs review:`. Manual drafting remains available.
- Invalid outcomes and setup-only failures no longer consume the three-per-minute inference allowance. Actual inference attempts still do. Rate limits include `Retry-After`, and the UI observes the delay.
- Setup logs store safe diagnostic codes, without exception messages, prompt contents or student answers. Added recognition of explicit `:latest` model names.
- Full backend suite: **81 passed** (17.99 seconds), with the existing upstream Starlette/httpx deprecation warning. Twelve new mocked regression tests exercise setup failures, permissions, privacy and inference limits.
- Frontend typecheck and production build passed. **Four new focused browser checks passed** (5.2 seconds), exercising readiness messages, disabled generation, the successful draft path and the retry countdown using mocked APIs; they do not change demo records. An initial test selector matched both the app alert and the Next.js route announcer; the selector was corrected before the passing run.

The real setup blocker remains: explicitly install `embeddinggemma`, then sign in as administrator and index reviewed resources. Real source-grounded generation remains unverified until that setup is complete. The earlier four end-to-end workflow results remain historical; they were not rerun during this focused fix.

## Supabase PostgreSQL migration — 2026-11-15

- Created the new `ictroot-ai` project in the organization selected by the user. The tool quoted $0/month and the user explicitly approved it. Inspected empty tables and security/performance advisories before applying the schema. MathRoot was left untouched.
- Removed the application's SQLite engine, pragmas and default URL. PostgreSQL URLs use psycopg, secret-redacted settings, mandatory remote TLS, bounded pools and connection timeouts. Server prepared statements are disabled for pooler compatibility. No database credentials or Supabase service key are placed in the frontend.
- Kept immutable revision `0001`; added revision `0002` for foreign-key indexes, RLS and table/sequence access restrictions. Cloud revision and metadata match. All 19 public tables (18 app tables plus migration metadata) have RLS enabled; queries confirmed `anon` and `authenticated` lack table-read grants.
- Supabase advisories reported informational default-deny RLS tables without browser policies and unused indexes on a new database, with no warning/error-level findings. These are expected for this backend-only access design and fresh deployment. Reference: [RLS policy notice](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy), [unused-index notice](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).
- Preserved a consistent, integrity-checked snapshot at `backups/sqlite-before-supabase-20261115T065338Z.db`. Imported **434 records** into Supabase, preserving IDs, password hashes, review flags and content. Verified counts including 3 users, 360 outcomes and 7 questions. A Windows ANSI text-read issue during the tool transfer was caught by a Unicode check and corrected atomically from the snapshot; the checked Unicode title now matches exactly. The recovery snapshot remains ignored and private.
- Removed the obsolete active `backend/ictroot.db`, `backend/migration-smoke.db`, redundant root `.env.example` and `backend/.env.postgres.example`. Canonical template is `backend/.env.example`. The isolated in-memory SQLite SQL-answer grader remains necessary and cannot access PostgreSQL.
- Added read-only `app.check_database`, hidden-input/atomic-save `app.configure_database`, and guarded one-time `app.migrate_legacy_sqlite`. The importer refuses nonempty destinations and never deletes its source. Invalid legacy conversion messages do not expose field values or silently turn text into verified flags. The configuration wizard works even when an older SQLite/invalid URL exists.
- Verification against disposable real PostgreSQL: **109 tests passed** in the final run (30.80 seconds), with the existing upstream Starlette/httpx deprecation warning. Alembic upgrade, schema-drift check, 434-record import, repeat-import refusal and preserved-password teacher login/question-bank/health/logout smoke passed. Frontend typecheck and production build passed. Only the task's disposable PostgreSQL container was stopped after verification; user services were left alone.
- Remote cloud checks were run through the connected management tool. The separate private PostgreSQL URI needed by the Windows backend is still absent; no successful local-to-Supabase runtime connection is claimed. Direct endpoint DNS was unavailable from this host, so use the exact Session pooler values from the dashboard's Connect dialog.

See [docs/SUPABASE.md](docs/SUPABASE.md) for the remaining connection step. Existing passwords are preserved. The new cloud database is populated already; do not seed or import it again.
