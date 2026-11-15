import json
import secrets
from pathlib import Path
from sqlalchemy import select
from .database import SessionLocal
from .models import *
from .security import hash_password
from .config import settings

ROOT=Path(__file__).resolve().parents[2]
NAMES=['Concept of ICT','Introduction to Computer','Data Representation','Fundamental of Digital Circuits','Computer Operating System','Data Communication and Networking','System Analysis and Design','Database Management','Programming','Web Development','Internet of Things','ICT in Business','New trends and Future Directions of ICT','Project']

def seed():
    if settings.environment!='development':raise RuntimeError('Demo seeding is disabled outside development')
    with SessionLocal() as db:
        if db.scalar(select(User)):print('Database already seeded; no changes made.');return
        version=CurriculumVersion(id='NIE-ICT-2017',source='https://nie.lk/pdffiles/tg/eALSyl%20ICT.pdf',applicability='Effective 2017. Latest official replacement not located in 2026-11-14 search; examination applicability requires confirmation.',verified_complete=False)
        db.add(version);db.flush()
        for i,name in enumerate(NAMES,1):db.add(Unit(id=i,version_id=version.id,name=name,grade=None,verified=i<=11))
        db.flush()
        extracted=ROOT/'curriculum/extracted-review.json'
        if extracted.exists():
            for row in json.loads(extracted.read_text(encoding='utf-8'))['outcomes']:
                if 1<=row['unit_id']<=14:db.add(Outcome(**row))
        oid='NIE2017-3.1-conversion-reviewed'
        db.add(Outcome(id=oid,unit_id=3,subtopic='Analyses how numbers are represented in computers',competency='Investigates how instructions and data are represented in computers and exploit them in arithmetic and logic operations',level='3.1',text='Converts decimal integers into binary, octal and hexadecimal numbers and vice versa',source_page=21,verified=True,reviewed_at='2026-11-14'))
        db.flush()
        password=secrets.token_urlsafe(15)
        users=[]
        for role,name in [('student','Demo Student'),('teacher','Demo Teacher'),('admin','Local Administrator')]:
            user=User(email=f'{role}@ictroot.local',name=name,role=role,password=hash_password(password),grade=12);db.add(user);users.append(user)
        db.flush();student,teacher,administrator=users
        classroom=ClassRoom(name='A/L ICT · Foundation practice',grade=12,teacher_id=teacher.id,code='ICTROOT12');db.add(classroom);db.flush()
        db.add(Membership(class_id=classroom.id,student_id=student.id))
        resource=Resource(outcome_id=oid,title='Locally authored number-system revision note',source='ICTRoot original demonstration note; curriculum mapping NIE PDF page 21',text='Binary is base two and uses digits 0 and 1. Positional values from right to left are 1, 2, 4, 8, 16 and so on. Decimal thirteen equals binary 1101 because 8 + 4 + 1 = 13. Octal uses base eight and hexadecimal uses base sixteen.',reviewed=True)
        db.add(resource);db.flush()
        qs=[]
        for number in [13,10,25,42,7,31]:
            correct=format(number,'b')
            options=[{'id':letter,'text':format(value,'b'),'misconception':None if value==number else 'You may have missed a binary place value. Check each power of two.'} for letter,value in zip('ABCD',[number+1,number,number-1,number+2])]
            q=Question(outcome_id=oid,kind='mcq',difficulty='easy' if number<16 else 'medium',prompt=f'Which binary number represents decimal {number}?',options=options,key={'answer':'B'},explanation=f'{number} in decimal is {correct} in binary. Sum the powers of two in the positions containing 1.',status='approved',sources=[resource.id],author_id=teacher.id,rubric=[])
            db.add(q);qs.append(q)
        q=Question(outcome_id=oid,kind='number',difficulty='medium',prompt='Convert decimal 59 to hexadecimal. Enter only the hexadecimal digits.',options=[],key={'answer':'3B','base':16},explanation='59 = 3 × 16 + 11. The hexadecimal digit for 11 is B, giving 3B.',status='approved',sources=[resource.id],author_id=teacher.id,rubric=[])
        db.add(q);qs.append(q);db.flush()
        assessment=Assessment(title='Number systems · First steps',teacher_id=teacher.id,class_id=classroom.id,duration=15,published=True);db.add(assessment);db.flush()
        for pos,q in enumerate(qs):
            db.add(AssessmentQuestion(assessment_id=assessment.id,question_id=q.id,position=pos))
            db.add(Validation(question_id=q.id,reviewer_id=teacher.id,decision='approved',reason='Original local demo question checked by deterministic integer conversion; not official examination material.'))
        db.commit()
        print('LOCAL DEMO ACCOUNTS (save this password; it is not written to source files):')
        for role in ('student','teacher','admin'):print(f'{role}@ictroot.local : {password}')

if __name__=='__main__':seed()
