"""Pure conversion tests for the one-time legacy importer; no app SQLite fixture."""
import pytest
from app import models as m
from app.migrate_legacy_sqlite import convert_legacy_value

def test_invalid_legacy_timestamp_does_not_disclose_raw_value():
    private='PRIVATE-RECORD-VALUE'
    with pytest.raises(ValueError) as error:convert_legacy_value(m.GenerationLog.__table__.c.created,private)
    assert private not in str(error.value)
    assert 'ai_generation_logs.created' in str(error.value)

@pytest.mark.parametrize('value',['false','true',2,-1])
def test_invalid_legacy_boolean_cannot_verify_content(value):
    with pytest.raises(ValueError):convert_legacy_value(m.Outcome.__table__.c.verified,value)

def test_legacy_review_flags_and_sinhala_json_are_preserved():
    assert convert_legacy_value(m.Outcome.__table__.c.verified,0) is False
    assert convert_legacy_value(m.Outcome.__table__.c.verified,1) is True
    assert convert_legacy_value(m.Translation.__table__.c.content,'{"prompt":"සිංහල"}')=={'prompt':'සිංහල'}
