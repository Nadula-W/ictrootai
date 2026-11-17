"""Save a private Supabase connection without echoing it in the terminal."""
import getpass
import json
import re
import os
import tempfile
import argparse
from pathlib import Path
from dotenv import dotenv_values
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

def replace_connection_password(value,password):
    if not password:raise ValueError('Enter the database password from the ICTRoot Supabase project.')
    try:url=make_url(value.strip())
    except (ArgumentError,ValueError,TypeError):
        raise ValueError('Save the Supabase connection string first, then update its password.') from None
    # SQLAlchemy encodes reserved characters. Enter the original password here,
    # not a manually percent-encoded password or a whole connection string.
    return prepare_connection_url(url.set(password=password).render_as_string(hide_password=False))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--password-only',action='store_true',help='Replace only the saved database password; input is hidden and URL symbols are encoded automatically')
    args=parser.parse_args()
    folder=Path(__file__).resolve().parents[1]
    target=folder/'.env'
    original=target.read_text(encoding='utf-8') if target.exists() else (folder/'.env.example').read_text(encoding='utf-8')
    try:
        if args.password_only:
            saved=dotenv_values(target).get('DATABASE_URL','') if target.exists() else ''
            print('Enter only the database password set in Supabase for ictroot-ai. Input is hidden; URL characters are encoded automatically.')
            normalized=replace_connection_password(saved,getpass.getpass('Database password: '))
        else:
            print('Copy the connection string from Supabase > ictroot-ai > Connect > Session pooler.')
            print('Replace the database password placeholder before pasting. Input is hidden.')
            normalized=prepare_connection_url(getpass.getpass('Private PostgreSQL connection string: '))
    except ValueError as error:
        print(str(error));return 1
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
