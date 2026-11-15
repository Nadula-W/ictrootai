from datetime import datetime,timedelta,timezone
import json
import pytest
from sqlalchemy import select
from app import models as m
from app.schemas import QuestionDraft

def begin(c):
    r=c.post('/api/assessments/1/start');assert r.status_code==200,r.text
    return r.json()['id']

def test_auth_required(client):assert client.get('/api/me').status_code==401
def test_password_failure(client):assert client.post('/api/auth/login',json={'email':'student1@test.local','password':'wrong-password'}).status_code==401
def test_register_cannot_elevate(client):
    r=client.post('/api/auth/register',json={'name':'New learner','email':'new@test.local','password':'long-password-123','role':'admin'})
    assert r.status_code==200 and r.json()['role']=='student'
    assert 'httponly' in r.headers['set-cookie'].lower()
def test_logout(signed):
    c=signed();assert c.post('/api/auth/logout').status_code==200
    assert c.get('/api/me').status_code==401
def test_student_cannot_admin(signed):
    c=signed()
    for p in ['/api/admin/users','/api/questions','/api/teacher/submissions','/api/admin/ai']:
        assert c.get(p).status_code==403
def test_no_keys_before_submission(signed):
    c=signed();tid=begin(c);r=c.get(f'/api/attempts/{tid}').json()
    q=r['questions'][0]
    assert 'key' not in q and 'explanation' not in q and 'sources' not in q
    assert all('misconception' not in o for o in q['options'])
    assert c.get(f'/api/attempts/{tid}/results').status_code==409
def test_answer_submit_duplicate_and_resume(signed):
    c=signed();tid=begin(c)
    assert begin(c)==tid
    assert c.put(f'/api/attempts/{tid}/answers/1',json={'value':'B'}).status_code==200
    assert c.get(f'/api/attempts/{tid}').json()['answers']['1']=='B'
    assert c.post(f'/api/attempts/{tid}/submit').status_code==200
    r=c.get(f'/api/attempts/{tid}/results').json();assert r['score']==1 and r['pending']==0
    assert c.post(f'/api/attempts/{tid}/submit').status_code==409
    assert c.put(f'/api/attempts/{tid}/answers/1',json={'value':'A'}).status_code==409
    p=c.get('/api/progress').json();assert p[0]['accuracy']==100 and p[0]['recommended_difficulty']=='medium'
def test_option_id_validation(signed):
    c=signed();tid=begin(c);assert c.put(f'/api/attempts/{tid}/answers/1',json={'value':'Z'}).status_code==422
def test_wrong_answer_misconception_is_tentative(signed):
    c=signed();tid=begin(c);c.put(f'/api/attempts/{tid}/answers/1',json={'value':'A'});c.post(f'/api/attempts/{tid}/submit')
    result=c.get(f'/api/attempts/{tid}/results').json()['items'][0]
    assert result['score']==0 and 'single answer' in result['misconception_notice']
def test_foreign_student_cannot_see_attempt(signed):
    c=signed();tid=begin(c);signed(5,'student')
    assert c.get(f'/api/attempts/{tid}').status_code==404
    assert c.post('/api/assessments/1/start').status_code==404
def test_foreign_teacher_access(signed):
    c=signed();tid=begin(c);signed(4,'teacher')
    assert c.get(f'/api/attempts/{tid}').status_code==404
    assert c.get('/api/classes').json()==[]
    assert c.post('/api/assessments',json={'title':'Test','class_id':1,'duration':10,'question_ids':[1]}).status_code==404
def test_create_class_and_assessment(signed):
    c=signed(2,'teacher');r=c.post('/api/classes',json={'name':'New class','grade':13});assert r.status_code==200
    r=c.post('/api/assessments',json={'title':'New assessment','class_id':r.json()['id'],'duration':45,'question_ids':[1],'published':True});assert r.status_code==200
def test_join_class(signed):
    c=signed(5,'student');assert c.get('/api/assessments').json()==[]
    assert c.post('/api/classes/join',json={'code':'TESTCODE'}).status_code==200
    assert len(c.get('/api/assessments').json())==1
