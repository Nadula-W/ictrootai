'use client';

import {useEffect, useId, useState} from 'react';
import {ChartNoAxesCombined, Clock, RefreshCw, Target, Users} from 'lucide-react';
import './class-reports.css';

type Classroom = {id: number; name: string; grade?: number};
type Learner = {
  id: number; name: string; email: string; grade: number;
  started_assessments: number; submitted_assessments: number;
  marked_answers: number; pending_answers: number; accuracy: number | null;
};
type OutcomeProgress = {
  outcome_id: string; text: string; answered: number; accuracy: number | null;
  pending_answers: number; recommended_difficulty: string; evidence_notice?: string | null;
};
type ProgressReport = {
  class_id: number; class_name: string; student: {id: number; name: string; email: string};
  submitted_assessments: number; marked_answers: number; pending_answers: number;
  accuracy: number | null; recommended_difficulty: string;
  outcomes: OutcomeProgress[]; weak_outcomes: OutcomeProgress[];
  possible_misconceptions: {outcome_id: string; label: string; evidence_count: number; question_count: number; notice: string}[];
  accuracy_notice: string; misconception_notice: string;
};
type Props = {
  classes: any[];
  api: (path: string, method?: string, body?: unknown) => Promise<any>;
};

function percentage(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? `${Math.round(value)}%` : 'Not marked yet';
}

function message(error: unknown) {
  return error instanceof Error ? error.message : 'This report could not be loaded. Try again.';
}

