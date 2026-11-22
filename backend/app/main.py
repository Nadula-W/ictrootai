import csv
import io
import json
import secrets
import threading
import time
import math
import httpx
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from . import models as m, ai, assessment_tools, practice
from .database import get_db
from .config import settings
from .security import current_user, staff, admin, hash_password, verify_password, digest
from .schemas import *
from .verification import mark

app=FastAPI(title='ICTRoot AI',version='0.1.0')
app.include_router(assessment_tools.router)
app.include_router(practice.router)
limits={}
limit_lock=threading.Lock()

def rate_limit(key, maximum=10, window=60):
    with limit_lock:
        now=time.monotonic()
        old=[t for t in limits.get(key,[]) if now-t<window]
        if len(old)>=maximum:
            retry_after=max(1,math.ceil(window-(now-old[0])))
            raise HTTPException(429,f'Too many requests. Try again in {retry_after} seconds.',headers={'Retry-After':str(retry_after)})
        limits[key]=old+[now]
        if len(limits)>10000:
            for k in list(limits):
                if not limits[k] or now-limits[k][-1]>window: limits.pop(k,None)

@app.middleware('http')
async def security_headers(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        allowed={'http://localhost:3000','http://127.0.0.1:3000'} if settings.environment=='development' else set()
        if origin and origin not in allowed and origin != str(request.base_url).rstrip('/'):
            return Response('Origin rejected',403)
        if int(request.headers.get('content-length','0'))>6*1024*1024:
            return Response('Upload too large',413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    return response

def public_user(user):
    return {k:getattr(user,k) for k in ('id','email','name','role','grade','language')}

def issue_session(db,user,response):
    token=secrets.token_urlsafe(48)
    db.add(m.Session(token_hash=digest(token),user_id=user.id,expires=datetime.now(timezone.utc)+timedelta(hours=12)))
    db.commit()
    response.set_cookie('ictroot_session',token,httponly=True,samesite='strict',secure=settings.secure_cookies,max_age=43200)
    return public_user(user)

@app.post('/api/auth/register')
def register(data:Register,response:Response,request:Request,db:DBSession=Depends(get_db)):
    rate_limit('register:'+request.client.host,5)
    if '@' not in data.email: raise HTTPException(422,'Valid email required')
    user=m.User(email=data.email.lower().strip(),name=data.name,password=hash_password(data.password),grade=data.grade,role='student')
    db.add(user)
    try: db.flush()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Account already exists')
    return issue_session(db,user,response)

@app.post('/api/auth/login')
def login(data:Credentials,response:Response,request:Request,db:DBSession=Depends(get_db)):
    rate_limit('login:'+request.client.host,15)
    user=db.scalar(select(m.User).where(m.User.email==data.email.lower().strip()))
    if not user or not verify_password(data.password,user.password): raise HTTPException(401,'Invalid email or password')
    return issue_session(db,user,response)

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,db:DBSession=Depends(get_db)):
    session=db.get(m.Session,digest(request.cookies.get('ictroot_session','')))
    if session: db.delete(session);db.commit()
    response.delete_cookie('ictroot_session');return {'ok':True}

@app.get('/api/me')
def me(user=Depends(current_user)): return public_user(user)

class Preferences(BaseModel):
    grade:Literal[12,13]
    language:Literal['en','si']

@app.patch('/api/me')
def preferences(data:Preferences,user=Depends(current_user),db:DBSession=Depends(get_db)):
    user.grade=data.grade;user.language=data.language;db.commit();return public_user(user)

@app.get('/api/health')
def health(db:DBSession=Depends(get_db)):
    db.execute(text('SELECT 1'));return {'backend':'ok','database':'ok'}

def owned_class(db,cid,user):
    classroom=db.get(m.ClassRoom,cid)
    if not classroom or (user.role!='admin' and classroom.teacher_id!=user.id): raise HTTPException(404,'Class not found')
    return classroom

def accessible_assessment(db,aid,user):
    assessment=db.get(m.Assessment,aid)
    if not assessment: raise HTTPException(404,'Assessment not found')
    if user.role=='student':
        if not assessment.published or not db.get(m.Membership,(assessment.class_id,user.id)): raise HTTPException(404,'Assessment not found')
    elif user.role!='admin' and assessment.teacher_id!=user.id: raise HTTPException(404,'Assessment not found')
    return assessment

@app.get('/api/classes')
def classes(user=Depends(current_user),db:DBSession=Depends(get_db)):
    stmt=select(m.ClassRoom)
    if user.role=='student': stmt=stmt.join(m.Membership).where(m.Membership.student_id==user.id)
    elif user.role!='admin':stmt=stmt.where(m.ClassRoom.teacher_id==user.id)
    return [{'id':c.id,'name':c.name,'grade':c.grade,'code':c.code,'members':len(db.scalars(select(m.Membership).where(m.Membership.class_id==c.id)).all())} for c in db.scalars(stmt)]

class ClassInput(BaseModel):
    name:str=Field(min_length=3,max_length=120)
    grade:Literal[12,13]

@app.post('/api/classes')
def create_class(data:ClassInput,user=Depends(staff),db:DBSession=Depends(get_db)):
    c=m.ClassRoom(**data.model_dump(),teacher_id=user.id,code=secrets.token_hex(4).upper());db.add(c);db.commit();return {'id':c.id,'code':c.code}

class JoinInput(BaseModel):
    code:str=Field(max_length=20)

@app.post('/api/classes/join')
def join_class(data:JoinInput,user=Depends(current_user),db:DBSession=Depends(get_db)):
    if user.role!='student':raise HTTPException(403,'Student access required')
    rate_limit(f'join:{user.id}',10)
    c=db.scalar(select(m.ClassRoom).where(m.ClassRoom.code==data.code.upper().strip()))
    if not c:raise HTTPException(404,'Class code not found')
    if not db.get(m.Membership,(c.id,user.id)):db.add(m.Membership(class_id=c.id,student_id=user.id));db.commit()
    return {'ok':True}

@app.get('/api/curriculum')
def curriculum(user=Depends(current_user),db:DBSession=Depends(get_db)):
    units=db.scalars(select(m.Unit).order_by(m.Unit.id)).all()
    versions=db.scalars(select(m.CurriculumVersion)).all()
    outcomes=db.scalars(select(m.Outcome)).all()
    levels=sorted(db.scalars(select(m.CompetencyLevel)).all(),key=lambda level:(level.unit_id,tuple(int(part) for part in level.level.split('.'))))
    marker=db.get(m.AppSetting,'curriculum_inventory')
    inventory=inventory_status(marker,outcomes,versions)
    inventory['level_count']=len(levels)
    outcomes_by_unit={u.id:[] for u in units}
    levels_by_unit={u.id:[] for u in units}
    for o in outcomes:
        outcomes_by_unit.setdefault(o.unit_id,[]).append({'id':o.id,'text':o.text,'level':o.level,'subtopic':o.subtopic,'competency':o.competency,'source_page':o.source_page,'source_pages':o.source_pages or [o.source_page],'verified':o.verified,'reviewed_at':o.reviewed_at,'review_note':o.review_note,'catalogued':o.catalogued})
    for level in levels:
        levels_by_unit.setdefault(level.unit_id,[]).append({key:getattr(level,key) for key in ('id','level','title','source_pages','contents','periods','review_note')}|{'source_verified':True})
    return {'inventory':inventory,'versions':[{'id':v.id,'source':v.source,'applicability':v.applicability,'verified_complete':v.verified_complete} for v in versions], 'units':[{'id':u.id,'name':u.name,'grade':u.grade,'verified':u.verified,'levels':levels_by_unit[u.id],'outcomes':outcomes_by_unit[u.id]} for u in units]}

def inventory_status(marker,outcomes,versions):
    try:inventory=json.loads(marker.value) if marker else {}
    except (ValueError,TypeError):inventory={}
    official=[o for o in outcomes if o.catalogued]
    verified=sum(o.verified for o in official)
    complete=bool(inventory.get('complete') and inventory.get('outcome_count')==len(official)==verified and any(v.id==inventory.get('version_id') and v.verified_complete for v in versions))
    return {**inventory,'unit_count':inventory.get('unit_count',0),'level_count':inventory.get('level_count',0),'outcome_count':len(official),'verified_outcome_count':verified,'complete':complete,'exam_applicability_verified':False}

@app.get('/api/curriculum/source')
def curriculum_source():
    return FileResponse(Path(__file__).resolve().parents[2]/'curriculum/nie-ict-2017.pdf',media_type='application/pdf',headers={'Content-Disposition':'inline; filename="nie-ict-2017.pdf"'})

@app.post('/api/admin/curriculum')
def import_curriculum(data:CurriculumImport,user=Depends(admin),db:DBSession=Depends(get_db)):
    for row in data.outcomes:
        if not db.get(m.Unit,row.unit_id):raise HTTPException(422,'Unknown unit')
        o=db.get(m.Outcome,row.id)
        if not o: o=m.Outcome(**row.model_dump());db.add(o)
        else:
            if o.catalogued and any(getattr(o,k)!=v for k,v in row.model_dump().items()):
                o.catalogued=False
                db.get(m.CurriculumVersion,db.get(m.Unit,o.unit_id).version_id).verified_complete=False
            for k,v in row.model_dump().items():setattr(o,k,v)
        o.reviewed_at=datetime.now(timezone.utc).isoformat() if row.verified else None
    db.commit();return {'imported':len(data.outcomes)}

@app.get('/api/coverage')
def coverage(user=Depends(current_user),db:DBSession=Depends(get_db)):
    # Load each collection once: cloud round trips must not scale with outcomes
    # or question counts. Select only coverage metadata, never answer-key JSON.
    outcomes=db.scalars(select(m.Outcome)).all()
    approved_by_outcome={}
    for q in db.execute(select(m.Question.id,m.Question.outcome_id,m.Question.kind,m.Question.difficulty).where(m.Question.status=='approved')):
        approved_by_outcome.setdefault(q.outcome_id,[]).append(q)
    reviewed_outcomes=set(db.scalars(select(m.Resource.outcome_id).where(m.Resource.reviewed==True)))
    reviewed_translations=set(db.scalars(select(m.Translation.question_id).where(m.Translation.reviewed==True,m.Translation.language=='si')))
    versions=db.scalars(select(m.CurriculumVersion)).all()
    marker=db.get(m.AppSetting,'curriculum_inventory')
    inventory=inventory_status(marker,outcomes,versions)
    complete=inventory['complete']
    rows=[]
    for o in outcomes:
        qs=approved_by_outcome.get(o.id,[])
        translated=any(q.id in reviewed_translations for q in qs)
        rows.append({'id':o.id,'text':o.text,'unit_id':o.unit_id,'verified':o.verified,'catalogued':o.catalogued,'approved_questions':len(qs),'formats':sorted({q.kind for q in qs}),'difficulties':sorted({q.difficulty for q in qs}),'sinhala':translated,'reviewed_at':o.reviewed_at,'covered':bool(o.verified and qs and o.id in reviewed_outcomes)})
    official=[r for r in rows if r['catalogued']]
    source_coverage=round(100*sum(r['covered'] for r in official)/len(official),1) if complete and official else None
    warning='The 2017 source inventory is verified. Question coverage is separate; Project has no explicit outcome bullets. Current examination-year applicability still requires official confirmation.' if complete else 'Coverage of imported outcomes only. Complete official outcome inventory and examination applicability are not yet verified.'
    return {'outcomes':rows,'imported_outcomes':len(rows),'covered_outcomes':sum(r['covered'] for r in rows),'official_outcomes':len(official),'source_verified_outcomes':inventory['verified_outcome_count'],'source_outcome_coverage_percentage':source_coverage,'official_denominator_verified':complete,'full_syllabus_percentage':None,'warning':warning}

def question_public(q,user,language,db):
    result={k:getattr(q,k) for k in ('id','outcome_id','kind','difficulty','prompt','status')}
    result['options']=[{'id':o['id'],'text':o['text']} for o in q.options]
    result['language']='en';result['language_notice']=None
    if language=='si':
        tr=db.scalar(select(m.Translation).where(m.Translation.question_id==q.id,m.Translation.language=='si',m.Translation.reviewed==True))
        if tr: result.update(tr.content);result['language']='si'
        else:result['language_notice']='Reviewed Sinhala translation unavailable. Showing original English.'
    if user.role!='student':result.update(key=q.key,explanation=q.explanation,sources=q.sources,rubric=q.rubric,options=q.options)
    return result

@app.get('/api/questions')
def questions(outcome_id:str|None=None,language:Literal['en','si']='en',user=Depends(staff),db:DBSession=Depends(get_db)):
    stmt=select(m.Question)
    if user.role!='admin':stmt=stmt.where((m.Question.status=='approved') | (m.Question.author_id==user.id))
    if outcome_id:stmt=stmt.where(m.Question.outcome_id==outcome_id)
    return [question_public(q,user,language,db) for q in db.scalars(stmt)]

@app.post('/api/questions')
def create_question(data:QuestionDraft,user=Depends(staff),db:DBSession=Depends(get_db)):
    if not db.get(m.Outcome,data.outcome_id):raise HTTPException(422,'Unknown learning outcome')
    q=m.Question(**data.model_dump(),author_id=user.id,status='draft');db.add(q);db.commit();return {'id':q.id}

@app.post('/api/questions/{qid}/review')
def review_question(qid:int,data:Decision,user=Depends(staff),db:DBSession=Depends(get_db)):
    q=db.get(m.Question,qid)
    if not q or (user.role!='admin' and q.author_id!=user.id):raise HTTPException(404,'Draft not found')
    try:QuestionDraft.model_validate({k:getattr(q,k) for k in QuestionDraft.model_fields})
    except ValueError:raise HTTPException(422,'Question configuration is invalid; create a corrected draft before approval')
    if q.status=='approved':raise HTTPException(409,'Approved questions are immutable; create a new draft')
    if data.decision=='approved' and q.sources:
        for rid in q.sources:
            r=db.get(m.Resource,rid)
            if not r or not r.reviewed or r.outcome_id!=q.outcome_id:raise HTTPException(422,'Sources must be reviewed and linked to the same outcome')
    q.status=data.decision;db.add(m.Validation(question_id=q.id,reviewer_id=user.id,decision=data.decision,reason=data.reason));db.commit();return {'status':q.status}

@app.post('/api/assessments')
def create_assessment(data:AssessmentCreate,user=Depends(staff),db:DBSession=Depends(get_db)):
    owned_class(db,data.class_id,user)
    if len(set(data.question_ids))!=len(data.question_ids):raise HTTPException(422,'Duplicate question IDs')
    for qid in data.question_ids:
        q=db.get(m.Question,qid)
        if not q or q.status!='approved':raise HTTPException(422,'Only approved questions can be assigned')
    a=m.Assessment(**data.model_dump(exclude={'question_ids'}),teacher_id=user.id);db.add(a);db.flush()
    for pos,qid in enumerate(data.question_ids):db.add(m.AssessmentQuestion(assessment_id=a.id,question_id=qid,position=pos))
    db.commit();return {'id':a.id}

@app.get('/api/assessments')
def assessments(user=Depends(current_user),db:DBSession=Depends(get_db)):
    from sqlalchemy import func
    from .assessment_lifecycle import finalize_expired
    stmt=select(m.Assessment)
    if user.role=='student':stmt=stmt.join(m.Membership,m.Membership.class_id==m.Assessment.class_id).where(m.Membership.student_id==user.id,m.Assessment.published==True)
    elif user.role!='admin':stmt=stmt.where(m.Assessment.teacher_id==user.id)
    visible=db.scalars(stmt).all();ids=[a.id for a in visible]
    if finalize_expired(db,assessment_ids=ids,student_id=user.id if user.role=='student' else None):db.commit()
    attempts={a.assessment_id:a for a in db.scalars(select(m.Attempt).where(m.Attempt.assessment_id.in_(ids),m.Attempt.student_id==user.id))}
    counts=dict(db.execute(select(m.AssessmentQuestion.assessment_id,func.count()).where(m.AssessmentQuestion.assessment_id.in_(ids)).group_by(m.AssessmentQuestion.assessment_id)).all())
    return [{'id':a.id,'title':a.title,'duration':a.duration,'class_id':a.class_id,'questions':counts.get(a.id,0),'published':a.published,'attempt_id':attempts[a.id].id if a.id in attempts else None,'submitted':attempts[a.id].submitted if a.id in attempts else False} for a in visible]

@app.post('/api/assessments/{aid}/start')
def start(aid:int,user=Depends(current_user),db:DBSession=Depends(get_db)):
    if user.role!='student':raise HTTPException(403,'Student access required')
    accessible_assessment(db,aid,user)
    attempt=db.scalar(select(m.Attempt).where(m.Attempt.assessment_id==aid,m.Attempt.student_id==user.id))
    if not attempt:
        attempt=m.Attempt(assessment_id=aid,student_id=user.id);db.add(attempt)
        try:db.commit()
        except IntegrityError:
            db.rollback();attempt=db.scalar(select(m.Attempt).where(m.Attempt.assessment_id==aid,m.Attempt.student_id==user.id))
    return {'id':attempt.id}

def owned_attempt(db,tid,user,lock=False):
    stmt=select(m.Attempt).where(m.Attempt.id==tid)
    if lock:stmt=stmt.with_for_update()
    attempt=db.scalar(stmt)
    if not attempt:raise HTTPException(404,'Attempt not found')
    if user.role=='student' and attempt.student_id!=user.id:raise HTTPException(404,'Attempt not found')
    accessible_assessment(db,attempt.assessment_id,user)
    return attempt

def attempt_questions(db,attempt):
    return db.scalars(select(m.Question).join(m.AssessmentQuestion).where(m.AssessmentQuestion.assessment_id==attempt.assessment_id).order_by(m.AssessmentQuestion.position)).all()

def deadline(db,attempt):
    from .assessment_lifecycle import attempt_deadline
    return attempt_deadline(attempt.started,db.get(m.Assessment,attempt.assessment_id).duration)

@app.get('/api/attempts/{tid}')
def get_attempt(tid:int,language:Literal['en','si']='en',user=Depends(current_user),db:DBSession=Depends(get_db)):
    from .assessment_lifecycle import finalize_expired
    a=owned_attempt(db,tid,user)
    if finalize_expired(db,attempt_ids=[a.id]):db.commit()
    if not a.submitted:db.refresh(a,attribute_names=['submitted'])
    answers=db.scalars(select(m.Answer).where(m.Answer.attempt_id==a.id)).all()
    return {'id':a.id,'title':db.get(m.Assessment,a.assessment_id).title,'submitted':a.submitted,'deadline':deadline(db,a).isoformat(),'questions':[question_public(q,user,language,db) for q in attempt_questions(db,a)],'answers':{str(x.question_id):x.value for x in answers}}

@app.put('/api/attempts/{tid}/answers/{qid}')
def save_answer(tid:int,qid:int,data:AnswerInput,user=Depends(current_user),db:DBSession=Depends(get_db)):
    a=owned_attempt(db,tid,user,True)
    if user.role!='student':raise HTTPException(403,'Student access required')
    # Atomic guard serializes writes with submission in PostgreSQL.
    guarded=db.execute(update(m.Attempt).where(m.Attempt.id==a.id,m.Attempt.submitted==False).values(submitted=False))
    if guarded.rowcount!=1:raise HTTPException(409,'Attempt already submitted')
    if datetime.now(timezone.utc)>=deadline(db,a):raise HTTPException(409,'Time expired; no further answers can be saved')
    if qid not in [q.id for q in attempt_questions(db,a)]:raise HTTPException(404,'Question not in assessment')
    q=db.get(m.Question,qid)
    if q.kind=='mcq' and data.value not in [o['id'] for o in q.options]:raise HTTPException(422,'Unknown option ID')
    row=db.get(m.Answer,(tid,qid))
    if row:row.value=data.value
    else:db.add(m.Answer(attempt_id=tid,question_id=qid,value=data.value))
    db.commit();return {'saved':True}

@app.post('/api/attempts/{tid}/submit')
def submit(tid:int,user=Depends(current_user),db:DBSession=Depends(get_db)):
    from .assessment_lifecycle import grade_saved_answers
    a=owned_attempt(db,tid,user,True)
    if user.role!='student':raise HTTPException(403,'Student access required')
    guard=db.execute(update(m.Attempt).where(m.Attempt.id==a.id,m.Attempt.submitted==False).values(submitted=True))
    if guard.rowcount!=1:raise HTTPException(409,'Attempt already submitted')
    grade_saved_answers(db,[a])
    db.commit();return {'submitted':True}

@app.get('/api/attempts/{tid}/results')
def results(tid:int,user=Depends(current_user),db:DBSession=Depends(get_db)):
    from .assessment_lifecycle import finalize_expired
    a=owned_attempt(db,tid,user)
    if finalize_expired(db,attempt_ids=[a.id]):db.commit()
    if not a.submitted:db.refresh(a,attribute_names=['submitted'])
    if not a.submitted:raise HTTPException(409,'Submit assessment to see answers')
    items=[]
    for q in attempt_questions(db,a):
        answer=db.get(m.Answer,(tid,q.id))
        possible=next((o.get('misconception') for o in q.options if o['id']==answer.value),None) if answer.score==0 else None
        follow=db.scalar(select(m.Question).where(m.Question.outcome_id==q.outcome_id,m.Question.status=='approved',m.Question.id!=q.id))
        correct_answer=next((o['text'] for o in q.options if o['id']==q.key.get('answer')),None) if q.kind=='mcq' else q.key.get('answer')
        items.append({'question_id':q.id,'prompt':q.prompt,'value':answer.value,'score':answer.score,'key':q.key,'correct_answer':correct_answer,'rubric':q.rubric,'explanation':q.explanation,'reason':answer.reason,'possible_misconception':possible,'misconception_notice':'Possible explanation only; a single answer is insufficient evidence.' if possible else None,'revise':db.get(m.Outcome,q.outcome_id).text,'follow_up':follow.prompt if follow else 'Ask your teacher for another reviewed question on this outcome.'})
    return {'id':tid,'score':sum(x['score'] or 0 for x in items),'total':len(items),'pending':sum(x['score'] is None for x in items),'items':items}

@app.get('/api/progress')
def progress(user=Depends(current_user),db:DBSession=Depends(get_db)):
    from .assessment_lifecycle import finalize_expired
    if finalize_expired(db,student_id=user.id):db.commit()
    rows=db.execute(select(m.Answer.score,m.Question.outcome_id,m.Outcome.text).select_from(m.Answer).join(m.Attempt,m.Answer.attempt_id==m.Attempt.id).join(m.Question,m.Answer.question_id==m.Question.id).join(m.Outcome,m.Outcome.id==m.Question.outcome_id).where(m.Attempt.student_id==user.id,m.Attempt.submitted==True).order_by(m.Attempt.started,m.Attempt.id,m.Question.id)).all()
    topics={}
    names={}
    for row in rows:
        if row.score is None:continue
        topics.setdefault(row.outcome_id,[]).append(row.score);names[row.outcome_id]=row.text
    return [{'outcome_id':oid,'text':names[oid],'answered':len(scores),'accuracy':round(100*sum(scores)/len(scores)),'recommended_difficulty':'easy' if sum(scores[-5:])/len(scores[-5:])<0.5 else ('hard' if len(scores)>=3 and sum(scores[-5:])/len(scores[-5:])>=0.8 else 'medium')} for oid,scores in topics.items()]

@app.get('/api/history')
def history(user=Depends(current_user),db:DBSession=Depends(get_db)):
    from .assessment_lifecycle import finalize_expired
    if finalize_expired(db,student_id=user.id):db.commit()
    return [{'id':a.id,'title':title,'started':a.started.isoformat(),'submitted':a.submitted} for a,title in db.execute(select(m.Attempt,m.Assessment.title).join(m.Assessment,m.Assessment.id==m.Attempt.assessment_id).where(m.Attempt.student_id==user.id).order_by(m.Attempt.started.desc(),m.Attempt.id.desc()))]

@app.get('/api/teacher/submissions')
def submissions(user=Depends(staff),db:DBSession=Depends(get_db)):
    from sqlalchemy import func
    from .assessment_lifecycle import finalize_expired
    scope=select(m.Assessment.id)
    if user.role!='admin':scope=scope.where(m.Assessment.teacher_id==user.id)
    if finalize_expired(db,assessment_ids=list(db.scalars(scope))):db.commit()
    answer_stats=select(m.Answer.attempt_id.label('attempt_id'),func.sum(m.Answer.score).label('score'),func.count(m.Answer.question_id).filter(m.Answer.score.is_(None)).label('pending')).group_by(m.Answer.attempt_id).subquery()
    question_counts=select(m.AssessmentQuestion.assessment_id.label('assessment_id'),func.count().label('total')).group_by(m.AssessmentQuestion.assessment_id).subquery()
    stmt=select(m.Attempt.id,m.User.name.label('student'),m.Assessment.title,answer_stats.c.score,answer_stats.c.pending,question_counts.c.total).select_from(m.Attempt).join(m.Assessment,m.Assessment.id==m.Attempt.assessment_id).join(m.User,m.User.id==m.Attempt.student_id).outerjoin(answer_stats,answer_stats.c.attempt_id==m.Attempt.id).outerjoin(question_counts,question_counts.c.assessment_id==m.Assessment.id).where(m.Attempt.submitted==True)
    if user.role!='admin':stmt=stmt.where(m.Assessment.teacher_id==user.id)
    return [{'id':row.id,'student':row.student,'title':row.title,'score':row.score or 0,'total':row.total or 0,'pending':row.pending or 0} for row in db.execute(stmt.order_by(m.Attempt.started.desc(),m.Attempt.id.desc()))]

class GradeInput(BaseModel):
    score:float=Field(ge=0,le=1)
    reason:str=Field(min_length=5,max_length=2000)

@app.post('/api/attempts/{tid}/answers/{qid}/review')
def grade(tid:int,qid:int,data:GradeInput,user=Depends(staff),db:DBSession=Depends(get_db)):
    a=owned_attempt(db,tid,user,True)
    if not a.submitted:raise HTTPException(409,'Attempt not submitted')
    answer=db.get(m.Answer,(tid,qid))
    if not answer:raise HTTPException(404,'Answer not found')
    answer.score=data.score;answer.reason=data.reason;answer.reviewed_by=user.id
    db.add(m.TeacherReview(attempt_id=tid,question_id=qid,teacher_id=user.id,**data.model_dump()));db.commit();return {'ok':True}

@app.get('/api/teacher/export')
def export(user=Depends(staff),db:DBSession=Depends(get_db)):
    output=io.StringIO();writer=csv.writer(output);writer.writerow(['attempt','student','assessment','score','total','pending'])
    for r in submissions(user,db):
        writer.writerow([r['id'],*("'"+str(r[k]) if str(r[k]).startswith(('=','+','-','@')) else r[k] for k in ('student','title','score','total','pending'))])
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=ictroot-report.csv'})

@app.get('/api/admin/ai')
def ai_status(user=Depends(admin),db:DBSession=Depends(get_db)):
    try:
        models=ai.local_models();return {'connected':True,'models':[m['name'] for m in models],'selected':ai.model_name(db),'embedding_model':settings.embedding_model,'embedding_available':ai.model_installed(settings.embedding_model,models)}
    except Exception:return {'connected':False,'models':[],'selected':ai.model_name(db),'embedding_available':False,'message':'Ollama unavailable. Approved questions and deterministic marking remain usable.'}

class ModelInput(BaseModel):
    model:str=Field(max_length=150)

@app.put('/api/admin/ai')
def configure_model(data:ModelInput,user=Depends(admin),db:DBSession=Depends(get_db)):
    try:names=[x['name'] for x in ai.local_models()]
    except Exception:raise HTTPException(503,'Ollama unavailable')
    if data.model not in names:raise HTTPException(422,'Choose an installed local model')
    row=db.get(m.AppSetting,'ollama_model')
    if row:row.value=data.model
    else:db.add(m.AppSetting(key='ollama_model',value=data.model))
    db.commit();return {'selected':data.model}

@app.get('/api/ai/readiness')
def generation_readiness(outcome_id:str,user=Depends(staff),db:DBSession=Depends(get_db)):
    outcome=db.get(m.Outcome,outcome_id)
    if not outcome or not outcome.verified:
        return {'ready':False,'code':'outcome_unverified','message':'This syllabus learning outcome has not been checked against its official source. Choose a source-verified outcome or ask an administrator to review it.','outcome_id':outcome_id,'reviewed_resources':0,'indexed_resources':0}
    resources=db.scalars(select(m.Resource).where(m.Resource.outcome_id==outcome.id)).all()
    reviewed=[r for r in resources if r.reviewed]
    response={'outcome_id':outcome_id,'reviewed_resources':len(reviewed),'indexed_resources':sum(bool(r.embedding) and r.embedding_model==settings.embedding_model for r in reviewed)}
    try:ai.require_generation_setup(db,resources)
    except ai.AISetupError as error:return {**response,'ready':False,'code':error.code,'message':str(error)}
    return {**response,'ready':True,'code':'ready','message':'Local models and reviewed resource index are available. Generated questions will still need teacher approval.'}

@app.post('/api/ai/generate')
def generate_question(data:GenerateInput,response:Response,user=Depends(staff),db:DBSession=Depends(get_db)):
    outcome=db.get(m.Outcome,data.outcome_id)
    if not outcome or not outcome.verified:raise HTTPException(422,'Select a source-verified learning outcome')
    resources=db.scalars(select(m.Resource).where(m.Resource.outcome_id==outcome.id)).all()
    try:ai.require_generation_setup(db,resources)
    except ai.AISetupError as error:
        # Setup checks perform no inference and must not consume the inference limit.
        db.add(m.GenerationLog(model=ai.model_name(db),outcome_id=outcome.id,status=error.code));db.commit()
        response.status_code=503
        return {'detail':str(error),'error_code':error.code}
    rate_limit(f'ai:{user.id}',3,60)
    try:draft=ai.generate(db,data,outcome,resources)
    except ai.AISetupError as error:
        db.add(m.GenerationLog(model=ai.model_name(db),outcome_id=outcome.id,status=error.code));db.commit()
        response.status_code=503
        return {'detail':str(error),'error_code':error.code}
    except httpx.TimeoutException:
        db.add(m.GenerationLog(model=ai.model_name(db),outcome_id=outcome.id,status='generation_timeout'));db.commit()
        raise HTTPException(503,'Local AI took too long to respond. Wait before trying again, or use manual drafting.')
    except Exception as error:
        db.add(m.GenerationLog(model=ai.model_name(db),outcome_id=outcome.id,status=type(error).__name__));db.commit()
        raise HTTPException(503,'Generation unavailable or invalid response. Check Ollama, embeddings and reviewed resources. Use manual drafting.')
    q=m.Question(**draft.model_dump(),author_id=user.id,status='draft');db.add(q)
    db.add(m.GenerationLog(model=ai.model_name(db),outcome_id=outcome.id,status='draft_created'));db.commit();return {'id':q.id,'status':'draft'}

@app.get('/api/admin/resources')
def resources(user=Depends(admin),db:DBSession=Depends(get_db)):
    return [{'id':r.id,'outcome_id':r.outcome_id,'title':r.title,'source':r.source,'text':r.text,'reviewed':r.reviewed,'indexed':bool(r.embedding)} for r in db.scalars(select(m.Resource))]

@app.post('/api/admin/resources')
async def upload_resource(outcome_id:str=Form(...),title:str=Form(...),source:str=Form(...),file:UploadFile=File(...),user=Depends(admin),db:DBSession=Depends(get_db)):
    if not db.get(m.Outcome,outcome_id):raise HTTPException(422,'Unknown learning outcome')
    data=await file.read(5*1024*1024+1)
    if len(data)>5*1024*1024:raise HTTPException(413,'Maximum file size is 5 MB')
    name=(file.filename or '').lower()
    try:
        if name.endswith('.pdf'):
            from pypdf import PdfReader
            reader=PdfReader(io.BytesIO(data))
            if len(reader.pages)>200:raise ValueError('Too many pages')
            content='\n'.join(p.extract_text() or '' for p in reader.pages)
        elif name.endswith('.txt'):content=data.decode('utf-8-sig')
        elif name.endswith('.json'):
            raw=json.loads(data);content=raw['text']
            if not isinstance(content,str):raise ValueError('text must be a string')
        else:raise ValueError('Unsupported file')
        if not content.strip() or len(content)>1000000:raise ValueError('Empty or oversized extracted content')
    except Exception:raise HTTPException(422,'Cannot extract this document; use PDF, UTF-8 TXT, or JSON with a text field')
    chunks=[content[i:i+1600] for i in range(0,len(content),1400)]
    for chunk in chunks:db.add(m.Resource(outcome_id=outcome_id,title=title[:200],source=source[:2000],text=chunk,reviewed=False))
    db.commit();return {'chunks':len(chunks),'status':'unreviewed'}

@app.post('/api/admin/resources/{rid}/review')
def review_resource(rid:int,data:Decision,user=Depends(admin),db:DBSession=Depends(get_db)):
    r=db.get(m.Resource,rid)
    if not r:raise HTTPException(404,'Resource not found')
    r.reviewed=data.decision=='approved';r.embedding=None;r.embedding_model=None;db.commit();return {'reviewed':r.reviewed}

@app.post('/api/admin/resources/{rid}/index')
def index_resource(rid:int,user=Depends(admin),db:DBSession=Depends(get_db)):
    rate_limit(f'index:{user.id}',10)
    r=db.get(m.Resource,rid)
    if not r or not r.reviewed:raise HTTPException(422,'Review resource before indexing')
    try:r.embedding=ai.embed(r.text);r.embedding_model=settings.embedding_model
    except Exception:raise HTTPException(503,'Local embedding model unavailable. See README setup.')
    db.commit();return {'indexed':True}

@app.get('/api/admin/users')
def users(user=Depends(admin),db:DBSession=Depends(get_db)):return [public_user(u) for u in db.scalars(select(m.User))]

class RoleInput(BaseModel):
    role:Literal['student','teacher','admin']

@app.patch('/api/admin/users/{uid}')
def set_role(uid:int,data:RoleInput,user=Depends(admin),db:DBSession=Depends(get_db)):
    if uid==user.id:raise HTTPException(422,'Cannot change your own role')
    target=db.get(m.User,uid)
    if not target:raise HTTPException(404,'User not found')
    target.role=data.role
    for s in db.scalars(select(m.Session).where(m.Session.user_id==uid)):db.delete(s)
    db.commit();return public_user(target)

@app.get('/api/admin/logs')
def logs(user=Depends(admin),db:DBSession=Depends(get_db)):
    return [{'id':r.id,'model':r.model,'outcome_id':r.outcome_id,'status':r.status,'created':r.created.isoformat()} for r in db.scalars(select(m.GenerationLog).order_by(m.GenerationLog.id.desc()).limit(100))]

class TranslationInput(BaseModel):
    prompt:str=Field(min_length=5,max_length=10000)
    options:list[dict]=Field(default_factory=list,max_length=5)

@app.put('/api/questions/{qid}/translation')
def translation_draft(qid:int,data:TranslationInput,user=Depends(staff),db:DBSession=Depends(get_db)):
    q=db.get(m.Question,qid)
    if not q or (user.role!='admin' and q.author_id!=user.id):raise HTTPException(404,'Question not found')
    if q.kind=='mcq' and [o.get('id') for o in data.options]!=[o['id'] for o in q.options]:raise HTTPException(422,'Translation must preserve option IDs and order')
    # Only display fields can be translated; answer keys and identifiers stay unchanged.
    content={'prompt':data.prompt,'options':[{'id':o.get('id'),'text':str(o.get('text',''))[:1000]} for o in data.options]}
    tr=db.scalar(select(m.Translation).where(m.Translation.question_id==qid,m.Translation.language=='si'))
    if tr:tr.content=content;tr.reviewed=False
    else:db.add(m.Translation(question_id=qid,language='si',content=content,reviewed=False))
    db.commit();return {'status':'translation_draft'}

@app.post('/api/questions/{qid}/translation/review')
def review_translation(qid:int,data:Decision,user=Depends(staff),db:DBSession=Depends(get_db)):
    q=db.get(m.Question,qid)
    if not q or (user.role!='admin' and q.author_id!=user.id):raise HTTPException(404,'Question not found')
    tr=db.scalar(select(m.Translation).where(m.Translation.question_id==qid,m.Translation.language=='si'))
    if not tr:raise HTTPException(404,'Translation draft not found')
    tr.reviewed=data.decision=='approved'
    db.add(m.Validation(question_id=qid,reviewer_id=user.id,decision='translation_'+data.decision,reason=data.reason));db.commit();return {'reviewed':tr.reviewed}
