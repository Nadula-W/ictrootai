"""Save a private Supabase connection without echoing it in the terminal."""
import getpass
import json
import re
import os
import tempfile
from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from .db_url import validate_database_url

def prepare_connection_url(value):
    try:url=make_url(value.strip())
    except (ArgumentError,ValueError,TypeError):
        raise ValueError('Paste the PostgreSQL connection string from Supabase Connect.') from None
    if url.host not in ('localhost','127.0.0.1','::1') and 'sslmode' not in url.query:
        url=url.update_query_dict({'sslmode':'require'})
    return validate_database_url(url.render_as_string(hide_password=False))

def main():
    print('Copy the connection string from Supabase > ictroot-ai > Connect > Session pooler.')
    print('Replace the database password placeholder before pasting. Input is hidden.')
    try:normalized=prepare_connection_url(getpass.getpass('Private PostgreSQL connection string: '))
    except ValueError as error:
        print(str(error));return 1
    folder=Path(__file__).resolve().parents[1]
    target=folder/'.env'
    original=target.read_text(encoding='utf-8') if target.exists() else (folder/'.env.example').read_text(encoding='utf-8')
    line='DATABASE_URL='+json.dumps(normalized)
    contents=re.sub(r'^DATABASE_URL=.*$',lambda _:line,original,flags=re.MULTILINE)
    if contents==original and not re.search(r'^DATABASE_URL=',original,re.MULTILINE):contents+='\n'+line+'\n'
    staged=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=folder,prefix='.env-',delete=False) as stream:
            staged=Path(stream.name)
            stream.write(contents);stream.flush();os.fsync(stream.fileno())
        os.replace(staged,target)
    except OSError:
        print('Could not save the database configuration. The previous configuration was preserved; credentials were not printed.')
        return 1
    finally:
        if staged and staged.exists():staged.unlink()
    print('Saved backend/.env. Credentials were not printed. Run python -m app.check_database, then restart the backend to load the new connection.')
    return 0

if __name__=='__main__':raise SystemExit(main())
