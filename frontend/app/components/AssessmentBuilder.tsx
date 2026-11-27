'use client';
import {useUi} from './UiLanguage';

import {FormEvent, useMemo, useState} from 'react';
import {CheckCircle2, ClipboardList, ListFilter} from 'lucide-react';
import './workspace-tools.css';

type Row = Record<string, any>;
type Style = 'custom' | 'paper_i' | 'paper_ii';
type Props = {
  classes: any[];
  units: any[];
  questions: any[];
  api: (path: string, method?: string, body?: unknown) => Promise<any>;
  onCreated: () => Promise<void>;
  onClose: () => void;
};
const kinds = [
  ['mcq', 'Multiple choice'], ['number', 'Number conversion'], ['boolean', 'Boolean logic'], ['output', 'Output prediction'], ['sql', 'SQL query'], ['short', 'Short answer'], ['structured', 'Structured answer'],
];
const practiceNotice = 'These are practice formats built from your approved question bank, not official examination replicas.';

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'The request could not be completed. Please try again.';
}

export default function AssessmentBuilder({classes, units, questions, api, onCreated, onClose}: Props) {
  const {t}=useUi();
  const [title, setTitle] = useState('');
  const [classId, setClassId] = useState('');
  const [duration, setDuration] = useState(60);
  const [style, setStyle] = useState<Style>('custom');
  const [count, setCount] = useState(10);
  const [difficulty, setDifficulty] = useState('');
  const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
  const [unitIds, setUnitIds] = useState<number[]>([]);
  const [outcomeIds, setOutcomeIds] = useState<string[]>([]);
  const [mode, setMode] = useState('balanced');
  const [selected, setSelected] = useState<number[]>([]);
  const [preview, setPreview] = useState<Row | null>(null);
  const [published, setPublished] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const safeUnits: Row[] = Array.isArray(units) ? units : [];
  const safeClasses: Row[] = Array.isArray(classes) ? classes : [];
  const allOutcomes: Row[] = safeUnits.flatMap(unit => (unit.outcomes || []).map((outcome: Row) => ({...outcome, unit_id: Number(unit.id), unit_name: unit.name})));
  const outcomeById = new Map<string, Row>(allOutcomes.map(outcome => [outcome.id, outcome]));
  const verifiedOutcomes = allOutcomes.filter(outcome => outcome.verified);
  const availableOutcomes = verifiedOutcomes.filter(outcome => !unitIds.length || unitIds.includes(outcome.unit_id));
  const allowedKinds = style === 'paper_i' ? ['mcq'] : style === 'paper_ii' ? ['short', 'structured'] : kinds.map(([kind]) => kind);
  const matching: Row[] = (Array.isArray(questions) ? questions : []).filter(question => {
    const outcome = outcomeById.get(question.outcome_id);
    return question.status === 'approved' && outcome?.verified
      && (!unitIds.length || unitIds.includes(outcome.unit_id))
      && (!outcomeIds.length || outcomeIds.includes(question.outcome_id))
      && (!difficulty || question.difficulty === difficulty)
      && allowedKinds.includes(question.kind)
      && (!selectedKinds.length || selectedKinds.includes(question.kind));
  });
  const selectedQuestions = useMemo(() => {
    const metadata: Row[] = Array.isArray(preview?.questions) ? preview.questions : [];
    const byId = new Map<number, Row>([...questions, ...metadata].map(question => [Number(question.id), question]));
    return selected.map(id => byId.get(id)).filter((question): question is Row => Boolean(question));
  }, [selected, preview, questions]);
  const representedOutcomes = new Set(selectedQuestions.map(question => question.outcome_id)).size;

  function invalidate() {
    setSelected([]); setPreview(null); setError('');
  }

  function changeStyle(next: Style) {
    setStyle(next);
    setSelectedKinds(next === 'paper_i' ? ['mcq'] : next === 'paper_ii' ? ['short', 'structured'] : []);
    invalidate();
  }

  function toggleUnit(id: number, checked: boolean) {
    setUnitIds(current => checked ? [...current, id] : current.filter(value => value !== id));
    setOutcomeIds([]); invalidate();
  }

  async function buildPreview() {
    if (!Number.isInteger(count) || count < 1 || count > 100) {setError('Choose between 1 and 100 questions.'); return;}
    setBusy(true); setError(''); setPreview(null); setSelected([]);
    try {
      const result = await api('/assessments/preview', 'POST', {outcome_ids: outcomeIds, unit_ids: unitIds, difficulty: difficulty || null, kinds: selectedKinds, count, style});
      setPreview(result); setSelected(result.question_ids.map(Number));
    } catch (error) {setError(errorMessage(error));}
    finally {setBusy(false);}
  }

  function toggleQuestion(id: number, checked: boolean) {
    setError('');
    if (checked && selected.length >= 100) {setError('An assessment can contain at most 100 questions.'); return;}
    setSelected(current => checked ? [...current, id] : current.filter(value => value !== id));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saved || busy) return;
    if (!selected.length) {setError('Preview a selection or choose approved questions first.'); return;}
    if (!classId) {setError('Choose a class for this assessment.'); return;}
    setBusy(true); setError('');
    try {
      await api('/assessments', 'POST', {title: title.trim(), class_id: Number(classId), duration, question_ids: selected, published});
      setSaved(true);
      try {await onCreated(); onClose();}
      catch {setError('The assessment was saved, but the workspace could not refresh. Close this dialog and reload the page to view it.');}
    } catch (error) {setError(errorMessage(error));}
    finally {setBusy(false);}
  }

  return <form className="assessment-builder workspace-tool" onSubmit={submit}>
    <div className="workspace-heading"><span><ClipboardList size={25}/></span><div><h2>{t('Create an assessment')}</h2><p>{t('Choose the class, build a balanced selection, then save or publish.')}</p></div></div>
    {!safeClasses.length && <div className="workspace-note"><ListFilter size={22}/><p>{t('Create a class in My classes before assigning an assessment.')}</p></div>}
    <div className="builder-basics">
      <label className="builder-title">{t('Assessment title')}<input autoFocus value={title} onChange={event => setTitle(event.target.value)} required minLength={3} maxLength={200} placeholder="For example, Data representation revision" disabled={busy || saved}/></label>
      <label>{t('Assign to class')}<select value={classId} onChange={event => setClassId(event.target.value)} required disabled={busy || saved}><option value="">{t('Select a class')}</option>{safeClasses.map(classroom => <option key={classroom.id} value={classroom.id}>{classroom.name} · Grade {classroom.grade}</option>)}</select></label>
      <label>{t('Duration (minutes)')}<input type="number" min={1} max={240} value={duration} onChange={event => setDuration(Number(event.target.value))} required disabled={busy || saved}/></label>
    </div>

    <fieldset disabled={busy || saved} className="builder-section"><legend>{t('Question selection')}</legend>
      <div className="builder-filter-grid">
        <label>{t('Practice format')}<select value={style} onChange={event => changeStyle(event.target.value as Style)}><option value="custom">{t('Custom practice')}</option><option value="paper_i">{t('Paper I-style · multiple choice')}</option><option value="paper_ii">{t('Paper II-style · short and structured')}</option></select></label>
        <label>{t('Selection method')}<select value={mode} onChange={event => {setMode(event.target.value); invalidate();}}><option value="balanced">{t('Build a balanced selection')}</option><option value="manual">{t('Choose questions manually')}</option></select></label>
        <label>{t('Difficulty')}<select value={difficulty} onChange={event => {setDifficulty(event.target.value); invalidate();}}><option value="">{t('All difficulties')}</option><option value="easy">{t('Easy')}</option><option value="medium">{t('Medium')}</option><option value="hard">{t('Hard')}</option></select></label>
        {mode === 'balanced' && <label>{t('Number of questions')}<input type="number" min={1} max={100} value={count} onChange={event => {setCount(Number(event.target.value)); invalidate();}} required/></label>}
      </div>
      <p className="workspace-source-note">{practiceNotice}</p>

      <details className="builder-filter-details"><summary>Filter by units{unitIds.length ? ` (${unitIds.length} selected)` : ' (all units)'}</summary><div className="builder-checkbox-grid">{safeUnits.map(unit => <label className="workspace-checkbox" key={unit.id}><input type="checkbox" checked={unitIds.includes(Number(unit.id))} onChange={event => toggleUnit(Number(unit.id), event.target.checked)}/><span>{unit.id}. {unit.name}</span></label>)}</div></details>
      <details className="builder-filter-details"><summary>Filter by learning outcomes{outcomeIds.length ? ` (${outcomeIds.length} selected)` : ' (all source-checked outcomes)'}</summary><p className="workspace-source-note">Leave outcomes unchecked to include all source-checked outcomes in the selected units.</p><div className="builder-outcome-options">{availableOutcomes.map(outcome => <label className="workspace-checkbox" key={outcome.id}><input type="checkbox" checked={outcomeIds.includes(outcome.id)} onChange={event => {setOutcomeIds(current => event.target.checked ? [...current, outcome.id] : current.filter(id => id !== outcome.id)); invalidate();}}/><span><strong>{outcome.level} · {outcome.text}</strong><small>{outcome.unit_name} · {outcome.id}</small></span></label>)}{!availableOutcomes.length && <p className="workspace-source-note">No source-checked outcomes are available in these units yet.</p>}</div></details>

      <fieldset className="builder-format-options"><legend>{t('Question formats')}</legend><div>{kinds.filter(([kind]) => allowedKinds.includes(kind)).map(([kind, label]) => <label className="workspace-checkbox" key={kind}><input type="checkbox" checked={selectedKinds.includes(kind)} onChange={event => {setSelectedKinds(current => event.target.checked ? [...current, kind] : current.filter(value => value !== kind)); invalidate();}}/><span>{label}</span></label>)}</div><p className="workspace-source-note">{style === 'custom' ? 'No format selected includes every supported format.' : 'The server enforces the formats allowed by this practice style.'}</p></fieldset>
      <p className="builder-bank-count"><strong>{matching.length}</strong> approved {matching.length === 1 ? 'question matches' : 'questions match'} these filters. Only source-checked learning outcomes are eligible.</p>

      {mode === 'balanced' ? <button type="button" className="secondary" onClick={buildPreview} disabled={busy || saved}>{busy ? 'Building selection…' : 'Preview balanced selection'}</button> : <div className="builder-question-picker" aria-label="Choose approved questions">
        {matching.map(question => <label className="workspace-checkbox" key={question.id}><input type="checkbox" checked={selected.includes(Number(question.id))} onChange={event => toggleQuestion(Number(question.id), event.target.checked)}/><span><strong>{question.prompt}</strong><small>{question.outcome_id} · {question.difficulty} · {question.kind}</small></span></label>)}
        {!matching.length && <p className="workspace-source-note">No approved questions match. Broaden the filters or approve more question drafts before creating this assessment.</p>}
      </div>}
    </fieldset>

    {preview && <section className="builder-preview" aria-label="Assessment preview"><div className="builder-preview-heading"><CheckCircle2 size={21}/><div><h3>{t('Selection ready')}</h3><p>{selected.length} questions across {representedOutcomes} learning {representedOutcomes === 1 ? 'outcome' : 'outcomes'} · {preview.available_count} matching approved questions available</p></div></div><p className="workspace-source-note">{preview.practice_notice || practiceNotice}</p><ol>{selectedQuestions.map(question => <li key={question.id}><p>{question.prompt}</p><small>{question.outcome_id} · {question.difficulty} · {question.kind}</small></li>)}</ol></section>}
    {mode === 'manual' && selected.length > 0 && <p className="builder-selection-summary" role="status">{selected.length} {selected.length === 1 ? 'question' : 'questions'} selected across {representedOutcomes} learning {representedOutcomes === 1 ? 'outcome' : 'outcomes'}.</p>}
    <label className="workspace-checkbox builder-publish"><input type="checkbox" checked={published} onChange={event => setPublished(event.target.checked)} disabled={busy || saved}/><span><strong>{t('Publish and assign immediately')}</strong><small>{t('Leave unchecked to save a draft assessment.')}</small></span></label>
    {error && <div className="workspace-error" role="alert">{error}</div>}
    <div className="builder-actions"><button type="button" className="secondary" onClick={onClose} disabled={busy}>{t('Cancel')}</button><button type="submit" className="primary" disabled={busy || saved || !selected.length || !safeClasses.length}>{saved ? 'Assessment saved' : busy ? 'Please wait…' : published ? 'Publish & assign assessment' : 'Save draft assessment'}</button></div>
  </form>;
}
