import {expect, Page, test} from '@playwright/test';

// All API responses are synthetic. No seeded accounts or live assessment data
// are used, and the browser clock makes debounce/deadline behavior deterministic.
const BASE = Date.parse('2026-11-22T12:00:00Z');
const questions = [
  {id:101,outcome_id:'fixture-outcome',kind:'short',difficulty:'medium',prompt:'Explain the purpose of a primary key.',options:[],status:'approved',language:'en',language_notice:null},
  {id:102,outcome_id:'fixture-outcome',kind:'short',difficulty:'medium',prompt:'Explain the purpose of a foreign key.',options:[],status:'approved',language:'en',language_notice:null},
];

function gate() {
  let release!: () => void;
  const promise = new Promise<void>(resolve => {release=resolve;});
  return {promise,release};
}

type Options = {
  questionCount?: number;
  expiredOnResume?: boolean;
  duplicateSubmission?: boolean;
  beforeSave?: (index: number, value: string) => Promise<void>;
};

async function attempt(page: Page, options: Options = {}) {
  const answerValues: Record<string,string> = {};
  const saves: {question:number;value:string}[] = [];
  const events: string[] = [];
  let submitted=Boolean(options.expiredOnResume);
  let submitCount=0;
  const included=questions.slice(0,options.questionCount || 2);
  await page.clock.install({time:new Date(BASE)});
  await page.clock.pauseAt(new Date(BASE+1000));
  await page.route('**/api/**',async route=>{
    const request=route.request();
    const url=new URL(request.url());
    const path=url.pathname;
    let status=200;
    let data:unknown=[];
    if(path==='/api/me') data={id:1,name:'Autosave fixture',email:'autosave@example.invalid',role:'student',grade:12,language:'en'};
    else if(path==='/api/classes') data=[{id:8,name:'Fixture ICT class',grade:12,code:'FIXTURE',members:1}];
    else if(path==='/api/curriculum') data={units:[{id:8,name:'Database Management',grade:null,outcomes:[{id:'fixture-outcome',level:'8.1',text:'Identifies database concepts',verified:true}]}]};
    else if(path==='/api/coverage') data={outcomes:[],covered_outcomes:0,imported_outcomes:1};
    else if(path==='/api/assessments') data=[{id:9,title:'Autosave regression assessment',class_id:8,duration:5,published:true,questions:included.length,attempt_id:41,submitted:false}];
    else if(path==='/api/assessments/9/start') {events.push('start');data={id:41};}
    else if(path==='/api/attempts/41') {events.push('attempt');data={id:41,title:'Autosave regression assessment',submitted,deadline:new Date(BASE+(options.expiredOnResume ? -1000 : 300000)).toISOString(),questions:included,answers:answerValues};}
    else if(/^\/api\/attempts\/41\/answers\/\d+$/.test(path) && request.method()==='PUT') {
      const question=Number(path.split('/').pop());
      const value=String(request.postDataJSON().value);
      const index=saves.length;
      saves.push({question,value});events.push(`save-start:${index}`);
      if(options.beforeSave) await options.beforeSave(index,value);
      answerValues[String(question)]=value;
      events.push(`save-finish:${index}`);data={saved:true};
    } else if(path==='/api/attempts/41/submit') {
      submitCount++;events.push('submit');submitted=true;
      if(options.duplicateSubmission) {status=409;data={detail:'Attempt already submitted'};}
      else data={submitted:true};
    } else if(path==='/api/attempts/41/results') {
      events.push('results');
      data={id:41,title:'Autosave regression assessment',score:0,total:included.length,pending:included.length,items:included.map(question=>({question_id:question.id,prompt:question.prompt,value:answerValues[String(question.id)] || '',score:null,key:{answer:'Teacher-reviewed expected answer'},correct_answer:'Teacher-reviewed expected answer',rubric:[{criterion:'Explains the concept',marks:1}],explanation:'This is a synthetic approved explanation.',reason:'Teacher review required',revise:'Database concepts',possible_misconception:null,follow_up:'Review the approved concept notes.'}))};
    }
    await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto('/');
  await expect(page.locator('.main-shell')).toBeVisible();
  await page.locator('nav').getByRole('button',{name:/^Assessments/}).click();
  await page.getByRole('button',{name:'Resume assessment',exact:true}).click();
  if(!options.expiredOnResume) await expect(page.getByRole('heading',{name:included[0].prompt,exact:true})).toBeVisible();
  return {saves,events,answerValues,get submitCount(){return submitCount;}};
}

test('rapid text entry is debounced and saves its latest value once',async({page})=>{
  const state=await attempt(page);
  const answer=page.getByRole('textbox',{name:'Your answer',exact:true});
  await answer.pressSequentially('A primary key uniquely identifies each record.');
  expect(state.saves).toHaveLength(0);
  await page.clock.fastForward(349);
  expect(state.saves).toHaveLength(0);
  await page.clock.fastForward(1);
  await expect.poll(()=>state.saves.length).toBe(1);
  expect(state.saves[0]).toEqual({question:101,value:'A primary key uniquely identifies each record.'});
  await expect.poll(()=>state.events.includes('save-finish:0')).toBe(true);
});

test('Next question waits for a delayed save and preserves the final text',async({page})=>{
  const saving=gate();
  try {
    const state=await attempt(page,{beforeSave:()=>saving.promise});
    await page.getByRole('textbox',{name:'Your answer',exact:true}).fill('The final answer before moving to the next question.');
    await page.getByRole('button',{name:'Next question',exact:true}).click();
    await expect.poll(()=>state.saves.length).toBe(1);
    await expect(page.getByRole('heading',{name:questions[0].prompt,exact:true})).toBeVisible();
    await expect(page.getByRole('heading',{name:questions[1].prompt,exact:true})).toHaveCount(0);
    expect(state.saves[0].value).toBe('The final answer before moving to the next question.');
    saving.release();
    await expect(page.getByRole('heading',{name:questions[1].prompt,exact:true})).toBeVisible();
    expect(state.answerValues['101']).toBe('The final answer before moving to the next question.');
    expect(state.submitCount).toBe(0);
  } finally {saving.release();}
});

test('submission flushes the latest pending edit after an in-flight save before posting submit',async({page})=>{
  const first=gate();const last=gate();
  try {
    const state=await attempt(page,{questionCount:1,beforeSave:index=>index===0 ? first.promise : last.promise});
    const answer=page.getByRole('textbox',{name:'Your answer',exact:true});
    await answer.fill('Earlier draft');
    await page.clock.fastForward(350);
    await expect.poll(()=>state.saves.length).toBe(1);
    await answer.fill('Latest complete answer');
    await page.locator('.question-footer').getByRole('button',{name:'Submit assessment',exact:true}).click();
    expect(state.submitCount).toBe(0);
    first.release();
    await expect.poll(()=>state.saves.length).toBe(2);
    expect(state.saves[1]).toEqual({question:101,value:'Latest complete answer'});
    expect(state.submitCount).toBe(0);
    last.release();
    await expect(page.getByRole('heading',{name:'Every answer is a chance to learn.',exact:true})).toBeVisible();
    expect(state.submitCount).toBe(1);
    expect(state.events.indexOf('save-finish:1')).toBeLessThan(state.events.indexOf('submit'));
    expect(state.events.indexOf('submit')).toBeLessThan(state.events.indexOf('results'));
    expect(state.answerValues['101']).toBe('Latest complete answer');
  } finally {first.release();last.release();}
});

test('the deadline triggers automatic submission after queued saves complete',async({page})=>{
  const saving=gate();
  try {
    const state=await attempt(page,{questionCount:1,beforeSave:()=>saving.promise});
    await page.getByRole('textbox',{name:'Your answer',exact:true}).fill('Saved before the deadline.');
    await page.clock.fastForward(350);
    await expect.poll(()=>state.saves.length).toBe(1);
    await page.clock.setSystemTime(new Date(BASE+301000));
    await page.clock.fastForward(1000);
    await expect(page.getByText('Time has expired. Finalizing your saved answers automatically. If the connection is interrupted, retry submission.',{exact:true})).toBeVisible();
    expect(state.submitCount).toBe(0);
    saving.release();
    await expect(page.getByRole('heading',{name:'Every answer is a chance to learn.',exact:true})).toBeVisible();
    expect(state.submitCount).toBe(1);
    expect(state.events.indexOf('save-finish:0')).toBeLessThan(state.events.indexOf('submit'));
    expect(state.answerValues['101']).toBe('Saved before the deadline.');
  } finally {saving.release();}
});

test('duplicate submission conflicts recover by loading the already-finalized results',async({page})=>{
  const state=await attempt(page,{questionCount:1,duplicateSubmission:true});
  await page.locator('.question-footer').getByRole('button',{name:'Submit assessment',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Every answer is a chance to learn.',exact:true})).toBeVisible();
  expect(state.submitCount).toBe(1);
  expect(state.events).toContain('results');
  await expect(page.locator('.alert[role="alert"]')).toHaveCount(0);
});

test('resuming an expired attempt finalized by the server opens results directly',async({page})=>{
  const state=await attempt(page,{questionCount:1,expiredOnResume:true});
  await expect(page.getByRole('heading',{name:'Every answer is a chance to learn.',exact:true})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'Your answer',exact:true})).toHaveCount(0);
  expect(state.events).toEqual(['start','attempt','results']);
  expect(state.submitCount).toBe(0);
  expect(state.saves).toHaveLength(0);
});
