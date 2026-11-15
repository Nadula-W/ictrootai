# ICTRoot AI contributor instructions

This repository is separate from MathRoot. Work only inside this repository. Never copy credentials or modify another project.

## Architecture

- `frontend/`: Next.js 16 App Router, React 19, TypeScript, Tailwind 4, CSS visual system and Lucide icons. Interactive workspace is in `app/page.tsx`; shared presentation helpers are in the same module. Read frontend/AGENTS.md and installed Next.js docs before framework changes.
- `backend/app/main.py`: FastAPI REST endpoints, server-side authorization and transaction boundaries.
- `models.py`, `database.py`, `schemas.py`: SQLAlchemy relational schema, session lifecycle and Pydantic contracts.
- `security.py`: scrypt password hashing, opaque server-side sessions. Roles come from the database, never client input.
- `ai.py`: loopback Ollama, schema-validated draft generation, local embeddings and cosine retrieval over stored vectors. No student data in prompts or logs.
- `verification.py`: deterministic grading; no eval or untrusted Python. Student SQL uses disposable SQLite with a restricted authorizer and instruction budget.
- `curriculum/`: original NIE PDF and explicitly unverified machine extraction. Internal outcome IDs are application identifiers, not NIE-issued identifiers.
- `backend/migrations/`: immutable Alembic revision snapshots. Add a new revision for future changes; never rewrite an applied revision.

## Commands (PowerShell, repository root)

```powershell
.\scripts\setup-backend.ps1
.\scripts\setup-frontend.ps1
.\scripts\start-backend.ps1
# Separate terminal:
.\scripts\start-frontend.ps1
# Validation:
.\scripts\test.ps1
cd frontend
npx playwright install chromium --no-shell
$env:ICTROOT_DEMO_PASSWORD = Read-Host 'Local demo password'
npx playwright test
```

## Rules

- Never mark extracted curriculum rows verified without checking source wording, mapping and page. Do not claim full coverage while the official inventory is unverified.
- Student API responses before submission must exclude answer keys, explanations, rubrics and distractor misconception labels.
- Assessments accept approved immutable questions only. Changes require a new question draft.
- Enforce class ownership on all teacher queries. Check student membership for assessment access. Keep duplicate submission protection atomic.
- Descriptive scores stay pending until teacher review. AI confidence is never proof of correctness.
- Never execute student Python or SQL against application/PostgreSQL databases.
- Never permit external AI endpoints or cloud-backed Ollama models. Never download models automatically.
- Sinhala translations keep English originals and technical identifiers. Unreviewed translations never appear as reviewed content.
- Keep `.env`, databases, sessions, local passwords and dependency directories untracked.
- Keep IMPLEMENTATION_STATUS.md current. Report actual tests and limitations; do not replace unfinished features with success claims.
- Run meaningful backend regression tests, typecheck and build for relevant changes. Browser tests modify demo records; use an isolated demo DB when possible.
