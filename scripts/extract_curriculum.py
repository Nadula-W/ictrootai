"""Extract table columns as review candidates, never automatic verification.
Run from repository root using backend/.venv/Scripts/python.exe.
"""
import hashlib
import json
import re
from pathlib import Path
from pypdf import PdfReader

root=Path(__file__).resolve().parents[1]
pdf=root/'curriculum/nie-ict-2017.pdf'
reader=PdfReader(pdf)
records=[]
level=None
topic=[]
current=None
competencies={}
unit=None
competency=[]

def finish():
    global current
    if current:
        current['text']=' '.join(current.pop('lines')).strip()
        if len(current['text'])>3:records.append(current)
    current=None

for page_index in range(11,61):
    lines=(reader.pages[page_index].extract_text(extraction_mode='layout') or '').splitlines()
    if not lines:continue
    header=next((line for line in lines if 'Learning outcomes' in line and 'Contents' in line),None)
    if not header:continue
    content_start=header.index('Contents')-2
    outcome_start=header.index('Learning outcomes')-2
    periods_start=header.index('Periods')-2
    for line in lines:
        if line==header:continue
        left=line[:22].strip()
        middle=line[22:content_start].strip()
        outcome=line[outcome_start:periods_start].strip()
        if '8.0 Learning' in line:finish();break
        if left.startswith('Competency'):
            match=re.search(r'(\d+)',left)
            if match:
                if unit:competencies[unit]=' '.join(competency)
                unit=int(match.group(1));competency=[]
        elif left and unit and not left.isdigit():competency.append(left)
        match=re.match(r'^(\d{1,2}\.\d{1,2})\s+(.+)',middle)
        if match:
            finish();level=match.group(1);topic=[match.group(2)]
        elif middle and level:topic.append(middle)
        if outcome and level and 'Learning outcomes' not in outcome:
            if outcome.startswith(('\uf0b7','•')):
                finish()
                current={'unit_id':int(level.split('.')[0]),'level':level,'source_page':page_index+1,'lines':[outcome[1:].strip()],'verified':False}
            elif current:current['lines'].append(outcome)
        if level:
            # Preserve source wording separately for human table-layout review.
            for row in records[-1:]:
                if row['level']==level:row['subtopic']=' '.join(topic)
finish()
if unit:competencies[unit]=' '.join(competency)
counts={}
for row in records:
    lev=row['level'];counts[lev]=counts.get(lev,0)+1
    row['id']=f'NIE2017-{lev}-{counts[lev]:02}'
    row.setdefault('subtopic','Competency level '+lev+' — extraction awaiting review')
    row['competency']=competencies.get(row['unit_id'],'Source table requires manual review')
output={'source':'https://nie.lk/pdffiles/tg/eALSyl%20ICT.pdf','sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'review_status':'machine_extracted_unverified','outcomes':records}
(root/'curriculum/extracted-review.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Extracted {len(records)} unverified outcome candidates; inspect every row against PDF before approval.')
