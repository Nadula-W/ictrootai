"""Checks for the source audit and its non-destructive PostgreSQL installation."""
import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import select,func
from app import models as m
from app.curriculum_catalogue import load_catalogue,install_catalogue,ROOT,VERSION

def test_catalogue_accounts_for_missing_iot_and_preserves_source_defects():
    catalogue=load_catalogue()
    rows={o['id']:o for o in catalogue['outcomes']}
    assert len(rows)==368 and len(catalogue['levels'])==82
    assert all(o['verified'] for o in rows.values())
    assert rows['NIE2017-11.2-01']['unit_id']==12
    assert rows['NIE2017-11.2-01']['level']=='12.2'
    assert sum(o['unit_id']==11 for o in rows.values())==9
    assert rows['NIE2017-3.1-04']['text']=='Converts decimal integers into binary, octal and hexadecimal numbers and vice versa'
    assert rows['NIE2017-3.1-04']['source_page']==21
    assert rows['NIE2017-6.11-01']['text'].endswith('does not provide')
    project=catalogue['units'][-1]
    assert project['grade']==13 and len(project['levels'])==2
    assert not any(level['outcomes'] for level in project['levels'])
    assert not catalogue['inventory']['exam_applicability_verified']

@pytest.mark.parametrize('mutation',['pdf','hash','duplicate','missing','unverified','page'])
def test_catalogue_rejects_incomplete_or_changed_source(tmp_path,mutation):
    import shutil
    target=tmp_path/'curriculum'
    shutil.copytree(ROOT/'curriculum',target)
    if mutation=='pdf':
        (target/'nie-ict-2017.pdf').write_bytes(b'different source')
    else:
        path=target/'reviewed/units-01-05.json'
        data=json.loads(path.read_text(encoding='utf-8'))
        row=data['units'][0]['levels'][0]['outcomes'][0]
        if mutation=='hash':data['source_sha256']='0'*64
        elif mutation=='duplicate':row['id']=data['units'][0]['levels'][0]['outcomes'][1]['id']
        elif mutation=='missing':data['units'].pop()
        elif mutation=='unverified':row['verified']=False
        elif mutation=='page':row['source_page']=9000
        path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError):load_catalogue(tmp_path)

def test_catalogue_upsert_preserves_questions_and_supplementary_outcomes(env):
    catalogue=load_catalogue()
    with env() as db:
        db.add(m.CurriculumVersion(id=VERSION,source='Before review',applicability='Fixture',verified_complete=False))
        db.flush()
        db.get(m.Unit,3).version_id=VERSION
        before_key=copy.deepcopy(db.get(m.Question,1).key)
        before_users=db.scalar(select(func.count()).select_from(m.User))
        first=install_catalogue(db,catalogue);db.commit()
        assert first['inserted']==368
        assert db.get(m.Outcome,'3.1-test').text=='Number conversion test outcome'
        assert db.get(m.Outcome,'3.1-test').catalogued is False
        assert db.get(m.Question,1).key==before_key
        assert db.scalar(select(func.count()).select_from(m.User))==before_users
        reviewed_at=db.get(m.Outcome,'NIE2017-3.1-04').reviewed_at
        second=install_catalogue(db,catalogue);db.commit()
        assert second['inserted']==0 and second['updated']==368
        assert db.get(m.Outcome,'NIE2017-3.1-04').reviewed_at==reviewed_at
        assert db.scalar(select(func.count()).select_from(m.CompetencyLevel))==82
        assert db.scalar(select(func.count()).select_from(m.Outcome))==369
        assert db.get(m.CurriculumVersion,VERSION).verified_complete is True

def test_catalogue_refuses_conflicting_version_without_committing(env):
    with env() as db:
        with pytest.raises(ValueError,match='different curriculum version'):
            install_catalogue(db,load_catalogue())
        db.rollback()
        assert db.get(m.Unit,3).version_id=='test'
        assert db.scalar(select(func.count()).select_from(m.Outcome))==1
