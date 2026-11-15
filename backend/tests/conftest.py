import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base,get_db
from app.main import app,limits
from app import models as m
from app.security import hash_password

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
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
        db.add(m.AssessmentQuestion(assessment_id=1,question_id=1,position=0));db.commit()
    def override():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=override
    limits.clear()
    yield factory
    app.dependency_overrides.clear();engine.dispose()

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
