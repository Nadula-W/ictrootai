# Architecture and trust boundaries

The browser speaks to same-origin `/api`; Next.js rewrites to loopback FastAPI. FastAPI owns authentication, authorization, question-key filtering, review decisions, assessment timing and persistence. SQLAlchemy supports SQLite locally and a private Supabase PostgreSQL connection. Ollama is loopback-only and receives curriculum material, not student information.

## Schema

`users → sessions`; `classes → class_memberships`; `curriculum_versions → units → learning_outcomes → learning_resources / questions`; `questions → translations / question_validations`; `classes → assessments → assessment_questions`; `assessments → student_attempts → student_answers`; `student_answers → teacher_reviews` (attempt and question references); `ai_generation_logs`; `app_settings`.

User role is a constrained API-managed string; source of authority is the DB. Structured question options, answer keys, rubrics and source references live in JSON fields. Every outcome has a unique application ID, competency-level reference, source page, review flag and timestamp. Grade mappings can be null to avoid invented classification.

## Assessment lifecycle

Only approved immutable questions enter assessments. Class ownership controls teacher operations; membership and publication control student access. One attempt per assessment/student is enforced by a database unique constraint. Start is idempotent. Server time defines a deadline. Autosaved answers are mutable only before deadline and submission. A conditional update serializes saves and submission; duplicate submissions return 409. Results, keys and misconception labels are available to the owning student only after submission. Teachers can see keys in their authorized question bank.

Scoring uses normalized 0–1 per question. Deterministic strategies handle MCQ, numbers, Boolean equivalence, approved expected output and SQL fixture results. Descriptive answers stay pending until a teacher stores a score/reason. Overrides are audited. Missing responses score zero. No LLM has final-score authority.

SQL query execution uses a new in-memory SQLite DB for each comparison. Only fixture CREATE TABLE/INSERT statements are accepted; ATTACH/DETACH/PRAGMA/virtual tables are denied. Student SELECT/WITH queries run with an authorizer, function allowlist, size limits, instruction budget and row cap. This is bounded SQL evaluation, not a general-purpose isolated code sandbox. Student Python execution is absent.

## Content lifecycle

PDF/table extraction → unverified outcomes → administrator source review. Resource upload → unreviewed chunks → administrator review → local embedding. Retrieval uses only matching-outcome reviewed resources with current-model vectors and a similarity threshold. Local schema-constrained generation → draft → teacher review with reason → immutable approval. Source attachment establishes provenance, not automatic correctness. Sinhala drafts have an independent review flag; original English remains authoritative until translation review.

## Local security and deployment limits

Passwords use per-user salts and scrypt. Session tokens have 384 bits of random entropy and only SHA-256 hashes are stored. Cookies are HttpOnly, SameSite Strict and optionally Secure; non-development configuration requires Secure cookies. Server-side sessions expire after 12 hours. Mutations reject foreign browser origins. Expensive AI operations and login attempts are process-rate-limited. HTML in questions is rendered as React text, never injected markup.

Uploads are not stored under user-supplied filesystem paths and are size-limited. File parsers still warrant worker isolation for public multi-tenant deployment. Rate limits are in-memory and unsuitable for multiple workers without shared storage. Deployment needs HTTPS, explicit trusted origins/proxy settings, database least privilege, monitoring, user recovery and operational backups. No claim of a completed penetration test is made.
