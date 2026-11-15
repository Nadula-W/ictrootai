# Implementation status — 2026-11-14

Working local application delivered in `E:\ictrootai`; MathRoot was not accessed or modified. This status intentionally distinguishes functional workflows from the complete requested production/curriculum scope.

| Phase | Implemented and exercised | Remaining |
| --- | --- | --- |
| 1. Foundation | Next.js/React/TypeScript/Tailwind frontend; FastAPI/Pydantic/SQLAlchemy backend; virtual environment; SQLite; pinned dependencies; Windows scripts | Production hosting and PostgreSQL credentials |
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
3. **Supabase credentials absent:** provide a private PostgreSQL connection in backend/.env, run Alembic on a disposable Supabase environment, verify RLS/revoked Data API access and application workflows. No remote integration success is claimed.
4. **Reviewed content/translation staffing:** authorised teachers must populate and review conceptual questions, rubrics, source notes and Sinhala translations. Locally authored demo questions are not official exam materials.

No paid AI, external student-data transmission, deployment, Git commit or remote push occurred.