def test_timer_enforced(signed,env):
    c=signed();tid=begin(c)
    with env() as db:
        db.get(m.Attempt,tid).started=datetime.now(timezone.utc)-timedelta(hours=1);db.commit()
    assert c.put(f'/api/attempts/{tid}/answers/1',json={'value':'B'}).status_code==409
    assert c.post(f'/api/attempts/{tid}/submit').status_code==200
    assert c.get(f'/api/attempts/{tid}/results').json()['score']==0
def test_sinhala_fallback(signed):
    c=signed();tid=begin(c);q=c.get(f'/api/attempts/{tid}?language=si').json()['questions'][0]
    assert q['language']=='en' and 'Sinhala' in q['language_notice']
def test_translation_review(signed):
    c=signed(2,'teacher')
    r=c.put('/api/questions/1/translation',json={'prompt':'සිංහල පරිවර්තන පරීක්ෂණය','options':[{'id':k,'text':v} for k,v in zip('ABCD',['1110','1101','1100','1111'])]});assert r.status_code==200
    assert c.post('/api/questions/1/translation/review',json={'decision':'approved','reason':'Technical symbols and wording reviewed'}).status_code==200
    signed();tid=begin(c);q=c.get(f'/api/attempts/{tid}?language=si').json()['questions'][0]
    assert q['language']=='si' and 'key' not in q
def test_coverage_honesty(signed):
    r=signed().get('/api/coverage').json();assert r['full_syllabus_percentage'] is None and not r['official_denominator_verified']
def test_curriculum_import(signed):
    c=signed(3,'admin');row={'id':'new-1','unit_id':3,'subtopic':'Test','competency':'Fixture','level':'3.1','text':'A fixture outcome','source_page':21,'verified':False}
    assert c.post('/api/admin/curriculum',json={'outcomes':[row]}).status_code==200
    assert c.post('/api/admin/curriculum',json={'outcomes':[{**row,'unit_id':999}]}).status_code==422
def test_question_schema_invalid():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):QuestionDraft(outcome_id='x',kind='mcq',difficulty='easy',prompt='Valid prompt',options=[{'id':'A','text':'yes'}]*4,key={'answer':'A'},explanation='explanation')
def test_manual_draft_approval(signed):
    c=signed(2,'teacher');q={'outcome_id':'3.1-test','kind':'number','difficulty':'easy','prompt':'Enter binary thirteen','key':{'answer':'1101','base':2},'explanation':'Eight plus four plus one.'}
    r=c.post('/api/questions',json=q);assert r.status_code==200
    qid=r.json()['id'];assessment={'title':'Draft test','class_id':1,'duration':15,'question_ids':[qid]}
    assert c.post('/api/assessments',json=assessment).status_code==422
    assert c.post(f'/api/questions/{qid}/review',json={'decision':'approved','reason':'Calculated binary representation'}).status_code==200
    assert c.post('/api/assessments',json=assessment).status_code==200
def test_teacher_review_audit(signed,env):
    c=signed();tid=begin(c);c.post(f'/api/attempts/{tid}/submit');signed(2,'teacher')
    assert c.post(f'/api/attempts/{tid}/answers/1/review',json={'score':0.5,'reason':'Accepted partial credit after discussion'}).status_code==200
    with env() as db:assert db.scalar(select(m.TeacherReview)).score==0.5
def test_upload_review(signed):
    c=signed(3,'admin');r=c.post('/api/admin/resources',data={'outcome_id':'3.1-test','title':'Notes','source':'Original notes'},files={'file':('notes.txt',b'Binary uses powers of two','text/plain')});assert r.status_code==200
    resources=c.get('/api/admin/resources').json();assert not resources[0]['reviewed']
    assert c.post('/api/admin/resources',data={'outcome_id':'3.1-test','title':'x','source':'x'},files={'file':('bad.exe',b'invalid')}).status_code==422
def test_origin_rejected(signed):
    assert signed().post('/api/auth/logout',headers={'Origin':'https://attacker.example'}).status_code==403
