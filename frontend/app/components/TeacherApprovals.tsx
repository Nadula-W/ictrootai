'use client';
import {useEffect,useState} from 'react';
type Api=(path:string,method?:string,body?:unknown)=>Promise<any>;
export default function TeacherApprovals({api}:{api:Api}){
 const [rows,setRows]=useState<any[]>([]),[reason,setReason]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){const data=await api('/admin/teacher-applications');setRows(Array.isArray(data)?data:[])}
 useEffect(()=>{load().catch(e=>setError(e.message))},[]);
 async function decide(id:number,decision:string){setBusy(true);setError('');try{await api(`/admin/teacher-applications/${id}/review`,'POST',{decision,reason});await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="panel"><h1>Teacher approvals</h1><p>Approve teachers to give them control of classes, teaching resources, questions and exams.</p><label>Decision reason<input value={reason} onChange={e=>setReason(e.target.value)} minLength={5}/></label>{error&&<p role="alert">{error}</p>}{rows.map(row=><article className="panel spaced" key={row.id}><h3>{row.name}</h3><p>{row.email}</p><p>{row.message}</p><p>Status: {row.status}</p>{row.status==='pending'?<div className="toolbar"><button className="primary" disabled={busy||reason.trim().length<5} onClick={()=>decide(row.id,'approved')}>Accept teacher</button><button className="secondary" disabled={busy||reason.trim().length<5} onClick={()=>decide(row.id,'rejected')}>Decline request</button></div>:<p>{row.reason}</p>}</article>)}{!rows.length&&<p>No teacher applications yet.</p>}</section>
}
