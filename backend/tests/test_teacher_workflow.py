from sqlalchemy import select
from app import models as m,ai

def test_application_never_grants_its_own_role_and_requires_admin(env,signed):
    c=signed();r=c.post('/api/teacher-applications',json={'message':'I teach ICT','role':'admin'})
    assert r.status_code==200 and r.json()['status']=='pending'
    aid=r.json()['id']
    assert c.get('/api/me').json()['role']=='student'
    assert c.get('/api/admin/teacher-applications').status_code==403
    assert c.post(f'/api/admin/teacher-applications/{aid}/review',json={'decision':'approved','reason':'Trusted teacher'}).status_code==403
    signed(2,'teacher');assert c.post(f'/api/admin/teacher-applications/{aid}/review',json={'decision':'approved','reason':'Trusted teacher'}).status_code==403
    signed(3,'admin');assert c.post(f'/api/admin/teacher-applications/{aid}/review',json={'decision':'approved','reason':'Teaching credentials checked'}).status_code==200
    assert c.post(f'/api/admin/teacher-applications/{aid}/review',json={'decision':'approved','reason':'Repeated approval'}).status_code==409
    with env() as db:assert db.get(m.User,1).role=='teacher'

def test_rejected_request_can_be_resubmitted_without_promoting_user(env,signed):
    c=signed();first=c.post('/api/teacher-applications',json={'message':'First application'}).json()
    assert c.post('/api/teacher-applications',json={'message':'Duplicate'}).json()['id']==first['id']
    signed(3,'admin');assert c.post(f"/api/admin/teacher-applications/{first['id']}/review",json={'decision':'rejected','reason':'More details required'}).status_code==200
    signed();assert c.get('/api/me').json()['role']=='student'
    assert c.post('/api/teacher-applications',json={'message':'School confirmed'}).json()['status']=='pending'
    with env() as db:assert len(db.scalars(select(m.TeacherApplication)).all())==1

def test_teacher_can_prepare_resources_and_student_cannot(signed,monkeypatch):
    c=signed(2,'teacher');monkeypatch.setattr(ai,'embed',lambda _: [.1,.2])
    response=c.post('/api/admin/resources',data={'outcome_id':'3.1-test','title':'Binary note','source':'Teacher original'},files={'file':('note.txt',b'Binary digits are zero and one.','text/plain')})
    assert response.status_code==200
    row=c.get('/api/admin/resources').json()[0]
    assert c.post(f"/api/admin/resources/{row['id']}/review",json={'decision':'approved','reason':'Source checked'}).status_code==200
    assert c.post(f"/api/admin/resources/{row['id']}/index").status_code==200
    signed();assert c.get('/api/admin/resources').status_code==403