def test_role_change_invalidates_session(signed):
    c=signed();student_cookie=c.cookies.get('ictroot_session');signed(3,'admin')
    assert c.patch('/api/admin/users/1',json={'role':'teacher'}).status_code==200
    c.cookies.clear();c.cookies.set('ictroot_session',student_cookie)
    assert c.get('/api/me').status_code==401

def test_structured_pending_then_teacher_mark(signed):
    c=signed(2,'teacher')
    q={'outcome_id':'3.1-test','kind':'structured','difficulty':'medium','prompt':'Explain a binary place value. Give an example.','key':{'answer':'Each place represents a power of two.'},'explanation':'Moving left doubles the place value.','rubric':[{'criterion':'Explains power of two','weight':0.5},{'criterion':'Correct example','weight':0.5}]}
    qid=c.post('/api/questions',json=q).json()['id']
    c.post(f'/api/questions/{qid}/review',json={'decision':'approved','reason':'Rubric and explanation reviewed'})
    aid=c.post('/api/assessments',json={'title':'Structured fixture','class_id':1,'duration':15,'question_ids':[qid],'published':True}).json()['id']
    signed();tid=c.post(f'/api/assessments/{aid}/start').json()['id']
    c.put(f'/api/attempts/{tid}/answers/{qid}',json={'value':'Each position is a power of two, such as 8.'});c.post(f'/api/attempts/{tid}/submit')
    assert c.get(f'/api/attempts/{tid}/results').json()['pending']==1
    signed(2,'teacher');c.post(f'/api/attempts/{tid}/answers/{qid}/review',json={'score':1,'reason':'Both approved rubric elements satisfied'})
    assert c.get(f'/api/attempts/{tid}/results').json()['pending']==0

def test_extracted_curriculum_schema_and_unit_mapping():
    from pathlib import Path
    from app.schemas import CurriculumImport
    raw=json.loads((Path(__file__).resolve().parents[2]/'curriculum/extracted-review.json').read_text(encoding='utf-8'))
    parsed=CurriculumImport.model_validate(raw)
    ids=[o.id for o in parsed.outcomes]
    assert len(ids)==len(set(ids))
    assert all(o.unit_id==int(o.level.split('.')[0]) and not o.verified for o in parsed.outcomes)
    # Project (14) has competency levels but no bulleted outcome column in the source table.
    assert set(o.unit_id for o in parsed.outcomes)==set(range(1,14))

@pytest.mark.parametrize('kind,key',[('boolean',{'answer':'A'}),('boolean',{'answer':'A','variables':['wrong']}),('boolean',{'answer':"__import__('os')",'variables':['A']}),('sql',{'expected_rows':[],'fixtures':[123]}),('sql',{'expected_rows':['wrong-shape']}),('sql',{'expected_rows':[],'fixtures':['ATTACH DATABASE x AS other']}),('number',{'base':2}),('number',{'base':2.0,'answer':'10'})])
def test_malformed_technical_keys_cannot_be_drafted(kind,key):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):QuestionDraft(outcome_id='3.1-test',kind=kind,difficulty='medium',prompt='Technical question example',key=key,explanation='Approved explanation text')

def test_valid_technical_keys():
    common={'outcome_id':'3.1-test','difficulty':'medium','prompt':'Technical question example','explanation':'Approved explanation text'}
    assert QuestionDraft(**common,kind='boolean',key={'answer':'not (A and B)','variables':['A','B']})
    assert QuestionDraft(**common,kind='sql',key={'expected_rows':[[1]],'fixtures':['CREATE TABLE sample(value INTEGER)','INSERT INTO sample VALUES (1)']})

def test_invalid_legacy_draft_review_returns_validation_error(signed,env):
    with env() as db:
        q=m.Question(outcome_id='3.1-test',kind='boolean',difficulty='easy',prompt='Malformed legacy question',options=[],key={'answer':'A'},explanation='Legacy key lacks a variable list.',status='draft',sources=[],author_id=2,rubric=[])
        db.add(q);db.commit();qid=q.id
    c=signed(2,'teacher')
    assert c.post(f'/api/questions/{qid}/review',json={'decision':'approved','reason':'Attempting review of legacy draft'}).status_code==422
