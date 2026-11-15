from types import SimpleNamespace
import pytest
from app.verification import mark,truth_table,sql_rows

@pytest.mark.parametrize('value,base,expected',[('00001101',2,'1101'),('3b',16,'3B'),('17',8,'017'),('13',10,'013')])
def test_number_equivalence(value,base,expected):
    assert mark(SimpleNamespace(kind='number',key={'answer':expected,'base':base}),value)[0]==1

def test_invalid_number():assert mark(SimpleNamespace(kind='number',key={'answer':'11','base':2}),'12')[0]==0
def test_boolean_truth_table():assert truth_table('A and B',['A','B'])==[False,False,False,True]
def test_demorgan():assert mark(SimpleNamespace(kind='boolean',key={'answer':'not (A and B)','variables':['A','B']}),'not A or not B')[0]==1
@pytest.mark.parametrize('expression',["__import__('os').system('whoami')",'A.foo','A + B','[A]', 'A == B'])
def test_boolean_rejects_code(expression):
    with pytest.raises(ValueError):truth_table(expression,['A','B'])
def test_boolean_variable_limit():
    with pytest.raises(ValueError):truth_table('A',list('ABCDEFGHI'))
def test_output_does_not_execute():assert mark(SimpleNamespace(kind='output',key={'answer':'hello'}),"print('hello')")[0]==0
def test_structured_pending():assert mark(SimpleNamespace(kind='structured',key={}), 'some prose')[0] is None
def test_sql_results():assert sql_rows('SELECT name FROM learners ORDER BY name',["CREATE TABLE learners(name TEXT)","INSERT INTO learners VALUES ('Nila'),('Amal')"])==[['Amal'],['Nila']]
@pytest.mark.parametrize('query',['DROP TABLE learners','SELECT 1; DROP TABLE learners',"SELECT load_extension('evil')","WITH x AS (SELECT 1) DELETE FROM learners",'SELECT * FROM sqlite_master'])
def test_sql_readonly(query):
    import sqlite3
    if query=='SELECT * FROM sqlite_master':
        assert sql_rows(query,[])==[]
    else:
        with pytest.raises((ValueError,sqlite3.Error)):sql_rows(query,[])
def test_sql_query_budget():
    import sqlite3
    with pytest.raises(sqlite3.Error):sql_rows('WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT sum(n) FROM x',[])

def test_sql_fixture_cannot_attach_files():
    with pytest.raises(ValueError):sql_rows('SELECT 1',["ATTACH DATABASE 'anything.db' AS other"])

def test_malformed_legacy_boolean_does_not_block_submission():
    score,reason=mark(SimpleNamespace(kind='boolean',key={'answer':'A'}),'A')
    assert score is None and 'configuration' in reason

def test_malformed_legacy_sql_does_not_blame_student():
    score,reason=mark(SimpleNamespace(kind='sql',key={'expected_rows':[],'fixtures':[123]}),'SELECT 1')
    assert score is None and 'configuration' in reason

def test_sql_numeric_result_equivalence_and_duplicates():
    q=SimpleNamespace(kind='sql',key={'expected_rows':[[1],[1.0]],'fixtures':[]})
    assert mark(q,'SELECT 1.0 UNION ALL SELECT 1')[0]==1
    assert mark(q,'SELECT 1')[0]==0
