'use client';
import {useState,useRef,useEffect} from 'react';
type Row=Record<string,any>;
type Props={api:(path:string,method?:string,body?:unknown)=>Promise<any>;outcomes:Row[];count:number;difficulty:string;kind:string;onChange:(rows:Row[])=>void};
export default function ExamAiQuestions({api,outcomes,count,difficulty,kind,onChange}:Props){
 const [rows,setRows]=useState<Row[]>([]),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(''),[reason,setReason]=useState(''),[checked,setChecked]=useState<Record<number,boolean>>({});
 const cancelled=useRef(false);useEffect(()=>()=>{cancelled.current=true},[]);
 function update(next:Row[]){setRows(next);onChange(next)}
 async function generate(){
  if(!outcomes.length){setError('Select at least one source-verified learning outcome above.');return}
  cancelled.current=false;setBusy(true);setError('');let current=rows;
  try{
   for(const outcome of outcomes){const status=await api('/ai/readiness?outcome_id='+encodeURIComponent(outcome.id));if(!status.ready)throw new Error(`${outcome.level}: ${status.message}`)}
   for(let index=current.length;index<count;index++){
    if(cancelled.current)break;
    setMessage(`Generating question ${index+1} of ${count} with local AI…`);
    const outcome=outcomes[index%outcomes.length];
    let result:Row;
    try{result=await api('/ai/generate','POST',{outcome_id:outcome.id,difficulty:difficulty||'medium',kind,option_count:4})}
    catch(e){const retry=(e as {retryAfter?:number}).retryAfter;if(!retry)throw e;for(let seconds=retry;seconds>0&&!cancelled.current;seconds--){setMessage(`Local AI limit reached. Continuing in ${seconds}s…`);await new Promise(resolve=>setTimeout(resolve,1000))}if(cancelled.current)break;index--;continue}
    const bank=await api('/questions');const question=bank.find((q:Row)=>q.id===result.id);if(!question)throw new Error('Draft saved, but it could not be loaded. Find it in Question bank before generating again.');
    current=[...current,question];if(cancelled.current)break;update(current);
   }
   setMessage('Drafts are saved in Question bank. Review each answer, explanation and source, then approve below.');
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 async function approve(row:Row){setBusy(true);setError('');try{await api(`/questions/${row.id}/review`,'POST',{decision:'approved',reason});update(rows.map(q=>q.id===row.id?{...q,status:'approved'}:q))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="panel spaced" aria-label="AI exam questions"><h3>Generate and review AI questions</h3><p>Uses your local models and reviewed, indexed teaching notes. Questions join the exam only after your approval.</p><button type="button" className="secondary" disabled={busy||rows.length>=count} onClick={generate}>{rows.length?'Continue generating':'Generate AI questions'}</button>{busy&&<button type="button" className="secondary" onClick={()=>{cancelled.current=true;setMessage('Stopping after the current request. Saved drafts are retained.')}}>Stop generation</button>}{message&&<p role="status">{message}</p>}{error&&<p role="alert" className="alert">{error}</p>}{rows.length>0&&<label>Review reason<input value={reason} onChange={e=>setReason(e.target.value)} placeholder="Explain how you checked these questions"/></label>}{rows.map(row=><details className="panel spaced" key={row.id}><summary>{row.status==='approved'?'Approved':'Needs your review'} · {row.prompt}</summary><ul>{row.options.map((o:Row)=><li key={o.id}>{o.id}: {o.text}</li>)}</ul><p>Answer: {JSON.stringify(row.key)}</p><p>{row.explanation}</p><p>Sources: {row.sources.join(', ')}</p>{row.rubric.length>0&&<pre>{JSON.stringify(row.rubric,null,2)}</pre>}{row.status!=='approved'&&<><label><input type="checkbox" checked={Boolean(checked[row.id])} onChange={e=>setChecked({...checked,[row.id]:e.target.checked})}/>I checked the answer, explanation and sources</label><button type="button" className="primary" disabled={busy||!checked[row.id]||reason.trim().length<5} onClick={()=>approve(row)}>Approve for this exam</button></>}</details>)}</section>
}
