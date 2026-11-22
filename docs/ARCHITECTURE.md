# Architecture and trust boundaries

The browser speaks to same-origin `/api`; Next.js forwards requests to FastAPI. FastAPI owns authentication, authorization, answer-key filtering, assessment timing and transactions. **Supabase PostgreSQL is the only application database.** SQLAlchemy uses a private psycopg connection configured in `backend/.env`; no SQLite application-storage fallback exists. Ollama stays loopback-only.

## Persistent schema and connections

The 18 application tables cover users/sessions, classes/memberships, curriculum versions/units/outcomes, resources, questions/translations/validation, assessments/question selection, attempts/answers, teacher reviews, AI logs and settings. Foreign keys enforce references; a unique constraint permits one attempt per assessment/student. New migrations add missing access-path/foreign-key indexes and backend-only access controls without rewriting applied revisions.

Options, keys, rubrics and source references are JSON documents. Resource embeddings include model identity. Progress is derived from finalized answers. Grade mappings stay null when official classification is unverified.

The backend has a bounded pool with stale-connection checks and timeouts. Supabase session pooling supports a persistent Windows backend on IPv4. Remote connections require TLS; credentials are never sent to the frontend or printed in logs. Configuration/health checks report missing or unavailable PostgreSQL explicitly.

`DATABASE_TRANSPORT` defaults to `direct`. The opt-in `supabase_websocket` mode wraps the existing PostgreSQL/TLS stream in Supabase's certificate-verified shared-pooler `/v2` WebSocket connection on port 443. Its loopback listener starts lazily and bounds connections to the SQLAlchemy pool limit. It accepts only shared Supabase pooler hostnames, keeps original PostgreSQL credentials/TLS settings and never logs wire contents. The proxy uses transaction pooling; prepared statements are disabled and application code must not depend on persistent session state. Engine disposal stops new local accepts while preserving checked-out connections. This transport does not change storage, authorization or browser privileges.

Authentication remains scrypt plus opaque server-side sessions; it does not use Supabase Auth or browser JWT claims. Migrations enable RLS and revoke `PUBLIC`, `anon` and `authenticated` access to application tables/sequences and migration metadata. The runtime connection must own the application tables or have explicit server-role grants/policies. Broad browser grants are not a fix for backend configuration errors.

## Assessment lifecycle

Only approved immutable questions enter assessments. Teacher operations enforce class ownership; student operations require membership and publication. Start is idempotent. Server time sets the deadline. Saves are allowed only before deadline/submission. PostgreSQL row locking and conditional updates serialize saves with submission; duplicate submissions return 409.

Student responses exclude keys, explanations, rubrics and misconception labels before submission. Results reveal the approved answer and grading reason afterward. Teachers see keys in their authorized question bank and review their class submissions.

Each question currently contributes 0–1. Deterministic strategies cover MCQs, integer base conversions, Boolean equivalence, approved expected outputs and SQL fixture results. Descriptive scores remain pending until teacher review. Overrides require a reason and create an audit record. Detected malformed legacy technical configurations are deferred for teacher review. LLM confidence never determines final verified marks.

## Isolated SQL-answer grading

Student SQL runs against a fresh **in-memory SQLite exercise database** per comparison. It is independent of PostgreSQL, contains approved exercise fixtures only, stores no application records and never connects to Supabase.

Fixtures accept bounded CREATE TABLE/INSERT statements. ATTACH/DETACH/PRAGMA/virtual tables are denied. Student SELECT/WITH queries use a read-only authorizer, function allowlist, size limit, instruction budget and row cap. Comparisons preserve duplicate counts and normalize numeric equivalence. SQLite exercise semantics do not claim full PostgreSQL dialect support. Arbitrary student Python execution is absent.

## Content and AI lifecycle

PDF extraction produces unverified outcomes. Administrators compare wording, mappings and pages with the official source. Uploaded passages become unreviewed chunks, then reviewed notes, then locally indexed embeddings. Retrieval uses matching-outcome reviewed chunks with current-model vectors and a relevance threshold.

Question bank checks readiness before generation: verified outcome, local models, reviewed material and a current index. Setup-only failures do not spend inference quota; actual attempts remain limited and include retry guidance.

Schema-constrained local generation creates a draft with sources. Teacher approval enables assessment use. Provenance alone is not proof of correctness. Student data stays out of prompts/logs, and the model cannot modify DB records. Sinhala drafts have independent review status while English originals remain preserved.

## Legacy migration and tests

The former SQLite application file is preserved privately in `backups/` until its records are imported and verified. The one-time importer reads that source and writes to migrated PostgreSQL tables; it is not a runtime storage mode. Never remove the only copy of user records or report migration success without verification.

Database integration tests require a separate `TEST_DATABASE_URL` and create constrained generated PostgreSQL schemas. They never select the application database implicitly or fall back to SQLite. Pure grading/configuration tests can run without a database. Skipped integration tests remain an explicit verification limitation.

## Deployment limits

Session tokens have 384 bits of entropy; only hashes are stored. Cookies are HttpOnly/SameSite Strict; non-development requires Secure cookies. Sessions expire after 12 hours. Mutations reject foreign browser origins. React renders question content as text rather than injected HTML.

Public multi-tenant deployment still needs parser worker isolation, shared rate-limit storage for multiple workers, HTTPS/proxy configuration, least-privilege server roles, monitoring, account recovery and tested backups. PostgreSQL storage removes the local-file bottleneck but does not complete those operational requirements.
