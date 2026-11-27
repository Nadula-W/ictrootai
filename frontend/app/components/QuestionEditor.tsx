'use client';
import {useUi} from './UiLanguage';

import {FormEvent, useState} from 'react';
import {FilePenLine, Plus, ShieldCheck, Trash2} from 'lucide-react';
import './workspace-tools.css';

type Row = Record<string, any>;
type Choice = {id: string; text: string; misconception: string};
type Criterion = {criterion: string; marks: number; expected: string; part: string};
type Props = {
  outcomes: any[];
  initialDraft: any;
  api: (path: string, method?: string, body?: unknown) => Promise<any>;
  onSaved: () => Promise<void>;
  onClose: () => void;
};

function readDraft(value: unknown): Row {
  if (typeof value === 'string') {
    try {const parsed=JSON.parse(value); return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};}
    catch {return {};}
  }
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {};
}

function initialChoices(initial: Row): Choice[] {
  if (Array.isArray(initial.options) && [4,5].includes(initial.options.length)) return initial.options.map((option: Row) => ({id:String(option.id),text:String(option.text || ''),misconception:String(option.misconception || '')}));
  return ['A','B','C','D'].map(id => ({id,text:'',misconception:''}));
}

function initialCriteria(initial: Row): Criterion[] {
  if (!Array.isArray(initial.rubric) || !initial.rubric.length) return [{criterion:'',marks:1,expected:'',part:''}];
  return initial.rubric.map((row: Row) => ({criterion:String(row.criterion || row.description || ''),marks:Number(row.marks ?? row.max_marks ?? row.weight ?? 1),expected:Array.isArray(row.expected_elements) ? row.expected_elements.join('\n') : String(row.expected || ''),part:String(row.part || '')}));
}

