'use client';

import {useMemo, useState} from 'react';
import {BookOpen, CheckCircle2, FileText, Search, ShieldCheck} from 'lucide-react';
import './workspace-tools.css';

type Row = Record<string, any>;
type Props = {
  curriculum: any;
  coverage: any;
  isAdmin: boolean;
  onEdit: (outcome: any, unitId: number) => void;
};

function pageNumbers(row: Row): number[] {
  const pages = Array.isArray(row.source_pages) ? row.source_pages : [row.source_page];
  return [...new Set<number>(pages.map(Number).filter((page: number) => Number.isInteger(page) && page > 0))];
}

function SourceLinks({row}: {row: Row}) {
  const pages = pageNumbers(row);
  if (!pages.length) return null;
  return <span className="syllabus-source-links">PDF {pages.length === 1 ? 'page' : 'pages'} {pages.map((page, index) => <span key={page}>
    {index > 0 && ', '}<a href={`/api/curriculum/source#page=${page}`} target="_blank" rel="noreferrer" aria-label={`Open source PDF page ${page}`}>{page}</a>
  </span>)}</span>;
}

function unitLevels(unit: Row): Row[] {
  const outcomes: Row[] = Array.isArray(unit.outcomes) ? unit.outcomes : [];
  const levels: Row[] = Array.isArray(unit.levels) ? unit.levels.map((level: Row) => ({...level, level: String(level.level ?? level.id)})) : [];
  const represented = new Set(levels.map(level => level.level));
  for (const outcome of outcomes) {
    const code = String(outcome.level ?? 'Other');
    if (!represented.has(code)) {
      levels.push({level: code, title: outcome.subtopic || `Competency level ${code}`, contents: [], source_pages: pageNumbers(outcome)});
      represented.add(code);
    }
  }
  return levels.sort((a, b) => String(a.level).localeCompare(String(b.level), undefined, {numeric: true}));
}

function reviewedDate(value: unknown) {
  if (typeof value !== 'string' || !value) return 'Review date not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
}

