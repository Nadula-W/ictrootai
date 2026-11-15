"""Database integration tests use PostgreSQL and an isolated schema per test.

TEST_DATABASE_URL is deliberately separate from the application's DATABASE_URL.
Without it, integration tests are skipped instead of creating a SQLite substitute.
"""
import os
import re
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker
from app.config import validate_database_url
from app.database import Base,build_engine,get_db
from app.main import app,limits
from app import models as m
from app.security import hash_password

@pytest.fixture
def env():
    configured_url=os.environ.get('TEST_DATABASE_URL','').strip()
    if not configured_url:
        pytest.skip('Set TEST_DATABASE_URL to a disposable PostgreSQL database to run database integration tests')
    try:
        database_url=validate_database_url(configured_url)
        engine=build_engine(database_url,pool_size=2,max_overflow=0)
    except ValueError:
        pytest.fail('TEST_DATABASE_URL must be a valid PostgreSQL URL; remote connections require TLS',pytrace=False)
    schema='ictroot_test_'+uuid.uuid4().hex
    if not re.fullmatch(r'ictroot_test_[0-9a-f]{32}',schema):
        raise RuntimeError('Unsafe test schema identifier')
    created=False
    previous_overrides=app.dependency_overrides.copy()
    try:
        try:
            with engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created=True
        except Exception as error:
            pytest.fail(f'PostgreSQL test setup failed ({type(error).__name__}); check TEST_DATABASE_URL and CREATE SCHEMA privileges',pytrace=False)
        isolated_engine=engine.execution_options(schema_translate_map={None:schema})
        Base.metadata.create_all(isolated_engine)
        factory=sessionmaker(isolated_engine,expire_on_commit=False)
        with factory() as db:
            db.add(m.CurriculumVersion(id='test',source='NIE test reference',applicability='Test fixture only',verified_complete=False));db.flush()
            db.add(m.Unit(id=3,version_id='test',name='Data Representation',grade=12,verified=True));db.flush()
            db.add(m.Outcome(id='3.1-test',unit_id=3,subtopic='Number systems',competency='Fixture',level='3.1',text='Number conversion test outcome',source_page=21,verified=True));db.flush()
            for uid,role in [(1,'student'),(2,'teacher'),(3,'admin'),(4,'teacher'),(5,'student')]:db.add(m.User(id=uid,email=f'{role}{uid}@test.local',name=role+str(uid),password=hash_password('Test-password-123'),role=role))
            db.flush()
            db.add(m.ClassRoom(id=1,name='Test class',teacher_id=2,grade=12,code='TESTCODE'));db.flush()
            db.add(m.Membership(class_id=1,student_id=1))
            db.add(m.Question(id=1,outcome_id='3.1-test',kind='mcq',difficulty='easy',prompt='Which number is binary thirteen?',options=[{'id':k,'text':v,'misconception':'Place value confusion' if k!='B' else None} for k,v in zip('ABCD',['1110','1101','1100','1111'])],key={'answer':'B'},explanation='8 plus 4 plus 1 equals 13.',status='approved',author_id=2,sources=[],rubric=[]));db.flush()
            db.add(m.Assessment(id=1,title='Number systems',teacher_id=2,class_id=1,duration=15,published=True));db.flush()
            db.add(m.AssessmentQuestion(assessment_id=1,question_id=1,position=0));db.flush()
            # Explicit fixture IDs do not advance PostgreSQL's serial sequences.
            for table in Base.metadata.sorted_tables:
                column=table._autoincrement_column
                if column is None:
                    continue
                sequence=db.scalar(text('SELECT pg_get_serial_sequence(:table_name,:column_name)'),{'table_name':f'{schema}.{table.name}','column_name':column.name})
                if sequence:
                    maximum=db.scalar(select(func.max(table.c[column.name])))
                    db.execute(text('SELECT setval(CAST(:sequence AS regclass),:value,:called)'),{'sequence':sequence,'value':maximum or 1,'called':maximum is not None})
            db.commit()
        def override():
            with factory() as db:yield db
        app.dependency_overrides[get_db]=override
        limits.clear()
        yield factory
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        if created:
            # Only this function's validated, randomly named test schema is removed.
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()

@pytest.fixture
def client(env):
    with TestClient(app) as c:yield c

@pytest.fixture
def signed(client):
    def sign(uid=1,role='student'):
        response=client.post('/api/auth/login',json={'email':f'{role}{uid}@test.local','password':'Test-password-123'})
        assert response.status_code==200,response.text
        return client
    return sign
