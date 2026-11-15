"""No eval, student Python execution, or access to the application DB."""
import ast
import itertools
import sqlite3
from collections import Counter
from decimal import Decimal

def boolean_value(expression, values):
    if len(expression) > 500:
        raise ValueError('Expression too long')
    tree = ast.parse(expression, mode='eval')
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Name) and node.id in values: return values[node.id]
        if isinstance(node, ast.Constant) and node.value in (0,1): return bool(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not,ast.Invert)): return not visit(node.operand)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And,ast.Or)):
            items = [visit(v) for v in node.values]
            return all(items) if isinstance(node.op,ast.And) else any(items)
        if isinstance(node, ast.BinOp) and isinstance(node.op,(ast.BitAnd,ast.BitOr,ast.BitXor)):
            a,b=visit(node.left),visit(node.right)
            return a and b if isinstance(node.op,ast.BitAnd) else (a or b if isinstance(node.op,ast.BitOr) else a != b)
        raise ValueError('Use variables A–H, and/or/not, &, |, ^ and parentheses')
    return visit(tree)

def truth_table(expression, variables):
    if not variables or len(variables)>8 or any(not isinstance(v,str) or len(v)!=1 or v not in 'ABCDEFGH' for v in variables) or len(set(variables)) != len(variables):
        raise ValueError('One to eight unique variables A–H required')
    return [boolean_value(expression,dict(zip(variables,row))) for row in itertools.product((False,True),repeat=len(variables))]

def sql_rows(query, fixtures):
    if len(query)>10000 or not query.lstrip().lower().startswith(('select ', 'with ')):
        raise ValueError('Only read-only SELECT queries are supported')
    with sqlite3.connect(':memory:', isolation_level=None) as conn:
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1000000)
        conn.set_authorizer(lambda action,*_: sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH,sqlite3.SQLITE_PRAGMA,sqlite3.SQLITE_CREATE_VTABLE) else sqlite3.SQLITE_OK)
        conn.set_progress_handler(lambda: 1, 1000000)
        for statement in fixtures:
            if len(statement)>100000 or not statement.lstrip().lower().startswith(('create table ', 'insert into ')):
                raise ValueError('Fixtures support CREATE TABLE and INSERT INTO only')
            conn.execute(statement)
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE}
        def authorize(action, arg1, arg2, *_):
            if action == sqlite3.SQLITE_FUNCTION and arg2 not in ('count','sum','avg','min','max','lower','upper','length','coalesce','round','abs'):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
        conn.set_authorizer(authorize)
        ticks=0
        def budget():
            nonlocal ticks
            ticks+=1
            return ticks>1000
        conn.set_progress_handler(budget,1000)
        rows=conn.execute(query).fetchmany(1001)
        if len(rows)>1000: raise ValueError('Result exceeds 1000 rows')
        return [list(r) for r in rows]

def mark(question, answer):
    key=question.key
    try:
        if question.kind=='mcq': correct=answer==key['answer']
        elif question.kind=='number': correct=int(answer.strip(),key['base'])==int(str(key['answer']),key['base'])
        elif question.kind=='boolean': correct=truth_table(answer,key['variables'])==truth_table(key['answer'],key['variables'])
        elif question.kind=='output': correct=answer.strip().replace('\r\n','\n')==key['answer'].strip().replace('\r\n','\n')
        elif question.kind=='sql':
            actual=sql_rows(answer,key.get('fixtures',[])); expected=key['expected_rows']
            def normalized(rows):
                return [tuple(('number',Decimal(str(cell))) if isinstance(cell,(int,float)) else (type(cell).__name__,cell) for cell in row) for row in rows]
            correct=actual==expected if key.get('ordered',False) else Counter(normalized(actual))==Counter(normalized(expected))
        else: return None,'Teacher review required; no final AI mark awarded'
        return float(correct),'Deterministic '+question.kind+' comparison'
    except (KeyError,TypeError,IndexError,AttributeError):
        return None,'Question configuration is invalid; teacher review required, no final mark awarded'
    except (ValueError, SyntaxError, sqlite3.Error, RecursionError):
        return 0.0,'Answer could not be parsed safely for this question format'
