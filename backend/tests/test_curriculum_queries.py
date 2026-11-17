"""PostgreSQL regressions for batched curriculum/dashboard reads.

The env fixture requires an explicit disposable TEST_DATABASE_URL and owns its
temporary schema; these tests never use the application's configured database.
"""
from contextlib import contextmanager

from sqlalchemy import event, select

from app import models as m
from app.main import coverage, curriculum


@contextmanager
def count_reads(db):
    statements=[]
    connection=db.connection()

    def record(_connection,_cursor,statement,_parameters,_context,_many):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)

    event.listen(connection,'before_cursor_execute',record)
    try:
        yield statements
    finally:
        event.remove(connection,'before_cursor_execute',record)


def test_curriculum_batches_outcomes_and_preserves_unit_order(env):
    with env() as db:
        user=db.get(m.User,1)
        for uid in (9,1):
            db.add(m.Unit(id=uid,version_id='test',name=f'Unit {uid}',grade=None,verified=False))
        db.flush()
        for i in range(45):
            db.add(m.Outcome(id=f'batch-{i:03}',unit_id=(1,3,9)[i%3],subtopic='Fixture subtopic',competency='Fixture competency',level='1.1',text=f'Fixture outcome {i}',source_page=1,verified=False))
        db.flush()
        original_order=[o.id for o in db.scalars(select(m.Outcome))]
        with count_reads(db) as queries:
            result=curriculum(user=user,db=db)

        assert len(queries)==3
        assert [u['id'] for u in result['units']]==[1,3,9]
        assert result['versions']==[{'id':'test','source':'NIE test reference','applicability':'Test fixture only','verified_complete':False}]
        for unit in result['units']:
            expected=[oid for oid in original_order if (oid=='3.1-test' and unit['id']==3) or (oid.startswith('batch-') and (1,3,9)[int(oid[6:])%3]==unit['id'])]
            assert [o['id'] for o in unit['outcomes']]==expected
            assert all(set(o)=={'id','text','level','subtopic','competency','source_page','verified','reviewed_at'} for o in unit['outcomes'])


def test_coverage_is_five_reads_with_reviewed_only_counts(env):
    with env() as db:
        user=db.get(m.User,1)
        for oid,verified in [('covered',True),('unreviewed-material',True),('unverified-outcome',False),('unreviewed-translation',True)]:
            db.add(m.Outcome(id=oid,unit_id=3,subtopic='Fixture',competency='Fixture',level='3.1',text=oid,source_page=21,verified=verified))
        # Extra empty outcomes must not increase database round trips.
        for i in range(45):
            db.add(m.Outcome(id=f'empty-{i:03}',unit_id=3,subtopic='Fixture',competency='Fixture',level='3.1',text=f'Empty fixture {i}',source_page=21,verified=False))
        db.flush()
        data=[(100,'covered','mcq','easy','approved'),(101,'covered','output','hard','approved'),(102,'covered','short','medium','draft'),(103,'unreviewed-material','mcq','medium','approved'),(104,'unverified-outcome','mcq','medium','approved'),(105,'unreviewed-translation','mcq','medium','approved'),(106,'unreviewed-translation','mcq','hard','draft')]
        for qid,oid,kind,difficulty,status in data:
            db.add(m.Question(id=qid,outcome_id=oid,kind=kind,difficulty=difficulty,prompt='Fixture question',options=[],key={'answer':'private-key'},explanation='Private explanation',status=status,author_id=2,sources=[],rubric=[]))
        for oid,reviewed in [('covered',True),('unreviewed-material',False),('unverified-outcome',True),('unreviewed-translation',True)]:
            db.add(m.Resource(outcome_id=oid,title='Fixture',source='Fixture source',text='Fixture material',reviewed=reviewed))
        db.flush()
        for qid,reviewed in [(100,False),(101,True),(105,False),(106,True)]:
            db.add(m.Translation(question_id=qid,language='si',content={'prompt':'Translation fixture'},reviewed=reviewed))
        db.flush()
        expected_order=[o.id for o in db.scalars(select(m.Outcome))]
        with count_reads(db) as queries:
            result=coverage(user=user,db=db)

        assert len(queries)==5
        assert not any('questions.key' in sql or 'questions.explanation' in sql for sql in queries)
        assert [row['id'] for row in result['outcomes']]==expected_order
        by_id={row['id']:row for row in result['outcomes']}
        assert by_id['covered']['approved_questions']==2
        assert by_id['covered']['formats']==['mcq','output']
        assert by_id['covered']['difficulties']==['easy','hard']
        assert by_id['covered']['sinhala'] is True
        assert by_id['covered']['covered'] is True
        assert by_id['unreviewed-material']['covered'] is False
        assert by_id['unverified-outcome']['covered'] is False
        assert by_id['unreviewed-translation']['sinhala'] is False
        assert by_id['unreviewed-translation']['covered'] is True
        assert by_id['3.1-test']['covered'] is False
        assert by_id['empty-000']['approved_questions']==0
        assert by_id['empty-000']['formats']==[]
        assert result['covered_outcomes']==2
        assert result['imported_outcomes']==50
        assert result['official_denominator_verified'] is False
        assert result['full_syllabus_percentage'] is None
        assert result['warning']=='Coverage of imported outcomes only. Complete official outcome inventory and examination applicability are not yet verified.'
