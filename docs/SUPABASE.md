# ICTRoot Supabase database

Project: **ictroot-ai**, reference `zbugipqjwamlrgdyycpr`, Mumbai (`ap-south-1`). Created on 2026-11-15 in the organization explicitly selected by the user, at the quoted **$0/month** creation cost. The separate MathRoot project was not changed.

**Current installation is connected (2026-11-17).** The private pooler URI and `DATABASE_TRANSPORT=supabase_websocket` are saved in `backend/.env`. Schema revision is `0002`; live student/teacher browser sign-in, dashboard loading, navigation, logout and database health checks passed. Start the backend normally; these setup steps are for a new installation or recovery, not something to repeat at each startup.

Application persistence is PostgreSQL only. The backend uses SQLAlchemy and psycopg; it requires a private PostgreSQL connection string, not a Supabase publishable API key. The connected management tool can manage the project/schema but does not supply the local backend's private database password.

1. Open the [ICTRoot Supabase project](https://supabase.com/dashboard/project/zbugipqjwamlrgdyycpr).
2. Click **Connect**, then choose **Session pooler**. Copy the provided connection string; do not construct the pooler hostname from the region.
3. Replace the password placeholder with the project's database password. If you do not have it, reset it in this new project's Database settings. URL-encode reserved password characters.
4. Save the connection privately from a Command Prompt terminal:

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m app.configure_database
.venv\Scripts\python.exe -m app.check_database
```

Paste the connection string into the hidden prompt. It is saved only to the ignored `backend/.env`. The helper adds `sslmode=require` when TLS is unspecified; explicit insecure remote modes are rejected. **Restart the backend after saving** because changing `.env` alone does not refresh an already-running process. The main database cannot fall back to SQLite.

If a saved URL reaches the correct project but reports password authentication failure, update only the password without rebuilding the URL:

```cmd
.venv\Scripts\python.exe -m app.configure_database --password-only
.venv\Scripts\python.exe -m app.check_database
```

Enter the original database password exactly as set in Supabase. The hidden prompt encodes reserved URL characters automatically and saves the result to `.env`. Do not enter your Supabase account sign-in password or a percent-encoded version.

If `app.check_database` reports `database_timeout`, a timeout alone does not establish that the password is wrong. A healthy project in the Supabase dashboard does not prove the network path from the local backend is working. PostgreSQL requires successful protocol/TLS negotiation in addition to an open TCP port. Do not disable TLS or reset passwords repeatedly to work around a handshake timeout. See [Supabase pooler troubleshooting](https://supabase.com/docs/guides/database/supavisor).

On this computer, raw PostgreSQL TCP reaches the shared pooler but stalls before the TLS handshake. Supabase's secure WebSocket route works on the same network. The backend supports an explicit alternative in the ignored `backend/.env`:

```dotenv
DATABASE_TRANSPORT=supabase_websocket
```

Keep the existing `DATABASE_URL` and `sslmode=require`. Install `requirements.lock.txt` and restart the backend after changing transport. This mode connects to the shared pooler at `wss://POOLER_HOST/v2` on port 443 through a bounded loopback relay. The outer WebSocket certificate and hostname are verified, and psycopg still negotiates PostgreSQL TLS inside it. Credentials stay within PostgreSQL; they are absent from the WebSocket URL and browser. It uses the same Supabase database, with no new service or Data API grants. Only Supabase shared pooler hostnames are accepted. The `/v2` proxy uses transaction pooling, so server prepared statements remain disabled; application code must not depend on persistent session state. New installations default to `DATABASE_TRANSPORT=direct`.

References: [Supabase serverless PostgreSQL drivers](https://supabase.com/docs/guides/database/connecting-to-postgres/serverless-drivers), [Supavisor WebSocket proxy implementation](https://github.com/supabase/supavisor/blob/main/lib/supavisor_web/ws_proxy.ex).

The application schema is managed through Alembic. Revision **0002** is already applied in this cloud project. **434 legacy records have already been imported and checked**, including 3 accounts, 360 outcome records and 7 questions. Do not import or seed them again. Start the backend and sign in with your existing password.

```cmd
.venv\Scripts\python.exe -m alembic upgrade head
```

The preserved recovery snapshot is `backups/sqlite-before-supabase-20261115T065338Z.db`. If restoring into a different empty, migrated PostgreSQL destination, `app.migrate_legacy_sqlite --source <snapshot>` preserves IDs/password hashes/review flags, checks row counts and updates sequences. It refuses nonempty destinations and never deletes the source. It is one-time compatibility tooling, not a second database mode. Backups are excluded from Git because they contain private records.

All app tables use RLS and deny direct `anon`/`authenticated` access. FastAPI applies student/teacher/class authorization and uses the private table-owner connection. Keep that credential on the server; a publishable browser key cannot substitute for it. PostgreSQL is used for application data only; student SQL still runs against a bounded in-memory grading fixture, never Supabase.

Source: [Supabase connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres).
