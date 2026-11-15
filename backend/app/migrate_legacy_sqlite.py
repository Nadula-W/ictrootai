"""One-time, read-only legacy import. SQLite is never application storage.

Imports all known application tables in a single PostgreSQL transaction. The
destination must be empty and migrated; local data is never deleted by this tool.
"""
import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import Boolean,DateTime,JSON,select,func,text
from sqlalchemy.exc import SQLAlchemyError
from .database import Base,engine
from . import models

def convert_legacy_value(column,value):
    if value is None:return None
    try:
        if isinstance(column.type,JSON) and isinstance(value,str):return json.loads(value)
        if isinstance(column.type,Boolean):
            if not isinstance(value,(int,bool)) or value not in (0,1):raise ValueError('Invalid Boolean')
            return bool(value)
        if isinstance(column.type,DateTime) and isinstance(value,str):
            parsed=datetime.fromisoformat(value)
            if column.type.timezone and parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
            return parsed
        return value
    except (ValueError,TypeError,OverflowError):
        raise ValueError(f'Legacy field {column.table.name}.{column.name} cannot be converted safely. No field values were printed.') from None

def read_legacy(source):
    path=Path(source).resolve(strict=True)
    # Read-only URI; no sqlite file can be created by a misspelled source path.
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
        connection.row_factory=sqlite3.Row
        connection.execute('BEGIN')
        if connection.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Legacy database integrity check failed')
        available={row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        data={}
        for table in Base.metadata.sorted_tables:
            if table.name not in available:raise ValueError('Legacy database does not contain the full ICTRoot schema')
            rows=[]
            for row in connection.execute(f'SELECT * FROM "{table.name}"'):
                values=dict(row)
                for col in table.columns:
                    values[col.name]=convert_legacy_value(col,values.get(col.name))
                rows.append(values)
            data[table.name]=rows
        return data

def import_legacy(source,destination_engine):
    if destination_engine is None:raise ValueError('Configure Supabase DATABASE_URL before importing legacy data')
    if destination_engine.dialect.name!='postgresql':raise ValueError('Legacy records can only be imported into PostgreSQL')
    data=read_legacy(source)
    with destination_engine.begin() as connection:
        revision=connection.scalar(text('SELECT version_num FROM alembic_version'))
        if revision!='0002':raise ValueError('Run alembic upgrade head before importing')
        for table in Base.metadata.sorted_tables:
            if connection.scalar(select(func.count()).select_from(table)):
                raise ValueError('Destination application tables must be empty; import refuses to overwrite existing data')
        # Schema-owner privilege is already needed to run migrations. Take locks
        # so no request can insert records between emptiness checks and import.
        tables=','.join('"'+t.name+'"' for t in Base.metadata.sorted_tables)
        connection.execute(text('LOCK TABLE '+tables+' IN ACCESS EXCLUSIVE MODE'))
        for table in Base.metadata.sorted_tables:
            if connection.scalar(select(func.count()).select_from(table)):
                raise ValueError('Destination changed during import; no records were overwritten')
            if data[table.name]:connection.execute(table.insert(),data[table.name])
            count=connection.scalar(select(func.count()).select_from(table))
            if count!=len(data[table.name]):raise ValueError('Record-count verification failed; import rolled back')
            column=table._autoincrement_column
            if column is not None:
                sequence=connection.scalar(text('SELECT pg_get_serial_sequence(:table,:column)'),{'table':table.name,'column':column.name})
                if sequence:
                    maximum=connection.scalar(select(func.max(table.c[column.name])))
                    connection.execute(text('SELECT setval(CAST(:sequence AS regclass),:value,:called)'),{'sequence':sequence,'value':maximum or 1,'called':maximum is not None})
    return {name:len(rows) for name,rows in data.items()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,help='Preserved legacy ICTRoot SQLite snapshot')
    args=parser.parse_args()
    try:
        counts=import_legacy(args.source,engine)
    except (ValueError,OSError,sqlite3.Error,SQLAlchemyError) as error:
        if isinstance(error,ValueError):print(str(error))
        else:print('Import failed. No local data was deleted. Check the source and PostgreSQL connection; credentials and records were not printed.')
        return 1
    print('Imported and verified',sum(counts.values()),'records across',len(counts),'tables. Original local data was preserved.')
    return 0

if __name__=='__main__':raise SystemExit(main())