export default function CurriculumExplorer({curriculum, coverage, isAdmin, onEdit}: Props) {
  const [search, setSearch] = useState('');
  const [unitFilter, setUnitFilter] = useState('');
  const [reviewFilter, setReviewFilter] = useState('all');
  const units: Row[] = Array.isArray(curriculum?.units) ? curriculum.units : [];
  const allOutcomes: Row[] = units.flatMap(unit => unit.outcomes || []);
  const inventory: Row = curriculum?.inventory || {};
  const hasCatalogue = allOutcomes.some(outcome => typeof outcome.catalogued === 'boolean');
  const officialOutcomes = hasCatalogue ? allOutcomes.filter(outcome => outcome.catalogued) : allOutcomes;
  const officialIds = new Set(officialOutcomes.map(outcome => outcome.id));
  const sourceCount = Number(inventory.outcome_count ?? officialOutcomes.length);
  const verifiedCount = Number(inventory.verified_outcome_count ?? officialOutcomes.filter(outcome => outcome.verified).length);
  const levelCount = Number(inventory.level_count ?? units.reduce((total, unit) => total + unitLevels(unit).length, 0));
  const coverageRows: Row[] = Array.isArray(coverage?.outcomes) ? coverage.outcomes : [];
  const coverageById = useMemo(() => new Map(coverageRows.map(row => [row.id, row])), [coverageRows]);
  const coveredCount = coverageRows.filter(row => row.covered && officialIds.has(row.id)).length;
  const additionalCount = hasCatalogue ? allOutcomes.length - officialOutcomes.length : 0;
  const term = search.trim().toLowerCase();
  const filtering = Boolean(term || unitFilter || reviewFilter !== 'all');

  function acceptsReview(outcome: Row) {
    const info = coverageById.get(outcome.id);
    if (reviewFilter === 'verified') return outcome.verified;
    if (reviewFilter === 'pending') return !outcome.verified;
    if (reviewFilter === 'covered') return Boolean(info?.covered);
    if (reviewFilter === 'no_questions') return !info?.approved_questions;
    return true;
  }

  const visible = units.filter(unit => !unitFilter || String(unit.id) === unitFilter).map(unit => {
    const unitMatches = !term || `${unit.id} ${unit.name} ${unit.competency || ''}`.toLowerCase().includes(term);
    const levels = unitLevels(unit).map(level => {
      const contents: string[] = Array.isArray(level.contents) ? level.contents.map(String) : [];
      const levelMatches = unitMatches || `${level.level} ${level.title} ${contents.join(' ')}`.toLowerCase().includes(term);
      const allRows: Row[] = (unit.outcomes || []).filter((outcome: Row) => String(outcome.level ?? 'Other') === level.level);
      const outcomes = allRows.filter(outcome => acceptsReview(outcome) && (levelMatches || `${outcome.id} ${outcome.text} ${outcome.competency || ''}`.toLowerCase().includes(term)));
      const emptySourceLevel = allRows.length === 0 && (unit.id === 14 || level.source_verified || Array.isArray(unit.levels));
      const showEmpty = emptySourceLevel && levelMatches && (reviewFilter === 'all' || (reviewFilter === 'verified' && level.source_verified));
      return {...level, level: String(level.level), title: level.title, periods: level.periods, review_note: level.review_note, contents, outcomes, show: outcomes.length > 0 || showEmpty, emptySourceLevel};
    }).filter(level => level.show);
    return {unit, levels};
  }).filter(group => group.levels.length > 0);
  const shownCount = visible.reduce((count, group) => count + group.levels.reduce((total, level) => total + level.outcomes.length, 0), 0);

  return <div className="curriculum-explorer workspace-tool">
    <div className="workspace-metrics" aria-label="Curriculum coverage summary">
      <div><BookOpen size={20}/><strong>{inventory.unit_count ?? units.length}</strong><span>Syllabus units</span></div>
      <div><FileText size={20}/><strong>{levelCount}</strong><span>Competency levels</span></div>
      <div><ShieldCheck size={20}/><strong>{verifiedCount}<small> / {sourceCount}</small></strong><span>{hasCatalogue ? 'Official outcomes source checked' : 'Imported outcomes source checked'}</span></div>
      <div><CheckCircle2 size={20}/><strong>{coveredCount}<small> / {sourceCount}</small></strong><span>Outcomes with reviewed practice</span></div>
    </div>

    <div className="workspace-note" role="note">
      <ShieldCheck size={22}/><div><strong>{inventory.complete ? 'The 2017 source inventory has been checked.' : 'Source review and practice coverage are separate.'}</strong>
        <p>Source checking confirms syllabus wording and page references. Practice coverage also needs reviewed teaching notes and approved questions. Current examination applicability still requires official confirmation.</p>
        {additionalCount > 0 && <p>{additionalCount} additional authored outcome {additionalCount === 1 ? 'is' : 'are'} preserved alongside the official inventory.</p>}
      </div>
    </div>

    <div className="workspace-filters">
      <label className="workspace-search">Search units, topics or outcomes<div><Search size={18}/><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Try SQL, IoT, 3.1, or a learning outcome"/></div></label>
      <label>Unit<select value={unitFilter} onChange={event => setUnitFilter(event.target.value)}><option value="">All units</option>{units.map(unit => <option key={unit.id} value={unit.id}>{unit.id}. {unit.name}</option>)}</select></label>
      <label>Source review and practice<select value={reviewFilter} onChange={event => setReviewFilter(event.target.value)}>
        <option value="all">All statuses</option><option value="verified">Source checked</option><option value="pending">Needs source review</option><option value="covered">Reviewed practice available</option><option value="no_questions">No approved questions</option>
      </select></label>
    </div>
    <p className="workspace-results" aria-live="polite">Showing {shownCount} outcome {shownCount === 1 ? 'record' : 'records'} across {visible.length} {visible.length === 1 ? 'unit' : 'units'}.</p>

    <div className="syllabus-units">
      {visible.map(({unit, levels}) => <details className="syllabus-unit" key={unit.id} open={filtering || undefined}>
        <summary><span className="syllabus-unit-number">{unit.id}</span><div><h2>{unit.name}</h2><p>{unitLevels(unit).length} competency levels · {(unit.outcomes || []).length} outcome records{unit.grade ? ` · Grade ${unit.grade}` : ' · Grade split not confirmed'}</p></div><span className={`workspace-tag ${unit.verified ? 'checked' : 'pending'}`}>{unit.verified ? 'Source checked' : 'Review recorded outcomes'}</span></summary>
        <div className="syllabus-unit-body">
          {unit.competency && <p className="syllabus-competency">{unit.competency}</p>}
          {levels.map(level => <details className="syllabus-level" key={level.level} open={filtering || undefined}>
            <summary><span className="syllabus-level-code">{level.level}</span><div><h3>{level.title || `Competency level ${level.level}`}</h3><p>{level.emptySourceLevel ? 'No explicit outcome bullets in the source' : `${level.outcomes.length} outcome ${level.outcomes.length === 1 ? 'record' : 'records'}`}{Number.isFinite(level.periods) ? ` · ${level.periods} periods` : ''}</p></div></summary>
            <div className="syllabus-level-body">
              <SourceLinks row={level}/>
              {level.review_note && <p className="workspace-source-note">{level.review_note}</p>}
              {level.contents.length > 0 && <details className="syllabus-topics"><summary>Topics in this level ({level.contents.length})</summary><ul>{level.contents.map((content: string, index: number) => <li key={`${index}-${content}`}>{content}</li>)}</ul></details>}
              {level.emptySourceLevel && <div className="workspace-note project-note"><BookOpen size={20}/><p>The source documents this project competency but provides no separate learning-outcome bullets. The competency is included here without inventing outcomes.</p></div>}
              {level.outcomes.map((outcome: Row) => {
                const info = coverageById.get(outcome.id);
                return <article className="syllabus-outcome" key={outcome.id}>
                  <div className="syllabus-outcome-top"><code>{outcome.id}</code><span className={`workspace-tag ${outcome.verified ? 'checked' : 'pending'}`}>{outcome.verified ? 'Source checked' : 'Needs source review'}</span>{outcome.catalogued === false && <span className="workspace-tag neutral">Additional authored outcome</span>}</div>
                  <p className="syllabus-outcome-text">{outcome.text}</p>
                  <div className="syllabus-outcome-meta"><SourceLinks row={outcome}/><span>{info?.approved_questions || 0} approved questions</span><span>{info?.covered ? 'Reviewed practice available' : 'Practice content still needed'}</span><span>Sinhala: {info?.sinhala ? 'reviewed' : 'unavailable'}</span></div>
                  {outcome.review_note && <p className="workspace-source-note">{outcome.review_note}</p>}
                  <div className="syllabus-outcome-footer"><span>{outcome.verified ? reviewedDate(outcome.reviewed_at) : 'Source review pending'}</span>{isAdmin && <button type="button" className="secondary" onClick={() => onEdit(outcome, Number(unit.id))} aria-label={`Edit outcome ${outcome.id}`}>Edit / review</button>}</div>
                </article>;
              })}
            </div>
          </details>)}
        </div>
      </details>)}
    </div>
    {!visible.length && <div className="workspace-empty"><Search size={26}/><h3>No matching curriculum records</h3><p>Try a broader search or clear the filters.</p><button type="button" className="secondary" onClick={() => {setSearch(''); setUnitFilter(''); setReviewFilter('all');}}>Clear filters</button></div>}
    <p className="workspace-source-note">Source: <a href="/api/curriculum/source" target="_blank" rel="noreferrer">NIE A/L ICT syllabus, effective from 2017</a>. Page links use physical PDF page numbers. Source numbering and wording defects are documented in review notes; application outcome IDs are not NIE-issued identifiers.</p>
  </div>;
}