export default function ClassReports({classes, api}: Props) {
  const available: Classroom[] = (Array.isArray(classes) ? classes : []).filter(classroom => Number.isInteger(classroom.id) && classroom.id > 0);
  const initial = available[0] ? String(available[0].id) : '';
  const [classId, setClassId] = useState(initial);
  const [studentId, setStudentId] = useState('');
  const [students, setStudents] = useState<Learner[]>([]);
  const [report, setReport] = useState<ProgressReport | null>(null);
  const [loadingRoster, setLoadingRoster] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [rosterError, setRosterError] = useState('');
  const [reportError, setReportError] = useState('');
  const [revision, setRevision] = useState(0);
  const headingId = useId();
  const detailHeadingId = useId();
  const classOptionsKey = available.map(classroom => classroom.id).join(',');
  const validClass = available.some(classroom => String(classroom.id) === classId);

  useEffect(() => {
    if (!validClass) {
      setClassId(initial); setStudentId(''); setStudents([]); setReport(null);
    }
  }, [validClass, initial]);

  useEffect(() => {
    let active = true;
    setStudents([]); setReport(null); setRosterError(''); setReportError('');
    if (!classId || !classOptionsKey.split(',').includes(classId)) {setLoadingRoster(false); return;}
    setLoadingRoster(true);
    api(`/classes/${classId}/students`).then(result => {
      if (!active) return;
      const roster: Learner[] = Array.isArray(result.students) ? result.students : [];
      setStudents(roster);
      setStudentId(current => roster.some(student => String(student.id) === current) ? current : '');
    }).catch(error => {if (active) setRosterError(message(error));})
      .finally(() => {if (active) setLoadingRoster(false);});
    return () => {active = false;};
  }, [classId, classOptionsKey, revision, api]);

  useEffect(() => {
    let active = true;
    setReport(null); setReportError('');
    if (!classId || !studentId || !students.some(student => String(student.id) === studentId)) {setLoadingReport(false); return;}
    setLoadingReport(true);
    api(`/classes/${classId}/students/${studentId}/progress`).then(result => {if (active) setReport(result);})
      .catch(error => {if (active) setReportError(message(error));})
      .finally(() => {if (active) setLoadingReport(false);});
    return () => {active = false;};
  }, [classId, studentId, students, api]);

  function changeClass(value: string) {
    setStudentId(''); setReport(null); setClassId(value);
  }

  const selected = students.find(student => String(student.id) === studentId);
  const submitted = students.reduce((total, student) => total + (student.submitted_assessments || 0), 0);
  const pending = students.reduce((total, student) => total + (student.pending_answers || 0), 0);

  return <section className="class-reports panel spaced" aria-labelledby={headingId}>
    <div className="class-report-heading">
      <div><h2 id={headingId}><ChartNoAxesCombined size={23}/>Class progress reports</h2><p>Choose a class, then a learner to plan their next revision.</p></div>
      <button type="button" className="secondary" onClick={() => setRevision(value => value + 1)} disabled={!validClass || loadingRoster || loadingReport}><RefreshCw size={16}/>Refresh reports</button>
    </div>
    {!available.length ? <div className="class-report-empty"><Users size={26}/><p>Create a class to see its learners and assessment progress here.</p></div> : <>
      <label className="class-report-class-picker">Report class<select value={classId} onChange={event => changeClass(event.target.value)}>
        {available.map(classroom => <option key={classroom.id} value={classroom.id}>{classroom.name}{classroom.grade ? ` · Grade ${classroom.grade}` : ''}</option>)}
      </select></label>
      {rosterError ? <div className="class-report-error" role="alert"><p>{rosterError}</p><button type="button" className="secondary" onClick={() => setRevision(value => value + 1)}>Retry class report</button></div> : loadingRoster ? <p className="class-report-empty" role="status">Loading class learners…</p> : <>
        <div className="class-report-class-stats" aria-label="Class assessment totals"><p><Users size={17}/><strong>{students.length}</strong> {students.length === 1 ? 'learner' : 'learners'}</p><p><ChartNoAxesCombined size={17}/><strong>{submitted}</strong> submitted assessments</p><p><Clock size={17}/><strong>{pending}</strong> answers awaiting marks</p></div>
        {!students.length ? <div className="class-report-empty"><Users size={26}/><p>No learners have joined this class yet. Share its class code to invite them.</p></div> : <div className="class-report-layout">
          <div className="class-report-roster-section"><h3>Learners</h3><p className="class-report-help">Select a learner to view their report.</p><ul className="class-report-roster">{students.map(student => <li key={student.id}><button type="button" aria-pressed={String(student.id) === studentId} aria-label={`View ${student.name}'s progress`} onClick={() => setStudentId(String(student.id))}>
            <span className="class-report-learner"><strong>{student.name}</strong><span>{student.email}</span></span>
            <span className="class-report-learner-stats"><span><span>Accuracy</span><strong>{percentage(student.accuracy)}</strong></span><span><span>Submitted</span><strong>{student.submitted_assessments}</strong></span><span><span>Awaiting marks</span><strong>{student.pending_answers}</strong></span></span>
          </button></li>)}</ul></div>
          <div className="class-report-detail" aria-live="polite">
            {!selected ? <div className="class-report-empty"><Target size={28}/><p>Select a learner to see revision priorities and recent performance.</p></div> : loadingReport ? <p className="class-report-empty" role="status">Loading {selected.name}&apos;s progress…</p> : reportError ? <div className="class-report-error" role="alert"><p>{reportError}</p><button type="button" className="secondary" onClick={() => setRevision(value => value + 1)}>Retry learner report</button></div> : report ? <section aria-labelledby={detailHeadingId}>
              <div className="class-report-student-heading"><h3 id={detailHeadingId}>{report.student.name}&apos;s progress</h3><p>Assessment results from {report.class_name} only.</p></div>
              <dl className="class-report-student-stats"><div><dt>Accuracy</dt><dd>{percentage(report.accuracy)}</dd></div><div><dt>Submitted assessments</dt><dd>{report.submitted_assessments}</dd></div><div><dt>Marked answers</dt><dd>{report.marked_answers}</dd></div><div><dt>Awaiting teacher marks</dt><dd>{report.pending_answers}</dd></div></dl>
              <p className="class-report-help">{report.accuracy_notice}</p>
              {report.pending_answers > 0 && <p className="class-report-pending"><Clock size={17}/>Review pending answers in Submissions before treating these results as complete.</p>}
              <div className="class-report-recommendation"><Target size={21}/><div><h4>Next practice: {report.recommended_difficulty}</h4><p>{report.marked_answers ? 'Based on recent marked answers. Adjust this with your knowledge of the learner.' : 'No marked answers yet. Start with medium practice and review their responses.'}</p></div></div>
              <section className="class-report-topic-section"><h4>Revision priorities</h4>{report.weak_outcomes.length ? <ul className="class-report-priorities">{report.weak_outcomes.map(outcome => <li key={outcome.outcome_id}><strong>{outcome.text}</strong><span>{percentage(outcome.accuracy)} · {outcome.answered} marked {outcome.answered === 1 ? 'answer' : 'answers'} · Try {outcome.recommended_difficulty} practice</span>{outcome.evidence_notice && <span>{outcome.evidence_notice}</span>}</li>)}</ul> : <p className="class-report-help">{report.marked_answers ? 'No revision priorities identified from the marked answers yet.' : 'Revision priorities appear after assessment answers have been marked.'}</p>}</section>
              <section className="class-report-topic-section"><h4>Progress by learning outcome</h4>{report.outcomes.length ? <ul className="class-report-outcomes">{report.outcomes.map(outcome => <li key={outcome.outcome_id}><div><strong>{outcome.text}</strong><span>{outcome.answered} marked · {outcome.pending_answers} awaiting marks · Suggested difficulty: {outcome.recommended_difficulty}</span></div><strong>{percentage(outcome.accuracy)}</strong>{typeof outcome.accuracy === 'number' && <progress max={100} value={outcome.accuracy} aria-label={`${outcome.text} accuracy`}>{outcome.accuracy}%</progress>}</li>)}</ul> : <p className="class-report-help">No submitted assessment answers yet. Saved work appears here after submission.</p>}</section>
              <section className="class-report-topic-section"><h4>Repeated patterns to discuss</h4><p className="class-report-help">{report.misconception_notice}</p>{report.possible_misconceptions.length ? <ul className="class-report-patterns">{report.possible_misconceptions.map((pattern, index) => <li key={`${pattern.outcome_id}-${index}`}><strong>{pattern.label}</strong><span>{pattern.evidence_count} responses across {pattern.question_count} {pattern.question_count === 1 ? 'question' : 'questions'}</span></li>)}</ul> : <p className="class-report-help">No repeated pattern has enough evidence yet. One incorrect answer is not proof of a misconception.</p>}</section>
            </section> : null}
          </div>
        </div>}
      </>}
    </>}
  </section>;
}