export default function QuestionEditor({outcomes, initialDraft, api, onSaved, onClose}: Props) {
  const {t}=useUi();
  const initial = readDraft(initialDraft);
  const initialKey: Row = initial.key && typeof initial.key === 'object' ? initial.key : {};
  const [outcomeId, setOutcomeId] = useState(String(initial.outcome_id || ''));
  const [kind, setKind] = useState(String(initial.kind || 'mcq'));
  const [difficulty, setDifficulty] = useState(String(initial.difficulty || 'medium'));
  const [prompt, setPrompt] = useState(String(initial.prompt || ''));
  const [explanation, setExplanation] = useState(String(initial.explanation || ''));
  const [options, setOptions] = useState<Choice[]>(() => initialChoices(initial));
  const [correctOption, setCorrectOption] = useState(String(initial.kind === 'mcq' ? initialKey.answer ?? '' : ''));
  const [answerText, setAnswerText] = useState(String(initial.kind !== 'mcq' ? initialKey.answer ?? '' : ''));
  const [base, setBase] = useState(Number(initialKey.base || 10));
  const [variables, setVariables] = useState(Array.isArray(initialKey.variables) ? initialKey.variables.join(', ') : 'A, B');
  const [sqlKey, setSqlKey] = useState(JSON.stringify(initial.kind === 'sql' ? initialKey : {fixtures:[],expected_rows:[],ordered:false}, null, 2));
  const [criteria, setCriteria] = useState<Criterion[]>(() => initialCriteria(initial));
  const [sourceRefs, setSourceRefs] = useState(Array.isArray(initial.sources) ? initial.sources.join(', ') : '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const safeOutcomes: Row[] = Array.isArray(outcomes) ? outcomes : [];
  const selectedOutcome = safeOutcomes.find(outcome => outcome.id === outcomeId);
  const descriptive = kind === 'short' || kind === 'structured';
  const totalMarks = criteria.reduce((total, criterion) => total + (Number.isFinite(criterion.marks) ? criterion.marks : 0), 0);

  function resizeOptions(count: number) {
    const next = options.slice(0, count);
    for (const id of ['A','B','C','D','E','F','G','H']) {
      if (next.length >= count) break;
      if (!next.some(option => option.id === id)) next.push({id,text:'',misconception:''});
    }
    setOptions(next);
    if (!next.some(option => option.id === correctOption)) setCorrectOption('');
  }

  function changeOption(index: number, patch: Partial<Choice>) {
    setOptions(current => current.map((option, position) => position === index ? {...option,...patch} : option));
  }

  function changeCriterion(index: number, patch: Partial<Criterion>) {
    setCriteria(current => current.map((criterion, position) => position === index ? {...criterion,...patch} : criterion));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || saved) return;
    setError('');
    if (!outcomeId) {setError('Select a learning outcome for this question.'); return;}
    if (prompt.trim().length < 5) {setError('Write a question prompt with at least 5 characters.'); return;}
    if (explanation.trim().length < 5) {setError('Add a worked explanation with at least 5 characters.'); return;}
    const sources = sourceRefs.trim() ? sourceRefs.split(',').map(value => Number(value.trim())) : [];
    if (sources.some(value => !Number.isInteger(value) || value < 1)) {setError('Resource references must be positive whole-number IDs separated by commas.'); return;}
    let key: Row = initial.kind === kind ? {...initialKey} : {};
    let rubric: Row[] = [];
    if (kind === 'mcq') {
      if (options.some(option => !option.text.trim())) {setError('Write text for every answer option.'); return;}
      if (new Set(options.map(option => option.text.trim().toLowerCase())).size !== options.length) {setError('Answer options must have different text.'); return;}
      if (!options.some(option => option.id === correctOption)) {setError('Choose exactly one correct answer option.'); return;}
      key = {answer:correctOption};
    } else if (descriptive) {
      if (!criteria.length || criteria.some(criterion => !criterion.criterion.trim() || !Number.isFinite(criterion.marks) || criterion.marks <= 0)) {setError('Each marking criterion needs a description and positive marks.'); return;}
      rubric = criteria.map(criterion => ({criterion:criterion.criterion.trim(),marks:criterion.marks,expected_elements:criterion.expected.split('\n').map(value=>value.trim()).filter(Boolean),...(criterion.part.trim() ? {part:criterion.part.trim()} : {})}));
      key = answerText.trim() ? {...key,answer:answerText.trim()} : key;
    } else if (kind === 'sql') {
      try {key=JSON.parse(sqlKey);}
      catch {setError('The SQL exercise key must be valid JSON. Check commas, brackets and quotation marks.'); return;}
      if (!key || typeof key !== 'object' || Array.isArray(key)) {setError('The SQL exercise key must be a JSON object.'); return;}
      if (!Array.isArray(key.expected_rows) || (key.fixtures !== undefined && !Array.isArray(key.fixtures))) {setError('The SQL key needs an expected_rows array and a fixtures array of approved exercise statements.'); return;}
    } else {
      if (!answerText.trim()) {setError('Enter the approved expected answer.'); return;}
      key = {...key,answer:answerText};
      if (kind === 'number') key.base = base;
      if (kind === 'boolean') {
        const names=variables.split(/[\s,]+/).filter(Boolean);
        if (!names.length || names.length > 8 || new Set(names).size !== names.length || names.some(name => !/^[A-H]$/.test(name))) {setError('Use between 1 and 8 unique Boolean variables, A through H, separated by commas.'); return;}
        key.variables = names;
      }
    }
    const payload = {outcome_id:outcomeId,kind,difficulty,prompt,options:kind === 'mcq' ? options.map(option => ({id:option.id,text:option.text,...(option.misconception.trim() ? {misconception:option.misconception.trim()} : {})})) : [],key,explanation,sources:[...new Set(sources)],rubric};
    setBusy(true);
    try {
      await api('/questions', 'POST', payload);
      setSaved(true);
      try {await onSaved(); onClose();}
      catch {setError('The question draft was saved, but the workspace could not refresh. Close this dialog and reload the page to find it.');}
    } catch (error) {setError(error instanceof Error ? error.message : 'The draft could not be saved. Check the fields and try again.');}
    finally {setBusy(false);}
  }

  return <form className="question-editor workspace-tool" onSubmit={submit}>
    <div className="workspace-heading"><span><FilePenLine size={25}/></span><div><h2>{initial.id ? 'Create a revised question draft' : 'Manual question draft'}</h2><p>{t('Write the question, expected answer and explanation. Saving creates a draft for review.')}</p></div></div>
    <div className="workspace-note"><ShieldCheck size={21}/><p>{initial.id ? 'This revision is saved as a new draft. Published assessments retain their approved question version.' : 'A teacher must check and approve the saved draft before it can be used in an assessment.'}</p></div>
    <fieldset className="question-editor-fields" disabled={busy || saved}>
      <div className="question-editor-grid"><label className="question-editor-full">{t('Learning outcome')}<select value={outcomeId} onChange={event=>setOutcomeId(event.target.value)} required><option value="">{t('Select a learning outcome')}</option>{safeOutcomes.map(outcome=><option key={outcome.id} value={outcome.id}>{outcome.verified ? 'Source checked' : 'Needs source review'}: {outcome.level} · {outcome.text}</option>)}</select></label>
        <label>{t('Question format')}<select value={kind} onChange={event=>{setKind(event.target.value);setError('');}}><option value="mcq">{t('Multiple choice')}</option><option value="short">{t('Short answer')}</option><option value="structured">{t('Structured answer')}</option><option value="number">{t('Number conversion')}</option><option value="boolean">Boolean equivalence</option><option value="output">{t('Output prediction')}</option><option value="sql">{t('SQL query')}</option></select></label>
        <label>{t('Difficulty')}<select value={difficulty} onChange={event=>setDifficulty(event.target.value)}><option value="easy">{t('Easy')}</option><option value="medium">{t('Medium')}</option><option value="hard">{t('Hard')}</option></select></label>
      </div>
      {selectedOutcome && !selectedOutcome.verified && <p className="workspace-source-note">This outcome still needs source checking. You can prepare a manual draft; AI generation requires a source-checked outcome.</p>}
      <label>{t('Question prompt')}<textarea value={prompt} onChange={event=>setPrompt(event.target.value)} minLength={5} maxLength={10000} required placeholder="Write the complete question and any data students need."/></label>

      {kind === 'mcq' && <section className="question-options-editor"><div className="question-editor-section-heading"><h3>{t('Answer options')}</h3><label>{t('Number of options')}<select value={options.length} onChange={event=>resizeOptions(Number(event.target.value))}><option value={4}>{t('4 options')}</option><option value={5}>{t('5 options')}</option></select></label></div>{options.map((option,index)=><div className="question-option-editor" key={option.id}><label>Option {option.id}<input value={option.text} onChange={event=>changeOption(index,{text:event.target.value})} required maxLength={1000}/></label><label>Possible misconception for option {option.id} (optional)<input value={option.misconception} onChange={event=>changeOption(index,{misconception:event.target.value})} maxLength={500} placeholder="For example, confusing bits with bytes"/></label></div>)}<label>{t('Correct answer')}<select value={correctOption} onChange={event=>setCorrectOption(event.target.value)} required><option value="">{t('Choose the correct option')}</option>{options.map(option=><option key={option.id} value={option.id}>Option {option.id}{option.text ? ` · ${option.text.slice(0,80)}` : ''}</option>)}</select></label><p className="workspace-source-note">A single selected distractor suggests a possible misconception; it does not establish one.</p></section>}

      {descriptive && <section className="question-rubric-editor"><div className="question-editor-section-heading"><div><h3>{t('Teacher marking rubric')}</h3><p className="workspace-source-note">{criteria.length} criteria · {totalMarks} rubric marks. Descriptive answers remain pending until teacher review.</p></div><button type="button" className="secondary" disabled={criteria.length >= 30} onClick={()=>setCriteria(current=>[...current,{criterion:'',marks:1,expected:'',part:''}])}><Plus size={16}/>{t('Add criterion')}</button></div>{criteria.map((criterion,index)=><div className="question-criterion-editor" key={index}><div className="question-criterion-top"><h4>Criterion {index+1}</h4><button type="button" className="question-remove-criterion" aria-label={`Remove criterion ${index+1}`} disabled={criteria.length === 1} onClick={()=>setCriteria(current=>current.filter((_,position)=>position!==index))}><Trash2 size={16}/></button></div><label>Criterion {index+1}<input required value={criterion.criterion} onChange={event=>changeCriterion(index,{criterion:event.target.value})} maxLength={1000} placeholder="Describe what earns credit."/></label><div className="question-editor-grid"><label>Marks for criterion {index+1}<input type="number" min={0.1} max={100} step="any" required value={criterion.marks} onChange={event=>changeCriterion(index,{marks:Number(event.target.value)})}/></label><label>Part for criterion {index+1} (optional)<input value={criterion.part} onChange={event=>changeCriterion(index,{part:event.target.value})} maxLength={30} placeholder="For example, (a)(i)"/></label></div><label>Expected elements for criterion {index+1} (optional)<textarea value={criterion.expected} onChange={event=>changeCriterion(index,{expected:event.target.value})} maxLength={5000} placeholder="One expected point or accepted alternative per line."/></label></div>)}<label>{t('Model answer (optional)')}<textarea value={answerText} onChange={event=>setAnswerText(event.target.value)} maxLength={10000} placeholder="Record the main points and accepted alternatives for the reviewer."/></label></section>}

      {kind === 'number' && <section className="question-technical-editor"><h3>{t('Approved number key')}</h3><div className="question-editor-grid"><label>{t('Answer base')}<select value={base} onChange={event=>setBase(Number(event.target.value))}><option value={2}>Binary (2)</option><option value={8}>Octal (8)</option><option value={10}>Decimal (10)</option><option value={16}>Hexadecimal (16)</option></select></label><label>{t('Expected answer')}<input value={answerText} onChange={event=>setAnswerText(event.target.value)} required maxLength={1000} placeholder="Digits in the selected base"/></label></div><p className="workspace-source-note">Equivalent numerical representations are checked deterministically in the selected base.</p></section>}
      {kind === 'boolean' && <section className="question-technical-editor"><h3>{t('Approved Boolean key')}</h3><label>{t('Boolean variables')}<input value={variables} onChange={event=>setVariables(event.target.value)} required placeholder="A, B" maxLength={30}/></label><label>{t('Expected Boolean expression')}<input value={answerText} onChange={event=>setAnswerText(event.target.value)} required maxLength={500} placeholder="A and B"/></label><p className="workspace-source-note">Use A–H, lowercase and/or/not, &amp;, |, ^ and parentheses. The grader compares truth tables without executing student code.</p></section>}
      {kind === 'output' && <section className="question-technical-editor"><h3>{t('Approved output key')}</h3><label>{t('Expected output')}<textarea className="question-code-input" value={answerText} onChange={event=>setAnswerText(event.target.value)} required maxLength={10000} spellCheck={false}/></label><p className="workspace-source-note">Output is compared with this approved text. Student Python is not executed.</p></section>}
      {kind === 'sql' && <section className="question-technical-editor"><h3>{t('Approved SQL exercise key')}</h3><p className="workspace-source-note">Define approved CREATE TABLE / INSERT fixtures, exact expected_rows and an ordered flag. The exercise runs only in the isolated in-memory grader, never against Supabase.</p><label>{t('SQL fixture and expected-result JSON')}<textarea className="question-code-input" value={sqlKey} onChange={event=>setSqlKey(event.target.value)} required maxLength={100000} spellCheck={false}/></label></section>}

      <label>{t('Worked explanation')}<textarea value={explanation} onChange={event=>setExplanation(event.target.value)} minLength={5} maxLength={10000} required placeholder="Explain the correct answer and the reasoning a student should learn."/></label>
      <details className="question-source-editor"><summary>{t('Reviewed resource references (optional)')}</summary><label>{t('Resource IDs')}<input value={sourceRefs} onChange={event=>setSourceRefs(event.target.value)} maxLength={2000} placeholder="For example, 1, 2"/></label><p className="workspace-source-note">References are checked during approval. Use IDs of reviewed resources for the selected outcome.</p></details>
    </fieldset>
    {error && <div className="workspace-error" role="alert">{error}</div>}
    <div className="builder-actions"><button type="button" className="secondary" onClick={onClose} disabled={busy}>{t('Cancel')}</button><button type="submit" className="primary" disabled={busy || saved}>{saved ? 'Draft saved' : busy ? 'Saving draft…' : 'Validate & save draft'}</button></div>
  </form>;
}
