'use client';
import {useEffect,useState} from 'react';
export default function TeacherRequest({api}:{api:(p:string,m?:string,b?:unknown)=>Promise<any>}){
 const [application,setApplication]=useState<any>(null),[message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{api('/teacher-applications/me').then(setApplication).catch(e=>setError(e.message))},[]);
 return <section className="panel spaced"><h2>Become a teacher</h2><p>Administrator approval unlocks classes, teaching resources, question review and exam creation.</p>{application?.status==='pending'?<p role="status">Your teacher application is awaiting administrator approval.</p>:<><p>{application?.reason}</p><label>School or teaching details<textarea value={message} maxLength={2000} onChange={e=>setMessage(e.target.value)}/></label><button className="primary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{setApplication(await api('/teacher-applications','POST',{message}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}>Request teacher access</button></>}{error&&<p role="alert">{error}</p>}</section>
}
