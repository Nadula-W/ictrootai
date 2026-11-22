"""Validate and install the source-audited NIE 2017 inventory without deleting records.

Source verification describes comparison with the supplied PDF. It is separate
from teacher approval of questions and confirmation of a current examination year.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from . import models as m

ROOT=Path(__file__).resolve().parents[2]
SOURCE_SHA256='577659c643467316a84fae39fadc49b4753f8b8f553e8e66cf1655c8951082f8'
SOURCE_URL='https://nie.lk/pdffiles/tg/eALSyl%20ICT.pdf'
VERSION='NIE-ICT-2017'
FILES=('units-01-05.json','units-06-09.json','units-10-14.json')
EXPECTED_COUNTS={1:45,2:22,3:15,4:17,5:38,6:46,7:41,8:43,9:43,10:30,11:9,12:12,13:7,14:0}
EXPECTED_LEVELS={1:7,2:4,3:3,4:4,5:4,6:12,7:10,8:7,9:13,10:8,11:2,12:3,13:3,14:2}

def load_catalogue(root=ROOT):
    root=Path(root)
    pdf=root/'curriculum/nie-ict-2017.pdf'
    if hashlib.sha256(pdf.read_bytes()).hexdigest()!=SOURCE_SHA256:
        raise ValueError('The syllabus PDF differs from the source that was reviewed.')
    units=[];digests={};ids=set();level_ids=set()
    for name in FILES:
        raw=(root/'curriculum/reviewed'/name).read_bytes()
        if len(raw)>2_000_000:raise ValueError('Oversized curriculum review artifact.')
        document=json.loads(raw)
        if document.get('source_sha256')!=SOURCE_SHA256:
            raise ValueError('Review artifact has a different source hash.')
        digests[name]=hashlib.sha256(raw).hexdigest()
        units.extend(document['units'])
    if sorted(u['id'] for u in units)!=list(range(1,15)):
        raise ValueError('The catalogue must contain each of the 14 units once.')
    outcomes=[];levels=[]
    for unit in units:
        uid=unit['id'];unit_outcomes=[]
        if not unit.get('verified',True) or not unit.get('competency'):
            raise ValueError('Every unit needs checked competency wording.')
        if len(unit['levels'])!=EXPECTED_LEVELS[uid]:
            raise ValueError('Competency-level count differs from the reviewed inventory.')
        for level in unit['levels']:
            code=level['id']
            if not re.fullmatch(fr'{uid}\.\d{{1,2}}',code) or code in level_ids:
                raise ValueError('Invalid or duplicated competency-level code.')
            level_ids.add(code)
            if not level.get('title') or not level.get('source_pages') or not isinstance(level.get('contents'),list):
                raise ValueError('Each competency level needs title, source pages and contents.')
            levels.append({'id':VERSION+':'+code,'unit_id':uid,'level':code,'title':level['title'],
                'source_pages':level['source_pages'],'contents':level['contents'],'periods':level.get('periods'),
                'review_note':level.get('review_note') or 'Source table checked by Codex; see the versioned review artifact for source anomalies.'})
            for outcome in level['outcomes']:
                oid=outcome['id'];pages=outcome.get('source_pages') or [outcome['source_page']]
                if oid in ids or not re.fullmatch(r'[A-Za-z0-9._-]{1,120}',oid):
                    raise ValueError('Invalid or duplicated outcome ID.')
                ids.add(oid)
                if outcome.get('verified') is not True or len(outcome.get('text',''))<5:
                    raise ValueError('Every catalogue outcome must have source-checked wording.')
                if outcome['source_page'] not in pages or any(type(p) is not int or not 12<=p<=61 for p in pages):
                    raise ValueError('Invalid physical PDF page reference.')
                row={'id':oid,'unit_id':uid,'level':code,'text':outcome['text'],'subtopic':level['title'],
                    'competency':unit['competency'],'source_page':outcome['source_page'],'source_pages':pages,
                    'verified':True,'catalogued':True,'review_note':outcome.get('review_note') or 'Source wording, competency, level and physical PDF page cross-checked by Codex.'}
                unit_outcomes.append(row);outcomes.append(row)
        if len(unit_outcomes)!=EXPECTED_COUNTS[uid]:
            raise ValueError('Learning-outcome count differs from the reviewed inventory.')
    original=json.loads((root/'curriculum/extracted-review.json').read_text(encoding='utf-8'))['outcomes']
    if not {row['id'] for row in original}<=ids:
        raise ValueError('A legacy candidate is missing; reconciliation must preserve all existing IDs.')
    inventory={'version_id':VERSION,'source':SOURCE_URL,'source_sha256':SOURCE_SHA256,
        'reviewed_on':'2026-11-22','reviewed_by':'Codex source comparison','unit_count':14,
        'level_count':len(levels),'outcome_count':len(outcomes),'complete':True,
        'exam_applicability_verified':False,'artifact_sha256':digests,
        'scope':'All competency levels and explicit learning-outcome bullets in the NIE source effective from 2017. Project has two levels and no explicit outcome bullets.',
        'applicability':'Effective from 2017. No newer official replacement was located in the 2026-11-22 search; a specific examination-year confirmation is not established.'}
    return {'units':sorted(units,key=lambda u:u['id']),'levels':levels,'outcomes':outcomes,'inventory':inventory}

def install_catalogue(db,catalogue):
    """Stage an idempotent upsert; caller owns the transaction and backup."""
    now=datetime.now(timezone.utc).isoformat()
    version=db.get(m.CurriculumVersion,VERSION)
    if not version:
        version=m.CurriculumVersion(id=VERSION,source=SOURCE_URL,applicability=catalogue['inventory']['applicability'],verified_complete=False)
        db.add(version);db.flush()
    version.source=SOURCE_URL;version.applicability=catalogue['inventory']['applicability']
    existing_units={u.id:u for u in db.scalars(select(m.Unit))}
    for unit in catalogue['units']:
        target=existing_units.get(unit['id'])
        if target and target.version_id!=VERSION:
            raise ValueError('An existing unit belongs to a different curriculum version; no records were committed.')
        if not target:target=m.Unit(id=unit['id'],version_id=VERSION);db.add(target)
        target.name=unit['name'];target.grade=unit.get('grade');target.verified=True
    db.flush()
    existing_levels={level.id:level for level in db.scalars(select(m.CompetencyLevel))}
    for row in catalogue['levels']:
        target=existing_levels.get(row['id'])
        if not target:target=m.CompetencyLevel(id=row['id']);db.add(target)
        for key,value in row.items():setattr(target,key,value)
    existing={o.id:o for o in db.scalars(select(m.Outcome))}
    inserted=0;updated=0
    for row in catalogue['outcomes']:
        target=existing.get(row['id'])
        if target is None:target=m.Outcome(id=row['id']);db.add(target);inserted+=1
        else:updated+=1
        changed=any(getattr(target,key,None)!=value for key,value in row.items())
        for key,value in row.items():setattr(target,key,value)
        if changed or not target.reviewed_at:target.reviewed_at=now
    inventory=catalogue['inventory'].copy()
    marker=db.get(m.AppSetting,'curriculum_inventory')
    if not marker:marker=m.AppSetting(key='curriculum_inventory');db.add(marker)
    marker.value=json.dumps(inventory,ensure_ascii=False,sort_keys=True)
    version.verified_complete=True
    db.flush()
    actual=list(db.scalars(select(m.Outcome).where(m.Outcome.catalogued==True)))
    if {o.id for o in actual}!={o['id'] for o in catalogue['outcomes']}:
        raise ValueError('Stored source inventory differs from the reviewed catalogue.')
    return {'inserted':inserted,'updated':updated,'preserved_supplementary_outcomes':sum(not o.catalogued for o in existing.values()),**inventory}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Back up existing curriculum metadata, then upsert the reviewed catalogue into configured PostgreSQL.')
    args=parser.parse_args()
    catalogue=load_catalogue()
    print('Source catalogue: 14 units, 82 competency levels, 368 source-verified outcomes; all 359 legacy IDs retained.')
    if not args.apply:
        print('Validation only. Use --apply to save to PostgreSQL; examination-year applicability remains unconfirmed.')
        return
    from .database import SessionLocal
    with SessionLocal() as db:
        backup=ROOT/'backups'/('curriculum-before-review-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        backup.parent.mkdir(exist_ok=True)
        snapshot={cls.__tablename__:[{column.name:getattr(row,column.name) for column in cls.__table__.columns} for row in db.scalars(select(cls))] for cls in (m.CurriculumVersion,m.Unit,m.Outcome,m.CompetencyLevel)}
        backup.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
        try:
            result=install_catalogue(db,catalogue);db.commit()
        except Exception:
            db.rollback();raise
    print('Source catalogue saved. Inserted '+str(result['inserted'])+' outcomes; updated '+str(result['updated'])+'. Existing questions and supplementary records preserved. Private curriculum backup retained.')

if __name__=='__main__':main()
