"""Settings-independent database URL validation, also used by the recovery wizard."""
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

def validate_database_url(value: str) -> str:
    """Normalize a private PostgreSQL URL without echoing credentials in errors."""
    try:url=make_url(value.strip())
    except (ArgumentError,ValueError,TypeError):
        raise ValueError('DATABASE_URL must be a PostgreSQL connection string from Supabase Connect.') from None
    if url.drivername not in ('postgres','postgresql','postgresql+psycopg'):
        raise ValueError('Only PostgreSQL is supported for application storage. Configure the Supabase DATABASE_URL.')
    if not url.host or not url.username or not url.database:
        raise ValueError('The PostgreSQL connection requires a host, username and database name.')
    if any(part in value for part in ('[YOUR-PASSWORD]','PROJECT_REF','YOUR_PROJECT','POOLER_HOST','URL_ENCODED_PASSWORD')):
        raise ValueError('Replace all placeholders in the Supabase connection string before starting the backend.')
    local=url.host in ('localhost','127.0.0.1','::1')
    if not local and url.query.get('sslmode') not in ('require','verify-ca','verify-full'):
        raise ValueError('Remote PostgreSQL connections require sslmode=require or a stricter verification mode.')
    return url.set(drivername='postgresql+psycopg').render_as_string(hide_password=False)
