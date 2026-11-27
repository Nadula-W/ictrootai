from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from .database import get_db
from .security import current_user,admin
from . import models as m
from .schemas import Decision
router=APIRouter(prefix='/api')
class ApplicationInput(BaseModel):
    message:str=Field(default='',max_length=2000)
def public(row):return {'id':row.id,'status':row.status,'message':row.message,'reason':row.reason,'created':row.created.isoformat()}
@router.get('/teacher-applications/me')
def mine(user=Depends(current_user),db=Depends(get_db)):
    row=db.scalar(select(m.TeacherApplication).where(m.TeacherApplication.user_id==user.id))
    return public(row) if row else None
@router.post('/teacher-applications')
def apply(data:ApplicationInput,user=Depends(current_user),db=Depends(get_db)):
    if user.role!='student':raise HTTPException(409,'This account already has staff access')
    row=db.scalar(select(m.TeacherApplication).where(m.TeacherApplication.user_id==user.id).with_for_update())
    if row and row.status=='pending':return public(row)
    if row:row.status='pending';row.message=data.message;row.reason='';row.reviewer_id=None
    else:row=m.TeacherApplication(user_id=user.id,message=data.message);db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();row=db.scalar(select(m.TeacherApplication).where(m.TeacherApplication.user_id==user.id))
    return public(row)
@router.get('/admin/teacher-applications')
def applications(user=Depends(admin),db=Depends(get_db)):
    return [public(row)|{'name':person.name,'email':person.email} for row,person in db.execute(select(m.TeacherApplication,m.User).join(m.User,m.User.id==m.TeacherApplication.user_id).order_by(m.TeacherApplication.created.desc()))]
@router.post('/admin/teacher-applications/{aid}/review')
def review(aid:int,data:Decision,user=Depends(admin),db=Depends(get_db)):
    row=db.scalar(select(m.TeacherApplication).where(m.TeacherApplication.id==aid).with_for_update())
    if not row:raise HTTPException(404,'Application not found')
    if row.status!='pending':raise HTTPException(409,'Application already reviewed')
    person=db.scalar(select(m.User).where(m.User.id==row.user_id).with_for_update())
    if person.role!='student':raise HTTPException(409,'Account already has staff access')
    row.status=data.decision;row.reason=data.reason;row.reviewer_id=user.id
    if data.decision=='approved':
        person.role='teacher';db.execute(delete(m.Session).where(m.Session.user_id==person.id))
    db.commit();return public(row)
