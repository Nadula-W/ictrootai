'use client';

import {useEffect, useState} from 'react';
import './practice.css';

type Api = (path: string, method?: string, body?: unknown) => Promise<any>;
type Pending = {id: number; student: string; prompt: string; value: string; rubric: {criterion?: string; weight?: number}[]; explanation: string};

export default function PracticeReviewPanel({api}: {api: Api}) {
  const [rows, setRows] = useState<Pending[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    api('/teacher/practice').then(data => {if (active) setRows(data);}).catch(error => {if (active) setError(error instanceof Error ? error.message : 'Cannot load practice responses.');}).finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, [api]);

  async function review(event: React.FormEvent<HTMLFormElement>, answerId: number) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(answerId);
    setError('');
    setNotice('');
    try {
      await api(`/teacher/practice/${answerId}/review`, 'POST', {score: Number(data.get('score')), reason: String(data.get('reason') || '')});
      setRows(previous => previous.filter(row => row.id !== answerId));
      setNotice('Practice mark saved. The decision and reason are recorded in the review history.');
    } catch (error) {setError(error instanceof Error ? error.message : 'The mark could not be saved.');}
    finally {setBusy(null);}
  }

  return <section className="practice-panel practice-review-panel" aria-label="Practice marking"><h2>Practice awaiting your review</h2><p>Review descriptive responses from students in your classes. Use the approved rubric; each decision keeps its reason.</p>
    {error && <p role="alert" className="practice-error">{error}</p>}{notice && <p role="status" className="practice-feedback">{notice}</p>}
    {loading ? <p role="status">Loading practice responses…</p> : !rows.length ? <p className="practice-note">No practice responses are awaiting your review.</p> : rows.map(row => <details key={row.id} className="practice-review-item"><summary><strong>{row.student}</strong><span>{row.prompt}</span></summary><h3>Student response</h3><pre>{row.value}</pre><h3>Approved explanation</h3><p>{row.explanation}</p><h3>Marking criteria</h3><ul>{row.rubric.map((item, index) => <li key={index}>{item.criterion || JSON.stringify(item)}{typeof item.weight === 'number' ? ` (${item.weight})` : ''}</li>)}</ul><form onSubmit={event => void review(event, row.id)}><label>Practice score (0–1)<input type="number" name="score" min="0" max="1" step="0.01" required defaultValue="0" disabled={busy !== null}/></label><label>Reason for practice mark<textarea name="reason" required minLength={5} maxLength={2000} disabled={busy !== null}/></label><button className="primary" disabled={busy !== null}>{busy === row.id ? 'Saving mark…' : 'Save practice mark'}</button></form></details>)}
  </section>;
}
