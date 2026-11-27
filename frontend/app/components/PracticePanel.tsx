'use client';

import {useEffect, useRef, useState} from 'react';
import {BookOpen, CheckCircle2, Clock, RefreshCw, Target} from 'lucide-react';
import './practice.css';

type Api = (path: string, method?: string, body?: unknown) => Promise<any>;
type Question = {id: number; outcome_id: string; kind: string; difficulty: string; prompt: string; options: {id: string; text: string}[]; language_notice?: string | null};
type Feedback = {id: number; score: number | null; pending: boolean; reason: string; correct_answer: Record<string, unknown>; explanation: string; rubric: {criterion?: string; weight?: number}[]; possible_misconception?: string | null; misconception_notice?: string | null};
type Revision = {outcome_id: string; text: string; attempts: number; marked_attempts: number; pending: number; recent_accuracy: number | null; recommended_difficulty: string; next_review_at: string; due: boolean; status: string; possible_misconceptions: {label: string; count: number; message: string}[]};
type Topic = {id: string; text: string};

function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request could not be completed. Try again.';
}

export default function PracticePanel({api}: {api: Api}) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [revision, setRevision] = useState<Revision[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [outcome, setOutcome] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [index, setIndex] = useState(0);
  const [value, setValue] = useState('');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [hint, setHint] = useState('');
  const attempted = useRef<{request_id: string; value: string} | null>(null);
  const question = questions[index];
  const locked = sending || feedback !== null || attempted.current !== null;

  useEffect(() => {
    let active = true;
    Promise.all([api('/practice'), api('/revision'), api('/curriculum')]).then(([practice, summary, curriculum]) => {
      if (!active) return;
      setQuestions(practice.questions);
      setHint(practice.message);
      setRevision(summary.outcomes);
      setTopics(curriculum.units.flatMap((unit: {outcomes: {id: string; text: string; verified: boolean}[]}) => unit.outcomes.filter(row => row.verified).map(row => ({id: row.id, text: row.text}))));
    }).catch(error => {if (active) setError(message(error));}).finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, [api]);

  async function loadPractice(topic = outcome, level = difficulty) {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (topic) params.set('outcome_id', topic);
      if (level) params.set('difficulty', level);
      const result = await api('/practice?' + params.toString());
      setQuestions(result.questions);
      setHint(result.message);
      setIndex(0);
      setValue('');
      setFeedback(null);
      attempted.current = null;
    } catch (error) {setError(message(error));}
    finally {setLoading(false);}
  }

  async function submit() {
    if (!question || sending || feedback) return;
    setSending(true);
    setError('');
    const request = attempted.current || {request_id: crypto.randomUUID(), value};
    attempted.current = request;
    try {
      const result = await api(`/practice/${question.id}/submit`, 'POST', request);
      setFeedback(result);
      try {setRevision((await api('/revision')).outcomes);}
      catch {setHint('Your answer is saved. Refresh revision suggestions when the connection returns.');}
    } catch (error) {setError(message(error) + ' Your answer is kept; retry to retrieve feedback.');}
    finally {setSending(false);}
  }

  function next() {
    if (index + 1 >= questions.length) {void loadPractice(); return;}
    setIndex(index + 1);
    setValue('');
    setFeedback(null);
    setError('');
    attempted.current = null;
  }

  const correctAnswer = feedback?.correct_answer.answer ?? feedback?.correct_answer.expected_rows ?? feedback?.correct_answer;

  return <section className="practice-panel" aria-label="Recommended practice">
    <header className="practice-heading"><div><p className="practice-kicker">YOUR NEXT SMALL STEP</p><h1>Practise, understand, improve.</h1><p>Approved questions, useful feedback and revision suggestions based on your own submitted work.</p></div><Target size={32} aria-hidden="true"/></header>
    {error && <div className="practice-error" role="alert">{error}</div>}
    <form className="practice-filters" onSubmit={event => {event.preventDefault(); void loadPractice();}}>
      <label>Practice topic<select value={outcome} onChange={event => setOutcome(event.target.value)} disabled={loading || sending}><option value="">Recommended topics</option>{topics.map(topic => <option key={topic.id} value={topic.id}>{topic.text}</option>)}</select></label>
      <label>Practice difficulty<select value={difficulty} onChange={event => setDifficulty(event.target.value)} disabled={loading || sending}><option value="">Recommended difficulty</option>{['easy', 'medium', 'hard'].map(level => <option key={level} value={level}>{level[0].toUpperCase() + level.slice(1)}</option>)}</select></label>
      <button type="submit" className="primary" disabled={loading || sending}><RefreshCw size={17}/>{loading ? 'Finding practice…' : 'Start practice'}</button>
    </form>
    <p className="practice-note">{hint}</p>
    {loading ? <div className="practice-empty" role="status">Loading approved practice…</div> : question ? <article className="practice-question">
      <div className="practice-question-top"><span>Question {index + 1} of {questions.length}</span><span>{question.kind.toUpperCase()} · {question.difficulty}</span></div>
      <h2>{question.prompt}</h2>
      {question.language_notice && <p className="practice-note">{question.language_notice}</p>}
      {question.kind === 'mcq' ? <div className="practice-options">{question.options.map(option => <button key={option.id} type="button" aria-pressed={value === option.id} disabled={locked} className={value === option.id ? 'selected' : ''} onClick={() => setValue(option.id)}><span>{option.id}</span>{option.text}</button>)}</div> : <label htmlFor="practice-response">Your answer<textarea id="practice-response" value={value} onChange={event => setValue(event.target.value)} maxLength={10000} disabled={locked} placeholder={question.kind === 'sql' ? 'Write a read-only SELECT query.' : 'Write your answer here.'}/></label>}
      {!feedback ? <div className="practice-actions"><p>Your response is saved when you submit.</p><button type="button" className="primary" disabled={!value || sending} onClick={() => void submit()}>{sending ? 'Checking your answer…' : attempted.current ? 'Retry answer' : 'Submit answer'}</button></div> : <section className="practice-feedback" aria-label="Practice feedback" role="status">
        <h3>{feedback.pending ? <><Clock size={20}/>Awaiting teacher review</> : feedback.score === 1 ? <><CheckCircle2 size={20}/>Well done</> : <>Let’s review this answer</>}</h3>
        <p>{feedback.pending ? 'Your response is saved. A teacher must review the rubric before this becomes a final mark.' : `Score: ${Math.round((feedback.score ?? 0) * 100)}%. ${feedback.reason}`}</p>
        <h4>Approved answer</h4><pre>{typeof correctAnswer === 'string' ? correctAnswer : JSON.stringify(correctAnswer, null, 2)}</pre>
        <h4>Explanation</h4><p>{feedback.explanation}</p>
        {!!feedback.rubric.length && <><h4>Marking criteria</h4><ul>{feedback.rubric.map((criterion, number) => <li key={number}>{criterion.criterion || JSON.stringify(criterion)}{typeof criterion.weight === 'number' ? ` (${criterion.weight})` : ''}</li>)}</ul></>}
        {feedback.possible_misconception && <p className="practice-note"><strong>Something to revisit: {feedback.possible_misconception}.</strong> {feedback.misconception_notice}</p>}
        <button type="button" className="primary" onClick={next}>{index + 1 < questions.length ? 'Next question' : 'Find more practice'}</button>
      </section>}
    </article> : <div className="practice-empty"><BookOpen size={28}/><p>No approved questions match this topic yet. Try another topic or ask your teacher to add reviewed questions.</p></div>}
    <section className="practice-revision" aria-label="Revision suggestions"><h2>Your revision suggestions</h2><p>Suggestions use your latest five marked responses. Review intervals are 1, 3 or 7 days; pending teacher marks do not lower your accuracy.</p>
      {!revision.length ? <p className="practice-empty">Submit your first practice answer to build your revision plan.</p> : <div className="practice-revision-grid">{revision.map(row => <article key={row.outcome_id} className="practice-revision-card"><span className="practice-status">{row.status}</span><h3>{row.text}</h3><p>{row.recent_accuracy === null ? 'No final marks yet' : `${row.recent_accuracy}% recent accuracy`} · {row.marked_attempts} marked{row.pending ? ` · ${row.pending} pending` : ''}</p><p><Clock size={15}/>{row.due ? 'Ready for revision' : `Review on ${new Date(row.next_review_at).toLocaleDateString('en-LK')}`} · {row.recommended_difficulty}</p>{row.possible_misconceptions.map(pattern => <details key={pattern.label}><summary>Possible pattern: {pattern.label}</summary><p>{pattern.message}</p></details>)}<button type="button" className="secondary" disabled={loading || sending} onClick={() => {setOutcome(row.outcome_id); setDifficulty(''); void loadPractice(row.outcome_id, '');}}>Practise this topic</button></article>)}</div>}
    </section>
  </section>;
}
