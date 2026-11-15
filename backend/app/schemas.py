from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Credentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)

class Register(Credentials):
    name: str = Field(min_length=1, max_length=120)
    grade: Literal[12, 13] = 12

class Option(BaseModel):
    id: str = Field(min_length=1, max_length=10)
    text: str = Field(min_length=1, max_length=1000)
    misconception: str | None = Field(default=None, max_length=500)

class QuestionDraft(BaseModel):
    outcome_id: str
    kind: Literal['mcq','number','boolean','output','sql','short','structured']
    difficulty: Literal['easy','medium','hard']
    prompt: str = Field(min_length=5, max_length=10000)
    options: list[Option] = Field(default_factory=list, max_length=5)
    key: dict
    explanation: str = Field(min_length=5, max_length=10000)
    sources: list[int] = Field(default_factory=list)
    rubric: list[dict] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid_key(self):
        if self.kind == 'mcq':
            ids = [o.id for o in self.options]
            if len(ids) not in (4,5) or len(set(ids)) != len(ids) or self.key.get('answer') not in ids:
                raise ValueError('MCQ requires four or five unique options and one matching answer ID')
        if self.kind == 'number':
            if not isinstance(self.key.get('base'),int) or self.key.get('base') not in (2,8,10,16):
                raise ValueError('Supported bases: 2, 8, 10, 16')
            if not isinstance(self.key.get('answer'),(str,int)):
                raise ValueError('Number keys require an approved answer')
            int(str(self.key['answer']), self.key['base'])
        if self.kind in ('short','structured') and not self.rubric:
            raise ValueError('Teacher marking rubric required')
        if self.kind in ('boolean','output') and not isinstance(self.key.get('answer'), str):
            raise ValueError('An approved expected answer is required')
        if self.kind == 'boolean':
            from .verification import truth_table
            variables=self.key.get('variables')
            if not isinstance(variables,list) or not all(isinstance(v,str) for v in variables):
                raise ValueError('Boolean keys require a variables list')
            try:truth_table(self.key['answer'],variables)
            except (ValueError,SyntaxError,RecursionError) as error:
                raise ValueError('Invalid approved Boolean expression or variables') from error
        if self.kind == 'sql':
            from .verification import sql_rows
            import sqlite3
            rows=self.key.get('expected_rows')
            if not isinstance(rows,list) or len(rows)>1000 or any(not isinstance(row,list) or any(not isinstance(cell,(str,int,float,type(None))) for cell in row) for row in rows):
                raise ValueError('SQL requires up to 1000 approved result rows containing scalar values')
            fixtures=self.key.get('fixtures',[])
            if not isinstance(fixtures,list) or len(fixtures)>100 or not all(isinstance(item,str) for item in fixtures):
                raise ValueError('SQL fixtures must be a list of at most 100 SQL strings')
            if 'ordered' in self.key and not isinstance(self.key['ordered'],bool):
                raise ValueError('SQL ordered must be a Boolean')
            try:sql_rows('SELECT 1',fixtures)
            except (ValueError,sqlite3.Error) as error:
                raise ValueError('Approved SQL fixtures are invalid or exceed execution limits') from error
        return self

class AssessmentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    class_id: int
    duration: int = Field(ge=1, le=240)
    question_ids: list[int] = Field(min_length=1, max_length=100)
    published: bool = False

class AnswerInput(BaseModel):
    value: str = Field(max_length=10000)

class Decision(BaseModel):
    decision: Literal['approved','rejected']
    reason: str = Field(min_length=5, max_length=2000)

class OutcomeInput(BaseModel):
    id: str = Field(pattern=r'^[A-Za-z0-9._-]{1,120}$')
    unit_id: int
    subtopic: str = Field(min_length=1)
    competency: str
    level: str
    text: str = Field(min_length=5)
    source_page: int = Field(ge=1, le=10000)
    verified: bool = False

class CurriculumImport(BaseModel):
    outcomes: list[OutcomeInput] = Field(min_length=1, max_length=2000)

class GenerateInput(BaseModel):
    outcome_id: str
    difficulty: Literal['easy','medium','hard'] = 'medium'
    kind: Literal['mcq','short','structured'] = 'mcq'
    option_count: Literal[4,5] = 4
